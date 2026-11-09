"""认证会话 Cookie 的共用接入层处理。"""

from __future__ import annotations

from fastapi import Response

_COOKIE_PATH: str = "/"
_COOKIE_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 60


def set_session_cookie(
    response: Response,
    *,
    cookie_name: str,
    token: str,
    secure: bool,
) -> None:
    """设置 HttpOnly 会话 Cookie。

    Args:
        response (Response): 当前 HTTP 响应。
        cookie_name (str): public 或 admin 域的 Cookie 名。
        token (str): 服务端会话 token。
        secure (bool): 是否仅通过 HTTPS 发送 Cookie。
    """
    response.set_cookie(
        key=cookie_name,
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=_COOKIE_PATH,
        max_age=_COOKIE_MAX_AGE_SECONDS,
    )


def clear_session_cookie(response: Response, *, cookie_name: str) -> None:
    """清除指定认证域的会话 Cookie。

    Args:
        response (Response): 当前 HTTP 响应。
        cookie_name (str): public 或 admin 域的 Cookie 名。
    """
    response.delete_cookie(key=cookie_name, path=_COOKIE_PATH)


__all__ = ["clear_session_cookie", "set_session_cookie"]
