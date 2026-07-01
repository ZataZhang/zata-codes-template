"""Agent 执行编排器。"""

from __future__ import annotations

from typing import Sequence
from uuid import uuid4

from backend.core.shared.interfaces.llm_client import LLMClient, LLMMessage
from backend.core.shared.interfaces.tool_registry import ToolRegistry
from backend.core.shared.models.agent import Agent
from backend.core.shared.models.session import ChatMessage, ToolCall


class AgentRunner:
    """负责根据 Agent 配置生成 assistant 回复。"""

    def __init__(
        self,
        agent: Agent,
        tool_registry: ToolRegistry,
        llm_client: LLMClient,
    ) -> None:
        """使用 Agent 配置与依赖初始化运行器。"""
        self._agent = agent
        self._tool_registry = tool_registry
        self._llm_client = llm_client

    def run(self, history: Sequence[ChatMessage], user_message: str) -> ChatMessage:
        """执行一轮对话，返回 assistant 消息。"""
        llm_messages = [LLMMessage(role=msg.role, content=msg.content) for msg in history]
        llm_messages.append(LLMMessage(role="user", content=user_message))

        response = self._llm_client.chat(
            model=self._agent.model,
            system_prompt=self._agent.system_prompt,
            messages=llm_messages,
        )

        tool_calls: list[ToolCall] = []
        content = response.content

        if self._agent.tool_ids:
            simulated_tool_name = self._select_tool_for_demo()
            if simulated_tool_name:
                tool_call = ToolCall(
                    id=str(uuid4()),
                    tool_name=simulated_tool_name,
                    arguments={"query": user_message},
                    status="running",
                )
                try:
                    result = self._tool_registry.execute(simulated_tool_name, tool_call.arguments)
                    tool_call.result = result
                    tool_call.status = "success"
                except Exception as exc:  # noqa: BLE001
                    tool_call.result = {"error": str(exc)}
                    tool_call.status = "error"
                tool_calls.append(tool_call)
                content = f"{response.content}\n\n（已调用工具：{simulated_tool_name}）"

        return ChatMessage(
            id=str(uuid4()),
            session_id="",
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )

    def _select_tool_for_demo(self) -> str | None:
        """MVP 演示：从 Agent 启用的工具中选择一个执行。"""
        for tool_id in self._agent.tool_ids:
            if tool_id in {"web_search", "code_runner"}:
                return tool_id
        return None
