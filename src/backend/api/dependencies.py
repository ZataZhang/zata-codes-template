"""FastAPI 依赖注入。"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED

from backend.core.agent.use_cases import AgentUseCase
from backend.core.session.use_cases import SessionUseCase
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.llm_client import LLMClient
from backend.core.shared.interfaces.session_repository import SessionRepository
from backend.core.shared.interfaces.tool_registry import ToolRegistry
from backend.core.shared.interfaces.tool_repository import (
    ToolRepository as ToolMetadataRepository,
)
from backend.core.shared.interfaces.workflow_repository import WorkflowRepository
from backend.core.use_cases.auth import AuthUseCase, User
from backend.core.workflow.use_cases import WorkflowUseCase


def get_auth_use_case(request: Request) -> AuthUseCase:
    """从应用状态中获取认证用例实例。"""
    return request.app.state.auth_use_case


def get_session_token(request: Request) -> str | None:
    """从请求 Cookie 中提取 session token。"""
    return request.cookies.get("session_id")


def get_current_user(request: Request) -> User:
    """获取当前登录用户，未登录时返回 401。"""
    token = get_session_token(request)
    if token is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="未登录",
        )
    auth_use_case = get_auth_use_case(request)
    user = auth_use_case.get_current_session(token)
    if user is None:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="会话已过期",
        )
    return user


def get_agent_repository(request: Request) -> AgentRepository:
    """从应用状态中获取 Agent Repository。"""
    return request.app.state.agent_repository


def get_session_repository(request: Request) -> SessionRepository:
    """从应用状态中获取 Session Repository。"""
    return request.app.state.session_repository


def get_workflow_repository(request: Request) -> WorkflowRepository:
    """从应用状态中获取 Workflow Repository。"""
    return request.app.state.workflow_repository


def get_tool_metadata_repository(request: Request) -> ToolMetadataRepository:
    """从应用状态中获取 Tool Metadata Repository。"""
    return request.app.state.tool_metadata_repository


def get_tool_registry(request: Request) -> ToolRegistry:
    """从应用状态中获取 Tool Registry。"""
    return request.app.state.tool_registry


def get_llm_client(request: Request) -> LLMClient:
    """从应用状态中获取 LLM Client。"""
    return request.app.state.llm_client


def get_agent_use_case(request: Request) -> AgentUseCase:
    """构造 Agent UseCase。"""
    return AgentUseCase(repository=get_agent_repository(request))


def get_session_use_case(request: Request) -> SessionUseCase:
    """构造 Session UseCase。"""
    return SessionUseCase(
        session_repository=get_session_repository(request),
        agent_repository=get_agent_repository(request),
        tool_registry=get_tool_registry(request),
        llm_client=get_llm_client(request),
    )


def get_workflow_use_case(request: Request) -> WorkflowUseCase:
    """构造 Workflow UseCase。"""
    return WorkflowUseCase(repository=get_workflow_repository(request))
