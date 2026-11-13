"""管理员表添加邮箱与 OIDC 身份字段，用于安全首绑现有管理员。

Revision ID: c5c119af8d7c
Revises: 52899a5a681f
Create Date: 2026-11-13 12:07:39.000000

背景：管理员 OIDC 首绑实现见 ``src/backend/core/auth/oidc_login.py``。

设计要点：邮箱允许为空以兼容既有账号；两个唯一约束分别保证邮箱唯一和外部身份唯一。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from alembic import op


class _OidcIdentifierString(TypeDecorator[str]):
    """迁移内的 OIDC 身份列类型：MySQL 二进制、PostgreSQL 文本。"""

    impl = sa.String
    cache_ok = True

    def __init__(self, length: int) -> None:
        """设置最大 Unicode 字符数。"""
        self._length = length
        super().__init__(length=length)

    def load_dialect_impl(self, dialect: Dialect):
        """按目标数据库选择精确比较列类型。"""
        if dialect.name == "mysql":
            return dialect.type_descriptor(VARBINARY(self._length * 4))
        return dialect.type_descriptor(sa.String(self._length))


# revision identifiers, used by Alembic.
revision: str = "c5c119af8d7c"
down_revision: Union[str, Sequence[str], None] = "52899a5a681f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加管理员邮箱、OIDC 身份及唯一约束。"""
    with op.batch_alter_table("admin_user") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=320), nullable=True))
        batch_op.add_column(sa.Column("oidc_issuer", _OidcIdentifierString(512), nullable=True))
        batch_op.add_column(sa.Column("oidc_subject", _OidcIdentifierString(255), nullable=True))
        batch_op.create_unique_constraint("uq_admin_user_email", ["email"])
        batch_op.create_unique_constraint(
            "uq_admin_user_oidc_identity",
            ["oidc_issuer", "oidc_subject"],
        )


def downgrade() -> None:
    """删除管理员邮箱与 OIDC 身份字段。"""
    with op.batch_alter_table("admin_user") as batch_op:
        batch_op.drop_constraint("uq_admin_user_oidc_identity", type_="unique")
        batch_op.drop_constraint("uq_admin_user_email", type_="unique")
        batch_op.drop_column("oidc_subject")
        batch_op.drop_column("oidc_issuer")
        batch_op.drop_column("email")
