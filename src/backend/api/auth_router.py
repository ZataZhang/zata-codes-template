"""Public 域认证路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse
from zata_oidc import OidcAuthenticationError

from backend.api.dependencies import (
    PUBLIC_SESSION_COOKIE_NAME,
    get_api_rate_limiter,
    get_public_auth_service,
    get_public_oidc_login_service,
    get_registration_policy_service,
)
from backend.api.schemas import (
    LoginRequest,
    PublicRegistrationStatusResponse,
    RegisterRequest,
    UserSessionResponse,
)
from backend.api.security.authentication import authenticate_and_set_cookie
from backend.api.security.oidc_callback_response import (
    OidcCallbackResponseConfig,
    build_oidc_callback_response,
)
from backend.api.security.rate_limiter import ApiRateLimiter
from backend.api.security.session_cookies import clear_session_cookie, set_session_cookie
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.oidc_login import OidcLoginError, OidcLoginService
from backend.core.auth.registration_policy_service import (
    RegistrationPolicyService,
    RegistrationPolicyUnavailable,
)
from backend.core.auth.service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_OIDC_TRANSACTION_COOKIE_NAME: str = "public_oidc_txn"
_OIDC_TRANSACTION_COOKIE_MAX_AGE_SECONDS: int = 600
_OIDC_CALLBACK_RESPONSE_CONFIG = OidcCallbackResponseConfig(
    portal="public",
    transaction_cookie_name=_OIDC_TRANSACTION_COOKIE_NAME,
    session_cookie_name=PUBLIC_SESSION_COOKIE_NAME,
    failure_redirect_path="/login",
    success_redirect_path="/app/dashboard",
    account_conflict_error="account_exists",
)


def _to_session_response(principal: AuthenticatedPrincipal) -> UserSessionResponse:
    """把已认证主体映射为 public 会话响应。"""
    return UserSessionResponse(
        user_id=principal.user_id,
        display_name=principal.display_name,
        email=principal.identifier,
    )


@router.post("/login", response_model=UserSessionResponse)
async def login_endpoint(
    request: Request,
    request_payload: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_public_auth_service),
    api_rate_limiter: ApiRateLimiter = Depends(get_api_rate_limiter),
) -> UserSessionResponse:
    """用户登录：校验凭据并创建会话。"""
    principal: AuthenticatedPrincipal = await authenticate_and_set_cookie(
        request,
        request_payload,
        response,
        auth_service=auth_service,
        api_rate_limiter=api_rate_limiter,
        cookie_name=PUBLIC_SESSION_COOKIE_NAME,
        operation="public_login",
    )
    return _to_session_response(principal)


@router.post("/register", response_model=UserSessionResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    request: Request,
    request_payload: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_public_auth_service),
    api_rate_limiter: ApiRateLimiter = Depends(get_api_rate_limiter),
) -> UserSessionResponse:
    """用户注册：创建账号并自动登录（主键由后端生成）。"""
    await api_rate_limiter.check_auth_attempt(
        request,
        operation="public_register",
        identifier=request_payload.email,
    )
    try:
        token, principal = auth_service.register(
            identifier=request_payload.email,
            display_name=request_payload.display_name,
            password=request_payload.password,
        )
    except RegistrationPolicyUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="registration_policy_unavailable",
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    set_session_cookie(
        response,
        cookie_name=PUBLIC_SESSION_COOKIE_NAME,
        token=token,
        secure=request.app.state.auth_cookie_secure,
    )
    return _to_session_response(principal)


@router.get("/registration-status", response_model=PublicRegistrationStatusResponse)
def public_registration_status_endpoint(
    policy_service: RegistrationPolicyService = Depends(get_registration_policy_service),
) -> PublicRegistrationStatusResponse:
    """公开返回注册渠道状态，不泄露邮箱域名白名单。"""
    try:
        policy = policy_service.get_registration_policy()
    except RegistrationPolicyUnavailable as unavailable_error:
        logger.warning(
            "registration_policy outcome=unavailable reason=%s",
            unavailable_error.reason,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="registration_policy_unavailable",
        ) from None
    return PublicRegistrationStatusResponse(registration_mode=policy.registration_mode)


@router.get("/oidc/status")
def public_oidc_status_endpoint(request: Request) -> dict[str, bool]:
    """返回 public OIDC 登录入口是否已完成配置。"""
    return {"enabled": bool(request.app.state.public_oidc_enabled)}


@router.get("/oidc/start")
def public_oidc_start_endpoint(
    request: Request,
    oidc_login_service: OidcLoginService | None = Depends(get_public_oidc_login_service),
) -> Response:
    """创建一次性 public OIDC 登录事务并跳转身份中心。"""
    if oidc_login_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="oidc_unavailable",
        )
    try:
        transaction_id, authorization_url = oidc_login_service.begin_login()
    except (OidcAuthenticationError, OidcLoginError) as oidc_error:
        reason = (
            oidc_error.reason.value
            if isinstance(oidc_error, OidcAuthenticationError)
            else oidc_error.reason.value
        )
        logger.warning("auth.oidc outcome=failed portal=public reason=%s", reason)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="oidc_unavailable",
        ) from None
    except Exception:
        logger.warning("auth.oidc outcome=failed portal=public reason=provider_unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="oidc_unavailable",
        ) from None
    redirect_response = RedirectResponse(authorization_url, status_code=status.HTTP_302_FOUND)
    redirect_response.set_cookie(
        key=_OIDC_TRANSACTION_COOKIE_NAME,
        value=transaction_id,
        httponly=True,
        secure=request.app.state.auth_cookie_secure,
        samesite="lax",
        path="/",
        max_age=_OIDC_TRANSACTION_COOKIE_MAX_AGE_SECONDS,
    )
    return redirect_response


@router.get("/oidc/callback")
def public_oidc_callback_endpoint(
    request: Request,
    oidc_login_service: OidcLoginService | None = Depends(get_public_oidc_login_service),
) -> Response:
    """消费 public OIDC 回调并安全创建或恢复 public 会话。"""
    return build_oidc_callback_response(
        request,
        oidc_login_service,
        _OIDC_CALLBACK_RESPONSE_CONFIG,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_public_auth_service),
) -> None:
    """用户登出：销毁会话并清除 Cookie。"""
    session_token: str | None = request.cookies.get(PUBLIC_SESSION_COOKIE_NAME)
    if session_token:
        auth_service.logout(session_token)
    clear_session_cookie(response, cookie_name=PUBLIC_SESSION_COOKIE_NAME)


@router.get("/me", response_model=UserSessionResponse)
async def get_current_session_endpoint(
    request: Request,
    auth_service: AuthService = Depends(get_public_auth_service),
) -> UserSessionResponse:
    """获取当前会话：触发滑动窗口续期。"""
    session_token: str | None = request.cookies.get(PUBLIC_SESSION_COOKIE_NAME)
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    principal: AuthenticatedPrincipal | None = auth_service.resolve_session(session_token)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话无效或已过期")
    return _to_session_response(principal)
