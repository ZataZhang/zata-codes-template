"""Workflow 执行器。"""

from __future__ import annotations

from collections import deque
from typing import Any

from backend.core.shared.models.workflow import Workflow, WorkflowNode


class WorkflowRunner:
    """按拓扑顺序执行工作流节点。"""

    def __init__(self, workflow: Workflow) -> None:
        """Initialize runner with workflow definition."""
        self._workflow = workflow

    def run(self) -> dict[str, Any]:
        """运行工作流并返回执行结果。"""
        if not self._workflow.nodes:
            return {"status": "completed", "results": [], "message": "工作流为空"}

        node_map = {node.id: node for node in self._workflow.nodes}
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_map}
        in_degree = {node_id: 0 for node_id in node_map}

        for edge in self._workflow.edges:
            if edge.source_node_id in adjacency and edge.target_node_id in in_degree:
                adjacency[edge.source_node_id].append(edge.target_node_id)
                in_degree[edge.target_node_id] += 1

        queue = deque([node_id for node_id, degree in in_degree.items() if degree == 0])
        results: list[dict[str, Any]] = []

        while queue:
            current_id = queue.popleft()
            node = node_map[current_id]
            result = self._execute_node(node)
            results.append({"node_id": current_id, "node_type": node.node_type, "result": result})

            for next_id in adjacency.get(current_id, []):
                in_degree[next_id] -= 1
                if in_degree[next_id] == 0:
                    queue.append(next_id)

        return {
            "status": "completed",
            "results": results,
            "message": f"执行完成，共 {len(results)} 个节点",
        }

    def _execute_node(self, node: WorkflowNode) -> Any:
        """执行单个节点（MVP 返回 mock 结果）。"""
        if node.node_type == "start":
            return {"message": "工作流开始"}
        if node.node_type == "end":
            return {"message": "工作流结束"}
        if node.node_type == "agent":
            agent_id = node.config.get("agent_id")
            return {"message": f"调用 Agent: {agent_id or '未指定'}"}
        if node.node_type == "tool":
            tool_id = node.config.get("tool_id")
            return {"message": f"调用工具: {tool_id or '未指定'}"}
        if node.node_type == "condition":
            return {"message": "条件判断（MVP 固定通过）"}
        return {"message": f"未知节点类型: {node.node_type}"}
