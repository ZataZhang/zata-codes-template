"""run_tracing_init — 新建 run / run_event / run_export_audit 三张表，建立 Run 执行轨迹基础

Revision ID: 52899a5a681f
Revises: b2f1a4c9d3e7
Create Date: 2026-09-23 11:38:30.000000

背景：模板需要一个领域无关的「Run 执行轨迹」持久化底座：Run projection、仅追加
的 canonical 事件流，以及原始事件下载审计。诊断树与可选 OTLP 导出都从这里的已
提交事件重建，不新增平行 trace 事实表。事件目录、状态机与投影语义见
``src/backend/core/shared/models/run_policy.py`` 与
``src/backend/core/run_tracing/trace_use_cases.py``。

设计要点：
- ``run`` 主键 ``id``；(``owner_id``, ``idempotency_key_hash``) 唯一约束
  ``uq_run_owner_idempotency`` 保证主体范围幂等；``lease_expires_at`` 建
  ``ix_run_lease_expires_at``，供执行实例租约扫描；``subject_id`` / ``owner_id``
  各建普通索引供诊断过滤。不含业务域外键。
- ``run_event`` 复合主键 (``run_id``, ``seq``)，``run_id`` 外键指向
  ``run.id``（ondelete RESTRICT）；``ck_run_event_positive_seq`` 保证序号从 1 起。
- ``run_export_audit`` 只记录下载事实（谁、哪条 Run、事件数与字节数），不保存内容，
  故只带 ``CreatedAtMixin`` 的 ``created_at``。
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "52899a5a681f"
down_revision: Union[str, Sequence[str], None] = "b2f1a4c9d3e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema：新建 Run 执行轨迹三张表。"""

    op.create_table(
        "run",
        sa.Column("id", sa.String(length=64), nullable=False, comment="Run ID。"),
        sa.Column("subject_id", sa.String(length=64), nullable=False, comment="执行主体 ID。"),
        sa.Column("subject_type", sa.String(length=64), nullable=False, comment="执行主体类型。"),
        sa.Column(
            "subject_name", sa.String(length=255), nullable=False, comment="执行主体展示名。"
        ),
        sa.Column("subject_snapshot", sa.JSON(), nullable=False, comment="创建时执行主体快照。"),
        sa.Column(
            "subject_snapshot_checksum",
            sa.String(length=64),
            nullable=False,
            comment="执行主体快照摘要。",
        ),
        sa.Column("owner_id", sa.String(length=64), nullable=False, comment="所属用户 ID。"),
        sa.Column("status", sa.String(length=32), nullable=False, comment="Run 状态。"),
        sa.Column(
            "last_event_seq",
            sa.Integer(),
            nullable=False,
            comment="最后事件序号。",
        ),
        sa.Column(
            "idempotency_key_hash",
            sa.String(length=64),
            nullable=False,
            comment="幂等键摘要。",
        ),
        sa.Column("request_checksum", sa.String(length=64), nullable=False, comment="请求摘要。"),
        sa.Column(
            "executor_instance_id",
            sa.String(length=128),
            nullable=True,
            comment="执行实例 ID。",
        ),
        sa.Column(
            "lease_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Lease 过期时间。",
        ),
        sa.Column("final_message_id", sa.String(length=64), nullable=True, comment="最终消息 ID。"),
        sa.Column("error", sa.JSON(), nullable=True, comment="终态错误。"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, comment="创建时间。"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True, comment="开始时间。"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True, comment="结束时间。"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "idempotency_key_hash", name="uq_run_owner_idempotency"),
        comment="Canonical Run projection。",
    )
    op.create_index(op.f("ix_run_subject_id"), "run", ["subject_id"], unique=False)
    op.create_index(op.f("ix_run_owner_id"), "run", ["owner_id"], unique=False)
    op.create_index("ix_run_lease_expires_at", "run", ["lease_expires_at"], unique=False)

    op.create_table(
        "run_event",
        sa.Column("run_id", sa.String(length=64), nullable=False, comment="Run ID。"),
        sa.Column("seq", sa.Integer(), nullable=False, comment="事件序号。"),
        sa.Column("schema_version", sa.Integer(), nullable=False, comment="Schema 版本。"),
        sa.Column("event_type", sa.String(length=64), nullable=False, comment="事件类型。"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, comment="发生时间。"),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, comment="记录时间。"),
        sa.Column("subject_id", sa.String(length=64), nullable=False, comment="执行主体 ID。"),
        sa.Column(
            "subject_snapshot_checksum",
            sa.String(length=64),
            nullable=False,
            comment="执行主体快照摘要。",
        ),
        sa.Column("payload", sa.JSON(), nullable=False, comment="事件载荷。"),
        sa.Column("payload_checksum", sa.String(length=64), nullable=False, comment="载荷摘要。"),
        sa.Column("provenance", sa.JSON(), nullable=False, comment="受控来源信息。"),
        sa.Column("trace_id", sa.String(length=64), nullable=True, comment="Trace ID。"),
        sa.Column("span_id", sa.String(length=64), nullable=True, comment="Span ID。"),
        sa.PrimaryKeyConstraint("run_id", "seq"),
        sa.ForeignKeyConstraint(["run_id"], ["run.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("seq > 0", name="ck_run_event_positive_seq"),
        comment="不可变、仅追加的 Canonical Run 事件。",
    )

    op.create_table(
        "run_export_audit",
        sa.Column("id", sa.String(length=64), nullable=False, comment="审计记录 ID。"),
        sa.Column("run_id", sa.String(length=64), nullable=False, comment="被下载的 Run ID。"),
        sa.Column("actor_id", sa.String(length=64), nullable=False, comment="下载管理员 ID。"),
        sa.Column("event_count", sa.Integer(), nullable=False, comment="导出事件数。"),
        sa.Column("byte_count", sa.Integer(), nullable=False, comment="导出文件字节数。"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
            comment="记录创建时间，UTC，数据库端默认值。",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="原始 Run 事件下载审计，不保存下载内容。",
    )
    op.create_index(
        op.f("ix_run_export_audit_run_id"), "run_export_audit", ["run_id"], unique=False
    )
    op.create_index(
        op.f("ix_run_export_audit_actor_id"), "run_export_audit", ["actor_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema：删除 Run 执行轨迹三张表。"""
    op.drop_index(op.f("ix_run_export_audit_actor_id"), table_name="run_export_audit")
    op.drop_index(op.f("ix_run_export_audit_run_id"), table_name="run_export_audit")
    op.drop_table("run_export_audit")
    op.drop_table("run_event")
    op.drop_index("ix_run_lease_expires_at", table_name="run")
    op.drop_index(op.f("ix_run_owner_id"), table_name="run")
    op.drop_index(op.f("ix_run_subject_id"), table_name="run")
    op.drop_table("run")
