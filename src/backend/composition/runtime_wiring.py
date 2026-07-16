"""Agent、Session、Workflow、Tool 与 LLM 运行依赖装配。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.engines.skills.registry.tool_registry import ToolRegistryImpl
from backend.infrastructure.models.llm_client import LangChainLLMClient
from backend.infrastructure.persistence.repos.agent_repo import (
    SqlAlchemyAgentRepository,
)
from backend.infrastructure.persistence.repos.session_repo import (
    SqlAlchemySessionRepository,
)
from backend.infrastructure.persistence.repos.tool_repo import SqlAlchemyToolRepository
from backend.infrastructure.persistence.repos.workflow_repo import (
    SqlAlchemyWorkflowRepository,
)


@dataclass(frozen=True)
class RuntimeComponents:
    """业务运行依赖装配结果。"""

    agent_repository: SqlAlchemyAgentRepository
    session_repository: SqlAlchemySessionRepository
    workflow_repository: SqlAlchemyWorkflowRepository
    tool_metadata_repository: SqlAlchemyToolRepository
    tool_registry: ToolRegistryImpl
    llm_client: LangChainLLMClient


def build_runtime_components(database_session: Any) -> RuntimeComponents:
    """创建业务仓库、工具注册表与 LLM 客户端。

    Args:
        database_session: SQLAlchemy 数据库会话。

    Returns:
        业务运行组件集合。
    """

    tool_metadata_repository = SqlAlchemyToolRepository(database_session)
    return RuntimeComponents(
        agent_repository=SqlAlchemyAgentRepository(database_session),
        session_repository=SqlAlchemySessionRepository(database_session),
        workflow_repository=SqlAlchemyWorkflowRepository(database_session),
        tool_metadata_repository=tool_metadata_repository,
        tool_registry=ToolRegistryImpl(tool_repository=SqlAlchemyToolRepository(database_session)),
        llm_client=LangChainLLMClient(),
    )


__all__ = ["RuntimeComponents", "build_runtime_components"]
