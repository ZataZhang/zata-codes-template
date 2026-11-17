"""skill_write_idempotency — 为 Skill 创建与版本写入增加重试键和请求摘要，避免重复写入。

Revision ID: 26e8967fcd01
Revises: 6b5270b7a87b
Create Date: 2026-11-13 21:57:39.000000

背景：Skill 串行写入与重试语义由 ``src/backend/core/agent/skills.py`` 统一提供。

设计要点：``uq_skill_create_idempotency`` 限定组织内创建重试键唯一，
``uq_skill_version_write_idempotency`` 限定同一 Skill 的版本重试键唯一；请求摘要用于拒绝同键不同内容。
空键允许历史记录与未提供重试键的调用继续存在，PostgreSQL 与 MySQL 共用同一约束定义。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "26e8967fcd01"
down_revision: Union[str, Sequence[str], None] = "6b5270b7a87b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """增加 Skill 创建和版本写入的可空重试键、请求摘要及唯一约束。"""
    op.add_column(
        "skill",
        sa.Column(
            "idempotency_key_hash",
            sa.String(length=64),
            nullable=True,
            comment="创建请求重试键摘要。",
        ),
    )
    op.add_column(
        "skill",
        sa.Column(
            "request_checksum",
            sa.String(length=64),
            nullable=True,
            comment="创建请求内容摘要，用于检测重试键冲突。",
        ),
    )
    op.create_index(
        "uq_skill_create_idempotency",
        "skill",
        ["organization_id", "idempotency_key_hash"],
        unique=True,
    )
    op.add_column(
        "skill_version",
        sa.Column(
            "idempotency_key_hash",
            sa.String(length=64),
            nullable=True,
            comment="版本写入重试键摘要。",
        ),
    )
    op.add_column(
        "skill_version",
        sa.Column(
            "request_checksum",
            sa.String(length=64),
            nullable=True,
            comment="版本写入请求摘要，用于检测重试键冲突。",
        ),
    )
    op.create_index(
        "uq_skill_version_write_idempotency",
        "skill_version",
        ["skill_id", "idempotency_key_hash"],
        unique=True,
    )


def downgrade() -> None:
    """先删除重试唯一约束，再删除对应列，保留所有 Skill 版本正文。"""
    op.drop_index("uq_skill_version_write_idempotency", table_name="skill_version")
    op.drop_column("skill_version", "request_checksum")
    op.drop_column("skill_version", "idempotency_key_hash")
    op.drop_index("uq_skill_create_idempotency", table_name="skill")
    op.drop_column("skill", "request_checksum")
    op.drop_column("skill", "idempotency_key_hash")
