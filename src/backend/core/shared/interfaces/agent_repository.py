"""Agent Repository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from backend.core.shared.models.agent import Agent


class AgentRepository(ABC):
    """Agent 数据访问抽象端口。"""

    @abstractmethod
    def create(self, agent: Agent) -> Agent:
        """创建 Agent 并返回持久化后的实体。"""

    @abstractmethod
    def get_by_id(self, agent_id: str) -> Agent | None:
        """根据 ID 读取 Agent。"""

    @abstractmethod
    def list_by_owner(self, owner_id: str) -> Sequence[Agent]:
        """读取指定用户的所有 Agent。"""

    @abstractmethod
    def update(self, agent: Agent) -> Agent:
        """更新 Agent 并返回更新后的实体。"""

    @abstractmethod
    def delete(self, agent_id: str) -> bool:
        """删除 Agent，返回是否成功。"""
