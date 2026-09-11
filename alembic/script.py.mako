"""${message} — <总分首句：一句话总结本次迁移改了什么（表 / 列 / 索引），及目的>

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

背景：<为什么需要这个变更；涉及的行为语义不要内联描述，压缩成一句并指向权威实现（文件路径），避免注释随代码漂移>

设计要点：<字段 / 索引 / 约束的分工与理由；索引与约束名写明，便于与 upgrade() 代码对应；涉及方言差异（如部分索引）时在此说明>
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, Sequence[str], None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    """Upgrade schema."""
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    """Downgrade schema."""
    ${downgrades if downgrades else "pass"}
