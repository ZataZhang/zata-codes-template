"""Public 用户目录：admin 域管理 public 用户的用例。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from backend.core.shared.interfaces.user_account_repository import (
    UserAccountRepository,
)
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

    def __init__(self, public_repository: UserAccountRepository) -> None:
        """初始化目录用例。

        Args:
            public_repository (UserAccountRepository): public 域用户仓库。
        """
        self._public_repository = public_repository

    def list_users(
        self,
        *,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
        status_filter: str | None = None,
        keyword: str | None = None,
    ) -> PublicUserPage:
        """分页列出 public 用户。

        Args:
            page (int): 页码，从 1 开始。
            page_size (int): 每页条数，受 ``_MAX_PAGE_SIZE`` 上限约束。
            status_filter (str | None): ``"active"`` / ``"disabled"`` 或 None。
            keyword (str | None): 对邮箱与展示名做模糊匹配的关键字。

        Returns:
            PublicUserPage: 当前页账户与总数。
        """
        normalized_page: int = page if page >= 1 else 1
        normalized_page_size: int = max(1, min(page_size, _MAX_PAGE_SIZE))
        offset: int = (normalized_page - 1) * normalized_page_size
        accounts, total = self._public_repository.list_accounts(
            offset=offset,
            limit=normalized_page_size,
            status_filter=status_filter,
            keyword=keyword,
        )
        return PublicUserPage(accounts=accounts, total=total)

    def get_user(self, account_id: str) -> UserAccount | None:
        """按主键读取单个 public 用户。

        Args:
            account_id (str): public 用户主键。

        Returns:
            UserAccount | None: 命中的账户，未命中返回 None。
        """
        return self._public_repository.get_by_id(account_id)

    def set_user_active(self, account_id: str, is_active: bool) -> UserAccount | None:
        """启用或禁用某个 public 用户。

        Args:
            account_id (str): public 用户主键。
            is_active (bool): 目标启用状态。

        Returns:
            UserAccount | None: 更新后的账户，未命中返回 None。
        """
        return self._public_repository.set_active(account_id, is_active)
