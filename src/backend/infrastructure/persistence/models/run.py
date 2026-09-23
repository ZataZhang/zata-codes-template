"""Canonical Run ORM 模型。

Run projection、仅追加事件与原始事件下载审计三张表。它是「Run 执行轨迹」子系统
的持久层：诊断树与可选 OTLP 导出都从这里的已提交事件重建，任何投影都不会回写。
表结构不含业务域外键，派生项目按需在自己的执行器里维护 subject 维度。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import CreatedAtMixin


class RunModel(Base):
    """Canonical Run projection 表。"""

    __tablename__ = "run"
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key_hash", name="uq_run_owner_idempotency"),
        Index("ix_run_lease_expires_at", "lease_expires_at"),
        {"comment": "Canonical Run projection。"},
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Run ID。")
    subject_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="执行主体 ID。"
    )
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="执行主体类型。")
    subject_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="执行主体展示名。"
    )
    subject_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, comment="创建时执行主体快照。"
    )
    subject_snapshot_checksum: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="执行主体快照摘要。"
    )
    owner_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="所属用户 ID。"
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, comment="Run 状态。")
    last_event_seq: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="最后事件序号。"
    )
    idempotency_key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="幂等键摘要。"
    )
    request_checksum: Mapped[str] = mapped_column(String(64), nullable=False, comment="请求摘要。")
    executor_instance_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, comment="执行实例 ID。"
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Lease 过期时间。"
    )
    final_message_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="最终消息 ID。"
    )
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, comment="终态错误。")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="创建时间。"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="开始时间。"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="结束时间。"
    )


class RunEventModel(Base):
    """仅追加 canonical Event 表。"""

    __tablename__ = "run_event"
    __table_args__ = ({"comment": "不可变、仅追加的 Canonical Run 事件。"},)
    run_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("run.id", ondelete="RESTRICT"),
        primary_key=True,
        comment="Run ID。",
    )
    seq: Mapped[int] = mapped_column(Integer, primary_key=True, comment="事件序号。")
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, comment="Schema 版本。")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="事件类型。")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="发生时间。"
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="记录时间。"
    )
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="执行主体 ID。")
    subject_snapshot_checksum: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="执行主体快照摘要。"
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, comment="事件载荷。")
    payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False, comment="载荷摘要。")
    provenance: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict, comment="受控来源信息。"
    )
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Trace ID。")
    span_id: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="Span ID。")


class RunExportAuditModel(Base, CreatedAtMixin):
    """管理员下载原始 Run 事件的持久审计表。"""

    __tablename__ = "run_export_audit"
    __table_args__ = ({"comment": "原始 Run 事件下载审计，不保存下载内容。"},)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="审计记录 ID。")
    run_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="被下载的 Run ID。"
    )
    actor_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="下载管理员 ID。"
    )
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="导出事件数。")
    byte_count: Mapped[int] = mapped_column(Integer, nullable=False, comment="导出文件字节数。")
