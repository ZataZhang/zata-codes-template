"""Admin 域用户 ORM 模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.types import OidcIdentifierString

from .base import TimestampMixin
from .organization import OrganizationModel


class AdminUserModel(Base, TimestampMixin):
    """Admin 域用户表（内部管理员，不开放自助注册）。

    仅由种子流程或内部接口创建，与 ``public_user`` 物理隔离。
    """

    __tablename__ = "admin_user"
    __table_args__ = (
        UniqueConstraint("email", name="uq_admin_user_email"),
        UniqueConstraint(
            "oidc_issuer",
            "oidc_subject",
            name="uq_admin_user_oidc_identity",
        ),
        CheckConstraint(
            "(role = 'platform' AND organization_id IS NULL) OR "
            "(role = 'org' AND organization_id IS NOT NULL)",
            name="ck_admin_user_role_organization",
        ),
        {"comment": "Admin 域用户表，存储内部管理员的认证与展示信息。"},
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
    email: Mapped[str | None] = mapped_column(
        String(320), nullable=True, comment="用于首次绑定企业身份的管理员邮箱。"
    )
    oidc_issuer: Mapped[str | None] = mapped_column(
        OidcIdentifierString(512), nullable=True, comment="已绑定企业身份的签发者 URL。"
    )
    oidc_subject: Mapped[str | None] = mapped_column(
        OidcIdentifierString(255),
        nullable=True,
        comment="已绑定企业身份在签发者范围内的稳定主键。",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用；禁用后无法登录且既有会话立即失效。",
    )
    role: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="platform",
        server_default="platform",
        comment="管理员角色：platform 或 org。",
    )
    organization_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("organization.id", name="fk_admin_user_organization_id_organization"),
        nullable=True,
        index=True,
        comment="组织管理员所属组织；平台管理员为空。",
    )
    organization: Mapped[OrganizationModel | None] = relationship(lazy="joined")
