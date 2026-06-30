"""基于 create_chat_model 的 LLM Client 基础设施实现。"""

from __future__ import annotations

import os
from typing import Sequence

from backend.core.shared.interfaces.llm_client import (
    LLMClient,
    LLMMessage,
    LLMResponse,
)
from backend.infrastructure.config.settings import create_chat_model


class LangChainLLMClient(LLMClient):
    """基于 langchain_openai 的 LLM Client 实现。"""

    def chat(
        self,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
    ) -> LLMResponse:
        """调用 LLM 生成回复。"""
        if os.getenv("MOCK_LLM_RESPONSE", "false").lower() == "true":
            return LLMResponse(
                content=(
                    "（Mock 回复）我已收到你的消息。"
                    "当前处于 MOCK_LLM_RESPONSE 模式，真实 LLM 未调用。"
                )
            )

        chat_model = create_chat_model(model_name=model, temperature=0.7)
        history = [(msg.role, msg.content) for msg in messages]
        response = chat_model.invoke(
            [
                ("system", system_prompt),
                *history,
            ]
        )
        content = response.content if hasattr(response, "content") else str(response)
        return LLMResponse(content=str(content))
