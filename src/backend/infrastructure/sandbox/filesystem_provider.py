"""基于本地目录的默认沙箱实现。

这是缺省档:行为与引入沙箱 Runtime 之前一致,使未配置 Docker 的部署零影响升级。
它**不提供执行隔离**——``execute`` 直接拒绝而不是回落到宿主执行,因为静默回落
会让调用方以为命令跑在沙箱里。需要命令执行能力时必须显式切换到 Docker 档。
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxExecutionResult,
    SandboxFileRead,
    SandboxFileWrite,
)
from backend.infrastructure.sandbox.sandbox_rules import (
    validated_runtime_asset_relative_path,
)


class FilesystemSandboxSession:
    """把会话专属本地目录暴露为沙箱环境。"""

    def __init__(self, session_root: Path) -> None:
        """绑定会话根目录。

        根目录在此规范化为绝对路径:配置里的 ``workspace_root`` 允许是相对路径
        (相对 backend 工作目录解析),而路径校验与枚举都产出绝对路径。两种表示
        混用会让 :meth:`list_files` 的相对路径计算抛 ``ValueError``。

        Args:
            session_root (Path): 该会话的隔离根目录;所有路径都被限制在其内。
        """
        self._session_root = session_root.resolve()

    @property
    def session_key(self) -> str:
        """返回会话根目录路径,作为本会话环境的稳定标识。"""
        return str(self._session_root)

    def execute(self, command: str, *, timeout_seconds: int) -> SandboxExecutionResult:
        """拒绝执行命令。

        Args:
            command (str): 待执行命令;本实现不会执行它。
            timeout_seconds (int): 超时秒数;本实现忽略。

        Returns:
            SandboxExecutionResult: 固定的拒绝结果,退出码非 0。
        """
        return SandboxExecutionResult(
            output="当前沙箱后端为 filesystem，不提供命令执行能力；"
            "需要执行命令请把沙箱后端切换为 docker。",
            exit_code=1,
            truncated=False,
        )

    def upload_files(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """把文件写入会话目录。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合。

        Raises:
            RuntimeError: 任一目标路径越出会话根目录。
        """
        for file_write in file_writes:
            host_path = self._resolved_host_path(file_write.sandbox_path)
            host_path.parent.mkdir(parents=True, exist_ok=True)
            host_path.write_bytes(file_write.content)

    def replace_runtime_assets(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """完整替换会话目录内的 Skill 运行资产根目录。

        全部文件先写入暂存目录,再整体换名到位:写入中途失败时旧资产原样保留,
        后续运行不会读到半套脚本。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合;路径必须
                位于 :data:`SANDBOX_SKILL_RUNTIME_ROOT` 之下。

        Raises:
            RuntimeError: 路径越界或任一文件写入失败。
        """
        runtime_root_path = self._resolved_runtime_asset_root()
        staging_root_path = runtime_root_path.with_name(f"{runtime_root_path.name}.staging")
        shutil.rmtree(staging_root_path, ignore_errors=True)
        try:
            # 空声明也要建出暂存目录:换名步骤依赖它存在,用来清空运行资产根目录。
            staging_root_path.mkdir(parents=True, exist_ok=True)
            for file_write in file_writes:
                relative_path = validated_runtime_asset_relative_path(file_write.sandbox_path)
                staged_path = staging_root_path / relative_path
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.write_bytes(file_write.content)
            shutil.rmtree(runtime_root_path, ignore_errors=True)
            staging_root_path.rename(runtime_root_path)
        except (OSError, RuntimeError, ValueError):
            shutil.rmtree(staging_root_path, ignore_errors=True)
            raise

    def _resolved_runtime_asset_root(self) -> Path:
        """返回运行资产根目录在宿主上的路径。"""
        return self._resolved_host_path(SANDBOX_SKILL_RUNTIME_ROOT)

    def list_files(self, sandbox_directory: str) -> Sequence[str]:
        """列出目录下全部文件的沙箱绝对路径。

        Args:
            sandbox_directory (str): 沙箱内目录绝对路径。

        Returns:
            Sequence[str]: 文件的沙箱绝对路径;目录不存在时为空。
        """
        host_directory = self._resolved_host_path(sandbox_directory)
        if not host_directory.is_dir():
            return []
        return [
            f"/{found_path.relative_to(self._session_root).as_posix()}"
            for found_path in sorted(host_directory.rglob("*"))
            if found_path.is_file()
        ]

    def download_files(self, sandbox_paths: Sequence[str]) -> Sequence[SandboxFileRead]:
        """从会话目录读回文件。

        Args:
            sandbox_paths (Sequence[str]): 沙箱内文件绝对路径集合。

        Returns:
            Sequence[SandboxFileRead]: 与入参等长的读取结果。
        """
        file_reads: list[SandboxFileRead] = []
        for sandbox_path in sandbox_paths:
            try:
                file_reads.append(
                    SandboxFileRead(
                        sandbox_path=sandbox_path,
                        content=self._resolved_host_path(sandbox_path).read_bytes(),
                        error=None,
                    )
                )
            except (OSError, RuntimeError) as read_error:
                file_reads.append(
                    SandboxFileRead(sandbox_path=sandbox_path, content=None, error=str(read_error))
                )
        return file_reads

    def _resolved_host_path(self, sandbox_path: str) -> Path:
        """把沙箱绝对路径解析为会话目录内的宿主路径。

        Raises:
            RuntimeError: 解析结果越出会话根目录。
        """
        resolved_root = self._session_root.resolve()
        candidate_path = (resolved_root / sandbox_path.lstrip("/")).resolve()
        if not candidate_path.is_relative_to(resolved_root):
            raise RuntimeError(f"沙箱路径越出会话根目录: {sandbox_path}")
        return candidate_path


class FilesystemSandboxProvider:
    """按会话在本地工作区下分配隔离目录。"""

    def __init__(self, workspace_root: Path) -> None:
        """绑定工作区根目录。

        Args:
            workspace_root (Path): 全部会话目录的父目录。
        """
        self._workspace_root = workspace_root

    def is_available(self) -> bool:
        """本地目录后端始终可用。"""
        return True

    def availability_detail(self) -> str | None:
        """本地目录后端无不可用原因。"""
        return None

    def acquire(self, thread_id: str) -> FilesystemSandboxSession:
        """取得会话专属目录,不存在时创建。

        Args:
            thread_id (str): 会话标识。

        Returns:
            FilesystemSandboxSession: 该会话的目录环境。
        """
        session_root = self._workspace_root / thread_id
        session_root.mkdir(parents=True, exist_ok=True)
        return FilesystemSandboxSession(session_root)

    def release(self, thread_id: str) -> None:
        """本地目录后端无运行资源需要释放。

        Args:
            thread_id (str): 会话标识;本实现忽略。
        """

    def destroy(self, thread_id: str) -> None:
        """删除会话目录及其内容。

        Args:
            thread_id (str): 会话标识。
        """
        shutil.rmtree(self._workspace_root / thread_id, ignore_errors=True)


__all__ = ["FilesystemSandboxProvider", "FilesystemSandboxSession"]
