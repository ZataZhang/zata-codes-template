"""基于 Docker 容器的沙箱执行环境实现。

会话到容器的映射用容器标签查询恢复,不建数据库表——Docker 本身已经是这个状态的
真源,再存一份副本只会引入迁移与一致性维护成本,进程重启后也能凭标签找回容器。

隔离参数是安全边界而非可调项:不注入宿主环境变量(模型 API 密钥就在其中)、不挂载
宿主目录与 Docker socket、非 root 运行、弃全部 Linux 特权能力、限制内存 CPU 与
进程数。出站网络由 :class:`SandboxEgressPolicy` 决定。
"""

from __future__ import annotations

import hashlib
import io
import shlex
import tarfile
import threading
from pathlib import PurePosixPath
from typing import Any, Sequence
from uuid import uuid4

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxExecutionResult,
    SandboxFileRead,
    SandboxFileWrite,
)
from backend.infrastructure.sandbox.egress_policy import SandboxEgressPolicy
from backend.infrastructure.sandbox.sandbox_rules import (
    build_file_listing_command,
    decode_file_listing,
    decode_truncated_output,
    validated_runtime_asset_relative_path,
    validated_sandbox_path,
)

# nobody:nogroup。容器内以非 root 执行,即使发生逃逸也不直接落到宿主 root。
_SANDBOX_USER = "65534:65534"
_SANDBOX_UID = 65534
_LISTING_TIMEOUT_SECONDS = 30
_RUNTIME_LABEL = "zata-sandbox-runtime"
_THREAD_LABEL = "zata-sandbox-thread"
_WORKSPACE_DIRECTORIES = (
    "/workspace",
    "/workspace/inputs",
    "/workspace/outputs",
    "/assets",
    "/tmp/agent",
    "/large_tool_results",
    "/conversation_history",
)


