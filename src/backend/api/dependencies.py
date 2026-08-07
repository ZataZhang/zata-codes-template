"""FastAPI 依赖注入。

认证按 public / admin 两域独立解析：各自读取独立 Cookie、查询独立的会话
命名空间与用户表，跨域 Cookie 无法通过对方守卫。
"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.status import HTTP_401_UNAUTHORIZED

from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.service import AuthService

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
