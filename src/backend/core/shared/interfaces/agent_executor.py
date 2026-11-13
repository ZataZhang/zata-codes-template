"""Agent 模型执行能力与 A2A 调用的跨层端口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from backend.core.shared.interfaces.agent_types import A2APeer


@dataclass(frozen=True)
class A2AResponse:
    """远端 A2A Task 的可追溯结果。"""

    task_id: str
    content: str


@dataclass(frozen=True)
class AgentExternalCall:
    """模型请求期间完成的一次受控 A2A 调用摘要。"""

    peer_id: str
    peer_name: str
    remote_task_id: str
    input_length: int
    result_checksum: str
    result_length: int


@dataclass(frozen=True)
class AgentExecutionResult:
    """模型最终回复和低敏执行元数据。"""

    content: str
    model_name: str
    external_calls: tuple[AgentExternalCall, ...] = ()


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
    ) -> AgentExecutionResult:
        """调用已配置模型及允许的 A2A 对端。"""
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
    "AgentExecutionResult",
    "AgentExecutor",
    "AgentExternalCall",
]
