"""SQLAlchemy Canonical Run repository。

每个方法在独立短事务内完成读写：读连接用完即还，写事务随 ``begin()`` 上下文提交，
避免长生命周期会话把连接占成 ``idle in transaction``。repository 只负责事务与
持久化，不裁决模型/工具父子关系，也不写任何业务域表。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, sessionmaker

from backend.core.shared.models.run import (
    TERMINAL_RUN_STATUSES,
    Run,
    RunEvent,
    RunEventCandidate,
    RunExportAudit,
    RunPage,
    RunQuery,
    RunStatus,
    RunSubjectSnapshot,
    RunTraceActivity,
    derive_root_span_id,
    derive_trace_id,
)
from backend.core.shared.models.run_policy import decide_projection_transition
from backend.infrastructure.persistence.models.run import (
    RunEventModel,
    RunExportAuditModel,
    RunModel,
)


def _checksum(document: Any) -> str:
    """计算 canonical JSON SHA-256。"""
    serialized_document = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized_document.encode("utf-8")).hexdigest()


def _to_run(run_model: RunModel, database_session: Session) -> Run:
    """从 projection 与不可变输入事件还原完整 Run。"""
    input_event = database_session.scalar(
        select(RunEventModel).where(
            RunEventModel.run_id == run_model.id,
            RunEventModel.event_type == "input.accepted",
        )
    )
    accepted_content = input_event.payload.get("content") if input_event else None
    return Run(
        id=run_model.id,
        owner_id=run_model.owner_id,
        subject_id=run_model.subject_id,
        subject_type=run_model.subject_type,
        subject_snapshot=RunSubjectSnapshot(**run_model.subject_snapshot),
        subject_snapshot_checksum=run_model.subject_snapshot_checksum,
        input_content=tuple(accepted_content) if isinstance(accepted_content, list) else (),
        last_event_seq=run_model.last_event_seq,
        status=RunStatus(run_model.status),
        created_at=run_model.created_at,
        started_at=run_model.started_at,
        finished_at=run_model.finished_at,
        final_message_id=run_model.final_message_id,
        error=run_model.error,
        executor_instance_id=run_model.executor_instance_id,
        lease_expires_at=run_model.lease_expires_at,
    )


def _to_event(event_model: RunEventModel) -> RunEvent:
    """把 ORM Event 转为 envelope。"""
    return RunEvent(
        run_id=event_model.run_id,
        seq=event_model.seq,
        schema_version=event_model.schema_version,
        event_type=event_model.event_type,
        occurred_at=event_model.occurred_at,
        recorded_at=event_model.recorded_at,
        subject_id=event_model.subject_id,
        subject_snapshot_checksum=event_model.subject_snapshot_checksum,
        payload=event_model.payload,
        payload_checksum=event_model.payload_checksum,
        provenance=event_model.provenance,
        trace_id=event_model.trace_id,
        span_id=event_model.span_id,
    )


class SqlAlchemyRunRepository:
    """每个操作使用独立事务的 Run repository。"""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        """初始化 repository。"""
        self._session_factory = session_factory

    def create_run(
        self, run: Run, *, idempotency_key_hash: str, request_checksum: str, input_text: str
    ) -> Run:
        """在一个事务创建 Run 与前两条事件。"""
        with self._session_factory.begin() as database_session:
            run_model = RunModel(
                id=run.id,
                subject_id=run.subject_id,
                subject_type=run.subject_type,
                subject_name=run.subject_snapshot.subject_name,
                subject_snapshot=asdict(run.subject_snapshot),
                subject_snapshot_checksum=run.subject_snapshot_checksum,
                owner_id=run.owner_id,
                status=run.status.value,
                last_event_seq=0,
                idempotency_key_hash=idempotency_key_hash,
                request_checksum=request_checksum,
                created_at=run.created_at,
            )
            database_session.add(run_model)
            database_session.flush()
            # 根 trace/span 由 run_id 确定性派生，因此创建期的两条事件也带上同一
            # trace，Run 从第一条事件起就有可重建的根节点，不依赖执行进程存活。
            run_trace_id = derive_trace_id(run.id)
            run_root_span_id = derive_root_span_id(run.id)
            self._append_locked(
                database_session,
                run_model,
                RunEventCandidate(
                    "run.created",
                    {
                        "subject_id": run.subject_id,
                        "subject_snapshot_checksum": run.subject_snapshot_checksum,
                    },
                    trace_id=run_trace_id,
                    span_id=run_root_span_id,
                ),
            )
            self._append_locked(
                database_session,
                run_model,
                RunEventCandidate(
                    "input.accepted",
                    {
                        "input_id": f"input_{run.id}",
                        "content": run.input_content or input_text,
                        "content_checksum": _checksum(run.input_content or input_text),
                        "resources": [],
                    },
                    trace_id=run_trace_id,
                    span_id=run_root_span_id,
                ),
            )
        return self.get_by_id(run.id)  # type: ignore[return-value]

    def get_by_id(self, run_id: str) -> Run | None:
        """读取 Run projection。"""
        with self._session_factory() as database_session:
            run_model = database_session.get(RunModel, run_id)
            return _to_run(run_model, database_session) if run_model else None

    def get_by_idempotency(self, owner_id: str, key_hash: str) -> tuple[Run, str] | None:
        """读取主体范围的幂等记录。"""
        with self._session_factory() as database_session:
            run_model = database_session.scalar(
                select(RunModel).where(
                    RunModel.owner_id == owner_id,
                    RunModel.idempotency_key_hash == key_hash,
                )
            )
            return (
                (_to_run(run_model, database_session), run_model.request_checksum)
                if run_model
                else None
            )

    def list_owner_runs(self, owner_id: str, *, offset: int = 0, limit: int = 50) -> Sequence[Run]:
        """按创建时间倒序列出主体名下的 Run，同刻按 ID 决胜保证顺序稳定。"""
        with self._session_factory() as database_session:
            run_models = database_session.scalars(
                select(RunModel)
                .where(RunModel.owner_id == owner_id)
                .order_by(RunModel.created_at.desc(), RunModel.id.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return [_to_run(run_model, database_session) for run_model in run_models]

    def append_event(self, run_id: str, candidate: RunEventCandidate) -> RunEvent:
        """锁定 projection 后原子追加事件并更新状态。"""
        with self._session_factory.begin() as database_session:
            run_model = database_session.scalar(
                select(RunModel).where(RunModel.id == run_id).with_for_update()
            )
            if run_model is None:
                raise LookupError("Run 不存在")
            event_model = self._append_locked(database_session, run_model, candidate)
            committed_event = _to_event(event_model)
        return committed_event

    def _append_locked(
        self, database_session: Session, run_model: RunModel, candidate: RunEventCandidate
    ) -> RunEventModel:
        """在调用方事务中裁决状态并追加一条事件。"""
        transition = decide_projection_transition(RunStatus(run_model.status), candidate)
        recorded_at = datetime.now(UTC)
        next_sequence = run_model.last_event_seq + 1
        event_model = RunEventModel(
            run_id=run_model.id,
            seq=next_sequence,
            schema_version=1,
            event_type=candidate.event_type,
            occurred_at=candidate.occurred_at or recorded_at,
            recorded_at=recorded_at,
            subject_id=run_model.subject_id,
            subject_snapshot_checksum=run_model.subject_snapshot_checksum,
            payload=candidate.payload,
            payload_checksum=_checksum(candidate.payload),
            provenance=candidate.provenance,
            trace_id=candidate.trace_id,
            span_id=candidate.span_id,
        )
        database_session.add(event_model)
        run_model.last_event_seq = next_sequence
        run_model.status = transition.next_status.value
        if candidate.event_type == "run.started":
            run_model.started_at = recorded_at
        if transition.is_terminal:
            run_model.finished_at = recorded_at
            run_model.lease_expires_at = None
        if candidate.event_type == "run.completed":
            run_model.final_message_id = candidate.payload["message_id"]
        if candidate.event_type == "run.failed":
            run_model.error = candidate.payload["error"]
        database_session.flush()
        return event_model

    def query_runs_page(self, query: RunQuery) -> RunPage:
        """跨 owner 分页查询 Run，供 admin 诊断列表使用。

        刻意不接收调用者身份：admin 诊断需要跨 owner 回看，因此授权判断留在
        API 层的 admin 认证依赖上，repository 只负责过滤与分页。
        """
        filter_conditions = []
        if query.run_id:
            filter_conditions.append(RunModel.id == query.run_id)
        if query.subject_id:
            filter_conditions.append(RunModel.subject_id == query.subject_id)
        if query.status is not None:
            filter_conditions.append(RunModel.status == query.status.value)
        if query.created_after is not None:
            filter_conditions.append(RunModel.created_at >= query.created_after)
        if query.created_before is not None:
            filter_conditions.append(RunModel.created_at <= query.created_before)
        with self._session_factory() as database_session:
            total_count = database_session.scalar(
                select(func.count()).select_from(RunModel).where(*filter_conditions)
            )
            run_models = database_session.scalars(
                select(RunModel)
                .where(*filter_conditions)
                .order_by(RunModel.created_at.desc(), RunModel.id.desc())
                .offset(query.offset)
                .limit(query.limit)
            ).all()
            return RunPage(
                runs=tuple(_to_run(run_model, database_session) for run_model in run_models),
                total=int(total_count or 0),
            )

    def summarize_trace_activity(self, run_ids: Sequence[str]) -> dict[str, RunTraceActivity]:
        """按 run 聚合 tracing 事件计数，避免列表页逐 Run 读取全部事件。"""
        if not run_ids:
            return {}
        with self._session_factory() as database_session:
            activity_rows = database_session.execute(
                select(RunEventModel.run_id, RunEventModel.event_type, func.count())
                .where(
                    RunEventModel.run_id.in_(list(run_ids)),
                    RunEventModel.event_type.in_(
                        ("model.call.started", "tool.call.started", "artifact.created")
                    ),
                )
                .group_by(RunEventModel.run_id, RunEventModel.event_type)
            ).all()
        activity_by_run_id: dict[str, RunTraceActivity] = {}
        for activity_run_id, event_type, event_count in activity_rows:
            current_activity = activity_by_run_id.get(activity_run_id, RunTraceActivity())
            if event_type == "model.call.started":
                activity_by_run_id[activity_run_id] = replace(
                    current_activity, model_call_count=int(event_count)
                )
            elif event_type == "tool.call.started":
                activity_by_run_id[activity_run_id] = replace(
                    current_activity, tool_call_count=int(event_count)
                )
            else:
                activity_by_run_id[activity_run_id] = replace(
                    current_activity, artifact_count=int(event_count)
                )
        return activity_by_run_id

    def list_events(self, run_id: str, after_seq: int) -> Sequence[RunEvent]:
        """按序读取已提交事件。"""
        with self._session_factory() as database_session:
            event_models = database_session.scalars(
                select(RunEventModel)
                .where(RunEventModel.run_id == run_id, RunEventModel.seq > after_seq)
                .order_by(RunEventModel.seq)
            ).all()
            return [_to_event(event_model) for event_model in event_models]

    def record_export_audit(self, audit: RunExportAudit) -> None:
        """持久记录原始事件下载，不写入原始内容。"""
        with self._session_factory.begin() as database_session:
            database_session.add(
                RunExportAuditModel(
                    id=audit.id,
                    run_id=audit.run_id,
                    actor_id=audit.actor_id,
                    event_count=audit.event_count,
                    byte_count=audit.byte_count,
                )
            )

    def claim(self, run_id: str, instance_id: str, lease_expires_at: datetime) -> bool:
        """认领 queued Run。"""
        with self._session_factory.begin() as database_session:
            run_model = database_session.scalar(
                select(RunModel).where(RunModel.id == run_id).with_for_update()
            )
            if run_model is None or run_model.status != RunStatus.QUEUED.value:
                return False
            run_model.executor_instance_id = instance_id
            run_model.lease_expires_at = lease_expires_at
            return True

    def heartbeat(self, run_id: str, instance_id: str, lease_expires_at: datetime) -> bool:
        """续租当前执行实例。

        读取必须和 ``append_event`` 抢同一把行锁。不加锁时这里读到的可能是终态提交
        前的旧版本：判定"还没终态"之后再把租约写回去，就会覆盖掉终态写清空的
        lease，留下一个已终态却带着未来租约的 Run。
        """
        with self._session_factory.begin() as database_session:
            run_model = database_session.scalar(
                select(RunModel).where(RunModel.id == run_id).with_for_update()
            )
            if (
                run_model is None
                or run_model.executor_instance_id != instance_id
                or RunStatus(run_model.status) in TERMINAL_RUN_STATUSES
            ):
                return False
            run_model.lease_expires_at = lease_expires_at
            return True

    def list_expired(self, now: datetime) -> Sequence[Run]:
        """列出 lease 已过期的非终态 Run。"""
        terminal_values = [status.value for status in TERMINAL_RUN_STATUSES]
        with self._session_factory() as database_session:
            run_models = database_session.scalars(
                select(RunModel).where(
                    RunModel.status.not_in(terminal_values),
                    or_(
                        RunModel.lease_expires_at < now,
                        and_(
                            RunModel.status == RunStatus.QUEUED.value,
                            RunModel.lease_expires_at.is_(None),
                            RunModel.created_at < now - timedelta(seconds=30),
                        ),
                    ),
                )
            ).all()
            return [_to_run(run_model, database_session) for run_model in run_models]
