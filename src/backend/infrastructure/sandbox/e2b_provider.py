"""基于阿里云 FC 云沙箱的沙箱执行环境实现。

这是继本地目录与 Docker 之后的第三个 ``SandboxProvider`` 实现,端口与语义完全对齐
——三者对"路径是否合法""输出如何截断""资产如何整体替换"给出同一答案,差异只落在
"命令与文件如何映射到远端"这一层。

会话到云沙箱的映射只存在于后端进程内,不建数据库表:与 Docker 档同一取舍,云沙箱
本身已经是这个状态的真源,再存一份副本只会引入第二真源。代价是后端进程重启后无法
再定位旧沙箱,它们会随存活窗口自然过期,期间可由:meth:`E2bSandboxProvider.
active_sandbox_ids` 观测并按运维动作回收。

本服务不支持暂停,因此 ``release`` 的语义是**续期保活**而不是停机:会话文件系统
保留到存活窗口耗尽,期间再次 acquire 会复用同一个沙箱。

**沙箱身份校验**:实测发现沙箱被销毁/回收后,envd 网关并不会让后续请求失败,而是
以 HTTP 200 返回**另一个干净环境**的执行结果(退出码 0、命令输出正常、但文件系统
是空的),``GET /health`` 也照样回 200。若不加区分,产物导出会在空环境上列出零个
文件,调用方就会以"无产物但成功"收尾——这是必须消除的假成功。因此每次 acquire 都
在沙箱内写入一枚随机身份标记,并让每条命令先自校验该标记:标记缺失即判定"当前通道
指向的不是本会话的沙箱",抛 :class:`E2bSandboxNotFoundError`,由调用方按"沙箱已丢失"
处理,而不是当成一次成功运行。

身份校验只加在**命令**路径上:文件 REST 通道的读写不带这层校验。这条缺口不会通向
假成功——产物导出先经 :meth:`E2bSandboxSession.list_files`(受校验保护)枚举,运行资产
替换的收尾维护命令也在命令路径上;但"输入被写进另一个环境后即被丢弃"是可能的浪费,
排障时值得知道。
"""

from __future__ import annotations

import shlex
import threading
from typing import Sequence
from uuid import uuid4

import httpx

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxExecutionResult,
    SandboxFileRead,
    SandboxFileWrite,
)
from backend.infrastructure.sandbox.e2b_control_plane import E2bControlPlane
from backend.infrastructure.sandbox.e2b_execution_channel import E2bExecutionChannel
from backend.infrastructure.sandbox.e2b_protocol import (
    E2bEndpointConfig,
    E2bProtocolError,
    E2bSandboxHandle,
    E2bSandboxNotFoundError,
)
from backend.infrastructure.sandbox.sandbox_rules import (
    MAX_SANDBOX_OUTPUT_BYTES,
    build_file_listing_command,
    decode_file_listing,
    decode_truncated_output,
    validated_runtime_asset_relative_path,
    validated_sandbox_path,
)

_WORKSPACE_ROOT = "/workspace"
_WORKSPACE_OUTPUT_ROOT = "/workspace/outputs"
_WORKSPACE_DIRECTORIES = ("/workspace/inputs", _WORKSPACE_OUTPUT_ROOT)
_LISTING_TIMEOUT_SECONDS = 30
_MAINTENANCE_TIMEOUT_SECONDS = 60
_IDENTITY_PROBE_TIMEOUT_SECONDS = 15
_DEFAULT_HTTP_TIMEOUT_SECONDS = 60.0
# 身份标记放在 /tmp 下的随机路径:既不会出现在工作区里被产物导出扫到,也几乎不可能
# 被 agent 的常规操作误删;真被清掉时按"沙箱已被回收"处理是安全方向。
_IDENTITY_PATH_TEMPLATE = "/tmp/.zata-sandbox-identity-{identity_suffix}"
_IDENTITY_LOST_EXIT_CODE = 97
_IDENTITY_LOST_MARKER = "__ZATA_SANDBOX_IDENTITY_LOST__"


