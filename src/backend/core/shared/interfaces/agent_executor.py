"""Agent 模型执行能力与 A2A 调用的跨层端口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable, Literal, Protocol, Sequence

from backend.core.shared.interfaces.agent_types import A2APeer


@dataclass(frozen=True)
class A2AResponse:
    """远端 A2A Task 的可追溯结果。"""

    task_id: str
    content: str


@dataclass(frozen=True)
class AgentExecutionResult:
    """模型最终回复。"""

    content: str
    model_name: str
    content_streamed: bool = False


#: 模型流式返回文本片段时的回调；调用方负责把片段写入唯一 Run/Event 事实源。
DeltaCallback = Callable[[str], Awaitable[None]]
ExternalCallPhase = Literal["started", "completed", "failed"]


@dataclass(frozen=True)
class AgentExternalCallEvent:
    """受控 A2A 调用的单个低敏生命周期事件。"""

    phase: ExternalCallPhase
    tool_call_id: str
    peer_id: str
    input_length: int
    remote_task_id: str | None = None
    result_checksum: str | None = None
    result_length: int | None = None
    error_code: str | None = None


ExternalCallCallback = Callable[[AgentExternalCallEvent], None]


@dataclass(frozen=True)
class AgentExecutionCallbacks:
    """Run 用例为一次执行提供的持久化回调。"""

    on_delta: DeltaCallback | None = None
    on_external_call: ExternalCallCallback | None = None


class AgentExecutor(Protocol):
    """执行已冻结的 Agent 快照；不接受命令、脚本或任意工具定义。"""

    @property
    def is_available(self) -> bool:
        """返回主模型三件套是否齐全。"""
        ...

    @property
    def unavailable_reason(self) -> str | None:
        """返回安全、稳定的不可用原因标识。"""
        ...

    @property
    def default_model_name(self) -> str | None:
        """返回配置的默认模型名称（如有）。"""
        ...

    async def execute(
        self,
        *,
        snapshot: dict[str, object],
        message: str,
        peers: Sequence[A2APeer],
        callbacks: AgentExecutionCallbacks | None = None,
    ) -> AgentExecutionResult:
        """调用已配置模型及允许的 A2A 对端。

        Args:
            snapshot (dict[str, object]): Run 创建时冻结的 Agent 配置。
            message (str): 当前用户消息。
            peers (Sequence[A2APeer]): 当前组织已批准的 A2A 对端。
            callbacks (AgentExecutionCallbacks | None): 流式文本和受控对端调用事件的
                持久化回调；为空时执行器可以一次性返回完整回复。
        """
        ...


class A2AClient(Protocol):
    """通过官方 A2A HTTP+JSON/REST 绑定调用受控对端。"""

    async def send_message(
        self, *, organization_id: str, peer_id: str, message: str, idempotency_key: str
    ) -> A2AResponse:
        """向指定已批准对端发送幂等消息并返回远端 Task ID 与文本结果。"""
        ...


__all__ = [
    "A2AClient",
    "A2AResponse",
    "AgentExecutionCallbacks",
    "AgentExecutionResult",
    "AgentExecutor",
    "AgentExternalCallEvent",
    "DeltaCallback",
    "ExternalCallCallback",
]
