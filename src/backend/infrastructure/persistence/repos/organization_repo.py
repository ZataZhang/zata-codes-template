"""组织仓库的 SQLAlchemy 实现。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.shared.interfaces.organization_repository import OrganizationRepository
from backend.core.shared.models.organization import Organization
from backend.infrastructure.persistence.models.organization import OrganizationModel


class SqlAlchemyOrganizationRepository(OrganizationRepository):
    """以短事务访问组织表。"""

    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        """初始化组织仓库。

        Args:
            session_factory (sessionmaker[Session]): 为每次仓库操作创建独立会话的工厂。
        """
        self._session_factory = session_factory

    def list_organizations(self) -> list[Organization]:
        """按名称列出组织。

        Returns:
            list[Organization]: 已创建的组织列表。
        """
        with self._session_factory() as session:
            organization_models = (
                session.query(OrganizationModel).order_by(OrganizationModel.name.asc()).all()
            )
            return [
                self._to_organization(organization_model)
                for organization_model in organization_models
            ]

    def create(self, name: str) -> Organization:
        """创建启用中的组织。

        Args:
            name (str): 组织名称。

        Returns:
            Organization: 新建组织。

        Raises:
            ValueError: 名称冲突时抛出 ``organization_name_conflict``。
        """
        now: datetime = datetime.now(timezone.utc)
        organization_model = OrganizationModel(
            id=uuid.uuid4().hex,
            name=name,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        try:
            with self._session_factory.begin() as session:
                session.add(organization_model)
                session.flush()
                return self._to_organization(organization_model)
        except IntegrityError as integrity_error:
            if self.find_by_name(name) is not None:
                raise ValueError("organization_name_conflict") from integrity_error
            raise

    def set_active(self, organization_id: str, *, is_active: bool) -> Organization | None:
        """更新组织启用状态。

        Args:
            organization_id (str): 组织主键。
            is_active (bool): 目标启用状态。

        Returns:
            Organization | None: 更新后组织；不存在时返回 None。
        """
        with self._session_factory.begin() as session:
            organization_model = session.get(OrganizationModel, organization_id)
            if organization_model is None:
                return None
            organization_model.is_active = is_active
            organization_model.updated_at = datetime.now(timezone.utc)
            return self._to_organization(organization_model)

    def get_by_id(self, organization_id: str) -> Organization | None:
        """按主键读取组织。

        Args:
            organization_id (str): 组织主键。

        Returns:
            Organization | None: 命中的组织；不存在时返回 None。
        """
        with self._session_factory() as session:
            organization_model = session.get(OrganizationModel, organization_id)
            return (
                self._to_organization(organization_model)
                if organization_model is not None
                else None
            )

    def find_by_name(self, name: str) -> Organization | None:
        """按名称读取组织。

        Args:
            name (str): 待查找的组织名称。

        Returns:
            Organization | None: 命中的组织；不存在时返回 None。
        """
        with self._session_factory() as session:
            organization_model = (
                session.query(OrganizationModel)
                .filter(OrganizationModel.name == name)
                .one_or_none()
            )
            return (
                self._to_organization(organization_model)
                if organization_model is not None
                else None
            )

    @staticmethod
    def _to_organization(organization_model: OrganizationModel) -> Organization:
        """把 ORM 行转换为领域组织对象。"""
        return Organization(
            id=organization_model.id,
            name=organization_model.name,
            is_active=organization_model.is_active,
            created_at=organization_model.created_at,
            updated_at=organization_model.updated_at,
        )


__all__ = ["SqlAlchemyOrganizationRepository"]
