"""Session / Message 领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence


@dataclass
class ToolCall:
    """工具调用领域对象。"""

    id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any | None = None
    status: str = "pending"


@dataclass
class ChatMessage:
    """聊天消息领域对象。"""

    id: str
    session_id: str
    role: str
    content: str
    tool_calls: Sequence[ToolCall] = field(default_factory=list)
    created_at: datetime | None = None


@dataclass
class ChatSession:
    """聊天会话领域对象。"""

    id: str
    owner_id: str
    agent_id: str
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
