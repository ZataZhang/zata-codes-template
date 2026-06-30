"""auth domains init

建立 public_user / admin_user 两套相互隔离的用户表，并移除被取代的示例
user_profile 表（双认证域分离）。

Revision ID: b2f1a4c9d3e7
Revises: da21c8e2e67c
Create Date: 2026-06-25 18:23:22.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f1a4c9d3e7"
down_revision: Union[str, Sequence[str], None] = "da21c8e2e67c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema：移除 user_profile，新建 public_user / admin_user。"""
    op.drop_table("user_profile")

    op.create_table(
        "public_user",
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="Public 用户主键 ID（UUID hex），同时用作业务资源 owner_id。",
        ),
        sa.Column(
            "email",
            sa.String(length=255),
            nullable=False,
            comment="登录邮箱，全局唯一，存储前归一化为小写。",
        ),
        sa.Column(
            "display_name",
            sa.String(length=128),
            nullable=False,
            comment="用户展示名称。",
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            comment="bcrypt 密码哈希，不存明文。",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="是否启用；禁用后无法登录且既有会话立即失效。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录创建时间，UTC，数据库端默认值。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录最近一次更新时间，UTC，数据库端自动维护。",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        comment="Public 域用户表，存储 C 端自助注册用户的认证与展示信息。",
    )
    op.create_index(op.f("ix_public_user_email"), "public_user", ["email"], unique=False)

    op.create_table(
        "admin_user",
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="Admin 用户主键 ID（UUID hex）。",
        ),
        sa.Column(
            "username",
            sa.String(length=64),
            nullable=False,
            comment="登录用户名，全局唯一，存储前归一化为小写。",
        ),
        sa.Column(
            "display_name",
            sa.String(length=128),
            nullable=False,
            comment="管理员展示名称。",
        ),
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            comment="bcrypt 密码哈希，不存明文。",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="是否启用；禁用后无法登录且既有会话立即失效。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录创建时间，UTC，数据库端默认值。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录最近一次更新时间，UTC，数据库端自动维护。",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        comment="Admin 域用户表，存储内部管理员的认证与展示信息。",
    )
    op.create_index(op.f("ix_admin_user_username"), "admin_user", ["username"], unique=False)


def downgrade() -> None:
    """Downgrade schema：删除双用户表并恢复 user_profile。"""
    op.drop_index(op.f("ix_admin_user_username"), table_name="admin_user")
    op.drop_table("admin_user")
    op.drop_index(op.f("ix_public_user_email"), table_name="public_user")
    op.drop_table("public_user")

    op.create_table(
        "user_profile",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
            comment="用户档案主键 ID，自增。",
        ),
        sa.Column(
            "username",
            sa.String(length=64),
            nullable=False,
            comment="登录用户名，全局唯一，长度 1~64。",
        ),
        sa.Column(
            "display_name",
            sa.String(length=128),
            nullable=True,
            comment="用户展示名，允许为空。",
        ),
        sa.Column("birth_date", sa.Date(), nullable=True, comment="用户出生日期，可为空。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录创建时间，UTC，数据库端默认值。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录最近一次更新时间，UTC，数据库端自动维护。",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
        comment="用户档案表，存储系统用户的基础身份信息与展示字段。",
    )
