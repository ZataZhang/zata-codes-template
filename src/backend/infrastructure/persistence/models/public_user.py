"""Public 域用户 ORM 模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class PublicUserModel(Base, TimestampMixin):
    """Public 域用户表（C 端自助注册用户）。

    与 ``admin_user`` 物理隔离：两套用户体系互不读写对方的表。
    """

    __tablename__ = "public_user"
    __table_args__ = (
        {
            "comment": "Public 域用户表，存储 C 端自助注册用户的认证与展示信息。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="Public 用户主键 ID（UUID hex），同时用作业务资源 owner_id。",
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="登录邮箱，全局唯一，存储前归一化为小写。",
    )
    display_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="用户展示名称。",
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="bcrypt 密码哈希，不存明文。",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用；禁用后无法登录且既有会话立即失效。",
    )
