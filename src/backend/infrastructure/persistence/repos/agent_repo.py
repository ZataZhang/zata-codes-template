"""Agent Repository SQLAlchemy 实现。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.models.agent import Agent
from backend.infrastructure.persistence.models.agent import AgentModel


def _to_agent(model: AgentModel) -> Agent:
    """将 ORM 模型转换为领域对象。"""
    return Agent(
        id=model.id,
        owner_id=model.owner_id,
        name=model.name,
        description=model.description,
        system_prompt=model.system_prompt,
        model=model.model,
        tool_ids=list(model.tool_ids or []),
        status=model.status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyAgentRepository(AgentRepository):
    """基于 SQLAlchemy 的 Agent Repository 实现。"""

    def __init__(self, db_session: Session) -> None:
        """Initialize repository with database session."""
        self._session = db_session

    def create(self, agent: Agent) -> Agent:
        """创建 Agent。"""
        now = datetime.now(timezone.utc)
        model = AgentModel(
            id=agent.id or str(uuid4()),
            owner_id=agent.owner_id,
            name=agent.name,
            description=agent.description,
            system_prompt=agent.system_prompt,
            model=agent.model,
            tool_ids=list(agent.tool_ids),
            status=agent.status,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        self._session.flush()
        return _to_agent(model)

    def get_by_id(self, agent_id: str) -> Agent | None:
        """根据 ID 读取 Agent。"""
        model = self._session.get(AgentModel, agent_id)
        if model is None:
            return None
        return _to_agent(model)

    def list_by_owner(self, owner_id: str) -> Sequence[Agent]:
        """读取指定用户的所有 Agent。"""
        models = (
            self._session.query(AgentModel)
            .filter(AgentModel.owner_id == owner_id)
            .order_by(AgentModel.updated_at.desc())
            .all()
        )
        return [_to_agent(model) for model in models]

    def update(self, agent: Agent) -> Agent:
        """更新 Agent。"""
        model = self._session.get(AgentModel, agent.id)
        if model is None:
            raise ValueError(f"Agent not found: {agent.id}")
        model.name = agent.name
        model.description = agent.description
        model.system_prompt = agent.system_prompt
        model.model = agent.model
        model.tool_ids = list(agent.tool_ids)
        model.status = agent.status
        model.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return _to_agent(model)

    def delete(self, agent_id: str) -> bool:
        """删除 Agent。"""
        model = self._session.get(AgentModel, agent_id)
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True
