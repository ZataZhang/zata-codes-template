"""LLM Client 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class LLMMessage:
    """LLM 对话消息。"""

    role: str
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """LLM 响应。"""

    content: str


class LLMClient(ABC):
    """大语言模型客户端抽象端口。"""

    @abstractmethod
    def chat(
        self,
        model: str,
        system_prompt: str,
        messages: Sequence[LLMMessage],
    ) -> LLMResponse:
        """调用 LLM 生成回复。"""
