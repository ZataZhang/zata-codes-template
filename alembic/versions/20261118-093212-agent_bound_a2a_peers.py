"""agent_bound_a2a_peers — 为 agent 增加绑定出站 A2A 对端的 JSON 列。

Revision ID: 8b3c6eee34c1
Revises: 26e8967fcd01
Create Date: 2026-11-18 09:32:12.000000

背景：出站调用只允许 Agent 创建时绑定的已批准对端，见 ``src/backend/core/agent/catalog.py`` 与 ``src/backend/core/agent/runs.py``。

设计要点：``agent.allowed_peer_ids`` 以 JSON 数组保存对端 ID，空数组表示不授权任何出站调用；存量 Agent 回填空数组后设为非空，避免旧数据被隐式授权。先回填再通过 ``batch_alter_table`` 收紧为空值约束，兼容 SQLite 测试迁移的整表重建策略，同时让 PostgreSQL/MySQL 使用原生列变更。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b3c6eee34c1"
down_revision: Union[str, Sequence[str], None] = "26e8967fcd01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_PEER_COLUMN_COMMENT = "本 Agent 可调用的已批准 A2A 对端 ID；空列表表示不授权任何出站对端。"


def upgrade() -> None:
    """新增 Agent 出站对端绑定列并回填空数组。"""
    op.add_column(
        "agent",
        sa.Column(
            "allowed_peer_ids",
            sa.JSON(),
            nullable=True,
            comment=_PEER_COLUMN_COMMENT,
        ),
    )
    op.execute("UPDATE agent SET allowed_peer_ids = '[]' WHERE allowed_peer_ids IS NULL")
    with op.batch_alter_table("agent") as agent_table:
        agent_table.alter_column(
            "allowed_peer_ids",
            existing_type=sa.JSON(),
            nullable=False,
            existing_comment=_PEER_COLUMN_COMMENT,
        )


def downgrade() -> None:
    """移除 Agent 出站对端绑定列。"""
    op.drop_column("agent", "allowed_peer_ids")
