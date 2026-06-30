"""Agent 用例。"""

from __future__ import annotations

from typing import Sequence
from uuid import uuid4

from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.models.agent import Agent


class AgentUseCase:
    """Agent 业务用例。"""

    def __init__(self, repository: AgentRepository) -> None:
        """Initialize use case with agent repository."""
        self._repository = repository

    def create_agent(
        self,
        owner_id: str,
        name: str,
        description: str,
        system_prompt: str,
        model: str,
        tool_ids: Sequence[str] | None = None,
    ) -> Agent:
        """创建 Agent。"""
        agent = Agent(
            id=str(uuid4()),
            owner_id=owner_id,
            name=name,
            description=description,
            system_prompt=system_prompt,
            model=model,
            tool_ids=list(tool_ids or []),
        )
        return self._repository.create(agent)

    def get_agent(self, agent_id: str, requester_id: str) -> Agent:
        """读取 Agent，校验所有权。"""
        agent = self._repository.get_by_id(agent_id)
        if agent is None:
            raise ValueError(f"Agent not found: {agent_id}")
        if not agent.is_owned_by(requester_id):
            raise PermissionError("Not authorized to access this agent")
        return agent

    def list_agents(self, owner_id: str) -> Sequence[Agent]:
        """列出用户的所有 Agent。"""
        return self._repository.list_by_owner(owner_id)

    def update_agent(
        self,
        agent_id: str,
        requester_id: str,
        name: str,
        description: str,
        system_prompt: str,
        model: str,
        tool_ids: Sequence[str] | None = None,
        status: str | None = None,
    ) -> Agent:
        """更新 Agent。"""
        agent = self.get_agent(agent_id, requester_id)
        agent.name = name
        agent.description = description
        agent.system_prompt = system_prompt
        agent.model = model
        agent.tool_ids = list(tool_ids or [])
        if status is not None:
            agent.status = status
        return self._repository.update(agent)

    def delete_agent(self, agent_id: str, requester_id: str) -> bool:
        """删除 Agent。"""
        self.get_agent(agent_id, requester_id)
        return self._repository.delete(agent_id)
