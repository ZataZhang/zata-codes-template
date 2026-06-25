"""Tool Repository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from backend.core.shared.models.agent import ToolDefinition


class ToolRepository(ABC):
    """工具元数据数据访问抽象端口。"""

    @abstractmethod
    def list_tools(self) -> Sequence[ToolDefinition]:
        """返回所有工具元数据。"""

    @abstractmethod
    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """根据 ID 读取工具元数据。"""
