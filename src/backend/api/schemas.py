"""API DTO 定义。"""

from __future__ import annotations

from typing import Annotated, Literal

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
    role: Literal["platform", "org"] = "platform"
    organization_id: str | None = None
    organization_name: str | None = None


class OrganizationCreateRequest(BaseModel):
    """创建组织请求。"""

    name: str = Field(min_length=1, max_length=128)


class OrganizationResponse(BaseModel):
    """组织管理响应。"""

    id: str
    name: str
    is_active: bool
    created_at: str | None = None


class OrganizationListResponse(BaseModel):
    """组织管理列表响应。"""

    items: list[OrganizationResponse]


class AdminCreateRequest(BaseModel):
    """创建管理员请求。"""

    username: str = Field(min_length=1, max_length=64)
    email: str = Field(min_length=3, max_length=320)
    display_name: str | None = Field(default=None, min_length=1, max_length=128)
    role: Literal["platform", "org"]
    organization_id: str | None = None
    password: PasswordText | None = None


class AdminDirectoryResponse(BaseModel):
    """管理员管理响应。"""

    id: str
    username: str
    display_name: str
    email: str | None = None
    role: Literal["platform", "org"]
    organization_id: str | None = None
    organization_name: str | None = None
    status: Literal["active", "disabled"]
    oidc_bound: bool
    created_at: str | None = None


class AdminDirectoryListResponse(BaseModel):
    """管理员管理列表响应。"""

    items: list[AdminDirectoryResponse]


class RegistrationPolicyRequest(BaseModel):
    """管理端注册策略更新请求。"""

    registration_mode: Literal["both", "oidc_only", "closed"]
    allowed_email_domains: list[str]


class RegistrationPolicyResponse(BaseModel):
    """管理端注册策略响应。"""

    registration_mode: Literal["both", "oidc_only", "closed"]
    allowed_email_domains: list[str]


class PublicRegistrationStatusResponse(BaseModel):
    """仅含前台注册模式的公开状态响应。"""

    registration_mode: Literal["both", "oidc_only", "closed"]


class PublicUserResponse(BaseModel):
    """admin 视角下的单个 public 用户。"""

    id: str
    email: str
    display_name: str
    status: str
    created_at: str | None = None
    organization_id: str
    organization_name: str


class PublicUserOrganizationRequest(BaseModel):
    """普通用户归属调整请求。"""

    organization_id: str = Field(min_length=1, max_length=64)


class PublicUserListResponse(BaseModel):
    """分页的 public 用户列表。"""

    items: list[PublicUserResponse]
    total: int
    page: int
    page_size: int
