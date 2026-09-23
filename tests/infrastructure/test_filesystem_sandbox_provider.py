"""基于本地目录的默认沙箱实现测试。

覆盖：不提供命令执行（拒绝而非回落宿主）、文件读写往返、路径越界拒绝，以及运行资产
目录"整体替换"的原子语义。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxFileWrite,
)
from backend.infrastructure.sandbox.filesystem_provider import (
    FilesystemSandboxProvider,
    FilesystemSandboxSession,
)


@pytest.fixture
def sandbox_provider(tmp_path: Path) -> FilesystemSandboxProvider:
    """返回以临时目录为工作区根的 filesystem 档后端。"""
    return FilesystemSandboxProvider(tmp_path / "workspace-root")


def test_provider_is_always_available(sandbox_provider: FilesystemSandboxProvider) -> None:
    """本地目录后端始终可用，且没有不可用原因。"""
    assert sandbox_provider.is_available() is True
    assert sandbox_provider.availability_detail() is None


def test_acquire_creates_session_directory(
    sandbox_provider: FilesystemSandboxProvider, tmp_path: Path
) -> None:
    """取得会话时创建其专属目录，并以目录路径作为稳定标识。"""
    sandbox_session = sandbox_provider.acquire("thread-a")

    assert isinstance(sandbox_session, FilesystemSandboxSession)
    assert sandbox_session.session_key == str(tmp_path / "workspace-root" / "thread-a")
    assert (tmp_path / "workspace-root" / "thread-a").is_dir()
    assert sandbox_provider.acquire("thread-a").session_key == sandbox_session.session_key


def test_execute_is_refused_instead_of_falling_back_to_host(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """filesystem 档拒绝执行命令，退出码非 0，绝不回落到宿主执行。"""
    execution = sandbox_provider.acquire("thread-a").execute("echo hi", timeout_seconds=30)

    assert execution.exit_code == 1
    assert "不提供命令执行能力" in execution.output
    assert execution.truncated is False


def test_upload_list_and_download_round_trip(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """文件写入后能被枚举并按沙箱绝对路径读回。"""
    sandbox_session = sandbox_provider.acquire("thread-a")
    sandbox_session.upload_files(
        [
            SandboxFileWrite(sandbox_path="/workspace/outputs/report.txt", content=b"hello"),
        ]
    )

    assert sandbox_session.list_files("/workspace/outputs") == ["/workspace/outputs/report.txt"]
    downloaded_reads = sandbox_session.download_files(["/workspace/outputs/report.txt"])
    assert downloaded_reads[0].content == b"hello"
    assert downloaded_reads[0].error is None


def test_relative_workspace_root_still_lists_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``workspace_root`` 为相对路径时枚举仍可用。

    配置里的默认值是相对路径，而路径校验与枚举产出绝对路径；两种表示混用曾让
    :meth:`list_files` 抛 ``ValueError``。
    """
    monkeypatch.chdir(tmp_path)
    sandbox_provider = FilesystemSandboxProvider(Path("sandbox-workspace"))
    sandbox_session = sandbox_provider.acquire("thread-a")
    sandbox_session.upload_files(
        [SandboxFileWrite(sandbox_path="/workspace/outputs/report.txt", content=b"hello")]
    )

    assert sandbox_session.list_files("/workspace/outputs") == ["/workspace/outputs/report.txt"]
    assert Path(sandbox_session.session_key).is_absolute()


def test_list_files_returns_empty_for_missing_directory(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """目录不存在时枚举返回空列表，而不是抛错。"""
    assert sandbox_provider.acquire("thread-a").list_files("/workspace/outputs") == []


def test_upload_rejects_path_escaping_session_root(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """上传路径越出会话根目录时整体拒绝，不静默写到宿主上的其他位置。"""
    sandbox_session = sandbox_provider.acquire("thread-a")

    with pytest.raises(RuntimeError, match="越出会话根目录"):
        sandbox_session.upload_files(
            [SandboxFileWrite(sandbox_path="/../../escape.txt", content=b"x")]
        )


def test_download_reports_per_item_error_for_escaping_path(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """下载路径越界时逐项标注失败，不中断其余项。"""
    file_reads = sandbox_provider.acquire("thread-a").download_files(["/../escape.txt"])

    assert len(file_reads) == 1
    assert file_reads[0].content is None
    assert file_reads[0].error is not None


def test_replace_runtime_assets_removes_stale_files(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """运行资产整体替换：上一版残留的脚本不得被后续运行读到。"""
    sandbox_session = sandbox_provider.acquire("thread-a")
    sandbox_session.replace_runtime_assets(
        [
            SandboxFileWrite(
                sandbox_path=f"{SANDBOX_SKILL_RUNTIME_ROOT}/skill-a/old.py", content=b"old"
            ),
        ]
    )
    assert sandbox_session.list_files(SANDBOX_SKILL_RUNTIME_ROOT) == [
        f"{SANDBOX_SKILL_RUNTIME_ROOT}/skill-a/old.py"
    ]

    sandbox_session.replace_runtime_assets(
        [
            SandboxFileWrite(
                sandbox_path=f"{SANDBOX_SKILL_RUNTIME_ROOT}/skill-a/new.py", content=b"new"
            ),
        ]
    )

    assert sandbox_session.list_files(SANDBOX_SKILL_RUNTIME_ROOT) == [
        f"{SANDBOX_SKILL_RUNTIME_ROOT}/skill-a/new.py"
    ]


def test_replace_runtime_assets_with_empty_set_clears_root(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """空声明表示清空运行资产根目录。"""
    sandbox_session = sandbox_provider.acquire("thread-a")
    sandbox_session.replace_runtime_assets(
        [
            SandboxFileWrite(
                sandbox_path=f"{SANDBOX_SKILL_RUNTIME_ROOT}/skill-a/x.py", content=b"x"
            ),
        ]
    )

    sandbox_session.replace_runtime_assets([])

    assert sandbox_session.list_files(SANDBOX_SKILL_RUNTIME_ROOT) == []


def test_replace_runtime_assets_rejects_paths_outside_root(
    sandbox_provider: FilesystemSandboxProvider,
) -> None:
    """越出运行资产根目录的路径被拒绝，且不留下半套资产。"""
    sandbox_session = sandbox_provider.acquire("thread-a")

    with pytest.raises(ValueError):
        sandbox_session.replace_runtime_assets(
            [SandboxFileWrite(sandbox_path="/workspace/outputs/sneaky.py", content=b"x")]
        )

    assert sandbox_session.list_files(SANDBOX_SKILL_RUNTIME_ROOT) == []


def test_destroy_removes_session_directory(
    sandbox_provider: FilesystemSandboxProvider, tmp_path: Path
) -> None:
    """销毁会话删除其目录及其内容。"""
    sandbox_provider.acquire("thread-a").upload_files(
        [SandboxFileWrite(sandbox_path="/workspace/outputs/x.txt", content=b"x")]
    )

    sandbox_provider.destroy("thread-a")

    assert not (tmp_path / "workspace-root" / "thread-a").exists()
