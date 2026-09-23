"""沙箱执行环境抽象端口。

刻意不引入任何容器技术概念:``SandboxProvider`` 只描述"按会话取得一个能执行命令
和读写文件的隔离环境",Docker、microVM 或纯文件工作区都可以实现它。隔离原语仍在
演进(gVisor / Kata / Firecracker),端口化让替换实现不触及 Runtime 层。

会话与环境的对应关系由实现自行持有,不在平台数据库建表——环境本身已经是这个状态
的真源,再存一份副本只会引入一致性维护成本。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

SANDBOX_SKILL_RUNTIME_ROOT: str = "/workspace/.skill-runtime"
"""Skill 运行资产在执行环境内的固定根目录。

平台只把 frontmatter ``runtime_assets`` 声明的文件写到这里，且每次都完整替换整个
根目录；Skill 知识绝不进入执行环境，二者因此可以分别排查。
"""


@dataclass(frozen=True)
class SandboxExecutionResult:
    """单次沙箱命令执行结果。

    Attributes:
        output (str): 合并后的 stdout 与 stderr 文本。
        exit_code (int): 命令退出码;非 0 表示命令自身失败。
        truncated (bool): 输出是否因超过容量上限被截断。截断时不能把 ``output``
            当作完整结果使用。
    """

    output: str
    exit_code: int
    truncated: bool


@dataclass(frozen=True)
class SandboxFileWrite:
    """待写入沙箱的单个文件。

    Attributes:
        sandbox_path (str): 沙箱内的绝对路径。
        content (bytes): 文件内容。
    """

    sandbox_path: str
    content: bytes


@dataclass(frozen=True)
class SandboxFileRead:
    """从沙箱读回的单个文件。

    Attributes:
        sandbox_path (str): 沙箱内的绝对路径。
        content (bytes | None): 文件内容;读取失败时为 ``None``。
        error (str | None): 读取失败原因;成功时为 ``None``。
    """

    sandbox_path: str
    content: bytes | None
    error: str | None


class SandboxSession(Protocol):
    """单个会话专属的隔离执行环境。

    同一会话的多次运行复用同一环境以保留文件系统;不同会话之间不共享任何状态。
    """

    @property
    def session_key(self) -> str:
        """返回本会话环境的稳定标识,用于判断缓存的 agent 是否仍然有效。"""
        ...

    def execute(self, command: str, *, timeout_seconds: int) -> SandboxExecutionResult:
        """在隔离环境内执行命令。

        Args:
            command (str): 待执行的 shell 命令。
            timeout_seconds (int): 超时秒数;超时必须终止命令而不是挂起。

        Returns:
            SandboxExecutionResult: 输出、退出码与截断标记。
        """
        ...

    def upload_files(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """把文件写入隔离环境。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合。

        Raises:
            RuntimeError: 任一文件写入失败;部分成功不能被当作成功。
        """
        ...

    def list_files(self, sandbox_directory: str) -> Sequence[str]:
        """列出目录下的全部文件绝对路径。

        Args:
            sandbox_directory (str): 沙箱内的目录绝对路径。

        Returns:
            Sequence[str]: 该目录下的文件路径;目录不存在时返回空序列。

        Raises:
            RuntimeError: 列表不完整,无法确认已枚举全部文件。
        """
        ...

    def download_files(self, sandbox_paths: Sequence[str]) -> Sequence[SandboxFileRead]:
        """从隔离环境读回文件。

        Args:
            sandbox_paths (Sequence[str]): 沙箱内的文件绝对路径集合。

        Returns:
            Sequence[SandboxFileRead]: 与入参等长的读取结果,逐项标注成功或失败。
        """
        ...

    def replace_runtime_assets(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """完整替换 Skill 运行资产根目录的内容。

        这是执行环境里唯一允许出现 Skill 字节的位置。实现必须整体替换而不是增量
        合并:先移除现有内容再写入本次声明,旧版本残留的脚本不得被后续运行使用;
        任一文件写入失败时整体失败,且不得留下可被后续运行当作有效资产的半成品。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合;路径必须
                位于 :data:`SANDBOX_SKILL_RUNTIME_ROOT` 之下。空集合表示清空该目录。

        Raises:
            RuntimeError: 路径越界或任一文件写入失败。
        """
        ...


class SandboxProvider(Protocol):
    """按会话提供隔离执行环境。"""

    def acquire(self, thread_id: str) -> SandboxSession:
        """取得会话专属环境,不存在时创建。

        Args:
            thread_id (str): 会话标识。

        Returns:
            SandboxSession: 该会话专属的隔离环境。

        Raises:
            RuntimeError: 环境无法创建或后端不可用。
        """
        ...

    def release(self, thread_id: str) -> None:
        """释放会话环境占用的运行资源,保留其文件系统。

        实现可因后端能力选择"续期保活"而不是真正停机:不支持暂停的执行环境(如云沙箱)
        无法在不销毁文件系统的前提下释放计算资源,此时只保证文件系统在存活窗口内仍可
        复用,调用方不能据此假定成本已归零。

        Args:
            thread_id (str): 会话标识。
        """
        ...

    def destroy(self, thread_id: str) -> None:
        """彻底销毁会话环境,含其文件系统。

        Args:
            thread_id (str): 会话标识。
        """
        ...

    def is_available(self) -> bool:
        """返回后端当前是否可用,供健康检查在 Run 创建前拒绝不可用 Runtime。"""
        ...

    def availability_detail(self) -> str | None:
        """返回不可用原因;可用时为 ``None``。"""
        ...


__all__ = [
    "SANDBOX_SKILL_RUNTIME_ROOT",
    "SandboxExecutionResult",
    "SandboxFileRead",
    "SandboxFileWrite",
    "SandboxProvider",
    "SandboxSession",
]