class DockerSandboxSession:
    """单个会话专属的 Docker 容器执行环境。"""

    def __init__(self, container: Any, *, command_timeout_seconds: int) -> None:
        """绑定容器与默认命令超时。

        Args:
            container (Any): 已启动的 Docker 容器对象。
            command_timeout_seconds (int): 未显式指定时的命令超时秒数。
        """
        self._container = container
        self._command_timeout_seconds = command_timeout_seconds

    @property
    def session_key(self) -> str:
        """返回容器 ID,作为本会话环境的稳定标识。"""
        return str(self._container.id)

    @property
    def container(self) -> Any:
        """返回底层容器对象,供 provider 管理生命周期。"""
        return self._container

    def execute(self, command: str, *, timeout_seconds: int) -> SandboxExecutionResult:
        """在容器内执行命令。

        Args:
            command (str): 待执行的 shell 命令。
            timeout_seconds (int): 超时秒数;非正数表示使用默认超时。

        Returns:
            SandboxExecutionResult: 输出、退出码与截断标记。
        """
        from docker.errors import DockerException

        effective_timeout_seconds = (
            timeout_seconds if timeout_seconds > 0 else self._command_timeout_seconds
        )
        # 用 timeout 包裹而不是依赖客户端超时:后者只会放弃等待,命令仍在容器内跑。
        bounded_command = (
            f"timeout --kill-after=5s {effective_timeout_seconds}s "
            f"/bin/sh -lc {shlex.quote(command)}"
        )
        try:
            execution = self._container.exec_run(
                ["/bin/sh", "-lc", bounded_command],
                user=_SANDBOX_USER,
                workdir="/workspace",
                demux=True,
            )
        except DockerException as docker_error:
            return SandboxExecutionResult(output=str(docker_error), exit_code=1, truncated=False)
        stdout_bytes, stderr_bytes = execution.output
        combined_output_bytes = (stdout_bytes or b"") + (stderr_bytes or b"")
        truncated_text, is_truncated = decode_truncated_output(combined_output_bytes)
        return SandboxExecutionResult(
            output=truncated_text,
            exit_code=execution.exit_code if execution.exit_code is not None else 1,
            truncated=is_truncated,
        )

    def upload_files(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """把文件写入容器。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合。

        Raises:
            RuntimeError: 任一文件写入失败。
        """
        for file_write in file_writes:
            normalized_path = validated_sandbox_path(file_write.sandbox_path)
            archive_bytes = _single_file_archive(normalized_path, file_write.content)
            if not self._container.put_archive("/", archive_bytes):
                raise RuntimeError(f"沙箱文件写入未被确认: {normalized_path}")

    def replace_runtime_assets(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """完整替换容器内 Skill 运行资产根目录。

        先在暂存目录写齐全部文件,再删除旧目录并把暂存目录换名到位:任一文件写入
        失败时旧内容原样保留、暂存目录被清理,不会出现"跑着一半资产"的容器。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合;路径必须
                位于 :data:`SANDBOX_SKILL_RUNTIME_ROOT` 之下。

        Raises:
            RuntimeError: 路径越界、目录切换失败或任一文件写入失败。
        """
        runtime_root_path = validated_sandbox_path(SANDBOX_SKILL_RUNTIME_ROOT)
        staging_root_path = f"{runtime_root_path}.staging-{uuid4().hex}"
        staged_relative_paths = [
            validated_runtime_asset_relative_path(file_write.sandbox_path)
            for file_write in file_writes
        ]
        try:
            self._run_runtime_asset_command(f"rm -rf -- {shlex.quote(staging_root_path)}")
            # 空声明也要建出暂存目录:换名步骤依赖它存在,用来清空运行资产根目录。
            self._run_runtime_asset_command(f"mkdir -p -- {shlex.quote(staging_root_path)}")
            if staged_relative_paths:
                staged_directories = sorted(
                    {
                        str(PurePosixPath(staged_path).parent)
                        for staged_path in staged_relative_paths
                    }
                )
                self._run_runtime_asset_command(
                    "mkdir -p -- "
                    + " ".join(
                        shlex.quote(f"{staging_root_path}/{directory}")
                        for directory in staged_directories
                    )
                )
            for file_write, staged_relative_path in zip(
                file_writes, staged_relative_paths, strict=True
            ):
                archive_bytes = _single_file_archive(
                    f"{staging_root_path}/{staged_relative_path}", file_write.content
                )
                if not self._container.put_archive("/", archive_bytes):
                    raise RuntimeError(f"Skill 运行资产写入未被确认: {file_write.sandbox_path}")
            # 换名是单次 rename:旧目录整体消失、新目录整体就位,中间态不可见。
            self._run_runtime_asset_command(
                f"rm -rf -- {shlex.quote(runtime_root_path)}"
                f" && mv -- {shlex.quote(staging_root_path)} {shlex.quote(runtime_root_path)}"
            )
        except (OSError, RuntimeError, ValueError):
            self._discard_staging_directory(staging_root_path)
            raise

    def _run_runtime_asset_command(self, command: str) -> None:
        """以沙箱用户执行一条资产目录维护命令。

        Raises:
            RuntimeError: 命令退出码非 0。
        """
        execution = self._container.exec_run(
            ["/bin/sh", "-lc", command], user=_SANDBOX_USER, workdir="/workspace"
        )
        if execution.exit_code != 0:
            execution_output = (execution.output or b"").decode("utf-8", errors="replace")
            raise RuntimeError(
                "Skill 运行资产目录维护失败"
                f"(exit={execution.exit_code}): {execution_output.strip()!r}"
            )

    def _discard_staging_directory(self, staging_root_path: str) -> None:
        """清理暂存目录;失败不再抛错,避免掩盖原始异常。"""
        from docker.errors import DockerException

        try:
            self._container.exec_run(
                ["/bin/sh", "-lc", f"rm -rf -- {shlex.quote(staging_root_path)}"],
                user=_SANDBOX_USER,
                workdir="/workspace",
            )
        except DockerException:
            return

    def list_files(self, sandbox_directory: str) -> Sequence[str]:
        """列出目录下全部文件的绝对路径。

        Args:
            sandbox_directory (str): 沙箱内目录绝对路径。

        Returns:
            Sequence[str]: 文件绝对路径;目录不存在时为空。

        Raises:
            RuntimeError: 输出被截断,无法确认已枚举全部文件。
        """
        normalized_directory = validated_sandbox_path(sandbox_directory)
        return decode_file_listing(
            self.execute(
                build_file_listing_command(normalized_directory),
                timeout_seconds=_LISTING_TIMEOUT_SECONDS,
            )
        )

    def download_files(self, sandbox_paths: Sequence[str]) -> Sequence[SandboxFileRead]:
        """从容器读回文件。

        Args:
            sandbox_paths (Sequence[str]): 沙箱内文件绝对路径集合。

        Returns:
            Sequence[SandboxFileRead]: 与入参等长的读取结果。
        """
        file_reads: list[SandboxFileRead] = []
        for sandbox_path in sandbox_paths:
            try:
                normalized_path = validated_sandbox_path(sandbox_path)
                file_reads.append(
                    SandboxFileRead(
                        sandbox_path=normalized_path,
                        content=self._read_single_file(normalized_path),
                        error=None,
                    )
                )
            except (OSError, ValueError, RuntimeError, tarfile.TarError) as read_error:
                file_reads.append(
                    SandboxFileRead(sandbox_path=sandbox_path, content=None, error=str(read_error))
                )
        return file_reads

    def _read_single_file(self, normalized_path: str) -> bytes:
        """从容器归档中取出单个普通文件的内容。"""
        archive_chunks, _stat = self._container.get_archive(normalized_path)
        archive_buffer = io.BytesIO(b"".join(archive_chunks))
        with tarfile.open(fileobj=archive_buffer, mode="r:") as archive:
            regular_members = [member for member in archive.getmembers() if member.isfile()]
            if len(regular_members) != 1:
                raise ValueError("下载目标不是单个普通文件")
            extracted_file = archive.extractfile(regular_members[0])
            if extracted_file is None:
                raise ValueError("无法读取下载文件内容")
            return extracted_file.read()


class DockerSandboxProvider:
    """按会话创建并复用受限 Docker 容器。"""

    def __init__(
        self,
        *,
        image: str,
        command_timeout_seconds: int,
        egress_policy: SandboxEgressPolicy,
        memory_limit: str = "1g",
    ) -> None:
        """初始化 Docker 客户端与容器创建参数。

        Args:
            image (str): 沙箱镜像。
            command_timeout_seconds (int): 默认命令超时秒数。
            egress_policy (SandboxEgressPolicy): 出站网络策略。
            memory_limit (str): 容器内存上限。
        """
        self._image = image
        self._command_timeout_seconds = command_timeout_seconds
        self._egress_policy = egress_policy
        self._memory_limit = memory_limit
        self._sessions: dict[str, DockerSandboxSession] = {}
        self._lock = threading.RLock()
        self._client, self._unavailable_reason = _connect_docker_client()

    def is_available(self) -> bool:
        """返回 Docker daemon 当前是否可达。"""
        return self._client is not None

    def availability_detail(self) -> str | None:
        """返回不可用原因;可用时为 ``None``。"""
        return self._unavailable_reason

    def acquire(self, thread_id: str) -> DockerSandboxSession:
        """取得会话专属容器,不存在时创建。

        Args:
            thread_id (str): 会话标识。

        Returns:
            DockerSandboxSession: 该会话专属的容器环境。

        Raises:
            RuntimeError: Docker 不可用或容器无法创建。
        """
        if self._client is None:
            raise RuntimeError(f"Docker 沙箱不可用: {self._unavailable_reason}")
        with self._lock:
            cached_session = self._sessions.get(thread_id)
            if cached_session is not None and self._ensure_running(cached_session.container):
                return cached_session
            existing_container = self._find_container_by_label(thread_id)
            running_container = (
                existing_container
                if existing_container is not None and self._ensure_running(existing_container)
                else self._create_container(thread_id)
            )
            acquired_session = DockerSandboxSession(
                running_container,
                command_timeout_seconds=self._command_timeout_seconds,
            )
            self._sessions[thread_id] = acquired_session
            return acquired_session

    def release(self, thread_id: str) -> None:
        """停止容器释放运行资源,保留其文件系统。

        Args:
            thread_id (str): 会话标识。
        """
        from docker.errors import DockerException

        with self._lock:
            released_session = self._sessions.get(thread_id)
            if released_session is None:
                return
            try:
                released_session.container.reload()
                if released_session.container.status == "running":
                    released_session.container.stop(timeout=10)
            except DockerException:
                # 容器已被外部删除时无需处理:下次 acquire 会重建。
                self._sessions.pop(thread_id, None)

    def destroy(self, thread_id: str) -> None:
        """彻底删除会话容器及其文件系统。

        Args:
            thread_id (str): 会话标识。
        """
        from docker.errors import DockerException

        with self._lock:
            destroyed_session = self._sessions.pop(thread_id, None)
            target_container = (
                destroyed_session.container
                if destroyed_session is not None
                else self._find_container_by_label(thread_id)
            )
            if target_container is None:
                return
            try:
                target_container.remove(force=True)
            except DockerException:
                return

    def _find_container_by_label(self, thread_id: str) -> Any | None:
        """按会话标签找回容器;Docker 是该映射的唯一真源。"""
        from docker.errors import DockerException

        if self._client is None:
            return None
        try:
            matched_containers = self._client.containers.list(
                all=True,
                filters={
                    "label": [
                        f"{_RUNTIME_LABEL}=sandbox",
                        f"{_THREAD_LABEL}={_thread_label_value(thread_id)}",
                    ]
                },
            )
        except DockerException:
            return None
        return matched_containers[0] if matched_containers else None

    def _create_container(self, thread_id: str) -> Any:
        """按安全默认值创建会话容器并初始化工作区。

        Raises:
            RuntimeError: 工作区初始化失败。
        """
        from docker.errors import NotFound

        if self._client is None:
            raise RuntimeError("Docker 客户端不可用")
        try:
            self._client.images.get(self._image)
        except NotFound:
            self._client.images.pull(self._image)
        created_container = self._client.containers.run(
            self._image,
            ["sleep", "infinity"],
            detach=True,
            init=True,
            working_dir="/workspace",
            network_mode=self._egress_policy.container_network_mode(),
            environment=self._egress_policy.container_environment(),
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            mem_limit=self._memory_limit,
            nano_cpus=1_000_000_000,
            pids_limit=256,
            labels={
                _RUNTIME_LABEL: "sandbox",
                _THREAD_LABEL: _thread_label_value(thread_id),
            },
        )
        attachable_network = self._egress_policy.attachable_network()
        if attachable_network is not None:
            self._client.networks.get(attachable_network).connect(created_container)
        # 只 mkdir 不 chown:cap_drop=ALL 已弃掉 CAP_CHOWN,即使以 root exec 也改不了
        # 属主。目录归属必须在镜像构建期完成(见 deploy/sandbox/Dockerfile.sandbox),
        # 这里以沙箱用户身份补齐缺失目录并验证输出目录确实可写。
        workspace_setup = created_container.exec_run(
            [
                "/bin/sh",
                "-lc",
                "mkdir -p "
                + " ".join(_WORKSPACE_DIRECTORIES)
                + " && test -w /workspace/outputs && test -w /large_tool_results",
            ],
            user=_SANDBOX_USER,
        )
        if workspace_setup.exit_code != 0:
            setup_output = (workspace_setup.output or b"").decode("utf-8", errors="replace")
            created_container.remove(force=True)
            raise RuntimeError(
                "沙箱工作区初始化失败：镜像需预先创建 /workspace/inputs、/workspace/outputs、"
                "/assets、/large_tool_results 与 /conversation_history 并归属 uid "
                f"{_SANDBOX_UID}。容器输出：{setup_output.strip()!r}"
            )
        return created_container

    @staticmethod
    def _ensure_running(container: Any) -> bool:
        """确保容器处于运行态;已被外部删除时返回 False。"""
        from docker.errors import DockerException

        try:
            container.reload()
            if container.status != "running":
                container.start()
            return True
        except DockerException:
            return False


def _connect_docker_client() -> tuple[Any | None, str | None]:
    """尝试连接 Docker daemon。

    daemon 不可达不抛异常中断应用启动:沙箱 Runtime 会因此不注册,绑定它的 Agent
    在目录中即显示为不可运行,而不是让用户提交后才失败。

    Returns:
        tuple[Any | None, str | None]: 客户端与不可用原因。
    """
    try:
        import docker
        from docker.errors import DockerException
    except ImportError:
        return None, "未安装 docker 依赖"
    try:
        docker_client = docker.from_env()
        docker_client.ping()
    except (DockerException, OSError) as connection_error:
        return None, f"无法连接 Docker daemon: {connection_error}"
    return docker_client, None


def _single_file_archive(sandbox_path: str, content: bytes) -> bytes:
    """把单个文件打包成 put_archive 可用的 tar 字节。"""
    archive_buffer = io.BytesIO()
    with tarfile.open(fileobj=archive_buffer, mode="w") as archive:
        file_info = tarfile.TarInfo(name=sandbox_path.lstrip("/"))
        file_info.size = len(content)
        file_info.mode = 0o600
        file_info.uid = _SANDBOX_UID
        file_info.gid = _SANDBOX_UID
        archive.addfile(file_info, io.BytesIO(content))
    return archive_buffer.getvalue()


def _thread_label_value(thread_id: str) -> str:
    """把会话标识哈希成容器标签值,避免原始标识出现在容器元数据里。"""
    return hashlib.sha256(thread_id.encode("utf-8")).hexdigest()[:32]


__all__ = ["DockerSandboxProvider", "DockerSandboxSession"]
