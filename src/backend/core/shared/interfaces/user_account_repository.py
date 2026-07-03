"""用户账户仓库抽象端口（按认证域分别实现）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from backend.core.shared.models.user_account import UserAccount


class UserAccountRepository(ABC):
    """单个认证域的用户账户数据访问端口。

    每个认证域（public / admin）由独立实现绑定到独立的物理表，从而在
    数据层实现两套用户体系的隔离：一个域的仓库永远不会读写另一个域的表。
    """

    @abstractmethod
    def find_by_identifier(self, identifier: str) -> UserAccount | None:
        """按登录标识（调用方已归一化为小写）查账户。

        Args:
            identifier (str): 归一化后的登录标识。

        Returns:
            UserAccount | None: 命中的账户，未命中返回 None。
        """

    @abstractmethod
    def get_by_id(self, account_id: str) -> UserAccount | None:
        """按主键查账户。

        Args:
            account_id (str): 账户主键。

        Returns:
            UserAccount | None: 命中的账户，未命中返回 None。
        """

    @abstractmethod
    def create(self, account: UserAccount) -> UserAccount:
        """持久化新账户并返回落库后的实体。

        Args:
            account (UserAccount): 待创建账户（含已生成的主键与哈希）。

        Returns:
            UserAccount: 落库后的账户（含 ``created_at``）。

        Raises:
            ValueError: 当登录标识已存在等唯一性约束冲突时。
        """

    @abstractmethod
    def set_active(self, account_id: str, is_active: bool) -> UserAccount | None:
        """更新账户启用状态。

        Args:
            account_id (str): 账户主键。
            is_active (bool): 目标启用状态。

        Returns:
            UserAccount | None: 更新后的账户，未命中返回 None。
        """

    @abstractmethod
    def set_password(self, account_id: str, password_hash: str) -> UserAccount | None:
        """更新账户密码哈希。

        Args:
            account_id (str): 账户主键。
            password_hash (str): 新的 bcrypt 密码哈希。

        Returns:
            UserAccount | None: 更新后的账户，未命中返回 None。
        """

    @abstractmethod
    def list_accounts(
        self,
        *,
        offset: int,
        limit: int,
        status_filter: str | None,
        keyword: str | None,
    ) -> tuple[Sequence[UserAccount], int]:
        """分页列出账户（供 admin 管理使用）。

        Args:
            offset (int): 跳过的记录数。
            limit (int): 本页最大返回条数。
            status_filter (str | None): ``"active"`` / ``"disabled"`` 或 None（不过滤）。
            keyword (str | None): 对登录标识与展示名做模糊匹配的关键字。

        Returns:
            tuple[Sequence[UserAccount], int]: (当前页账户, 满足条件的总数)。
        """
