"""Workflow 用例。"""

from __future__ import annotations

from typing import Sequence
from uuid import uuid4

from backend.core.shared.interfaces.workflow_repository import WorkflowRepository
from backend.core.shared.models.workflow import Workflow
from backend.core.workflow.runner.workflow_runner import WorkflowRunner


class WorkflowUseCase:
    """工作流业务用例。"""

    def __init__(self, repository: WorkflowRepository) -> None:
        self._repository = repository

    def create_workflow(
        self,
        owner_id: str,
        name: str,
        description: str,
    ) -> Workflow:
        """创建工作流。"""
        workflow = Workflow(
            id=str(uuid4()),
            owner_id=owner_id,
            name=name,
            description=description,
        )
        return self._repository.create(workflow)

    def get_workflow(self, workflow_id: str, requester_id: str) -> Workflow:
        """读取工作流。"""
        workflow = self._repository.get_by_id(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")
        if workflow.owner_id != requester_id:
            raise PermissionError("Not authorized to access this workflow")
        return workflow

    def list_workflows(self, owner_id: str) -> Sequence[Workflow]:
        """列出用户的所有工作流。"""
        return self._repository.list_by_owner(owner_id)

    def update_workflow(
        self,
        workflow_id: str,
        requester_id: str,
        name: str,
        description: str,
        nodes: Sequence[dict],
        edges: Sequence[dict],
        status: str | None = None,
    ) -> Workflow:
        """更新工作流。"""
        from backend.core.shared.models.workflow import WorkflowEdge, WorkflowNode

        workflow = self.get_workflow(workflow_id, requester_id)
        workflow.name = name
        workflow.description = description
        if status is not None:
            workflow.status = status

        workflow.nodes = [
            WorkflowNode(
                id=node.get("id") or str(uuid4()),
                node_type=node["node_type"],
                label=node["label"],
                config=node.get("config", {}),
                position_x=node.get("position_x", 0.0),
                position_y=node.get("position_y", 0.0),
            )
            for node in nodes
        ]
        workflow.edges = [
            WorkflowEdge(
                id=edge.get("id") or str(uuid4()),
                source_node_id=edge["source_node_id"],
                target_node_id=edge["target_node_id"],
            )
            for edge in edges
        ]
        return self._repository.update(workflow)

    def delete_workflow(self, workflow_id: str, requester_id: str) -> bool:
        """删除工作流。"""
        self.get_workflow(workflow_id, requester_id)
        return self._repository.delete(workflow_id)

    def run_workflow(self, workflow_id: str, requester_id: str) -> dict:
        """运行工作流并返回结果。"""
        workflow = self.get_workflow(workflow_id, requester_id)
        runner = WorkflowRunner(workflow)
        return runner.run()
