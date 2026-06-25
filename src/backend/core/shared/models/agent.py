"""Agent 领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence


@dataclass
class ToolDefinition:
    """工具定义领域对象。"""

    id: str
    name: str
    description: str
    schema: dict


@dataclass
class Agent:
    """Agent 领域对象。"""

    id: str
    owner_id: str
    name: str
    description: str
    system_prompt: str
    model: str
    tool_ids: Sequence[str] = field(default_factory=list)
    status: str = "idle"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def is_owned_by(self, user_id: str) -> bool:
        """检查 Agent 是否属于指定用户。"""
        return self.owner_id == user_id
