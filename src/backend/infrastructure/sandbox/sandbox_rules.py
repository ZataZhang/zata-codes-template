"""沙箱后端之间共享的路径与输出约束。

Docker、本地目录与云沙箱三个后端必须对"沙箱内路径是否合法""命令输出如何截断"
给出同一答案:同一份执行器、资源暂存器与产物导出代码在三个后端之间通用,任何一处
语义漂移都会让某个后端静默产生不同行为。规则集中在这里,由各后端复用。
"""

from __future__ import annotations

import shlex
from pathlib import PurePosixPath

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxExecutionResult,
)

MAX_SANDBOX_OUTPUT_BYTES: int = 100_000
"""单条命令输出的合并字节上限;超出部分被丢弃并在结果里标记截断。"""


def build_file_listing_command(sandbox_directory: str) -> str:
    """构造枚举目录下全部文件的命令。

    用 ``-print0`` 而不是换行分隔:沙箱内的 agent 可以造出含换行的文件名,按行切分会
    把一条路径切成两条,产物导出因此多出一个不存在的文件。

    Args:
        sandbox_directory (str): 沙箱内目录绝对路径。

    Returns:
        str: 可直接交给沙箱执行的命令。
    """
    return f"find {shlex.quote(sandbox_directory)} -type f -print0"


def decode_file_listing(listing: SandboxExecutionResult) -> list[str]:
    """把文件枚举命令的结果解码为路径列表。

    截断即拒绝:枚举不全时返回部分列表会让产物导出悄悄漏掉文件,而"少了几个产物"比
    "Run 失败"更难发现。目录不存在(命令非零退出)才按空列表处理。

    Args:
        listing (SandboxExecutionResult): 枚举命令的执行结果。

    Returns:
        list[str]: 文件绝对路径;目录不存在时为空。

    Raises:
        RuntimeError: 输出被截断,无法确认已枚举全部文件。
    """
    if listing.truncated:
        raise RuntimeError("沙箱文件列表过长,拒绝按不完整结果导出")
    if listing.exit_code != 0:
        return []
    return [found_path for found_path in listing.output.split("\0") if found_path]


def validated_sandbox_path(sandbox_path: str) -> str:
    """校验沙箱路径为无父目录穿越的绝对 POSIX 路径。

    Args:
        sandbox_path (str): 待校验路径。

    Returns:
        str: 规范化后的路径。

    Raises:
        ValueError: 路径为相对路径或含父目录穿越。
    """
    candidate_path = PurePosixPath(sandbox_path)
    if not candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise ValueError("沙箱文件路径必须是无父目录穿越的绝对 POSIX 路径")
    return str(candidate_path)


def validated_runtime_asset_relative_path(sandbox_path: str) -> str:
    """把运行资产路径校验为资产根目录内的相对路径。

    Args:
        sandbox_path (str): 待校验的沙箱绝对路径。

    Returns:
        str: 相对 :data:`SANDBOX_SKILL_RUNTIME_ROOT` 的 POSIX 路径。

    Raises:
        ValueError: 路径不在运行资产根目录之下,或仍是根目录本身。
    """
    normalized_path = PurePosixPath(validated_sandbox_path(sandbox_path))
    runtime_root_path = PurePosixPath(SANDBOX_SKILL_RUNTIME_ROOT)
    if not normalized_path.is_relative_to(runtime_root_path):
        raise ValueError(f"Skill 运行资产路径必须位于 {SANDBOX_SKILL_RUNTIME_ROOT} 之下")
    relative_path = normalized_path.relative_to(runtime_root_path)
    if str(relative_path) == ".":
        raise ValueError("Skill 运行资产路径不能是运行资产根目录本身")
    return str(relative_path)


def decode_truncated_output(combined_output_bytes: bytes) -> tuple[str, bool]:
    """把命令的合并输出按上限截断并解码为文本。

    Args:
        combined_output_bytes (bytes): stdout 与 stderr 的合并字节。

    Returns:
        tuple[str, bool]: 截断后的文本与是否发生截断。截断为真时调用方不能把该文本
            当作完整结果使用。
    """
    is_truncated = len(combined_output_bytes) > MAX_SANDBOX_OUTPUT_BYTES
    truncated_text = combined_output_bytes[:MAX_SANDBOX_OUTPUT_BYTES].decode(
        "utf-8", errors="replace"
    )
    return truncated_text, is_truncated


__all__ = [
    "MAX_SANDBOX_OUTPUT_BYTES",
    "decode_truncated_output",
    "validated_runtime_asset_relative_path",
    "validated_sandbox_path",
]
