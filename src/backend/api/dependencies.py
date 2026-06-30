"""FastAPI 依赖注入。

认证按 public / admin 两域独立解析：各自读取独立 Cookie、查询独立的会话
命名空间与用户表，跨域 Cookie 无法通过对方守卫。
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED

from backend.core.agent.use_cases import AgentUseCase
from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.service import AuthService
from backend.core.session.use_cases import SessionUseCase
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.llm_client import LLMClient
from backend.core.shared.interfaces.session_repository import SessionRepository
from backend.core.shared.interfaces.tool_registry import ToolRegistry
from backend.core.shared.interfaces.tool_repository import (
    ToolRepository as ToolMetadataRepository,
)
from backend.core.shared.interfaces.workflow_repository import WorkflowRepository
from backend.core.workflow.use_cases import WorkflowUseCase

# 两域会话 Cookie 名是接入层契约常量；配置仅在 composition root 使用。
PUBLIC_SESSION_COOKIE_NAME: str = "session_id"
ADMIN_SESSION_COOKIE_NAME: str = "admin_session_id"


def get_public_auth_service(request: Request) -> AuthService:
    """从应用状态获取 public 域认证服务。"""
    return request.app.state.public_auth_service


def get_admin_auth_service(request: Request) -> AuthService:
    """从应用状态获取 admin 域认证服务。"""
    return request.app.state.admin_auth_service


def get_public_user_directory(request: Request) -> PublicUserDirectory:
    """从应用状态获取 public 用户管理目录（供 admin 域使用）。"""
    return request.app.state.public_user_directory


def _resolve_principal(
    request: Request,
    *,
    cookie_name: str,
    auth_service: AuthService,
) -> AuthenticatedPrincipal:
    """从指定 Cookie 解析已认证主体。

    Args:
        request (Request): 当前请求。
        cookie_name (str): 本域会话 Cookie 名。
        auth_service (AuthService): 本域认证服务。

    Returns:
        AuthenticatedPrincipal: 已认证主体。

    Raises:
        HTTPException: 未携带 Cookie，或会话无效 / 过期 / 账户被禁用时返回 401。
    """
    session_token: str | None = request.cookies.get(cookie_name)
    if session_token is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="未登录")
    principal: AuthenticatedPrincipal | None = auth_service.resolve_session(session_token)
    if principal is None:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="会话无效或已过期")
    return principal


def get_current_public_user(request: Request) -> AuthenticatedPrincipal:
    """获取当前 public 域登录用户，未登录或失效时返回 401。"""
    return _resolve_principal(
        request,
        cookie_name=PUBLIC_SESSION_COOKIE_NAME,
        auth_service=get_public_auth_service(request),
    )


def get_current_admin_user(request: Request) -> AuthenticatedPrincipal:
    """获取当前 admin 域登录管理员，未登录或失效时返回 401。"""
    return _resolve_principal(
        request,
        cookie_name=ADMIN_SESSION_COOKIE_NAME,
        auth_service=get_admin_auth_service(request),
    )


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
