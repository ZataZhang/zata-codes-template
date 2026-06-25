"""Tool Registry 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence

from backend.core.shared.models.agent import ToolDefinition


class ToolRegistry(ABC):
    """工具注册表抽象端口。"""

    @abstractmethod
    def list_tools(self) -> Sequence[ToolDefinition]:
        """返回所有可用工具元数据。"""

    @abstractmethod
    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """根据 ID 读取工具元数据。"""

    @abstractmethod
    def execute(self, tool_id: str, arguments: dict[str, Any]) -> Any:
        """执行工具并返回结果。"""
