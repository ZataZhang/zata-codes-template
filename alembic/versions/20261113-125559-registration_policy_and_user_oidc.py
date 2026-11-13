"""新增注册策略存储与 public 用户 OIDC 身份列。

Revision ID: 8ebb55cb460e
Revises: c5c119af8d7c
Create Date: 2026-11-13 12:55:59.000000

背景：注册策略与 public OIDC 绑定行为见 ``src/backend/core/auth/registration_policy_service.py`` 和 ``oidc_login.py``。

设计要点：``system_settings`` 以 key 主键存 JSON 文本；``public_user`` 的 OIDC 身份列可空并由 ``uq_public_user_oidc_identity`` 保证唯一。MySQL 使用 VARBINARY 保持 issuer/subject 精确区分大小写及尾随字符。
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import VARBINARY
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from alembic import op


class _OidcIdentifierString(TypeDecorator[str]):
    """迁移内使用精确语义的 OIDC 身份列类型。"""

    impl = sa.String
    cache_ok = True

    def __init__(self, length: int) -> None:
        """设置最大 Unicode 字符数。"""
        self._length = length
        super().__init__(length=length)

    def load_dialect_impl(self, dialect: Dialect):
        """MySQL 使用二进制比较，其他数据库使用精确文本比较。"""
        if dialect.name == "mysql":
            return dialect.type_descriptor(VARBINARY(self._length * 4))
        return dialect.type_descriptor(sa.String(self._length))


# revision identifiers, used by Alembic.
revision: str = "8ebb55cb460e"
down_revision: Union[str, Sequence[str], None] = "c5c119af8d7c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建设置表并添加 public OIDC 身份列。"""
    op.create_table(
        "system_settings",
        sa.Column(
            "key",
            sa.String(length=128),
            nullable=False,
            comment="设置键，例如 registration_policy。",
        ),
        sa.Column(
            "value",
            sa.Text(),
            nullable=False,
            comment="设置值的 JSON 文本。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="设置最近更新时间，UTC，数据库端默认值。",
        ),
        sa.PrimaryKeyConstraint("key"),
        comment="系统级键值设置，以 JSON 文本保存每项配置。",
    )
    with op.batch_alter_table("public_user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "oidc_issuer",
                _OidcIdentifierString(512),
                nullable=True,
                comment="已绑定企业身份的签发者 URL。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "oidc_subject",
                _OidcIdentifierString(255),
                nullable=True,
                comment="已绑定企业身份在签发者范围内的稳定主键。",
            )
        )
        batch_op.create_unique_constraint(
            "uq_public_user_oidc_identity",
            ["oidc_issuer", "oidc_subject"],
        )


def downgrade() -> None:
    """删除 public OIDC 身份列与注册策略存储表。"""
    with op.batch_alter_table("public_user") as batch_op:
        batch_op.drop_constraint("uq_public_user_oidc_identity", type_="unique")
        batch_op.drop_column("oidc_subject")
        batch_op.drop_column("oidc_issuer")
    op.drop_table("system_settings")
