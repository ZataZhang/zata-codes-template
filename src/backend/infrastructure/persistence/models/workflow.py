"""Workflow ORM 模型。"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class WorkflowModel(Base, TimestampMixin):
    """工作流表。"""

    __tablename__ = "workflow"
    __table_args__ = (
        {
            "comment": "工作流表，存储用户编排的工作流元数据。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="工作流主键 ID，业务生成的唯一标识。",
    )
    owner_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="工作流所属用户 ID。",
    )
    name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="工作流名称。",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        comment="工作流描述。",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="draft",
        comment="工作流状态：draft、running、completed、error。",
    )

    nodes: Mapped[list["WorkflowNodeModel"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )
    edges: Mapped[list["WorkflowEdgeModel"]] = relationship(
        back_populates="workflow",
        cascade="all, delete-orphan",
    )


class WorkflowNodeModel(Base):
    """工作流节点表。"""

    __tablename__ = "workflow_node"
    __table_args__ = (
        {
            "comment": "工作流节点表，存储工作流画布中的节点。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="节点主键 ID，业务生成的唯一标识。",
    )
    workflow_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflow.id"),
        nullable=False,
        index=True,
        comment="节点所属工作流 ID。",
    )
    node_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="节点类型：start、end、agent、tool、condition。",
    )
    label: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="节点展示标签。",
    )
    config: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="节点配置，例如 agent_id、tool_id、条件表达式。",
    )
    position_x: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        comment="节点在画布上的 X 坐标。",
    )
    position_y: Mapped[float] = mapped_column(
        nullable=False,
        default=0.0,
        comment="节点在画布上的 Y 坐标。",
    )

    workflow: Mapped["WorkflowModel"] = relationship(back_populates="nodes")


class WorkflowEdgeModel(Base):
    """工作流边表。"""

    __tablename__ = "workflow_edge"
    __table_args__ = (
        {
            "comment": "工作流边表，存储工作流节点之间的连接关系。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="边主键 ID，业务生成的唯一标识。",
    )
    workflow_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("workflow.id"),
        nullable=False,
        index=True,
        comment="边所属工作流 ID。",
    )
    source_node_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="边起始节点 ID。",
    )
    target_node_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="边目标节点 ID。",
    )

    workflow: Mapped["WorkflowModel"] = relationship(back_populates="edges")
