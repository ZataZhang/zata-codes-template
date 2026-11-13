"""组织管理用例。"""

from __future__ import annotations

from typing import Sequence

from backend.core.shared.interfaces.organization_repository import OrganizationRepository
from backend.core.shared.models.organization import DEFAULT_ORGANIZATION_ID, Organization

_MAX_ORGANIZATION_NAME_LENGTH: int = 128


def validate_organization_name(name: str) -> str:
    """清理并校验组织名称。

    Args:
        name (str): 请求中的组织名称。

    Returns:
        str: 去除首尾空白后的组织名称。

    Raises:
        ValueError: 名称为空或超过数据库列长度时。
    """
    normalized_name: str = name.strip()
    if not normalized_name:
        raise ValueError("organization_name_required")
    if len(normalized_name) > _MAX_ORGANIZATION_NAME_LENGTH:
        raise ValueError("organization_name_too_long")
    return normalized_name


class OrganizationDirectory:
    """供平台管理员维护组织目录的用例。"""

    def __init__(self, organization_repository: OrganizationRepository) -> None:
        """初始化组织目录。

        Args:
            organization_repository (OrganizationRepository): 组织持久化端口。
        """
        self._organization_repository = organization_repository

    def list_organizations(self) -> Sequence[Organization]:
        """列出全部组织。

        Returns:
            Sequence[Organization]: 按仓库顺序返回的组织目录。
        """
        return self._organization_repository.list_organizations()

    def create_organization(self, name: str) -> Organization:
        """创建组织并拒绝重复名称。

        Args:
            name (str): 新组织名称。

        Returns:
            Organization: 新建组织。

        Raises:
            ValueError: 名称为空、过长或与既有组织冲突时。
        """
        normalized_name: str = validate_organization_name(name)
        if self._organization_repository.find_by_name(normalized_name) is not None:
            raise ValueError("organization_name_conflict")
        return self._organization_repository.create(normalized_name)

    def set_organization_active(
        self, organization_id: str, *, is_active: bool
    ) -> Organization | None:
        """启用或停用组织，默认组织始终保持启用。

        Args:
            organization_id (str): 目标组织主键。
            is_active (bool): 目标状态。

        Returns:
            Organization | None: 更新后组织；目标不存在时返回 None。

        Raises:
            ValueError: 尝试停用默认组织时。
        """
        if organization_id == DEFAULT_ORGANIZATION_ID and not is_active:
            raise ValueError("default_organization_cannot_be_disabled")
        return self._organization_repository.set_active(organization_id, is_active=is_active)


__all__ = ["OrganizationDirectory", "validate_organization_name"]
