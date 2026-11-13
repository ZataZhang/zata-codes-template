"""组织数据访问抽象端口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from backend.core.shared.models.organization import Organization


class OrganizationRepository(ABC):
    """组织信息的持久化访问契约。"""

    @abstractmethod
    def list_organizations(self) -> Sequence[Organization]:
        """按名称列出组织。

        Returns:
            Sequence[Organization]: 已创建组织列表。
        """

    @abstractmethod
    def create(self, name: str) -> Organization:
        """创建启用中的组织。

        Args:
            name (str): 已清理并校验的组织名称。

        Returns:
            Organization: 新建组织。

        Raises:
            ValueError: 名称已被占用时抛出 ``organization_name_conflict``。
        """

    @abstractmethod
    def set_active(self, organization_id: str, *, is_active: bool) -> Organization | None:
        """更新组织启用状态。

        Args:
            organization_id (str): 组织主键。
            is_active (bool): 目标状态。

        Returns:
            Organization | None: 更新后组织；主键不存在时返回 None。
        """

    @abstractmethod
    def get_by_id(self, organization_id: str) -> Organization | None:
        """按主键读取组织。

        Args:
            organization_id (str): 组织主键。

        Returns:
            Organization | None: 命中的组织；不存在时返回 None。
        """

    @abstractmethod
    def find_by_name(self, name: str) -> Organization | None:
        """按名称查找组织。

        Args:
            name (str): 待查找的名称。

        Returns:
            Organization | None: 命中的组织；不存在时返回 None。
        """


__all__ = ["OrganizationRepository"]