class E2bSandboxSession:
    """单个会话专属的云沙箱执行环境。"""

    def __init__(
        self,
        *,
        handle: E2bSandboxHandle,
        channel: E2bExecutionChannel,
        command_timeout_seconds: int,
    ) -> None:
        """绑定沙箱句柄与执行通道。

        Args:
            handle (E2bSandboxHandle): 云沙箱访问句柄。
            channel (E2bExecutionChannel): 该沙箱的执行通道客户端。
            command_timeout_seconds (int): 未显式指定时的命令超时秒数。
        """
        self._handle = handle
        self._channel = channel
        self._command_timeout_seconds = command_timeout_seconds
        identity_suffix = uuid4().hex
        self._identity_path = _IDENTITY_PATH_TEMPLATE.format(identity_suffix=identity_suffix)
        self._identity_nonce = identity_suffix

    @property
    def session_key(self) -> str:
        """返回云沙箱标识;沙箱被重建后该值改变,装配缓存随之失效。"""
        return self._handle.sandbox_id

    @property
    def sandbox_id(self) -> str:
        """返回云沙箱标识,供 provider 做生命周期管理。"""
        return self._handle.sandbox_id

    def is_alive(self) -> bool:
        """返回命令通道是否仍指向本会话的沙箱(不做控制面查询)。

        用一次被身份校验保护的空命令探测,而不是 ``GET /health``:实测后者在沙箱
        已被销毁后仍然返回 200,是个会骗人的存活信号。控制面侧的"沙箱还在不在"由
        :meth:`E2bSandboxProvider._is_session_reusable` 另外查询。
        """
        try:
            identity_probe = self.execute("true", timeout_seconds=_IDENTITY_PROBE_TIMEOUT_SECONDS)
        except E2bProtocolError:
            return False
        return identity_probe.exit_code == 0

    def execute(self, command: str, *, timeout_seconds: int) -> SandboxExecutionResult:
        """在云沙箱内执行命令。

        命令前会插入本会话的身份自校验:当前通道指向的若不是本会话的沙箱(被回收后
        网关可能返回别的环境),命令立即以固定退出码收场并由本方法转成异常,避免上层
        把"另一个空环境里的成功"当成真实结果。

        Args:
            command (str): 待执行的 shell 命令。
            timeout_seconds (int): 超时秒数;非正数表示使用默认超时。

        Returns:
            SandboxExecutionResult: 输出、退出码与截断标记。

        Raises:
            E2bSandboxNotFoundError: 身份校验失败,当前通道指向的不是本会话的沙箱。
            E2bProtocolError: 执行通道不可用或响应不可信;调用方必须把 Run 判为失败,
                不能把"没拿到结果"当成命令失败。
        """
        effective_timeout_seconds = (
            timeout_seconds if timeout_seconds > 0 else self._command_timeout_seconds
        )
        execution_outcome = self._channel.run_command(
            build_identity_guarded_command(
                identity_path=self._identity_path,
                identity_nonce=self._identity_nonce,
                command=command,
            ),
            timeout_seconds=effective_timeout_seconds,
            cwd=_WORKSPACE_ROOT,
            max_output_bytes=MAX_SANDBOX_OUTPUT_BYTES,
        )
        combined_output_bytes = execution_outcome.stdout_bytes + execution_outcome.stderr_bytes
        output_text, is_capped_by_combined_limit = decode_truncated_output(combined_output_bytes)
        if (
            execution_outcome.exit_code == _IDENTITY_LOST_EXIT_CODE
            and _IDENTITY_LOST_MARKER in output_text
        ):
            raise E2bSandboxNotFoundError(
                "云沙箱身份校验失败：执行通道指向的已不是本会话的沙箱"
                "(沙箱被回收后网关会返回另一个干净环境，而不是报错)"
            )
        return SandboxExecutionResult(
            output=output_text,
            exit_code=execution_outcome.exit_code,
            truncated=execution_outcome.truncated or is_capped_by_combined_limit,
        )

    def upload_files(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """把文件写入云沙箱。

        Args:
            file_writes (Sequence[SandboxFileWrite]): 待写入的文件集合。

        Raises:
            RuntimeError: 任一文件写入失败;部分成功不能被当作成功。
        """
        for file_write in file_writes:
            normalized_path = validated_sandbox_path(file_write.sandbox_path)
            self._channel.write_file(normalized_path, file_write.content)

    def replace_runtime_assets(self, file_writes: Sequence[SandboxFileWrite]) -> None:
        """完整替换云沙箱内 Skill 运行资产根目录。

        先在暂存目录写齐全部文件,再删除旧目录并把暂存目录换名到位:任一文件写入
        失败时旧内容原样保留、暂存目录被清理,不会出现"跑着一半资产"的沙箱。云沙箱
        不支持快照或事务,这个先写后换名的顺序是这里唯一可用的原子手段。

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
            self._run_maintenance_command(f"rm -rf -- {shlex.quote(staging_root_path)}")
            # 空声明也要建出暂存目录:换名步骤依赖它存在,用来清空运行资产根目录。
            self._run_maintenance_command(f"mkdir -p -- {shlex.quote(staging_root_path)}")
            for file_write, staged_relative_path in zip(
                file_writes, staged_relative_paths, strict=True
            ):
                self._channel.write_file(
                    f"{staging_root_path}/{staged_relative_path}", file_write.content
                )
            self._run_maintenance_command(
                f"rm -rf -- {shlex.quote(runtime_root_path)}"
                f" && mv -- {shlex.quote(staging_root_path)} {shlex.quote(runtime_root_path)}"
            )
        except (OSError, RuntimeError, ValueError):
            self._discard_staging_directory(staging_root_path)
            raise

    def list_files(self, sandbox_directory: str) -> Sequence[str]:
        """列出目录下全部文件的沙箱绝对路径。

        Args:
            sandbox_directory (str): 沙箱内目录绝对路径。

        Returns:
            Sequence[str]: 文件绝对路径;目录不存在时为空。

        Raises:
            RuntimeError: 输出被截断,无法确认已枚举全部文件。
            E2bProtocolError: 执行通道不可用;此时"空列表"会伪装成"没有产物"。
        """
        normalized_directory = validated_sandbox_path(sandbox_directory)
        return decode_file_listing(
            self.execute(
                build_file_listing_command(normalized_directory),
                timeout_seconds=_LISTING_TIMEOUT_SECONDS,
            )
        )

    def download_files(self, sandbox_paths: Sequence[str]) -> Sequence[SandboxFileRead]:
        """从云沙箱读回文件。

        Args:
            sandbox_paths (Sequence[str]): 沙箱内文件绝对路径集合。

        Returns:
            Sequence[SandboxFileRead]: 与入参等长的读取结果,逐项标注成功或失败。
        """
        file_reads: list[SandboxFileRead] = []
        for sandbox_path in sandbox_paths:
            try:
                normalized_path = validated_sandbox_path(sandbox_path)
                file_reads.append(
                    SandboxFileRead(
                        sandbox_path=normalized_path,
                        content=self._channel.read_file(normalized_path),
                        error=None,
                    )
                )
            except (OSError, RuntimeError, ValueError) as read_error:
                file_reads.append(
                    SandboxFileRead(sandbox_path=sandbox_path, content=None, error=str(read_error))
                )
        return file_reads

    def initialize_workspace(self) -> None:
        """绑定沙箱身份并确认执行模板已提供符合约定的可写工作目录。

        云沙箱默认镜像里没有 ``/workspace``,目录与属主必须由平台自建模板在构建期
        确定。确认失败时以明确异常收场而不是静默继续:缺少输出目录时 agent 写的每个
        交付文件都会丢失,继续跑只会产出"成功的空结果"。

        Raises:
            RuntimeError: 身份标记写不进去、工作目录不可创建或不可写,或执行通道直接
                以协议错误拒绝在该工作目录下启动命令(实测表现为 HTTP 400
                ``cwd '/workspace' does not exist``)——这些现象都指向"模板不合格"这
                同一个可诊断结论。
        """
        try:
            self._channel.write_file(self._identity_path, self._identity_nonce.encode("utf-8"))
        except E2bProtocolError as identity_write_error:
            raise RuntimeError(
                f"云沙箱身份标记写入失败({self._identity_path})：{identity_write_error}"
            ) from identity_write_error
        try:
            workspace_setup = self.execute(
                "mkdir -p "
                + " ".join(_WORKSPACE_DIRECTORIES)
                + f" && test -w {_WORKSPACE_ROOT} && test -w {_WORKSPACE_OUTPUT_ROOT}",
                timeout_seconds=_MAINTENANCE_TIMEOUT_SECONDS,
            )
        except E2bProtocolError as workspace_probe_error:
            raise RuntimeError(
                "云沙箱工作区不可用：执行模板需预建 /workspace/inputs、/workspace/outputs "
                f"并归属沙箱用户。执行通道返回：{workspace_probe_error}"
            ) from workspace_probe_error
        if workspace_setup.exit_code != 0:
            raise RuntimeError(
                "云沙箱工作区初始化失败：执行模板需预建 /workspace/inputs、"
                "/workspace/outputs 并归属沙箱用户。执行通道输出："
                f"{workspace_setup.output.strip()!r}"
            )

    def _run_maintenance_command(self, command: str) -> None:
        """执行一条资产目录维护命令。

        Raises:
            RuntimeError: 命令退出码非 0。
        """
        maintenance_result = self.execute(command, timeout_seconds=_MAINTENANCE_TIMEOUT_SECONDS)
        if maintenance_result.exit_code != 0:
            raise RuntimeError(
                "Skill 运行资产目录维护失败"
                f"(exit={maintenance_result.exit_code}): {maintenance_result.output.strip()!r}"
            )

    def _discard_staging_directory(self, staging_root_path: str) -> None:
        """清理暂存目录;失败不再抛错,避免掩盖原始异常。"""
        try:
            self.execute(
                f"rm -rf -- {shlex.quote(staging_root_path)}",
                timeout_seconds=_MAINTENANCE_TIMEOUT_SECONDS,
            )
        except E2bProtocolError:
            return


class E2bSandboxProvider:
    """按会话创建并复用阿里云 FC 云沙箱。"""

    def __init__(
        self,
        *,
        config: E2bEndpointConfig,
        command_timeout_seconds: int,
        http_client: httpx.Client | None = None,
    ) -> None:
        """初始化控制面、执行通道参数并探测后端可用性。

        探测失败不抛异常中断应用启动:沙箱 Runtime 会因此不注册,绑定它的 Agent 在
        目录中即显示为不可运行,而不是让用户提交后才失败。

        Args:
            config (E2bEndpointConfig): 云沙箱端点与默认参数。
            command_timeout_seconds (int): 未显式指定时的命令超时秒数。
            http_client (httpx.Client | None): 复用的 HTTP 客户端;``None`` 时自建。
        """
        self._config = config
        self._command_timeout_seconds = command_timeout_seconds
        self._http_client = http_client or httpx.Client(timeout=_DEFAULT_HTTP_TIMEOUT_SECONDS)
        self._control_plane = E2bControlPlane(config=config, http_client=self._http_client)
        self._sessions: dict[str, E2bSandboxSession] = {}
        self._lock = threading.RLock()
        self._unavailable_reason = self._probe_backend()

    def is_available(self) -> bool:
        """返回云沙箱控制面当前是否可达且凭据有效。"""
        return self._unavailable_reason is None

    def availability_detail(self) -> str | None:
        """返回不可用原因;可用时为 ``None``。"""
        return self._unavailable_reason

    def acquire(self, thread_id: str) -> E2bSandboxSession:
        """取得会话专属云沙箱,不存在或已过期时创建。

        Args:
            thread_id (str): 会话标识。

        Returns:
            E2bSandboxSession: 该会话专属的云沙箱环境。

        Raises:
            RuntimeError: 后端不可用、沙箱无法创建,或执行模板缺少约定工作目录。
        """
        if self._unavailable_reason is not None:
            raise RuntimeError(f"云沙箱不可用: {self._unavailable_reason}")
        with self._lock:
            cached_session = self._sessions.get(thread_id)
            if cached_session is not None and self._is_session_reusable(cached_session):
                self._renew_sandbox(cached_session.sandbox_id)
                return cached_session
            acquired_session = self._create_session()
            self._sessions[thread_id] = acquired_session
            return acquired_session

    def release(self, thread_id: str) -> None:
        """释放会话环境占用的运行资源,保留其文件系统。

        本服务不支持暂停,因此这里续期保活:文件系统保留到存活窗口耗尽。沙箱已被
        回收时丢弃本地映射,下次 acquire 会重建。

        Args:
            thread_id (str): 会话标识。
        """
        with self._lock:
            released_session = self._sessions.get(thread_id)
            if released_session is None:
                return
            try:
                self._renew_sandbox(released_session.sandbox_id)
            except E2bProtocolError:
                self._sessions.pop(thread_id, None)

    def destroy(self, thread_id: str) -> None:
        """彻底销毁会话沙箱及其文件系统。

        只能销毁本进程创建过的会话:会话到沙箱的映射在进程内,后端重启后旧沙箱由
        存活窗口回收,期间可由 :meth:`active_sandbox_ids` 观测。

        Args:
            thread_id (str): 会话标识。
        """
        with self._lock:
            destroyed_session = self._sessions.pop(thread_id, None)
            if destroyed_session is None:
                return
            try:
                self._control_plane.destroy_sandbox(destroyed_session.sandbox_id)
            except E2bProtocolError:
                return

    def active_sandbox_ids(self) -> list[str]:
        """列出云端仍存在的沙箱标识,供运维观测与回收孤儿沙箱。

        Returns:
            list[str]: 云侧沙箱标识列表。

        Raises:
            E2bProtocolError: 控制面不可用。
        """
        return self._control_plane.list_sandbox_ids()

    def _probe_backend(self) -> str | None:
        """探测控制面可用性,返回不可用原因或 ``None``。"""
        try:
            self._control_plane.probe()
        except E2bProtocolError as probe_error:
            return f"云沙箱控制面不可用: {probe_error}"
        return None

    def _create_session(self) -> E2bSandboxSession:
        """创建一个新沙箱并初始化它的工作区与身份标记。

        Raises:
            RuntimeError: 工作区或身份标记不符合约定;此时刚创建的沙箱会被销毁,
                避免留下一个不可用却仍占着存活窗口的孤儿。
        """
        sandbox_handle = self._control_plane.create_sandbox()
        created_session = E2bSandboxSession(
            handle=sandbox_handle,
            channel=E2bExecutionChannel(
                handle=sandbox_handle,
                username=self._config.username,
                http_client=self._http_client,
            ),
            command_timeout_seconds=self._command_timeout_seconds,
        )
        try:
            created_session.initialize_workspace()
        except RuntimeError:
            self._discard_sandbox(sandbox_handle.sandbox_id)
            raise
        return created_session

    def _is_session_reusable(self, cached_session: E2bSandboxSession) -> bool:
        """判断缓存的会话是否还能复用。

        两个判据回答两个不同问题,都要问:

        * 控制面查询(官方 ``Sandbox.getInfo``)回答"这个沙箱还在不在"——销毁后立刻
          404,是权威判据;
        * 命令通道的身份自校验回答"我的命令还落在这个环境里吗"——实测沙箱销毁后
          envd 仍会以 HTTP 200 返回另一个干净环境的结果,只有它能挡住这种情况。

        探测本身失败按"不可复用"处理:重建沙箱最多丢掉会话文件系统,而继续用一台
        可疑环境会污染 Run 结果。

        Args:
            cached_session (E2bSandboxSession): 缓存中的会话。

        Returns:
            bool: 可复用为真。
        """
        try:
            if not self._control_plane.sandbox_exists(cached_session.sandbox_id):
                return False
        except E2bProtocolError:
            return False
        return cached_session.is_alive()

    def _renew_sandbox(self, sandbox_id: str) -> None:
        """续期沙箱存活窗口。"""
        self._control_plane.renew_sandbox(sandbox_id, timeout_seconds=self._config.timeout_seconds)

    def _discard_sandbox(self, sandbox_id: str) -> None:
        """尽力销毁沙箱;失败不再抛错,避免掩盖原始异常。"""
        try:
            self._control_plane.destroy_sandbox(sandbox_id)
        except E2bProtocolError:
            return


def build_identity_guarded_command(*, identity_path: str, identity_nonce: str, command: str) -> str:
    """把用户命令前置一段沙箱身份自校验。

    校验必须是**独立语句**而不能把命令包进 ``{ ... ; }``:包裹会在命令尾部追加
    ``; }``,而那段文本会落进未加引号的 ``#`` 注释作用域,或把 heredoc 的终止行变成
    ``EOF ; }``,使合法命令以语法错误收场——同一字符串在 Docker 档却能正常执行,两个
    后端就会对同一输入给出不同结果。因此这里只做"前置 + 换行",命令体一个字符都不动。

    Args:
        identity_path (str): 身份标记文件在沙箱内的路径。
        identity_nonce (str): 本会话身份标记的期望内容。
        command (str): 原始用户命令,原样出现在最后。

    Returns:
        str: 校验通过后才执行原命令的 shell 脚本。
    """
    identity_guard = (
        f'if [ "$(cat {shlex.quote(identity_path)} 2>/dev/null)"'
        f" != {shlex.quote(identity_nonce)} ];"
        f" then echo {_IDENTITY_LOST_MARKER}; exit {_IDENTITY_LOST_EXIT_CODE}; fi"
    )
    return f"{identity_guard}\n{command}"


__all__ = ["E2bSandboxProvider", "E2bSandboxSession", "build_identity_guarded_command"]
