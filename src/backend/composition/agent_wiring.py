"""在线 Agent、Skill 与 A2A 运行依赖装配。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.agent import AgentCatalogUseCase, AgentRunUseCase, SkillUseCase
from backend.core.shared.interfaces.run_repository import RunRepository
from backend.engines.agent_adapters import OpenAICompatibleAgentExecutor
from backend.infrastructure.a2a import HttpA2AClient
from backend.infrastructure.persistence.repos.agent_repo import SqlAlchemyAgentRepository
from backend.infrastructure.security.environment_secret_resolver import (
    EnvironmentSecretResolver,
)


@dataclass(frozen=True)
class AgentComponents:
    """Agent 路由所需的组织范围用例集合。"""

    catalog: AgentCatalogUseCase
    skills: SkillUseCase
    runs: AgentRunUseCase


def build_agent_components(session_factory: Any, run_repository: RunRepository) -> AgentComponents:
    """装配 Agent、Skill 和 canonical Run 用例。

    Args:
        session_factory: SQLAlchemy 会话工厂。
        run_repository (RunRepository): 已装配的 Canonical Run 仓库。

    Returns:
        AgentComponents: 供 API 注入的用例集合。
    """
    agent_repository = SqlAlchemyAgentRepository(session_factory=session_factory)
    a2a_client = HttpA2AClient(agent_repository)
    agent_executor = OpenAICompatibleAgentExecutor(a2a_client)
    return AgentComponents(
        catalog=AgentCatalogUseCase(
            agent_repository,
            agent_executor,
            EnvironmentSecretResolver(),
        ),
        skills=SkillUseCase(agent_repository),
        runs=AgentRunUseCase(
            agent_repository=agent_repository,
            run_repository=run_repository,
            executor=agent_executor,
        ),
    )


__all__ = ["AgentComponents", "build_agent_components"]
