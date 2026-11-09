"""认证 HTTP 入口复用的登录流程。"""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, Request, Response, status

from backend.api.schemas import LoginRequest
from backend.api.security.rate_limiter import ApiRateLimiter
from backend.api.security.session_cookies import set_session_cookie
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.service import AuthService

LoginOperation = Literal["public_login", "admin_login"]


async def authenticate_and_set_cookie(
    request: Request,
    request_payload: LoginRequest,
    response: Response,
    *,
    auth_service: AuthService,
    api_rate_limiter: ApiRateLimiter,
    cookie_name: str,
    operation: LoginOperation,
) -> AuthenticatedPrincipal:
    """限流并认证登录请求，创建会话 Cookie 后返回主体。

    Args:
        request (Request): 当前登录请求。
        request_payload (LoginRequest): 已校验的用户凭据。
        response (Response): 接收会话 Cookie 的响应。
        auth_service (AuthService): 当前认证域的服务。
        api_rate_limiter (ApiRateLimiter): 共享 API 限流器。
        cookie_name (str): 当前认证域的 Cookie 名。
        operation (LoginOperation): public 或 admin 登录操作名。

    Returns:
        AuthenticatedPrincipal: 已认证主体。

    Raises:
        HTTPException: 凭据错误时返回 401；来源或账户限流时返回 429。
    """
    await api_rate_limiter.check_auth_attempt(
        request,
        operation=operation,
        identifier=request_payload.identifier,
    )
    try:
        session_token, principal = auth_service.authenticate(
            request_payload.identifier,
            request_payload.password,
        )
    except ValueError as auth_error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(auth_error),
        ) from auth_error

    set_session_cookie(
        response,
        cookie_name=cookie_name,
        token=session_token,
        secure=request.app.state.auth_cookie_secure,
    )
    return principal


__all__ = ["LoginOperation", "authenticate_and_set_cookie"]
