"""组织持久化 ORM 模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class OrganizationModel(Base, TimestampMixin):
    """组织表，只存储名称、启用状态与时间戳。"""

    __tablename__ = "organization"
    __table_args__ = (
        UniqueConstraint("name", name="uq_organization_name"),
        {"comment": "平台内组织目录，保存组织名称与启用状态。"},
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="组织主键 ID；默认组织固定为 default。",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="组织展示名称，全局唯一。",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="组织启用状态；停用后成员无法建立或继续使用会话。",
    )


__all__ = ["OrganizationModel"]
