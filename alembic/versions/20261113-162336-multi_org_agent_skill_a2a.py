"""multi_org_agent_skill_a2a — 扩展 Run 组织/会话快照并创建 Agent、Skill 与 A2A 目录表。

Revision ID: 6b5270b7a87b
Revises: b93aa5cf0228
Create Date: 2026-11-13 16:23:36.000000

背景：在线 Agent 与 A2A 持久化契约见 ``src/backend/core/agent/``；组织归属规则沿用 ``src/backend/core/auth/``。

设计要点：``run.organization_id`` 回填为固定默认组织后设为非空，``conversation_id`` 与 ``execution_snapshot`` 冻结会话和执行来源；Skill 版本以 ``uq_skill_version_number`` 保证线性序号。A2A 凭据仅存哈希或密文。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b5270b7a87b"
down_revision: Union[str, Sequence[str], None] = "b93aa5cf0228"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """扩展 Canonical Run 并创建组织 Agent、Skill 版本及 A2A 目录。"""
    # 1. 先将所有存量 Run 明确归入上游迁移创建的默认组织，再建立不可空范围列。
    op.add_column(
        "run",
        sa.Column(
            "organization_id",
            sa.String(length=64),
            nullable=True,
            comment="Run 创建时所属组织；不随成员调动改变。",
        ),
    )
    op.execute(
        sa.text(
            "UPDATE run SET organization_id = :organization_id WHERE organization_id IS NULL"
        ).bindparams(organization_id="default")
    )
    op.add_column(
        "run",
        sa.Column(
            "conversation_id",
            sa.String(length=64),
            nullable=True,
            comment="所属会话 ID；历史 Run 为空。",
        ),
    )
    op.add_column(
        "run",
        sa.Column(
            "execution_snapshot",
            sa.JSON(),
            nullable=True,
            comment="创建时冻结的 Agent、模型与 Skill 版本快照。",
        ),
    )
    with op.batch_alter_table("run") as batch_op:
        batch_op.alter_column("organization_id", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_foreign_key(
            "fk_run_organization_id_organization", "organization", ["organization_id"], ["id"]
        )
        batch_op.create_index("ix_run_organization_id", ["organization_id"])
        batch_op.create_index("ix_run_conversation_id", ["conversation_id"])

    # 2. 创建版本化 Skill，再创建可选关联 Skill 的 Agent。
    op.create_table(
        "skill",
        sa.Column("id", sa.String(length=64), nullable=False, comment="稳定 Skill ID。"),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            nullable=False,
            comment="Skill 创建时所属组织，不随成员调动改变。",
        ),
        sa.Column("created_by", sa.String(length=64), nullable=False, comment="创建管理员 ID。"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="Skill 名称。"),
        sa.Column("description", sa.Text(), nullable=False, comment="Skill 说明。"),
        sa.Column("current_version", sa.Integer(), nullable=False, comment="当前版本序号。"),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_skill_organization_id_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_skill_organization_name"),
        comment="组织内声明式 Skill 目录。",
    )
    op.create_index("ix_skill_organization_id", "skill", ["organization_id"])
    op.create_table(
        "skill_version",
        sa.Column("id", sa.String(length=64), nullable=False, comment="Skill 版本 ID。"),
        sa.Column("skill_id", sa.String(length=64), nullable=False, comment="所属 Skill ID。"),
        sa.Column(
            "organization_id", sa.String(length=64), nullable=False, comment="版本创建时所属组织。"
        ),
        sa.Column("version", sa.Integer(), nullable=False, comment="从 1 开始的线性版本号。"),
        sa.Column("body", sa.Text(), nullable=False, comment="声明式 Skill 正文。"),
        sa.Column("checksum", sa.String(length=64), nullable=False, comment="正文 SHA-256。"),
        sa.Column(
            "created_by", sa.String(length=64), nullable=False, comment="创建版本的管理员 ID。"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
            comment="版本创建时间（UTC）。",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_skill_version_organization_id_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skill.id"], name="fk_skill_version_skill_id_skill", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id", "version", name="uq_skill_version_number"),
        comment="只追加的 Skill 正文版本历史。",
    )
    op.create_index("ix_skill_version_skill_id", "skill_version", ["skill_id"])
    op.create_index("ix_skill_version_organization_id", "skill_version", ["organization_id"])
    op.create_table(
        "agent",
        sa.Column("id", sa.String(length=64), nullable=False, comment="稳定 Agent ID。"),
        sa.Column(
            "organization_id",
            sa.String(length=64),
            nullable=False,
            comment="Agent 创建时所属组织，不随成员调动改变。",
        ),
        sa.Column("created_by", sa.String(length=64), nullable=False, comment="创建管理员 ID。"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="Agent 名称。"),
        sa.Column("description", sa.Text(), nullable=False, comment="Agent 说明。"),
        sa.Column("instructions", sa.Text(), nullable=False, comment="模型系统指令。"),
        sa.Column(
            "model_name", sa.String(length=255), nullable=True, comment="覆盖默认模型的可选名称。"
        ),
        sa.Column("skill_id", sa.String(length=64), nullable=True, comment="绑定 Skill ID。"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用。"),
        sa.Column("is_published", sa.Boolean(), nullable=False, comment="是否对本组织成员发布。"),
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_agent_organization_id_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"], ["skill.id"], name="fk_agent_skill_id_skill", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_agent_organization_name"),
        comment="组织内 Agent 定义与发布状态。",
    )
    op.create_index("ix_agent_organization_id", "agent", ["organization_id"])

    # 3. 为 A2A 双向授权提供凭据哈希与审批后的对端目录。
    op.create_table(
        "a2a_credential",
        sa.Column("id", sa.String(length=64), nullable=False, comment="凭据 ID。"),
        sa.Column(
            "organization_id", sa.String(length=64), nullable=False, comment="凭据组织范围。"
        ),
        sa.Column("agent_id", sa.String(length=64), nullable=False, comment="凭据可调用的 Agent。"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="凭据用途名称。"),
        sa.Column(
            "token_hash",
            sa.String(length=64),
            nullable=False,
            comment="服务凭据 SHA-256，不保存明文。",
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, comment="凭据是否可用。"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间（UTC）。"
        ),
        sa.Column(
            "revoked_at", sa.DateTime(timezone=True), nullable=True, comment="撤销时间（UTC）。"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_a2a_credential_organization_id_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent.id"], name="fk_a2a_credential_agent_id_agent", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_a2a_credential_token_hash"),
        comment="按组织与 Agent 限定的入站 A2A 服务凭据。",
    )
    op.create_index("ix_a2a_credential_organization_id", "a2a_credential", ["organization_id"])
    op.create_index("ix_a2a_credential_agent_id", "a2a_credential", ["agent_id"])
    op.create_table(
        "a2a_peer",
        sa.Column("id", sa.String(length=64), nullable=False, comment="对端目录 ID。"),
        sa.Column(
            "organization_id", sa.String(length=64), nullable=False, comment="登记对端的组织。"
        ),
        sa.Column("created_by", sa.String(length=64), nullable=False, comment="登记管理员 ID。"),
        sa.Column("name", sa.String(length=128), nullable=False, comment="对端名称。"),
        sa.Column("card_url", sa.Text(), nullable=False, comment="经登记的 Agent Card URL。"),
        sa.Column(
            "endpoint_url", sa.Text(), nullable=False, comment="经验证的 A2A 1.0 REST 端点。"
        ),
        sa.Column(
            "credential_ciphertext",
            sa.Text(),
            nullable=True,
            comment="经服务端密钥加密的出站凭据。",
        ),
        sa.Column(
            "is_approved", sa.Boolean(), nullable=False, comment="是否通过平台网络策略审批。"
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, comment="是否启用。"),
        sa.Column(
            "approved_by", sa.String(length=64), nullable=True, comment="审批平台管理员 ID。"
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
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organization.id"],
            name="fk_a2a_peer_organization_id_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "name", name="uq_a2a_peer_organization_name"),
        comment="组织登记并经平台批准的外部 A2A 对端目录。",
    )
    op.create_index("ix_a2a_peer_organization_id", "a2a_peer", ["organization_id"])


def downgrade() -> None:
    """删除新增 Agent/A2A 表并撤销 Run 组织与会话列。"""
    op.drop_index("ix_a2a_peer_organization_id", table_name="a2a_peer")
    op.drop_table("a2a_peer")
    op.drop_index("ix_a2a_credential_agent_id", table_name="a2a_credential")
    op.drop_index("ix_a2a_credential_organization_id", table_name="a2a_credential")
    op.drop_table("a2a_credential")
    op.drop_index("ix_agent_organization_id", table_name="agent")
    op.drop_table("agent")
    op.drop_index("ix_skill_version_organization_id", table_name="skill_version")
    op.drop_index("ix_skill_version_skill_id", table_name="skill_version")
    op.drop_table("skill_version")
    op.drop_index("ix_skill_organization_id", table_name="skill")
    op.drop_table("skill")
    with op.batch_alter_table("run") as batch_op:
        batch_op.drop_index("ix_run_conversation_id")
        batch_op.drop_index("ix_run_organization_id")
        batch_op.drop_constraint("fk_run_organization_id_organization", type_="foreignkey")
        batch_op.drop_column("execution_snapshot")
        batch_op.drop_column("conversation_id")
        batch_op.drop_column("organization_id")
