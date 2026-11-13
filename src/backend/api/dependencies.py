"""FastAPI 依赖注入。

认证按 public / admin 两域独立解析：各自读取独立 Cookie、查询独立的会话
命名空间与用户表，跨域 Cookie 无法通过对方守卫。
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from backend.api.security.rate_limiter import ApiRateLimiter
from backend.core.auth.admin_directory import AdminDirectory
from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthDomain, AuthenticatedPrincipal
from backend.core.auth.oidc_login import (
    AdminOidcAccountResolver,
    OidcLoginDependencies,
    OidcLoginService,
    UserOidcAccountResolver,
)
from backend.core.auth.organization_directory import OrganizationDirectory
from backend.core.auth.registration_policy_service import RegistrationPolicyService
from backend.core.auth.service import AuthService
from backend.core.run_tracing import RunTraceUseCase

# 两域会话 Cookie 名是接入层契约常量；配置仅在 composition root 使用。
PUBLIC_SESSION_COOKIE_NAME: str = "session_id"
ADMIN_SESSION_COOKIE_NAME: str = "admin_session_id"


def get_public_auth_service(request: Request) -> AuthService:
    """从应用状态获取 public 域认证服务。"""
    return request.app.state.public_auth_service


def get_admin_auth_service(request: Request) -> AuthService:
    """从应用状态获取 admin 域认证服务。"""
    return request.app.state.admin_auth_service


def get_admin_oidc_gateway(request: Request) -> Any | None:
    """从应用状态获取已配置的管理员 OIDC 协议客户端。"""
    return request.app.state.admin_oidc_gateway


def get_admin_oidc_login_service(
    request: Request,
    gateway: Any | None = Depends(get_admin_oidc_gateway),
) -> OidcLoginService | None:
    """组合管理员 OIDC 用例；配置不完整时返回空值。"""
    if gateway is None:
        return None
    return OidcLoginService(
        dependencies=OidcLoginDependencies(
            gateway=gateway,
            transaction_store=request.app.state.admin_oidc_transaction_store,
            account_resolver=AdminOidcAccountResolver(request.app.state.admin_user_repository),
            session_store=request.app.state.admin_session_store,
            domain=AuthDomain.ADMIN,
        )
    )


def get_public_oidc_gateway(request: Request) -> Any | None:
    """从应用状态获取已配置的 public OIDC 协议客户端。"""
    return request.app.state.public_oidc_gateway


def get_public_oidc_login_service(
    request: Request,
    gateway: Any | None = Depends(get_public_oidc_gateway),
) -> OidcLoginService | None:
    """组合 public OIDC 用例；配置不完整时返回空值。"""
    if gateway is None:
        return None
    return OidcLoginService(
        dependencies=OidcLoginDependencies(
            gateway=gateway,
            transaction_store=request.app.state.public_oidc_transaction_store,
            account_resolver=UserOidcAccountResolver(
                repository=request.app.state.public_user_repository,
                registration_policy_provider=request.app.state.registration_policy_service,
                password_hasher=request.app.state.password_hasher,
            ),
            session_store=request.app.state.public_session_store,
            domain=AuthDomain.PUBLIC,
        )
    )


def get_public_user_directory(request: Request) -> PublicUserDirectory:
    """从应用状态获取 public 用户管理目录（供 admin 域使用）。"""
    return request.app.state.public_user_directory


def get_run_trace_use_case(request: Request) -> RunTraceUseCase:
    """从应用状态获取 Run 执行轨迹诊断用例（admin 域专用）。"""
    return request.app.state.run_trace_use_case


def get_api_rate_limiter(request: Request) -> ApiRateLimiter:
    """从应用状态获取共享 API 限流策略。"""
    return request.app.state.api_rate_limiter


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


def get_current_platform_admin(
    admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
) -> AuthenticatedPrincipal:
    """获取当前平台管理员；组织管理员访问平台接口时返回 403。"""
    if admin.role != "platform":
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="platform_admin_required")
    return admin


def get_organization_directory(request: Request) -> OrganizationDirectory:
    """从应用状态读取组织目录用例。"""
    return request.app.state.organization_directory


def get_admin_directory(request: Request) -> AdminDirectory:
    """从应用状态读取管理员目录用例。"""
    return request.app.state.admin_directory


def get_registration_policy_service(request: Request) -> RegistrationPolicyService:
    """从应用状态读取注册策略服务。"""
    return request.app.state.registration_policy_service
