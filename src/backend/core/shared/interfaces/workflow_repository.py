"""Workflow Repository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from backend.core.shared.models.workflow import Workflow


class WorkflowRepository(ABC):
    """工作流数据访问抽象端口。"""

    @abstractmethod
    def create(self, workflow: Workflow) -> Workflow:
        """创建工作流。"""

    @abstractmethod
    def get_by_id(self, workflow_id: str) -> Workflow | None:
        """根据 ID 读取工作流。"""

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> Sequence[Workflow]:
        """读取指定用户的所有工作流。"""

    @abstractmethod
    def update(self, workflow: Workflow) -> Workflow:
        """更新工作流。"""

    @abstractmethod
    def delete(self, workflow_id: str) -> bool:
        """删除工作流，返回是否成功。"""
