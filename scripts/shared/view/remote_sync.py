"""在查看器启动时异步刷新远端引用，并记录刷新状态供 Git Log 读取。"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import TypedDict

import instance

#: 项目内状态文件受 ``.env*`` 忽略规则覆盖；全局调用使用查看器缓存目录。
REMOTE_FETCH_STATE_FILE_NAME = ".env.view-fetch-state.json"
REMOTE_FETCH_LOCK_FILE_NAME = ".env.view-fetch.lock"
REMOTE_FETCH_SUCCESS_COOLDOWN_SECONDS = 300.0
REMOTE_FETCH_FAILURE_COOLDOWN_SECONDS = 30.0
REMOTE_FETCH_TIMEOUT_SECONDS = 25.0
REMOTE_FETCH_STALE_SECONDS = 35.0

_WORKER_ARGUMENT = "--worker"
_KNOWN_FETCH_STATES = frozenset({"idle", "running", "succeeded", "failed", "skipped"})


class RemoteFetchStatus(TypedDict):
    """远端引用刷新状态。"""

    state: str
    started_at: float | None
    finished_at: float | None
    reason: str


def start_background_remote_fetch(repository_root: Path) -> bool:
    """需要刷新时启动独立 Git fetch 进程，不等待网络请求结束。

    Args:
        repository_root (Path): 查看器所在的 Git 仓库或其子目录。

    Returns:
        bool: 状态目录可用或本轮处于冷却期时为 ``True``；无法启动时为 ``False``。
    """
    remote_fetch_state_path = _resolve_remote_fetch_state_path(repository_root)
    remote_fetch_lock_path = remote_fetch_state_path.with_name(REMOTE_FETCH_LOCK_FILE_NAME)
    try:
        remote_fetch_state_path.parent.mkdir(parents=True, exist_ok=True)
        if _is_recent_terminal_status(_read_status_file(remote_fetch_state_path), time.time()):
            return True
        lock_file_descriptor = _create_remote_fetch_lock(remote_fetch_lock_path)
        if lock_file_descriptor is None:
            return True
        os.close(lock_file_descriptor)

        if _is_recent_terminal_status(_read_status_file(remote_fetch_state_path), time.time()):
            remote_fetch_lock_path.unlink(missing_ok=True)
            return True

        started_at = time.time()
        _write_status_file(
            remote_fetch_state_path,
            RemoteFetchStatus(
                state="running",
                started_at=started_at,
                finished_at=None,
                reason="",
            ),
        )
        subprocess.Popen(
            [
                sys.executable,
                "-S",
                str(Path(__file__).resolve()),
                _WORKER_ARGUMENT,
                str(repository_root),
                str(remote_fetch_state_path),
                str(remote_fetch_lock_path),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=os.name != "nt",
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except OSError:
        _finish_remote_fetch(
            remote_fetch_state_path,
            remote_fetch_lock_path,
            started_at=None,
            state="failed",
            reason="fetch_failed",
        )
        return False
    return True


def read_remote_fetch_status(repository_root: Path) -> RemoteFetchStatus:
    """读取并规范化本仓库最近一次远端引用刷新状态。

    Args:
        repository_root (Path): 查看器所在的 Git 仓库或其子目录。

    Returns:
        RemoteFetchStatus: 可供界面判断的状态；状态文件不存在或损坏时为 ``idle``。
    """
    remote_fetch_status = _read_status_file(_resolve_remote_fetch_state_path(repository_root))
    remote_fetch_started_at = remote_fetch_status["started_at"]
    if (
        remote_fetch_status["state"] == "running"
        and remote_fetch_started_at is not None
        and time.time() - remote_fetch_started_at > REMOTE_FETCH_STALE_SECONDS
    ):
        return RemoteFetchStatus(
            state="failed",
            started_at=remote_fetch_started_at,
            finished_at=None,
            reason="timeout",
        )
    return remote_fetch_status


def run_remote_fetch_worker(
    repository_root: Path,
    remote_fetch_state_path: Path,
    remote_fetch_lock_path: Path,
) -> int:
    """执行后台 fetch，并把结果写入状态文件。

    Args:
        repository_root (Path): 查看器所在的 Git 仓库或其子目录。
        remote_fetch_state_path (Path): worker 状态文件。
        remote_fetch_lock_path (Path): 防止重复 fetch 的锁文件。

    Returns:
        int: fetch 成功或未配置远端时为 ``0``；其它失败为 ``1``。
    """
    started_at = _read_status_file(remote_fetch_state_path)["started_at"] or time.time()
    final_state = "failed"
    failure_reason = "fetch_failed"
    exit_code = 1
    try:
        configured_remotes = subprocess.run(
            ["git", "remote"],
            cwd=repository_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=REMOTE_FETCH_TIMEOUT_SECONDS,
        )
        if configured_remotes.returncode != 0:
            raise OSError("无法读取 Git remote 配置")
        if not configured_remotes.stdout.strip():
            final_state = "skipped"
            failure_reason = "no_remote"
            exit_code = 0
        else:
            fetch_process = subprocess.Popen(
                ["git", "fetch", "--all", "--prune", "--quiet"],
                cwd=repository_root,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=os.name != "nt",
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
            try:
                fetch_return_code = fetch_process.wait(timeout=REMOTE_FETCH_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                _terminate_remote_fetch_process(fetch_process)
                failure_reason = "timeout"
            else:
                if fetch_return_code == 0:
                    final_state = "succeeded"
                    failure_reason = ""
                    exit_code = 0
    except subprocess.TimeoutExpired:
        failure_reason = "timeout"
    except (OSError, UnicodeDecodeError):
        failure_reason = "fetch_failed"
    finally:
        _finish_remote_fetch(
            remote_fetch_state_path,
            remote_fetch_lock_path,
            started_at=started_at,
            state=final_state,
            reason=failure_reason,
        )
    return exit_code


def _terminate_remote_fetch_process(fetch_process: subprocess.Popen[bytes]) -> None:
    """超时时终止 Git 及其网络传输子进程，避免留下脱离 worker 的连接。"""
    if os.name == "nt":
        fetch_process.kill()
        fetch_process.wait()
        return

    try:
        os.killpg(fetch_process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        fetch_process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(fetch_process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    fetch_process.wait()


def _resolve_remote_fetch_state_path(repository_root: Path) -> Path:
    """把刷新状态放在查看器登记目录，适配项目内与全局调用。"""
    return instance.resolve_registry_path(repository_root).with_name(REMOTE_FETCH_STATE_FILE_NAME)


def _is_recent_terminal_status(remote_fetch_status: RemoteFetchStatus, current_time: float) -> bool:
    """判断最近的成功、失败或跳过结果是否仍在冷却期。"""
    finished_at = remote_fetch_status["finished_at"]
    if finished_at is None or remote_fetch_status["state"] == "running":
        return False
    cooldown_seconds = (
        REMOTE_FETCH_FAILURE_COOLDOWN_SECONDS
        if remote_fetch_status["state"] == "failed"
        else REMOTE_FETCH_SUCCESS_COOLDOWN_SECONDS
    )
    return current_time - finished_at <= cooldown_seconds


def _create_remote_fetch_lock(remote_fetch_lock_path: Path) -> int | None:
    """原子创建 fetch 锁；失效锁只尝试回收一次。"""
    for lock_attempt in range(2):
        try:
            return os.open(
                remote_fetch_lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError:
            if lock_attempt == 1:
                return None
            try:
                first_lock_stat = remote_fetch_lock_path.stat()
                if time.time() - first_lock_stat.st_mtime <= REMOTE_FETCH_STALE_SECONDS:
                    return None
                latest_lock_stat = remote_fetch_lock_path.stat()
                if (first_lock_stat.st_dev, first_lock_stat.st_ino) != (
                    latest_lock_stat.st_dev,
                    latest_lock_stat.st_ino,
                ):
                    return None
                remote_fetch_lock_path.unlink()
            except OSError:
                return None
    return None


def _read_status_file(remote_fetch_state_path: Path) -> RemoteFetchStatus:
    """读取状态文件，损坏或缺失时按空闲处理。"""
    try:
        parsed_status_dict = json.loads(remote_fetch_state_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return _idle_remote_fetch_status()
    if not isinstance(parsed_status_dict, dict):
        return _idle_remote_fetch_status()

    remote_fetch_state = parsed_status_dict.get("state")
    started_at = parsed_status_dict.get("started_at")
    finished_at = parsed_status_dict.get("finished_at")
    reason = parsed_status_dict.get("reason")
    if (
        remote_fetch_state not in _KNOWN_FETCH_STATES
        or (not isinstance(started_at, (int, float)) and started_at is not None)
        or (not isinstance(finished_at, (int, float)) and finished_at is not None)
        or not isinstance(reason, str)
    ):
        return _idle_remote_fetch_status()
    return RemoteFetchStatus(
        state=remote_fetch_state,
        started_at=float(started_at) if started_at is not None else None,
        finished_at=float(finished_at) if finished_at is not None else None,
        reason=reason,
    )


def _idle_remote_fetch_status() -> RemoteFetchStatus:
    """构造兼容旧版实例与损坏状态文件的空闲状态。"""
    return RemoteFetchStatus(state="idle", started_at=None, finished_at=None, reason="")


def _write_status_file(
    remote_fetch_state_path: Path, remote_fetch_status: RemoteFetchStatus
) -> None:
    """用原子替换更新状态，避免页面读到半截 JSON。"""
    temporary_state_path: Path | None = None
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=remote_fetch_state_path.parent,
        prefix=f"{remote_fetch_state_path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary_state_file:
        temporary_state_path = Path(temporary_state_file.name)
        json.dump(remote_fetch_status, temporary_state_file)
        temporary_state_file.write("\n")
    try:
        os.replace(temporary_state_path, remote_fetch_state_path)
    finally:
        if temporary_state_path.exists():
            temporary_state_path.unlink(missing_ok=True)


def _finish_remote_fetch(
    remote_fetch_state_path: Path,
    remote_fetch_lock_path: Path,
    *,
    started_at: float | None,
    state: str,
    reason: str,
) -> None:
    """写入终态并回收锁；失败提示只留稳定原因码，不存 Git 原始输出。"""
    try:
        _write_status_file(
            remote_fetch_state_path,
            RemoteFetchStatus(
                state=state,
                started_at=started_at,
                finished_at=time.time(),
                reason=reason,
            ),
        )
    except OSError:
        pass
    try:
        remote_fetch_lock_path.unlink(missing_ok=True)
    except OSError:
        pass


def _run_worker_from_arguments(argument_values: list[str]) -> int:
    """解析仅供父进程启动的 worker 参数。"""
    if len(argument_values) != 3:
        return 2
    return run_remote_fetch_worker(
        Path(argument_values[0]),
        Path(argument_values[1]),
        Path(argument_values[2]),
    )


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != _WORKER_ARGUMENT:
        raise SystemExit(2)
    raise SystemExit(_run_worker_from_arguments(sys.argv[2:]))
