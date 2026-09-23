#!/usr/bin/env python3
"""沙箱执行后端冒烟：装配后端并跑一次命令与文件往返。

这是 ``SandboxProvider`` 端口的**最小消费示例**，走的是真实装配路径，不是另一条
旁路：

    build_sandbox_provider() -> acquire() -> execute()
    -> upload_files() / list_files() / download_files() -> destroy()

三档后端都能跑。``filesystem`` 档按契约**拒绝**执行命令（它不提供命令执行能力，也
不回落到宿主执行），该拒绝被本脚本视为正确结果而不是失败；文件往返照常完成。

用法：
    just sandbox-smoke
    uv run python scripts/dev/sandbox_smoke.py

前置：
- 未配置 ``config.toml`` 的 ``[sandbox_agent]`` 段时，脚本以非零退出码结束并打印如何
  启用——「没有沙箱可测」不应该看起来像「测过了且通过」。
- ``docker`` 档需要宿主 Docker daemon、``uv sync --extra sandbox-docker``，以及已
  构建的沙箱镜像（``deploy/sandbox/Dockerfile.sandbox``）。
- ``e2b`` 档需要 ``E2B_API_KEY`` 与已发布的平台模板。

详见 ``docs/guides/sandbox-runtime.md``。
"""

from __future__ import annotations

import sys

from backend.composition.sandbox_wiring import build_sandbox_provider
from backend.core.shared.interfaces.sandbox_provider import (
    SandboxFileWrite,
    SandboxProvider,
    SandboxSession,
)
from backend.infrastructure.sandbox.filesystem_provider import FilesystemSandboxProvider

_SMOKE_THREAD_ID = "sandbox-smoke"
_SMOKE_OUTPUT_DIRECTORY = "/workspace/outputs"
_SMOKE_FILE_PATH = f"{_SMOKE_OUTPUT_DIRECTORY}/sandbox-smoke.txt"
_SMOKE_FILE_CONTENT = b"sandbox-smoke-ok\n"
_SMOKE_MARKER = "sandbox-smoke-ok"
_SMOKE_COMMAND = f"echo {_SMOKE_MARKER}"
_SMOKE_COMMAND_TIMEOUT_SECONDS = 30


def _report_step(step_description: str, detail: str = "") -> None:
    """打印一条通过的冒烟步骤。"""
    suffix = f" — {detail}" if detail else ""
    print(f"  [ok] {step_description}{suffix}")


def _fail_smoke(failure_description: str) -> int:
    """打印失败原因并返回非零退出码。"""
    print(f"  [fail] {failure_description}", file=sys.stderr)
    return 1


def _verify_command_execution(
    sandbox_provider: SandboxProvider, sandbox_session: SandboxSession
) -> int | None:
    """验证命令执行，返回 ``None`` 表示通过，否则返回非零退出码。"""
    execution = sandbox_session.execute(
        _SMOKE_COMMAND, timeout_seconds=_SMOKE_COMMAND_TIMEOUT_SECONDS
    )
    if isinstance(sandbox_provider, FilesystemSandboxProvider):
        if execution.exit_code == 0:
            return _fail_smoke("filesystem 档不应执行命令，却返回了成功")
        _report_step("命令按契约被拒绝（filesystem 档不提供执行能力）", execution.output.strip())
        return None
    if execution.exit_code != 0:
        return _fail_smoke(f"命令执行失败 exit={execution.exit_code}：{execution.output.strip()}")
    if _SMOKE_MARKER not in execution.output:
        return _fail_smoke(f"命令输出未包含预期标记：{execution.output.strip()}")
    _report_step("命令执行成功", execution.output.strip())
    return None


def _verify_file_round_trip(sandbox_session: SandboxSession) -> int | None:
    """验证文件写入/枚举/读回，返回 ``None`` 表示通过，否则返回非零退出码。"""
    sandbox_session.upload_files(
        [SandboxFileWrite(sandbox_path=_SMOKE_FILE_PATH, content=_SMOKE_FILE_CONTENT)]
    )
    _report_step("文件已写入", _SMOKE_FILE_PATH)

    listed_paths = list(sandbox_session.list_files(_SMOKE_OUTPUT_DIRECTORY))
    if _SMOKE_FILE_PATH not in listed_paths:
        return _fail_smoke(f"文件枚举未包含刚写入的文件：{listed_paths}")
    _report_step("文件枚举命中", f"{len(listed_paths)} 个文件")

    file_reads = sandbox_session.download_files([_SMOKE_FILE_PATH])
    read_result = file_reads[0]
    if read_result.content != _SMOKE_FILE_CONTENT:
        return _fail_smoke(f"文件内容往返不一致：error={read_result.error}")
    _report_step("文件内容往返一致")
    return None


def run_sandbox_smoke(sandbox_provider: SandboxProvider) -> int:
    """对已装配的后端跑一轮冒烟，返回进程退出码。

    Args:
        sandbox_provider (SandboxProvider): 已装配的沙箱后端。

    Returns:
        int: ``0`` 表示全部步骤通过，非零表示首个失败的步骤。
    """
    sandbox_session = sandbox_provider.acquire(_SMOKE_THREAD_ID)
    try:
        command_result = _verify_command_execution(sandbox_provider, sandbox_session)
        if command_result is not None:
            return command_result
        file_result = _verify_file_round_trip(sandbox_session)
        if file_result is not None:
            return file_result
    finally:
        # 冒烟不留资源：容器 / 云沙箱在结束时销毁，文件系统一并清掉。
        sandbox_provider.destroy(_SMOKE_THREAD_ID)
    _report_step("会话环境已销毁")
    return 0


def main() -> int:
    """装配沙箱后端并跑一轮冒烟，返回进程退出码。"""
    sandbox_provider = build_sandbox_provider()
    if sandbox_provider is None:
        print(
            "未装配沙箱后端：config.toml 里没有可用的 [sandbox_agent] 段。\n"
            "启用方式见 docs/guides/sandbox-runtime.md。最小步骤是取消 config.toml 中该段\n"
            '注释并把 provider 设为 "filesystem"（该档不需要 Docker 或云凭据）。',
            file=sys.stderr,
        )
        return 1
    print(f"后端: {type(sandbox_provider).__name__}")
    return run_sandbox_smoke(sandbox_provider)


if __name__ == "__main__":
    raise SystemExit(main())
