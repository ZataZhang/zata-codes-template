"""创建默认组织、回填用户归属并增加管理员角色约束。

Revision ID: b93aa5cf0228
Revises: 8ebb55cb460e
Create Date: 2026-11-13 12:57:32.000000

背景：组织与管理员授权语义见 ``src/backend/core/auth/admin_directory.py`` 和 ``directory.py``。

设计要点：迁移插入固定 ``default`` 组织并将存量用户迁入；``ck_admin_user_role_organization`` 保证平台管理员不关联组织、组织管理员必有关联组织。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b93aa5cf0228"
down_revision: Union[str, Sequence[str], None] = "8ebb55cb460e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建组织表，回填普通用户归属并增加管理员角色约束。"""
    op.create_table(
        "organization",
        sa.Column(
            "id",
            sa.String(length=64),
            nullable=False,
            comment="组织主键 ID；默认组织固定为 default。",
        ),
        sa.Column(
            "name",
            sa.String(length=128),
            nullable=False,
            comment="组织展示名称，全局唯一。",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            comment="组织启用状态；停用后成员无法建立或继续使用会话。",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="记录创建时间，UTC，数据库端默认值。",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="记录最近一次更新时间，UTC，数据库端自动维护。",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_organization_name"),
        comment="平台内组织目录，保存组织名称与启用状态。",
    )
    organization_table = sa.table(
        "organization",
        sa.column("id", sa.String(length=64)),
        sa.column("name", sa.String(length=128)),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        organization_table,
        [{"id": "default", "name": "默认组织", "is_active": True}],
    )

    op.add_column(
        "public_user",
        sa.Column(
            "organization_id",
            sa.String(length=64),
            nullable=True,
            comment="用户所属组织；当前用户只归属一个组织。",
        ),
    )
    database_connection = op.get_bind()
    database_connection.execute(
        sa.text("UPDATE public_user SET organization_id = :organization_id"),
        {"organization_id": "default"},
    )
    with op.batch_alter_table("public_user") as batch_op:
        batch_op.alter_column(
            "organization_id",
            existing_type=sa.String(length=64),
            nullable=False,
            server_default="default",
        )
        batch_op.create_foreign_key(
            "fk_public_user_organization_id_organization",
            "organization",
            ["organization_id"],
            ["id"],
        )
        batch_op.create_index("ix_public_user_organization_id", ["organization_id"])

    with op.batch_alter_table("admin_user") as batch_op:
        batch_op.add_column(
            sa.Column(
                "role",
                sa.String(length=16),
                server_default="platform",
                nullable=False,
                comment="管理员角色：platform 或 org。",
            )
        )
        batch_op.add_column(
            sa.Column(
                "organization_id",
                sa.String(length=64),
                nullable=True,
                comment="组织管理员所属组织；平台管理员为空。",
            )
        )
        batch_op.create_foreign_key(
            "fk_admin_user_organization_id_organization",
            "organization",
            ["organization_id"],
            ["id"],
        )
        batch_op.create_index("ix_admin_user_organization_id", ["organization_id"])
        batch_op.create_check_constraint(
            "ck_admin_user_role_organization",
            "(role = 'platform' AND organization_id IS NULL) OR "
            "(role = 'org' AND organization_id IS NOT NULL)",
        )


def downgrade() -> None:
    """删除管理员角色和普通用户组织归属字段。"""
    with op.batch_alter_table("admin_user") as batch_op:
        batch_op.drop_constraint("ck_admin_user_role_organization", type_="check")
        batch_op.drop_constraint(
            "fk_admin_user_organization_id_organization",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_admin_user_organization_id")
        batch_op.drop_column("organization_id")
        batch_op.drop_column("role")
    with op.batch_alter_table("public_user") as batch_op:
        batch_op.drop_constraint(
            "fk_public_user_organization_id_organization",
            type_="foreignkey",
        )
        batch_op.drop_index("ix_public_user_organization_id")
        batch_op.drop_column("organization_id")
    op.drop_table("organization")
