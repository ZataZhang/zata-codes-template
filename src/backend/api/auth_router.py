"""Public 域认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.exceptions import HTTPException

from backend.api.dependencies import (
    PUBLIC_SESSION_COOKIE_NAME,
    get_public_auth_service,
)
from backend.api.schemas import LoginRequest, RegisterRequest, UserSessionResponse
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

_COOKIE_PATH: str = "/"
_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 60  # 60 天，与会话绝对上限一致
_COOKIE_SECURE: bool = False  # 本地开发使用 http；生产经反代终止 TLS 后应置 True


def _set_session_cookie(response: Response, token: str) -> None:
    """设置 public 域 HttpOnly 会话 Cookie。"""
    response.set_cookie(
        key=PUBLIC_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path=_COOKIE_PATH,
        max_age=_COOKIE_MAX_AGE_SECONDS,
    )


def _clear_session_cookie(response: Response) -> None:
    """清除 public 域会话 Cookie。"""
    response.delete_cookie(key=PUBLIC_SESSION_COOKIE_NAME, path=_COOKIE_PATH)


def _to_session_response(principal: AuthenticatedPrincipal) -> UserSessionResponse:
    """把已认证主体映射为 public 会话响应。"""
    return UserSessionResponse(
        user_id=principal.user_id,
        display_name=principal.display_name,
        email=principal.identifier,
    )


@router.post("/login", response_model=UserSessionResponse)
async def login_endpoint(
    request_payload: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_public_auth_service),
) -> UserSessionResponse:
    """用户登录：校验凭据并创建会话。"""
    try:
        token, principal = auth_service.authenticate(
            request_payload.identifier, request_payload.password
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    _set_session_cookie(response, token)
    return _to_session_response(principal)


@router.post("/register", response_model=UserSessionResponse, status_code=status.HTTP_201_CREATED)
async def register_endpoint(
    request_payload: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_public_auth_service),
) -> UserSessionResponse:
    """用户注册：创建账号并自动登录（主键由后端生成）。"""
    try:
        token, principal = auth_service.register(
            identifier=request_payload.email,
            display_name=request_payload.display_name,
            password=request_payload.password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    _set_session_cookie(response, token)
    return _to_session_response(principal)


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
    _clear_session_cookie(response)


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
