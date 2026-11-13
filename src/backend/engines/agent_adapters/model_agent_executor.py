"""OpenAI 协议模型与已批准 A2A 对端的 Agent 执行适配器。"""

from __future__ import annotations

import hashlib
import json
from typing import Sequence

import httpx

from backend.core.shared.interfaces.agent_executor import (
    A2AClient,
    AgentExecutionResult,
    AgentExecutor,
    AgentExternalCall,
)
from backend.core.shared.interfaces.agent_types import A2APeer
from backend.infrastructure.config.settings import (
    PrimaryModelConfigError,
    PrimaryModelSettings,
    load_primary_model_settings,
)


class OpenAICompatibleAgentExecutor(AgentExecutor):
    """适配配置的主模型端点，仅暴露受控 A2A 函数。"""

    def __init__(self, a2a_client: A2AClient) -> None:
        """初始化模型与 A2A 适配。

        Args:
            a2a_client (A2AClient): 限定组织和已批准对端的 A2A 客户端。
        """
        self._a2a_client = a2a_client
        self._model_settings: PrimaryModelSettings | None = None
        self._configuration_error: str | None = None
        try:
            self._model_settings = load_primary_model_settings()
        except PrimaryModelConfigError:
            self._configuration_error = "model_configuration_incomplete"

    @property
    def is_available(self) -> bool:
        """返回完整模型三件套是否可用。"""
        return self._model_settings is not None

    @property
    def unavailable_reason(self) -> str | None:
        """返回不泄露环境值的模型不可用原因。"""
        if self._model_settings is not None:
            return None
        return self._configuration_error or "model_not_configured"

    @property
    def default_model_name(self) -> str | None:
        """返回默认模型名。"""
        return self._model_settings.model_name if self._model_settings else None

    async def execute(
        self,
        *,
        snapshot: dict[str, object],
        message: str,
        peers: Sequence[A2APeer],
    ) -> AgentExecutionResult:
        """调用默认 OpenAI-compatible 端点并执行模型选择的已批准对端。

        Args:
            snapshot (dict[str, object]): Run 创建时冻结的 Agent 配置。
            message (str): 当前用户消息。
            peers (Sequence[A2APeer]): 当前组织已批准的 A2A 对端。

        Returns:
            AgentExecutionResult: 最终回复和低敏调用摘要。

        Raises:
            RuntimeError: 模型未配置、响应无效或对端调用失败时抛出。
        """
        settings = self._model_settings
        if settings is None:
            raise RuntimeError(self.unavailable_reason or "model_not_configured")
        organization_id = str(snapshot["organization_id"])
        model_name = str(snapshot.get("model_name") or settings.model_name)
        system_prompt = self._build_system_prompt(snapshot)
        message_history: list[dict[str, object]] = [
            {"role": "system", "content": system_prompt},
        ]
        prior_messages = snapshot.get("conversation_history")
        if isinstance(prior_messages, list):
            message_history.extend(
                prior_message
                for prior_message in prior_messages
                if isinstance(prior_message, dict)
                and prior_message.get("role") in {"user", "assistant"}
                and isinstance(prior_message.get("content"), str)
            )
        message_history.append({"role": "user", "content": message})
        tool_definitions = self._build_tool_definitions(peers)
        completion_response = await self._create_completion(
            settings=settings,
            model_name=model_name,
            messages=message_history,
            tools=tool_definitions,
        )
        assistant_message = self._read_assistant_message(completion_response)
        external_calls: list[AgentExternalCall] = []
        tool_calls = assistant_message.get("tool_calls", [])
        if tool_calls:
            if not isinstance(tool_calls, list):
                raise RuntimeError("model_tool_response_invalid")
            message_history.append(assistant_message)
            peer_by_id = {peer.id: peer for peer in peers}
            for tool_call_index, tool_call in enumerate(tool_calls[:2]):
                function_document = (
                    tool_call.get("function") if isinstance(tool_call, dict) else None
                )
                if (
                    not isinstance(function_document, dict)
                    or function_document.get("name") != "call_a2a_peer"
                ):
                    raise RuntimeError("model_requested_unapproved_tool")
                try:
                    tool_arguments = json.loads(str(function_document.get("arguments", "")))
                except json.JSONDecodeError as decode_error:
                    raise RuntimeError("model_tool_arguments_invalid") from decode_error
                if not isinstance(tool_arguments, dict):
                    raise RuntimeError("model_tool_arguments_invalid")
                peer_id = str(tool_arguments.get("peer_id", ""))
                peer = peer_by_id.get(peer_id)
                peer_message = str(tool_arguments.get("message", "")).strip()
                if peer is None or not peer_message or len(peer_message) > 8_000:
                    raise RuntimeError("model_requested_unapproved_peer")
                peer_response = await self._a2a_client.send_message(
                    organization_id=organization_id,
                    peer_id=peer.id,
                    message=peer_message,
                    idempotency_key=(
                        f"{snapshot.get('run_id', 'run')}:a2a:{tool_call_index}"
                    ),
                )
                external_calls.append(
                    AgentExternalCall(
                        peer_id=peer.id,
                        peer_name=peer.name,
                        input_length=len(peer_message),
                        remote_task_id=peer_response.task_id,
                        result_checksum=hashlib.sha256(
                            peer_response.content.encode("utf-8")
                        ).hexdigest(),
                        result_length=len(peer_response.content),
                    )
                )
                message_history.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_call.get("id", "")),
                        "content": peer_response.content,
                    }
                )
            completion_response = await self._create_completion(
                settings=settings,
                model_name=model_name,
                messages=message_history,
                tools=None,
            )
            assistant_message = self._read_assistant_message(completion_response)
        final_content = assistant_message.get("content")
        if not isinstance(final_content, str):
            raise RuntimeError("model_response_content_missing")
        return AgentExecutionResult(
            content=final_content,
            model_name=model_name,
            external_calls=tuple(external_calls),
        )

    @staticmethod
    def _build_system_prompt(snapshot: dict[str, object]) -> str:
        """将冻结的 Agent 指令、Skill 正文与执行边界组合为系统提示。"""
        prompt_sections = [str(snapshot.get("instructions", ""))]
        skill_body = snapshot.get("skill_body")
        if isinstance(skill_body, str) and skill_body.strip():
            prompt_sections.append(f"Skill reference:\n{skill_body}")
        prompt_sections.append(
            "Only use the call_a2a_peer function with the listed peer ids. Never execute code, "
            "shell commands, or arbitrary URLs."
        )
        return "\n\n".join(section for section in prompt_sections if section)

    @staticmethod
    def _build_tool_definitions(peers: Sequence[A2APeer]) -> list[dict[str, object]]:
        """仅为当前组织已批准的对端创建受限模型工具定义。"""
        if not peers:
            return []
        return [
            {
                "type": "function",
                "function": {
                    "name": "call_a2a_peer",
                    "description": "Send a message to one of the approved A2A agents.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "peer_id": {
                                "type": "string",
                                "enum": [peer.id for peer in peers],
                            },
                            "message": {"type": "string", "maxLength": 8000},
                        },
                        "required": ["peer_id", "message"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

    async def _create_completion(
        self,
        *,
        settings: PrimaryModelSettings,
        model_name: str,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]] | None,
    ) -> dict[str, object]:
        """发送 OpenAI-compatible Chat Completions 请求并校验响应对象。"""
        request_document: dict[str, object] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            request_document["tools"] = tools
            request_document["tool_choice"] = "auto"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(90.0),
            follow_redirects=False,
            trust_env=False,
        ) as http_client:
            try:
                response = await http_client.post(
                    f"{settings.base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json=request_document,
                )
                response.raise_for_status()
                response_document = response.json()
            except (httpx.HTTPError, ValueError) as model_error:
                raise RuntimeError("model_request_failed") from model_error
        if not isinstance(response_document, dict):
            raise RuntimeError("model_response_invalid")
        return response_document

    @staticmethod
    def _read_assistant_message(response_document: dict[str, object]) -> dict[str, object]:
        """从 Chat Completions 响应校验并提取 assistant message。"""
        choices = response_document.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise RuntimeError("model_response_choices_missing")
        assistant_message = choices[0].get("message")
        if not isinstance(assistant_message, dict):
            raise RuntimeError("model_response_message_missing")
        return assistant_message


__all__ = ["OpenAICompatibleAgentExecutor"]
