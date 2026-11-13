"""平台管理员目录用例。"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from email.headerregistry import Address
from typing import Sequence

from backend.core.auth.password_policy import (
    is_password_within_byte_limit,
)
from backend.core.shared.interfaces.organization_repository import OrganizationRepository
from backend.core.shared.interfaces.password_hasher import PasswordHasher
from backend.core.shared.interfaces.user_account_repository import UserAccountRepository
from backend.core.shared.models.account_list_filter import AccountListFilter
from backend.core.shared.models.user_account import UserAccount

_MIN_PASSWORD_LENGTH: int = 6
_MAX_USERNAME_LENGTH: int = 64
_MAX_EMAIL_LENGTH: int = 320
_MAX_DISPLAY_NAME_LENGTH: int = 128
_ADMIN_LIST_PAGE_SIZE: int = 200


def is_valid_admin_email_address(email: str) -> bool:
    """使用标准库解析器判断管理员邮箱是否为完整地址。

    Args:
        email (str): 已去除首尾空白并转为小写的邮箱。

    Returns:
        bool: 邮箱具有有效本地部分和域名时返回 True。
    """
    try:
        parsed_address: Address = Address(addr_spec=email)
    except ValueError:
        return False
    return bool(parsed_address.username and parsed_address.domain)


@dataclass(frozen=True)
class AdminCreateCommand:
    """创建管理员所需字段。

    Attributes:
        username (str): 管理员登录名。
        email (str): 用于 OIDC 首绑的邮箱。
        display_name (str | None): 可选展示名称。
        role (str): ``platform`` 或 ``org``。
        organization_id (str | None): 组织管理员所属组织。
        password (str | None): 可选初始密码。
    """

    username: str
    email: str
    display_name: str | None
    role: str
    organization_id: str | None
    password: str | None


def validate_admin_create_command(
    command: AdminCreateCommand,
    *,
    organization_repository: OrganizationRepository,
    oidc_enabled: bool,
) -> AdminCreateCommand:
    """校验并归一化管理员创建字段。

    Args:
        command (AdminCreateCommand): 原始管理员创建字段。
        organization_repository (OrganizationRepository): 组织读取端口。
        oidc_enabled (bool): OIDC 客户端是否已完整装配。

    Returns:
        AdminCreateCommand: 归一化后的管理员创建字段。

    Raises:
        ValueError: 字段非法、组织不存在，或密码和 OIDC 登录条件不满足时。
    """
    normalized_username: str = command.username.strip().lower()
    normalized_email: str = command.email.strip().lower()
    if not normalized_username:
        raise ValueError("username_required")
    if len(normalized_username) > _MAX_USERNAME_LENGTH:
        raise ValueError("username_too_long")
    if not normalized_email:
        raise ValueError("email_required")
    if len(normalized_email) > _MAX_EMAIL_LENGTH:
        raise ValueError("email_too_long")
    if not is_valid_admin_email_address(normalized_email):
        raise ValueError("invalid_email")
    if command.role not in {"platform", "org"}:
        raise ValueError("invalid_admin_role")

    normalized_organization_id: str | None = command.organization_id
    if command.role == "platform":
        if normalized_organization_id is not None:
            raise ValueError("platform_admin_cannot_have_organization")
    else:
        normalized_organization_id = (
            normalized_organization_id.strip() if normalized_organization_id is not None else None
        )
        if not normalized_organization_id:
            raise ValueError("organization_required")
        if organization_repository.get_by_id(normalized_organization_id) is None:
            raise ValueError("organization_not_found")

    normalized_display_name: str | None = (
        command.display_name.strip() if command.display_name is not None else None
    )
    if normalized_display_name is not None and not normalized_display_name:
        raise ValueError("display_name_required")
    if normalized_display_name and len(normalized_display_name) > _MAX_DISPLAY_NAME_LENGTH:
        raise ValueError("display_name_too_long")
    normalized_display_name = normalized_display_name or normalized_username

    validated_password: str | None = None
    if command.password is None:
        if not oidc_enabled:
            raise ValueError("oidc_unavailable_password_required")
    else:
        validated_password = command.password
        if not is_password_within_byte_limit(validated_password):
            raise ValueError("password_too_long")
        if len(validated_password) < _MIN_PASSWORD_LENGTH:
            raise ValueError("password_too_short")

    return AdminCreateCommand(
        username=normalized_username,
        email=normalized_email,
        display_name=normalized_display_name,
        role=command.role,
        organization_id=normalized_organization_id,
        password=validated_password,
    )


class AdminDirectory:
    """供平台管理员维护两级管理员账号的用例。"""

    def __init__(
        self,
        *,
        admin_repository: UserAccountRepository,
        organization_repository: OrganizationRepository,
        password_hasher: PasswordHasher,
        oidc_enabled: bool,
    ) -> None:
        """初始化管理员目录。

        Args:
            admin_repository (UserAccountRepository): admin 域用户仓库。
            organization_repository (OrganizationRepository): 组织仓库。
            password_hasher (PasswordHasher): 密码哈希实现。
            oidc_enabled (bool): admin OIDC 客户端是否完整装配。
        """
        self._admin_repository = admin_repository
        self._organization_repository = organization_repository
        self._password_hasher = password_hasher
        self._oidc_enabled = oidc_enabled

    def list_admins(self) -> Sequence[UserAccount]:
        """列出所有管理员账户，不因数量限制而截断结果。

        Returns:
            Sequence[UserAccount]: 全部管理员账户。
        """
        admin_accounts: list[UserAccount] = []
        next_offset: int = 0
        total_count: int = 1
        while next_offset < total_count:
            account_page, total_count = self._admin_repository.list_accounts(
                offset=next_offset,
                limit=_ADMIN_LIST_PAGE_SIZE,
                filters=AccountListFilter(),
            )
            admin_accounts.extend(account_page)
            next_offset += len(account_page)
            if not account_page:
                break
        return admin_accounts

    def create_admin(self, command: AdminCreateCommand) -> UserAccount:
        """验证并创建平台管理员或组织管理员。

        Args:
            command (AdminCreateCommand): 管理员创建字段。

        Returns:
            UserAccount: 落库后的管理员账户。

        Raises:
            ValueError: 用户名 / 邮箱冲突或创建条件不满足时。
        """
        validated_command: AdminCreateCommand = validate_admin_create_command(
            command,
            organization_repository=self._organization_repository,
            oidc_enabled=self._oidc_enabled,
        )
        if self._admin_repository.find_by_identifier(validated_command.username) is not None:
            raise ValueError("username_conflict")
        if self._admin_repository.find_by_email(validated_command.email) is not None:
            raise ValueError("email_conflict")

        plain_password: str = (
            validated_command.password
            if validated_command.password is not None
            else secrets.token_urlsafe(32)
        )
        account = UserAccount(
            id=uuid.uuid4().hex,
            identifier=validated_command.username,
            display_name=validated_command.display_name or validated_command.username,
            password_hash=self._password_hasher.hash(plain_password),
            is_active=True,
            email=validated_command.email,
            role=validated_command.role,
            organization_id=validated_command.organization_id,
        )
        return self._admin_repository.create_unique(account)

    def set_admin_active(
        self, actor_id: str, account_id: str, *, is_active: bool
    ) -> UserAccount | None:
        """启用或禁用管理员，并禁止操作者禁用自己。

        Args:
            actor_id (str): 当前平台管理员主键。
            account_id (str): 目标管理员主键。
            is_active (bool): 目标启用状态。

        Returns:
            UserAccount | None: 更新后管理员；目标不存在时返回 None。

        Raises:
            ValueError: 操作者尝试禁用自己，或最后一名平台管理员受保护时。
        """
        if not is_active and actor_id == account_id:
            raise ValueError("self_disable")
        return self._admin_repository.set_active_with_platform_guard(account_id, is_active)

    def unbind_admin_oidc_identity(self, account_id: str) -> UserAccount | None:
        """清除管理员的本地 OIDC 绑定，不影响邮箱、密码或账号状态。

        Args:
            account_id (str): 目标管理员主键。

        Returns:
            UserAccount | None: 解绑后的管理员；目标不存在时返回 None。

        Raises:
            ValueError: 管理员当前没有完整的 OIDC 绑定时。
        """
        admin_account: UserAccount | None = self._admin_repository.get_by_id(account_id)
        if admin_account is None:
            return None
        if admin_account.oidc_issuer is None or admin_account.oidc_subject is None:
            raise ValueError("oidc_not_bound")
        unbound_account: UserAccount | None = self._admin_repository.unbind_oidc_identity(
            account_id
        )
        if unbound_account is not None:
            return unbound_account
        if self._admin_repository.get_by_id(account_id) is None:
            return None
        raise ValueError("oidc_not_bound")


__all__ = [
    "AdminCreateCommand",
    "AdminDirectory",
    "validate_admin_create_command",
]
