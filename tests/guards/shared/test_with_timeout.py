"""守护 `just test` 超时兜底脚本的守卫测试（guard test）。

本文件位于 ``tests/guards/shared/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

重点守两条不变量：

1. **0 / 1 / 自身进程组永不可被整组发信号。** 这不是防御性冗余：曾有 watchdog
   把 ``MagicMock.__index__``（默认返回 1）当成进程组，真的对 1 号组发了 SIGKILL
   把 runner 自己打没。去掉这层守卫会重演同一事故。
2. **命令正常退出或超时后都要清理后代进程。** Windows 上同样保证这条约定。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# with_timeout.py 不是包的一部分，import 前需把它所在目录放到 sys.path。
_JUST_SCRIPTS_PATH = Path(__file__).resolve().parents[3] / "scripts" / "shared" / "just"
if str(_JUST_SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(_JUST_SCRIPTS_PATH))

import with_timeout  # noqa: E402

_GRACE_SECONDS = 5.0


def _pid_alive(pid: int) -> bool:
    """只观察进程状态，允许 Windows 等待 Job 终止生效。"""
    if sys.platform == "win32":
        import _winapi

        try:
            process_handle = _winapi.OpenProcess(_winapi.SYNCHRONIZE, False, pid)
        except OSError as error:
            if error.winerror == 87:  # ERROR_INVALID_PARAMETER：指定 PID 已不存在。
                return False
            raise
        try:
            return _winapi.WaitForSingleObject(process_handle, 3000) == _winapi.WAIT_TIMEOUT
        finally:
            _winapi.CloseHandle(process_handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def test_refuses_to_signal_reserved_process_groups() -> None:
    """0 号组（调用者自身）与 1 号组（init）必须被拒绝。"""
    assert with_timeout.is_signalable_group(0) is False
    assert with_timeout.is_signalable_group(1) is False


@pytest.mark.skipif(sys.platform == "win32", reason="Windows 使用 Job Object")
def test_refuses_to_signal_own_process_group() -> None:
    """对自己所在的进程组发信号等于自杀，必须被拒绝。"""
    assert with_timeout.is_signalable_group(os.getpgrp()) is False


@pytest.mark.skipif(sys.platform == "win32", reason="Windows 使用 Job Object")
def test_accepts_a_foreign_process_group() -> None:
    """正常的子进程组（组 id == 子进程 pid）应当放行，守卫不能误伤真实场景。"""
    foreign_group_id = os.getpgrp() + 10_000
    assert with_timeout.is_signalable_group(foreign_group_id) is True


def test_propagates_child_exit_code() -> None:
    """未超时时必须原样透传被包装命令的退出码。"""
    exit_code = with_timeout.run(
        30.0, [sys.executable, "-c", "raise SystemExit(3)"], _GRACE_SECONDS
    )
    assert exit_code == 3


def test_returns_timeout_exit_code_when_command_hangs() -> None:
    """超时必须返回 124（GNU timeout 约定），而不是被挂住。"""
    hang_command = [sys.executable, "-c", "import time; time.sleep(30)"]
    exit_code = with_timeout.run(1.0, hang_command, _GRACE_SECONDS)
    assert exit_code == with_timeout.TIMEOUT_EXIT_CODE


@pytest.mark.parametrize("root_times_out", [False, True], ids=["normal-exit", "timeout"])
def test_reaps_subtree_left_behind(tmp_path: Path, root_times_out: bool) -> None:
    """顶层自然退出或超时时，均回收仍在运行的后代。"""
    pid_file = tmp_path / "orphan.pid"
    spawn_descendant = (
        "import pathlib, subprocess, sys, time;"
        "orphan = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)']);"
        f"pathlib.Path({str(pid_file)!r}).write_text(str(orphan.pid), encoding='utf-8')"
    )
    command_source = spawn_descendant + "; time.sleep(20)" if root_times_out else spawn_descendant
    timeout_seconds = 3.0 if root_times_out else 30.0
    exit_code = with_timeout.run(
        timeout_seconds, [sys.executable, "-c", command_source], _GRACE_SECONDS
    )

    expected_exit_code = with_timeout.TIMEOUT_EXIT_CODE if root_times_out else 0
    assert exit_code == expected_exit_code
    orphan_pid = int(pid_file.read_text(encoding="utf-8"))
    assert not _pid_alive(orphan_pid), f"顶层命令结束后，子进程 {orphan_pid} 仍存活"


def test_reports_missing_command_without_raising() -> None:
    """命令不存在时返回 127，不能把异常抛给 recipe。"""
    exit_code = with_timeout.run(5.0, ["/nonexistent/command"], _GRACE_SECONDS)
    assert exit_code == with_timeout.COMMAND_NOT_FOUND_EXIT_CODE
