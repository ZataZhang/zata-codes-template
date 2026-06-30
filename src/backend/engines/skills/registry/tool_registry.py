"""Tool Registry 实现与执行映射。"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from backend.core.shared.interfaces.tool_registry import ToolRegistry
from backend.core.shared.interfaces.tool_repository import ToolRepository
from backend.core.shared.models.agent import ToolDefinition
from backend.engines.skills.tools.code_runner import run_code_tool
from backend.engines.skills.tools.web_search import run_web_search_tool

ToolHandler = Callable[[dict[str, Any]], Any]

EXECUTION_REGISTRY: dict[str, ToolHandler] = {
    "web_search": run_web_search_tool,
    "code_runner": run_code_tool,
}


def execute_tool(
    tool_id: str,
    arguments: dict[str, Any],
    registry: dict[str, ToolHandler] | None = None,
) -> Any:
    """根据工具 ID 路由到对应处理器执行。"""
    resolved_registry = registry or EXECUTION_REGISTRY
    handler = resolved_registry.get(tool_id)
    if handler is None:
        raise ValueError(f"Tool handler not found: {tool_id}")
    return handler(arguments)


class ToolRegistryImpl(ToolRegistry):
    """工具注册表实现，组合工具元数据仓库与执行映射。"""

    def __init__(
        self,
        tool_repository: ToolRepository,
        execution_registry: dict[str, ToolHandler] | None = None,
    ) -> None:
        """Initialize registry with tool metadata and execution handlers."""
        self._tool_repository = tool_repository
        self._execution_registry = execution_registry or EXECUTION_REGISTRY

    def list_tools(self) -> Sequence[ToolDefinition]:
        """返回所有可用工具元数据。"""
        return self._tool_repository.list_tools()

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """根据 ID 读取工具元数据。"""
        return self._tool_repository.get_tool(tool_id)

    def execute(self, tool_id: str, arguments: dict[str, Any]) -> Any:
        """执行工具。"""
        return execute_tool(tool_id, arguments, registry=self._execution_registry)
