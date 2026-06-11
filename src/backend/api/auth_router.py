"""认证路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.exceptions import HTTPException

from backend.api.dependencies import get_auth_use_case, get_session_token
from backend.api.schemas import LoginRequest, UserSessionResponse
from backend.core.use_cases.auth import AuthUseCase, User

_AUTH_COOKIE_NAME: str = "session_id"
_AUTH_COOKIE_PATH: str = "/"
_AUTH_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 60  # 60 天，与绝对上限一致

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    """设置 HttpOnly session cookie。"""
    response.set_cookie(
        key=_AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # 本地开发使用 http
        samesite="lax",
        path=_AUTH_COOKIE_PATH,
        max_age=_AUTH_COOKIE_MAX_AGE_SECONDS,
    )


def _clear_session_cookie(response: Response) -> None:
    """清除 session cookie。"""
    response.delete_cookie(key=_AUTH_COOKIE_NAME, path=_AUTH_COOKIE_PATH)


@router.post("/login", response_model=UserSessionResponse)
async def login_endpoint(
    request_payload: LoginRequest,
    response: Response,
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
) -> UserSessionResponse:
    """用户登录：验证凭据并创建 Session。"""
    try:
        token, user = auth_use_case.login(
            identifier=request_payload.identifier,
            password=request_payload.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    _set_session_cookie(response, token)
    return UserSessionResponse(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout_endpoint(
    response: Response,
    session_token: str | None = Depends(get_session_token),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
) -> None:
    """用户登出：销毁 Session 并清除 Cookie。"""
    if session_token:
        auth_use_case.logout(session_token)
    _clear_session_cookie(response)


@router.get("/me", response_model=UserSessionResponse)
async def get_current_session_endpoint(
    session_token: str | None = Depends(get_session_token),
    auth_use_case: AuthUseCase = Depends(get_auth_use_case),
) -> UserSessionResponse:
    """获取当前会话：触发滑动窗口续期。"""
    if session_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")

    user: User | None = auth_use_case.get_current_session(session_token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已过期"
        )

    return UserSessionResponse(
        user_id=user.user_id,
        display_name=user.display_name,
        email=user.email,
    )
