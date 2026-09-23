"""Canonical Run repository 抽象端口。"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from backend.core.shared.models.run import (
    Run,
    RunEvent,
    RunEventCandidate,
    RunExportAudit,
    RunPage,
    RunQuery,
    RunTraceActivity,
)


class RunRepository(Protocol):
    """Run、Event、幂等与 lease 的事务端口。"""

    def create_run(
        self, run: Run, *, idempotency_key_hash: str, request_checksum: str, input_text: str
    ) -> Run:
        """事务创建 Run 与初始事件。"""
        ...

    def get_by_id(self, run_id: str) -> Run | None:
        """按 ID 读取 Run。"""
        ...

    def get_by_idempotency(self, owner_id: str, key_hash: str) -> tuple[Run, str] | None:
        """按主体与幂等键读取 Run。"""
        ...

    def list_owner_runs(self, owner_id: str, *, offset: int = 0, limit: int = 50) -> Sequence[Run]:
        """分页列出主体名下的 Run，最新优先（created_at 倒序，同刻按 ID 决胜）。"""
        ...

    def query_runs_page(self, query: RunQuery) -> RunPage:
        """跨 owner 分页查询 Run，供 admin 诊断列表使用，不过滤调用者身份。"""
        ...

    def summarize_trace_activity(self, run_ids: Sequence[str]) -> dict[str, RunTraceActivity]:
        """按 run 聚合 tracing 事件计数，避免列表页逐 Run 读取全部事件。"""
        ...

    def append_event(self, run_id: str, candidate: RunEventCandidate) -> RunEvent:
        """事务追加候选事件。"""
        ...

    def list_events(self, run_id: str, after_seq: int) -> Sequence[RunEvent]:
        """读取游标后的已提交事件。"""
        ...

    def record_export_audit(self, audit: RunExportAudit) -> None:
        """持久记录一次已准备好的原始事件下载，不保存事件内容。"""
        ...

    def claim(self, run_id: str, instance_id: str, lease_expires_at: datetime) -> bool:
        """认领 queued Run。"""
        ...

    def heartbeat(self, run_id: str, instance_id: str, lease_expires_at: datetime) -> bool:
        """续租当前执行实例。"""
        ...

    def list_expired(self, now: datetime) -> Sequence[Run]:
        """列出已过期的非终态 Run。"""
        ...
