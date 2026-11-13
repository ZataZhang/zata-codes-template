"""Public 用户目录：admin 域管理 public 用户的用例。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.core.shared.interfaces.organization_repository import OrganizationRepository
from backend.core.shared.interfaces.user_account_repository import (
    UserAccountRepository,
)
from backend.core.shared.models.account_list_filter import AccountListFilter
from backend.core.shared.models.user_account import UserAccount

_DEFAULT_PAGE_SIZE: int = 50
_MAX_PAGE_SIZE: int = 200


@dataclass(frozen=True)
class PublicUserPage:
    """分页的 public 用户列表结果。

    Attributes:
        accounts (Sequence[UserAccount]): 当前页账户。
        total (int): 满足过滤条件的总条数。
    """

    accounts: Sequence[UserAccount]
    total: int


class PublicUserDirectory:
    """供 admin 域只读与启停 public 用户的管理用例。

    仅依赖 public 域的用户仓库端口，不触达 admin 用户体系，从而保证 admin
    管理能力被限定在 public 用户范围内。
    """

    def __init__(
        self,
        *,
        public_repository: UserAccountRepository,
        organization_repository: OrganizationRepository | None = None,
    ) -> None:
        """初始化目录用例。

        Args:
            public_repository (UserAccountRepository): public 域用户仓库。
            organization_repository (OrganizationRepository | None): 可选组织仓库；管理归属时必需。
        """
        self._public_repository = public_repository
        self._organization_repository = organization_repository

    def list_users(
        self,
        *,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        filters: AccountListFilter | None = None,
    ) -> PublicUserPage:
        """分页列出 public 用户。

        Args:
            page (int): 页码，从 1 开始。
            page_size (int): 每页条数，受 ``_MAX_PAGE_SIZE`` 上限约束。
            filters (AccountListFilter | None): 可选状态、关键字与组织筛选条件。

        Returns:
            PublicUserPage: 当前页账户与总数。
        """
        normalized_page: int = page if page >= 1 else 1
        normalized_page_size: int = max(1, min(page_size, _MAX_PAGE_SIZE))
        offset: int = (normalized_page - 1) * normalized_page_size
        account_filters: AccountListFilter = filters or AccountListFilter()
        accounts, total = self._public_repository.list_accounts(
            offset=offset,
            limit=normalized_page_size,
            filters=account_filters,
        )
        return PublicUserPage(accounts=accounts, total=total)

    def get_user(
        self, account_id: str, *, organization_id: str | None = None
    ) -> UserAccount | None:
        """按主键读取单个 public 用户。

        Args:
            account_id (str): public 用户主键。

        Returns:
            UserAccount | None: 命中的账户，未命中返回 None。
        """
        account: UserAccount | None = self._public_repository.get_by_id(account_id)
        if account is not None and organization_id is not None:
            if account.organization_id != organization_id:
                return None
        return account

    def set_user_active(
        self,
        account_id: str,
        is_active: bool,
        *,
        organization_id: str | None = None,
    ) -> UserAccount | None:
        """启用或禁用某个 public 用户。

        Args:
            account_id (str): public 用户主键。
            is_active (bool): 目标启用状态。

        Returns:
            UserAccount | None: 更新后的账户，未命中返回 None。
        """
        current_account: UserAccount | None = self.get_user(
            account_id,
            organization_id=organization_id,
        )
        if current_account is None:
            return None
        return self._public_repository.set_active(
            account_id,
            is_active,
            organization_id=organization_id,
        )

    def set_user_organization(self, account_id: str, organization_id: str) -> UserAccount | None:
        """把 public 用户归属调整到已存在的组织。"""
        if self._organization_repository is None:
            raise RuntimeError("organization_repository_unavailable")
        if self._organization_repository.get_by_id(organization_id) is None:
            raise ValueError("organization_not_found")
        return self._public_repository.set_organization(account_id, organization_id)
