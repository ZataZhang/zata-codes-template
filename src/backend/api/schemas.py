"""API DTO 定义。"""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登录请求。"""

    identifier: str
    password: str


class UserSessionResponse(BaseModel):
    """用户会话响应。"""

    user_id: str
    display_name: str
    email: str
