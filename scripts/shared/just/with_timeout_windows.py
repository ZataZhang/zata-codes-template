"""使用 Windows Job Object 管理超时命令的进程树。"""

from __future__ import annotations

import ctypes
import subprocess
import sys
import uuid
from ctypes import wintypes

_JOB_OBJECT_ASSIGN_PROCESS = 0x0001
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9


class _BasicLimitInformation(ctypes.Structure):
    # winnt.h 中的 JOBOBJECT_BASIC_LIMIT_INFORMATION，含指针宽度的字段随 Python 位数变化。
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", ctypes.c_uint64 * 6),  # IO_COUNTERS 的六个 ULONGLONG
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
_kernel32.CreateJobObjectW.restype = wintypes.HANDLE
_kernel32.SetInformationJobObject.argtypes = (
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
)
_kernel32.SetInformationJobObject.restype = wintypes.BOOL
_kernel32.OpenJobObjectW.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
_kernel32.OpenJobObjectW.restype = wintypes.HANDLE
_kernel32.GetCurrentProcess.argtypes = ()
_kernel32.GetCurrentProcess.restype = wintypes.HANDLE
_kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
_kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
_kernel32.CloseHandle.restype = wintypes.BOOL


def run_in_job(timeout_seconds: float, command: list[str]) -> int:
    """等待加入独立 Job 的命令，并在返回前关闭 Job。

    Args:
        timeout_seconds: 等待命令退出的秒数。
        command: 原始命令和参数列表。

    Returns:
        命令或 Windows 启动进程的退出码。

    Raises:
        OSError: Job 配置或启动失败。
        subprocess.TimeoutExpired: 命令超时。
    """
    job_name = f"Local\\with-timeout-{uuid.uuid4().hex}"
    job_handle = _kernel32.CreateJobObjectW(None, job_name)
    if not job_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    worker: subprocess.Popen[bytes] | None = None
    try:
        job_limits = _ExtendedLimitInformation()
        job_limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not _kernel32.SetInformationJobObject(
            job_handle,
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(job_limits),
            ctypes.sizeof(job_limits),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        worker = subprocess.Popen(
            [sys.executable, "-I", __file__, job_name, *command],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return worker.wait(timeout=timeout_seconds)
    finally:
        _kernel32.CloseHandle(job_handle)
        if worker is not None and worker.poll() is None:
            # 工作进程可能在加入 Job 前就超时，关闭句柄后还需处理这一种情况。
            worker.kill()
            worker.wait()


def _run_worker(job_name: str, command: list[str]) -> int:
    """先把自身加入 Job，再派生用户命令，避免子树逃过回收。"""
    job_handle = _kernel32.OpenJobObjectW(_JOB_OBJECT_ASSIGN_PROCESS, False, job_name)
    if not job_handle:
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        if not _kernel32.AssignProcessToJobObject(job_handle, _kernel32.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        # 让等待进程持有唯一的 Job 句柄，这样它退出时系统也会回收子树。
        _kernel32.CloseHandle(job_handle)

    try:
        return subprocess.call(command)
    except FileNotFoundError:
        sys.stderr.write(f"with-timeout: Command not found: {command[0]}\n")
        return 127


if __name__ == "__main__":
    try:
        sys.exit(ctypes.c_int32(_run_worker(sys.argv[1], sys.argv[2:])).value)
    except OSError as error:
        sys.exit(f"with-timeout: Could not run the command in a Windows Job Object: {error}")
