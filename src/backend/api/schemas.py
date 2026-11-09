"""API DTO 定义。"""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from backend.core.auth.password_policy import (
    MAX_PASSWORD_UTF8_BYTES,
    is_password_within_byte_limit,
)


def _validate_bcrypt_password_bytes(password: str) -> str:
    """拒绝超过 bcrypt 有效输入长度的密码，避免尾部被静默截断。"""
    if not is_password_within_byte_limit(password):
        raise ValueError(f"Password must not exceed {MAX_PASSWORD_UTF8_BYTES} UTF-8 bytes")
    return password


PasswordText = Annotated[
    str,
    Field(min_length=1, max_length=MAX_PASSWORD_UTF8_BYTES),
    AfterValidator(_validate_bcrypt_password_bytes),
]


class LoginRequest(BaseModel):
    """登录请求。"""

    identifier: str = Field(min_length=1, max_length=320)
    password: PasswordText


class RegisterRequest(BaseModel):
    """注册请求（public 域；主键 user_id 由后端生成，不接受客户端传入）。"""

    display_name: str = Field(min_length=1, max_length=80)
    email: str = Field(min_length=3, max_length=320)
    password: PasswordText


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
