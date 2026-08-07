"""API DTO 定义。"""

from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    """登录请求。"""

    identifier: str
    password: str


class RegisterRequest(BaseModel):
    """注册请求（public 域；主键 user_id 由后端生成，不接受客户端传入）。"""

    display_name: str
    email: str
    password: str


class UserSessionResponse(BaseModel):
    """用户会话响应（public 域）。"""

    user_id: str
    display_name: str
    email: str


class AdminSessionResponse(BaseModel):
    """管理员会话响应（admin 域）。"""

    user_id: str
    display_name: str
    username: str


class PublicUserResponse(BaseModel):
    """admin 视角下的单个 public 用户。"""

    id: str
    email: str
    display_name: str
    status: str
    created_at: str | None = None


class PublicUserListResponse(BaseModel):
    """分页的 public 用户列表。"""

    items: list[PublicUserResponse]
    total: int
    page: int
    page_size: int
