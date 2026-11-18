"""OpenAI 协议模型与已批准 A2A 对端的 Agent 执行适配器。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from typing import Sequence

import httpx

from backend.core.shared.interfaces.agent_executor import (
    A2AClient,
    AgentExecutionCallbacks,
    AgentExecutionResult,
    AgentExecutor,
    AgentExternalCallEvent,
    DeltaCallback,
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
        callbacks: AgentExecutionCallbacks | None = None,
    ) -> AgentExecutionResult:
        """调用默认 OpenAI-compatible 端点并执行模型选择的已批准对端。

        Args:
            snapshot (dict[str, object]): Run 创建时冻结的 Agent 配置。
            message (str): 当前用户消息。
            peers (Sequence[A2APeer]): 当前组织已批准的 A2A 对端。
            callbacks (AgentExecutionCallbacks | None): 流式文本和 A2A 调用事件回调。

        Returns:
            AgentExecutionResult: 模型最终回复。

        Raises:
            RuntimeError: 模型未配置、响应无效或对端调用失败时抛出。
        """
        settings = self._model_settings
        if settings is None:
            raise RuntimeError(self.unavailable_reason or "model_not_configured")
        on_delta = callbacks.on_delta if callbacks else None
        on_external_call = callbacks.on_external_call if callbacks else None
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
        completion_response, content_streamed = await self._create_completion(
            settings=settings,
            model_name=model_name,
            messages=message_history,
            tools=tool_definitions,
            on_delta=on_delta,
        )
        assistant_message = self._read_assistant_message(completion_response)
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
                tool_call_id = uuid.uuid4().hex
                if on_external_call is not None:
                    on_external_call(
                        AgentExternalCallEvent(
                            phase="started",
                            tool_call_id=tool_call_id,
                            peer_id=peer.id,
                            input_length=len(peer_message),
                        )
                    )
                try:
                    peer_response = await self._a2a_client.send_message(
                        organization_id=organization_id,
                        peer_id=peer.id,
                        message=peer_message,
                        idempotency_key=(f"{snapshot.get('run_id', 'run')}:a2a:{tool_call_index}"),
                    )
                except asyncio.CancelledError:
                    if on_external_call is not None:
                        on_external_call(
                            AgentExternalCallEvent(
                                phase="failed",
                                tool_call_id=tool_call_id,
                                peer_id=peer.id,
                                input_length=len(peer_message),
                                error_code="a2a_call_cancelled",
                            )
                        )
                    raise
                except Exception:
                    if on_external_call is not None:
                        on_external_call(
                            AgentExternalCallEvent(
                                phase="failed",
                                tool_call_id=tool_call_id,
                                peer_id=peer.id,
                                input_length=len(peer_message),
                                error_code="a2a_call_failed",
                            )
                        )
                    raise
                result_checksum = hashlib.sha256(peer_response.content.encode("utf-8")).hexdigest()
                if on_external_call is not None:
                    on_external_call(
                        AgentExternalCallEvent(
                            phase="completed",
                            tool_call_id=tool_call_id,
                            peer_id=peer.id,
                            input_length=len(peer_message),
                            remote_task_id=peer_response.task_id,
                            result_checksum=result_checksum,
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
            completion_response, content_streamed = await self._create_completion(
                settings=settings,
                model_name=model_name,
                messages=message_history,
                tools=None,
                on_delta=on_delta,
            )
            assistant_message = self._read_assistant_message(completion_response)
        final_content = assistant_message.get("content")
        if not isinstance(final_content, str):
            raise RuntimeError("model_response_content_missing")
        return AgentExecutionResult(
            content=final_content,
            model_name=model_name,
            content_streamed=content_streamed,
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
        on_delta: DeltaCallback | None = None,
    ) -> tuple[dict[str, object], bool]:
        """发送 OpenAI-compatible Chat Completions 请求并校验响应对象。

        Args:
            settings (PrimaryModelSettings): 主模型端点与凭据。
            model_name (str): 本次调用使用的模型名。
            messages (list[dict[str, object]]): 已构造的对话消息。
            tools (list[dict[str, object]] | None): 允许模型调用的受控工具。
            on_delta (DeltaCallback | None): 流式文本片段回调。

        Returns:
            tuple[dict[str, object], bool]: 归一化后的响应对象，以及是否已经
            通过回调交付过文本片段。

        Raises:
            RuntimeError: 网络失败、响应不是合法 JSON 或流式分片不可解析。
        """
        request_document: dict[str, object] = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.2,
        }
        if tools:
            request_document["tools"] = tools
            request_document["tool_choice"] = "auto"
        if on_delta is not None:
            request_document["stream"] = True
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(90.0),
            follow_redirects=False,
            trust_env=False,
        ) as http_client:
            if on_delta is not None:
                return await self._stream_completion(
                    http_client=http_client,
                    settings=settings,
                    request_document=request_document,
                    on_delta=on_delta,
                )
            try:
                response = await http_client.post(
                    f"{settings.base_url.rstrip('/')}/chat/completions",
                    headers=self._request_headers(settings),
                    json=request_document,
                )
                response.raise_for_status()
                response_document = response.json()
            except (httpx.HTTPError, ValueError) as model_error:
                raise RuntimeError("model_request_failed") from model_error
        if not isinstance(response_document, dict):
            raise RuntimeError("model_response_invalid")
        return response_document, False

    @staticmethod
    def _request_headers(settings: PrimaryModelSettings) -> dict[str, str]:
        """构造只用于服务端模型调用、不进入日志或浏览器的请求头。"""
        return {
            "Authorization": f"Bearer {settings.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }

    async def _stream_completion(
        self,
        *,
        http_client: httpx.AsyncClient,
        settings: PrimaryModelSettings,
        request_document: dict[str, object],
        on_delta: DeltaCallback,
    ) -> tuple[dict[str, object], bool]:
        """逐片读取模型 SSE 响应，边交付文本片段边组装最终 assistant message。

        Args:
            http_client (httpx.AsyncClient): 已构造的受限 HTTP 客户端。
            settings (PrimaryModelSettings): 主模型端点与凭据。
            request_document (dict[str, object]): 已声明的流式请求体。
            on_delta (DeltaCallback): 文本片段回调。

        Returns:
            tuple[dict[str, object], bool]: 与非流式响应同构的归一化对象，以及
            是否已经交付过文本片段。

        Raises:
            RuntimeError: 连接失败、分片不可解析或端点没有返回可识别内容。
        """
        content_fragments: list[str] = []
        tool_call_fragments: dict[int, dict[str, object]] = {}
        finish_reason = ""
        streamed_any_content = False
        try:
            async with http_client.stream(
                "POST",
                f"{settings.base_url.rstrip('/')}/chat/completions",
                headers=self._request_headers(settings),
                json=request_document,
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    buffered_document = json.loads(await response.aread())
                    if not isinstance(buffered_document, dict):
                        raise RuntimeError("model_response_invalid")
                    return buffered_document, False
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    payload_text = line.removeprefix("data:").strip()
                    if payload_text == "[DONE]":
                        break
                    finish_reason = await self._consume_stream_chunk(
                        payload_text=payload_text,
                        content_fragments=content_fragments,
                        tool_call_fragments=tool_call_fragments,
                        fallback_finish_reason=finish_reason,
                        on_delta=on_delta,
                    )
                    streamed_any_content = streamed_any_content or bool(content_fragments)
        except (httpx.HTTPError, ValueError) as model_error:
            raise RuntimeError("model_request_failed") from model_error
        if not finish_reason:
            raise RuntimeError("model_stream_incomplete")
        assistant_message: dict[str, object] = {
            "role": "assistant",
            "content": "".join(content_fragments) if content_fragments else None,
        }
        if tool_call_fragments:
            assistant_message["tool_calls"] = [
                tool_call_fragments[fragment_index]
                for fragment_index in sorted(tool_call_fragments)
            ]
        return (
            {"choices": [{"message": assistant_message, "finish_reason": finish_reason}]},
            streamed_any_content,
        )

    async def _consume_stream_chunk(
        self,
        *,
        payload_text: str,
        content_fragments: list[str],
        tool_call_fragments: dict[int, dict[str, object]],
        fallback_finish_reason: str,
        on_delta: DeltaCallback,
    ) -> str:
        """解析单个 SSE 分片，交付文本片段并累积工具调用参数。

        Args:
            payload_text (str): ``data:`` 之后的 JSON 文本。
            content_fragments (list[str]): 已收到的文本片段。
            tool_call_fragments (dict[int, dict[str, object]]): 累积中的工具调用。
            fallback_finish_reason (str): 尚未收到 ``finish_reason`` 时的取值。
            on_delta (DeltaCallback): 文本片段回调。

        Returns:
            str: 本分片声明或延续的 ``finish_reason``。

        Raises:
            RuntimeError: 分片不是合法 JSON 对象。
        """
        try:
            chunk_document = json.loads(payload_text)
        except json.JSONDecodeError as decode_error:
            raise RuntimeError("model_response_invalid") from decode_error
        if not isinstance(chunk_document, dict):
            raise RuntimeError("model_response_invalid")
        choices = chunk_document.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            # 只带用量统计的分片不改变文本内容。
            return fallback_finish_reason
        choice_document = choices[0]
        delta_document = choice_document.get("delta")
        finish_reason = str(choice_document.get("finish_reason") or fallback_finish_reason)
        if not isinstance(delta_document, dict):
            return finish_reason
        delta_content = delta_document.get("content")
        if isinstance(delta_content, str) and delta_content:
            content_fragments.append(delta_content)
            await on_delta(delta_content)
        for fragment in delta_document.get("tool_calls") or []:
            if not isinstance(fragment, dict):
                continue
            fragment_index = int(fragment.get("index") or 0)
            accumulated = tool_call_fragments.setdefault(
                fragment_index,
                {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
            )
            if fragment.get("id"):
                accumulated["id"] = str(fragment["id"])
            function_fragment = fragment.get("function")
            if not isinstance(function_fragment, dict):
                continue
            accumulated_function = accumulated.get("function")
            if not isinstance(accumulated_function, dict):
                accumulated_function = {"name": "", "arguments": ""}
                accumulated["function"] = accumulated_function
            if function_fragment.get("name"):
                accumulated_function["name"] = str(accumulated_function["name"]) + str(
                    function_fragment["name"]
                )
            if function_fragment.get("arguments"):
                accumulated_function["arguments"] = str(accumulated_function["arguments"]) + str(
                    function_fragment["arguments"]
                )
        return finish_reason

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
