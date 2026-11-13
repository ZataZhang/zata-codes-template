"""Admin 域认证路由（不开放注册）。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from zata_oidc import OidcAuthenticationError

from backend.api.dependencies import (
    ADMIN_SESSION_COOKIE_NAME,
    get_admin_auth_service,
    get_admin_oidc_login_service,
    get_api_rate_limiter,
)
from backend.api.schemas import AdminSessionResponse, LoginRequest
from backend.api.security.authentication import authenticate_and_set_cookie
from backend.api.security.oidc_callback_response import (
    OidcCallbackResponseConfig,
    build_oidc_callback_response,
)
from backend.api.security.rate_limiter import ApiRateLimiter
from backend.api.security.session_cookies import clear_session_cookie
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.oidc_login import OidcLoginService
from backend.core.auth.service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
_OIDC_TRANSACTION_COOKIE_NAME: str = "admin_oidc_txn"
_OIDC_TRANSACTION_COOKIE_MAX_AGE_SECONDS: int = 600
_OIDC_CALLBACK_RESPONSE_CONFIG = OidcCallbackResponseConfig(
    portal="admin",
    transaction_cookie_name=_OIDC_TRANSACTION_COOKIE_NAME,
    session_cookie_name=ADMIN_SESSION_COOKIE_NAME,
    failure_redirect_path="/sign-in",
    success_redirect_path="/",
)


def _to_session_response(principal: AuthenticatedPrincipal) -> AdminSessionResponse:
    """把已认证主体映射为 admin 会话响应。"""
    return AdminSessionResponse(
        user_id=principal.user_id,
        display_name=principal.display_name,
        username=principal.identifier,
        role=principal.role,
        organization_id=principal.organization_id,
        organization_name=principal.organization_name,
    )


@router.post("/login", response_model=AdminSessionResponse)
async def admin_login_endpoint(
    request: Request,
    request_payload: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_admin_auth_service),
    api_rate_limiter: ApiRateLimiter = Depends(get_api_rate_limiter),
) -> AdminSessionResponse:
    """管理员登录：校验凭据并创建 admin 域会话。"""
    principal: AuthenticatedPrincipal = await authenticate_and_set_cookie(
        request,
        request_payload,
        response,
        auth_service=auth_service,
        api_rate_limiter=api_rate_limiter,
        cookie_name=ADMIN_SESSION_COOKIE_NAME,
        operation="admin_login",
    )
    return _to_session_response(principal)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def admin_logout_endpoint(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_admin_auth_service),
) -> None:
    """管理员登出：销毁 admin 域会话并清除 Cookie。"""
    session_token: str | None = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)
    if session_token:
        auth_service.logout(session_token)
    clear_session_cookie(response, cookie_name=ADMIN_SESSION_COOKIE_NAME)


@router.get("/me", response_model=AdminSessionResponse)
async def admin_me_endpoint(
    request: Request,
    auth_service: AuthService = Depends(get_admin_auth_service),
) -> AdminSessionResponse:
    """获取当前 admin 会话：触发滑动窗口续期。"""
    session_token: str | None = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    principal: AuthenticatedPrincipal | None = auth_service.resolve_session(session_token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话无效或已过期")
    return _to_session_response(principal)


@router.get("/oidc/status")
async def admin_oidc_status_endpoint(request: Request) -> dict[str, bool]:
    """返回管理员 OIDC 登录入口是否已完成配置。"""
    return {"enabled": bool(request.app.state.admin_oidc_enabled)}


@router.get("/oidc/start")
def admin_oidc_start_endpoint(
    request: Request,
    oidc_login_service: OidcLoginService | None = Depends(get_admin_oidc_login_service),
) -> Response:
    """创建短时登录事务并跳转到企业身份中心。"""
    if oidc_login_service is None:
        raise HTTPException(status_code=503, detail="oidc_unavailable")
    try:
        transaction_id, authorization_url = oidc_login_service.begin_login()
    except OidcAuthenticationError as oidc_error:
        reason = oidc_error.reason.value
        logger.warning("auth.oidc outcome=failed portal=admin reason=%s", reason)
        raise HTTPException(status_code=503, detail="oidc_unavailable") from None
    except Exception:
        logger.warning("auth.oidc outcome=failed portal=admin reason=provider_unavailable")
        raise HTTPException(status_code=503, detail="oidc_unavailable") from None

    response = RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=_OIDC_TRANSACTION_COOKIE_NAME,
        value=transaction_id,
        httponly=True,
        secure=request.app.state.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=_OIDC_TRANSACTION_COOKIE_MAX_AGE_SECONDS,
    )
    return response


@router.get("/oidc/callback")
def admin_oidc_callback_endpoint(
    request: Request,
    oidc_login_service: OidcLoginService | None = Depends(get_admin_oidc_login_service),
) -> Response:
    """消费回调事务，按已验证身份签发现有管理员会话。"""
    return build_oidc_callback_response(
        request,
        oidc_login_service,
        _OIDC_CALLBACK_RESPONSE_CONFIG,
    )
