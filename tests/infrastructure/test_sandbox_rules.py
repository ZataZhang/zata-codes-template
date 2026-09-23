"""沙箱后端共享路径与输出规则测试。

Docker、本地目录与云沙箱三个后端必须对"沙箱内路径是否合法""输出如何截断""文件枚举
如何解码"给出同一答案；这里的用例就是那份共同语义。
"""

from __future__ import annotations

import pytest

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxExecutionResult,
)
from backend.infrastructure.sandbox.sandbox_rules import (
    MAX_SANDBOX_OUTPUT_BYTES,
    build_file_listing_command,
    decode_file_listing,
    decode_truncated_output,
    validated_runtime_asset_relative_path,
    validated_sandbox_path,
)


def test_listing_command_uses_nul_separator() -> None:
    """文件枚举用 ``-print0``：含换行的文件名不能把一条路径切成两条。"""
    assert build_file_listing_command("/workspace/outputs") == (
        "find /workspace/outputs -type f -print0"
    )


def test_decode_file_listing_splits_on_nul_and_tolerates_missing_directory() -> None:
    """按 NUL 切分路径；目录不存在（非零退出）按空列表处理。"""
    listing = SandboxExecutionResult(output="/a/b\0/c\0", exit_code=0, truncated=False)
    assert decode_file_listing(listing) == ["/a/b", "/c"]

    missing_directory_listing = SandboxExecutionResult(output="", exit_code=1, truncated=False)
    assert decode_file_listing(missing_directory_listing) == []


def test_decode_file_listing_refuses_truncated_result() -> None:
    """枚举被截断即拒绝：部分列表会让产物导出悄悄漏掉文件。"""
    truncated_listing = SandboxExecutionResult(output="/a\0", exit_code=0, truncated=True)

    with pytest.raises(RuntimeError, match="拒绝按不完整结果导出"):
        decode_file_listing(truncated_listing)


@pytest.mark.parametrize(
    "valid_path", ["/workspace/outputs/x.txt", "/a", "/workspace/.skill-runtime"]
)
def test_validated_sandbox_path_accepts_absolute_without_traversal(valid_path: str) -> None:
    """合法路径原样规范化返回。"""
    assert validated_sandbox_path(valid_path) == valid_path


@pytest.mark.parametrize("invalid_path", ["relative/x.txt", "/a/../b", "../etc/passwd", ""])
def test_validated_sandbox_path_rejects_relative_and_traversal(invalid_path: str) -> None:
    """相对路径与父目录穿越被拒绝。"""
    with pytest.raises(ValueError, match="绝对 POSIX 路径"):
        validated_sandbox_path(invalid_path)


def test_validated_runtime_asset_relative_path_returns_path_within_root() -> None:
    """运行资产路径被解析为相对资产根目录的路径。"""
    sandbox_path = f"{SANDBOX_SKILL_RUNTIME_ROOT}/excel-diff/scripts/compare.py"

    assert validated_runtime_asset_relative_path(sandbox_path) == "excel-diff/scripts/compare.py"


@pytest.mark.parametrize(
    "invalid_path",
    [
        "/workspace/outputs/x.txt",
        SANDBOX_SKILL_RUNTIME_ROOT,
        f"{SANDBOX_SKILL_RUNTIME_ROOT}/../escape",
    ],
)
def test_validated_runtime_asset_relative_path_rejects_outside_root(invalid_path: str) -> None:
    """越界路径与资产根目录本身都被拒绝。"""
    with pytest.raises(ValueError):
        validated_runtime_asset_relative_path(invalid_path)


def test_decode_truncated_output_marks_over_cap_output() -> None:
    """超出上限时截断并打标；未超上限时原样返回且不截断。"""
    under_cap_text, under_cap_truncated = decode_truncated_output(b"ok")
    assert (under_cap_text, under_cap_truncated) == ("ok", False)

    oversized_bytes = b"x" * (MAX_SANDBOX_OUTPUT_BYTES + 10)
    oversized_text, oversized_truncated = decode_truncated_output(oversized_bytes)
    assert oversized_truncated is True
    assert len(oversized_text) == MAX_SANDBOX_OUTPUT_BYTES


def test_decode_truncated_output_replaces_undecodable_bytes() -> None:
    """非法 UTF-8 字节按替换字符解码，而不是抛异常中断调用方。"""
    decoded_text, is_truncated = decode_truncated_output(b"\xff\xfe")

    assert is_truncated is False
    assert decoded_text == "\ufffd\ufffd"
