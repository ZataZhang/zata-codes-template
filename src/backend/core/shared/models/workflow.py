"""Workflow 领域模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Sequence


@dataclass
class WorkflowNode:
    """工作流节点领域对象。"""

    id: str
    node_type: str
    label: str
    config: dict[str, Any] = field(default_factory=dict)
    position_x: float = 0.0
    position_y: float = 0.0


@dataclass
class WorkflowEdge:
    """工作流边领域对象。"""

    id: str
    source_node_id: str
    target_node_id: str


@dataclass
class Workflow:
    """工作流领域对象。"""

    id: str
    owner_id: str
    name: str
    description: str
    status: str = "draft"
    nodes: Sequence[WorkflowNode] = field(default_factory=list)
    edges: Sequence[WorkflowEdge] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
