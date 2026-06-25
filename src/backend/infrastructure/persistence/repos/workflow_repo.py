"""Workflow Repository SQLAlchemy 实现。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.shared.interfaces.workflow_repository import WorkflowRepository
from backend.core.shared.models.workflow import Workflow, WorkflowEdge, WorkflowNode
from backend.infrastructure.persistence.models.workflow import (
    WorkflowEdgeModel,
    WorkflowModel,
    WorkflowNodeModel,
)


def _to_node(model: WorkflowNodeModel) -> WorkflowNode:
    """将 ORM 模型转换为 WorkflowNode 领域对象。"""
    return WorkflowNode(
        id=model.id,
        node_type=model.node_type,
        label=model.label,
        config=model.config or {},
        position_x=model.position_x,
        position_y=model.position_y,
    )


def _to_edge(model: WorkflowEdgeModel) -> WorkflowEdge:
    """将 ORM 模型转换为 WorkflowEdge 领域对象。"""
    return WorkflowEdge(
        id=model.id,
        source_node_id=model.source_node_id,
        target_node_id=model.target_node_id,
    )


def _to_workflow(model: WorkflowModel) -> Workflow:
    """将 ORM 模型转换为 Workflow 领域对象。"""
    return Workflow(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        description=model.description,
        status=model.status,
        nodes=[_to_node(node) for node in model.nodes],
        edges=[_to_edge(edge) for edge in model.edges],
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyWorkflowRepository(WorkflowRepository):
    """基于 SQLAlchemy 的 Workflow Repository 实现。"""

    def __init__(self, db_session: Session) -> None:
        self._session = db_session

    def create(self, workflow: Workflow) -> Workflow:
        """创建工作流。"""
        now = datetime.now(timezone.utc)
        model = WorkflowModel(
            id=workflow.id or str(uuid4()),
            owner_id=workflow.owner_id,
            name=workflow.name,
            description=workflow.description,
            status=workflow.status,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        self._session.flush()

        for node in workflow.nodes:
            node_model = WorkflowNodeModel(
                id=node.id or str(uuid4()),
                workflow_id=model.id,
                node_type=node.node_type,
                label=node.label,
                config=node.config or {},
                position_x=node.position_x,
                position_y=node.position_y,
            )
            self._session.add(node_model)

        for edge in workflow.edges:
            edge_model = WorkflowEdgeModel(
                id=edge.id or str(uuid4()),
                workflow_id=model.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
            )
            self._session.add(edge_model)

        self._session.flush()
        return _to_workflow(model)

    def get_by_id(self, workflow_id: str) -> Workflow | None:
        """根据 ID 读取工作流。"""
        model = self._session.get(WorkflowModel, workflow_id)
        if model is None:
            return None
        return _to_workflow(model)

    def list_by_owner(self, owner_id: str) -> Sequence[Workflow]:
        """读取指定用户的所有工作流。"""
        models = (
            self._session.query(WorkflowModel)
            .filter(WorkflowModel.owner_id == owner_id)
            .order_by(WorkflowModel.updated_at.desc())
            .all()
        )
        return [_to_workflow(model) for model in models]

    def update(self, workflow: Workflow) -> Workflow:
        """更新工作流。"""
        model = self._session.get(WorkflowModel, workflow.id)
        if model is None:
            raise ValueError(f"Workflow not found: {workflow.id}")

        model.name = workflow.name
        model.description = workflow.description
        model.status = workflow.status
        model.updated_at = datetime.now(timezone.utc)

        self._session.query(WorkflowNodeModel).filter(
            WorkflowNodeModel.workflow_id == workflow.id
        ).delete()
        self._session.query(WorkflowEdgeModel).filter(
            WorkflowEdgeModel.workflow_id == workflow.id
        ).delete()

        for node in workflow.nodes:
            node_model = WorkflowNodeModel(
                id=node.id or str(uuid4()),
                workflow_id=model.id,
                node_type=node.node_type,
                label=node.label,
                config=node.config or {},
                position_x=node.position_x,
                position_y=node.position_y,
            )
            self._session.add(node_model)

        for edge in workflow.edges:
            edge_model = WorkflowEdgeModel(
                id=edge.id or str(uuid4()),
                workflow_id=model.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
            )
            self._session.add(edge_model)

        self._session.flush()
        return _to_workflow(model)

    def delete(self, workflow_id: str) -> bool:
        """删除工作流。"""
        model = self._session.get(WorkflowModel, workflow_id)
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True
