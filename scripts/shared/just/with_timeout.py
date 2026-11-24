"""运行带超时的命令，退出时回收整棵进程树。

POSIX 使用独立进程组，Windows 使用 Job Object。即使顶层 lint 或 pytest 命令
已经退出，也会清理它留下的后代进程。

用法::

    uv run python scripts/shared/just/with_timeout.py <秒数> <命令> [参数...]

环境变量：
    WITH_TIMEOUT_GRACE   POSIX 上 SIGTERM 到 SIGKILL 的宽限秒数（默认 10）
    WITH_TIMEOUT_QUIET   设为 1 时不打印回收日志

退出码：透传被包装命令的退出码；超时则为 124（沿用 GNU timeout 约定）。
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

TIMEOUT_EXIT_CODE = 124
USAGE_EXIT_CODE = 2
COMMAND_NOT_FOUND_EXIT_CODE = 127
DEFAULT_GRACE_SECONDS = 10.0
GROUP_POLL_INTERVAL_SECONDS = 0.1
# 转发给子进程组的信号：子进程在独立 session 里收不到终端信号，必须由本进程
# 代为转发，否则 Ctrl-C 和关窗口都打不到被包装的命令。Windows 没有 SIGHUP，按可用性取。
FORWARDED_SIGNALS = tuple(
    signal_number
    for signal_number in (
        getattr(signal, "SIGINT", None),
        getattr(signal, "SIGTERM", None),
        getattr(signal, "SIGHUP", None),
    )
    if signal_number is not None
)
#: Windows 通过 Job Object 清理进程树，不使用 POSIX 进程组原语。
SUPPORTS_PROCESS_GROUPS = hasattr(os, "killpg") and hasattr(os, "getpgrp")


def log(message: str) -> None:
    """Write a reaper log line to stderr unless silenced.

    Args:
        message: Message body appended after the ``with-timeout:`` prefix.
    """
    if os.environ.get("WITH_TIMEOUT_QUIET") == "1":
        return
    sys.stderr.write(f"with-timeout: {message}\n")
    sys.stderr.flush()


def is_signalable_group(process_group_id: int) -> bool:
    """Report whether a process group may be signalled as a whole.

    Process group 0 means "the caller's own group" to ``killpg`` and group 1 is
    init/launchd; neither can ever be a group created by our child, whose group
    id always equals its own pid. Signalling them is how a runner kills itself.

    Args:
        process_group_id: Candidate process group id.

    Returns:
        bool: True when the group is safe to signal.
    """
    if not SUPPORTS_PROCESS_GROUPS or process_group_id in (0, 1):
        return False
    return process_group_id != os.getpgrp()


def group_alive(process_group_id: int) -> bool:
    """Report whether a process group still has at least one member.

    ``PermissionError`` must not be folded into "gone". It means the group still
    has a member that merely refuses signals, and it is the answer macOS gives
    for a group whose only remaining member is a zombie — never ``ESRCH``.
    Reading that as "empty" let :func:`reap_group` return while the group still
    had a member, and would equally make it skip a live process owned by another
    uid.

    Args:
        process_group_id: Process group to probe with signal 0.

    Returns:
        bool: True when the group still has a member (zombies included).
    """
    if not SUPPORTS_PROCESS_GROUPS:
        return False
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # EPERM 是「组里仍有成员、只是不允许发信号」，不是「组不存在」。
        # macOS 上「组里只剩僵尸」走的就是这条分支；当成已清空会让回收提前返回。
        return True
    return True


def reap_group(process_group_id: int, grace_seconds: float, reason: str) -> None:
    """Ensure a process group is empty, escalating SIGTERM to SIGKILL.

    Args:
        process_group_id: Process group to clear.
        grace_seconds: Seconds to wait after SIGTERM before sending SIGKILL.
        reason: Short Chinese phrase describing why the sweep runs; it is
            prefixed to the log line.
    """
    if not SUPPORTS_PROCESS_GROUPS:
        return
    if not is_signalable_group(process_group_id):
        log(f"拒绝对进程组 {process_group_id} 发信号（0/1/自身组），跳过回收。")
        return
    if not group_alive(process_group_id):
        return

    log(f"{reason}，进程组 {process_group_id} 仍有存活成员，发送 SIGTERM。")
    try:
        os.killpg(process_group_id, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return

    deadline = time.monotonic() + grace_seconds
    while time.monotonic() < deadline:
        if not group_alive(process_group_id):
            log(f"进程组 {process_group_id} 已在宽限期内退出。")
            return
        time.sleep(GROUP_POLL_INTERVAL_SECONDS)

    log(f"宽限 {grace_seconds:g}s 后仍未退出，对进程组 {process_group_id} 发送 SIGKILL。")
    try:
        os.killpg(process_group_id, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _install_signal_forwarding(process_group_id: int) -> dict[int, object]:
    """Forward terminal signals to the child's detached process group.

    Args:
        process_group_id: Process group that should receive forwarded signals.

    Returns:
        dict[int, object]: Previous handlers, keyed by signal number.
    """

    def forward(signal_number: int, _frame: object) -> None:
        if is_signalable_group(process_group_id):
            try:
                os.killpg(process_group_id, signal_number)
            except (ProcessLookupError, PermissionError):
                pass

    previous_handlers: dict[int, object] = {}
    for signal_number in FORWARDED_SIGNALS:
        try:
            previous_handlers[signal_number] = signal.signal(signal_number, forward)
        except (OSError, ValueError):
            # Windows / 非主线程上装不了某些处理器：跳过该信号，不影响命令执行。
            continue
    return previous_handlers


def run(timeout_seconds: float, command: list[str], grace_seconds: float) -> int:
    """运行带超时的命令，并在返回前清理其进程树。

    Args:
        timeout_seconds: 命令超时秒数。
        command: 要执行的命令及参数。
        grace_seconds: POSIX 上 SIGTERM 到 SIGKILL 的宽限秒数。

    Returns:
        命令退出码，超时时为 124。
    """
    if sys.platform == "win32":
        from with_timeout_windows import run_in_job

        try:
            return run_in_job(timeout_seconds, command)
        except subprocess.TimeoutExpired:
            log(f"Command timed out after {timeout_seconds:g}s.")
            return TIMEOUT_EXIT_CODE
        except KeyboardInterrupt:
            return 128 + signal.SIGINT

    try:
        # start_new_session 让子进程成为新 session 的组长（pgid == 其 pid），整棵
        # 子树因此落在一个可被精确回收的组里，不会误伤同终端的其它进程。
        child = subprocess.Popen(command, start_new_session=True)
    except FileNotFoundError:
        sys.stderr.write(f"with-timeout: 找不到命令: {command[0]}\n")
        return COMMAND_NOT_FOUND_EXIT_CODE

    child_group_id = child.pid
    previous_handlers = _install_signal_forwarding(child_group_id)

    timed_out = False
    try:
        exit_code = child.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        log(f"命令超过 {timeout_seconds:g}s 未结束: {' '.join(command)}")
        reap_group(child_group_id, grace_seconds, "超时")
        try:
            exit_code = child.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            exit_code = TIMEOUT_EXIT_CODE
    finally:
        for signal_number, handler in previous_handlers.items():
            signal.signal(signal_number, handler)

    # 正常退出也要复查：本工具要兜的正是"顶层退出、子树还在"这一种泄漏。
    reap_group(child_group_id, grace_seconds, "命令已退出")

    if not SUPPORTS_PROCESS_GROUPS and child.poll() is None:
        # 其他缺少进程组支持的平台保留直接子进程回收。
        child.kill()
        child.wait()

    if timed_out:
        return TIMEOUT_EXIT_CODE
    if exit_code < 0:
        # 被信号打死：沿用 shell 的 128+signo 约定。
        return 128 - exit_code
    return exit_code


def main(argv: list[str]) -> int:
    """Parse arguments and delegate to :func:`run`.

    Args:
        argv: Full argument vector, including the script name.

    Returns:
        int: Process exit code.
    """
    if len(argv) < 3:
        sys.stderr.write(__doc__ or "")
        return USAGE_EXIT_CODE

    try:
        timeout_seconds = float(argv[1])
    except ValueError:
        sys.stderr.write(f"with-timeout: 超时秒数不是数字: {argv[1]}\n")
        return USAGE_EXIT_CODE

    grace_seconds = float(os.environ.get("WITH_TIMEOUT_GRACE", DEFAULT_GRACE_SECONDS))
    return run(timeout_seconds, argv[2:], grace_seconds)


if __name__ == "__main__":
    exit_code = main(sys.argv)
    if sys.platform == "win32" and exit_code >= 2**31:
        # Python 的 SystemExit 接收有符号整数，Windows 进程状态是 32 位无符号值。
        exit_code -= 2**32
    sys.exit(exit_code)
