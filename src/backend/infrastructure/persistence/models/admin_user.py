"""Admin 域用户 ORM 模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class AdminUserModel(Base, TimestampMixin):
    """Admin 域用户表（内部管理员，不开放自助注册）。

    仅由种子流程或内部接口创建，与 ``public_user`` 物理隔离。
    """

    __tablename__ = "admin_user"
    __table_args__ = (
        {
            "comment": "Admin 域用户表，存储内部管理员的认证与展示信息。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="Admin 用户主键 ID（UUID hex）。",
    )
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        comment="登录用户名，全局唯一，存储前归一化为小写。",
    )
    display_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="管理员展示名称。",
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
