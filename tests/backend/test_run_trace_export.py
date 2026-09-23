"""Canonical Run 原始事件导出用例测试。

覆盖 ``export_run_events`` 的接受路径与全部拒绝分支：Run 未终结、事件不完整、事件
数量超过上限、文件超过大小上限，以及“被拒绝时不写审计、被接受时审计数字与实际字节
一致”。内存 repository 只回放已提交 envelope，因此断言的就是回读后的同一份事实。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from backend.core.run_tracing import (
    RunExportError,
    RunTraceUseCase,
    trace_use_cases,
)
from backend.core.run_tracing.trace_use_cases import (
    MAX_RAW_EXPORT_BYTES,
    MAX_RAW_EXPORT_EVENTS,
)
from backend.core.shared.models.run import (
    Run,
    RunEvent,
    RunExportAudit,
    RunStatus,
    RunSubjectSnapshot,
)

_RUN_ID = "run_export_fixture"
_ACTOR_ID = "admin_7f3a91"
_BASE_TIME = datetime(2026, 9, 22, 6, 0, 0, tzinfo=UTC)
_TOOL_ARGUMENT_CANARY = "canary-tool-argument-4d21"
_TOOL_RESULT_CANARY = "canary-tool-result-9b07"


class _InMemoryRunRepository:
    """只实现导出用例依赖的三个方法的内存 repository。"""

    def __init__(self, run: Run | None, events: list[RunEvent]) -> None:
        """保存待回放的 Run 与事件。"""
        self._run = run
        self._events = events
        self.recorded_audits: list[RunExportAudit] = []

    def get_by_id(self, run_id: str) -> Run | None:
        """按 ID 返回 Run，未命中时返回 None。"""
        if self._run is not None and self._run.id == run_id:
            return self._run
        return None

    def list_events(self, run_id: str, after_seq: int) -> list[RunEvent]:
        """返回该 Run 游标之后的已提交事件；其他 Run 的事件一律不返回。"""
        return [event for event in self._events if event.run_id == run_id and event.seq > after_seq]

    def record_export_audit(self, audit: RunExportAudit) -> None:
        """在内存中记录一次下载审计。"""
        self.recorded_audits.append(audit)


def _build_run(status: RunStatus, last_event_seq: int) -> Run:
    """构造最小可用 Run projection。"""
    return Run(
        id=_RUN_ID,
        owner_id="owner_chen",
        subject_id="subject_freight",
        subject_type="internal",
        subject_snapshot=RunSubjectSnapshot(
            subject_type="internal",
            subject_id="subject_freight",
            subject_name="freight-agent",
            snapshot_checksum="c" * 64,
        ),
        subject_snapshot_checksum="c" * 64,
        status=status,
        last_event_seq=last_event_seq,
        created_at=_BASE_TIME,
        started_at=_BASE_TIME,
        finished_at=_BASE_TIME if status in {RunStatus.SUCCEEDED} else None,
    )


def _event(
    seq: int,
    event_type: str,
    payload: dict[str, object],
    *,
    run_id: str = _RUN_ID,
    trace_id: str = "9f2c" * 8,
    span_id: str = "1a2b" * 4,
) -> RunEvent:
    """构造一条已提交事件 envelope。"""
    occurred_at = _BASE_TIME + timedelta(seconds=seq)
    return RunEvent(
        run_id=run_id,
        seq=seq,
        event_type=event_type,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        subject_id="subject_freight",
        subject_snapshot_checksum="c" * 64,
        payload=payload,
        payload_checksum="d" * 64,
        trace_id=trace_id,
        span_id=span_id,
    )


def _tool_events() -> list[RunEvent]:
    """构造带工具原始入参与结果的两次事件。"""
    return [
        _event(
            1,
            "tool.call.started",
            {
                "tool_call_id": "call_1",
                "tool_name": "derive_row_ids",
                "arguments": {"raw": _TOOL_ARGUMENT_CANARY},
            },
        ),
        _event(
            2,
            "tool.call.completed",
            {"tool_call_id": "call_1", "result": {"raw": _TOOL_RESULT_CANARY}},
        ),
    ]


def _build_use_case(
    run: Run | None, events: list[RunEvent]
) -> tuple[RunTraceUseCase, _InMemoryRunRepository]:
    """装配导出用例与它写入审计的内存 repository。"""
    repository = _InMemoryRunRepository(run, events)
    return RunTraceUseCase(repository), repository


def test_terminal_run_exports_ordered_events_and_records_audit() -> None:
    """终态 Run 导出原始事件，并按实际字节数写下低敏审计。"""
    use_case, repository = _build_use_case(_build_run(RunStatus.SUCCEEDED, 2), _tool_events())

    export_bytes = use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    export_document = json.loads(export_bytes.decode("utf-8"))
    assert export_document["schema_version"] == 1
    assert export_document["run_id"] == _RUN_ID
    assert export_document["trace_id"] == "9f2c" * 8
    assert export_document["status"] == "succeeded"
    assert export_document["event_count"] == 2
    assert [event["seq"] for event in export_document["events"]] == [1, 2]
    # 导出的价值就是拿到诊断接口刻意不返回的原始入参与结果。
    assert _TOOL_ARGUMENT_CANARY in export_bytes.decode("utf-8")
    assert _TOOL_RESULT_CANARY in export_bytes.decode("utf-8")

    assert len(repository.recorded_audits) == 1
    audit = repository.recorded_audits[0]
    assert audit.actor_id == _ACTOR_ID
    assert audit.run_id == _RUN_ID
    assert audit.event_count == export_document["event_count"]
    assert audit.byte_count == len(export_bytes)


def test_unknown_run_is_rejected_without_audit() -> None:
    """未知 Run 抛 LookupError，且不写审计。"""
    use_case, repository = _build_use_case(None, [])

    with pytest.raises(LookupError):
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    assert repository.recorded_audits == []


@pytest.mark.parametrize(
    "status",
    [RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.CANCELLING],
)
def test_non_terminal_run_is_rejected_without_audit(status: RunStatus) -> None:
    """未终结的 Run 一律 409，避免导出仍在追加的事件流。"""
    use_case, repository = _build_use_case(_build_run(status, 0), [])

    with pytest.raises(RunExportError) as export_error:
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    assert export_error.value.status_code == 409
    assert repository.recorded_audits == []


def test_event_count_over_limit_is_rejected_without_audit() -> None:
    """事件数量超过上限时在加载事件之前就拒绝。"""
    run = _build_run(RunStatus.SUCCEEDED, MAX_RAW_EXPORT_EVENTS + 1)
    use_case, repository = _build_use_case(run, [])

    with pytest.raises(RunExportError) as export_error:
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    assert export_error.value.status_code == 413
    assert repository.recorded_audits == []


def test_event_count_at_limit_passes_the_count_guard() -> None:
    """上限本身是包含的：条数正好等于上限时不再因数量被拒。"""
    run = _build_run(RunStatus.SUCCEEDED, MAX_RAW_EXPORT_EVENTS)
    use_case, _repository = _build_use_case(run, [])

    with pytest.raises(RunExportError) as export_error:
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    # 事件缺失因此报 409，而不是报数量的 413。
    assert export_error.value.status_code == 409
    assert "不完整" in str(export_error.value)


@pytest.mark.parametrize(
    "events",
    [
        # 条数与 Run projection 不一致：少了一条。
        [_event(1, "tool.call.started", {"tool_call_id": "call_1"})],
        # 条数一致但序号有洞。
        [
            _event(1, "tool.call.started", {"tool_call_id": "call_1"}),
            _event(3, "tool.call.completed", {"tool_call_id": "call_1"}),
        ],
    ],
)
def test_incomplete_event_sequence_is_rejected_without_audit(
    events: list[RunEvent],
) -> None:
    """事件不完整或序号不连续时拒绝导出，不产出半份文件。"""
    use_case, repository = _build_use_case(_build_run(RunStatus.SUCCEEDED, 2), events)

    with pytest.raises(RunExportError) as export_error:
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    assert export_error.value.status_code == 409
    assert repository.recorded_audits == []


def test_events_belonging_to_another_run_are_not_exported() -> None:
    """别的 Run 的事件不得被当作本 Run 的内容：repository 的 run 作用域必须被遵守。

    真实实现按 ``(run_id, seq)`` 过滤；如果调用方传错 Run ID 或实现漏掉该过滤，条数校验会失败，
    而不是把另一条 Run 的事件导出去。
    """
    foreign_events = [
        _event(1, "tool.call.started", {"tool_call_id": "call_1"}, run_id="run_other"),
        _event(2, "tool.call.completed", {"tool_call_id": "call_1"}, run_id="run_other"),
    ]
    use_case, repository = _build_use_case(_build_run(RunStatus.SUCCEEDED, 2), foreign_events)

    with pytest.raises(RunExportError) as export_error:
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    assert export_error.value.status_code == 409
    assert repository.recorded_audits == []


def test_document_over_byte_limit_is_rejected_without_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """单条大事件把文件推过大小上限时立刻 413，不写出整份文档。"""
    monkeypatch.setattr(trace_use_cases, "MAX_RAW_EXPORT_BYTES", 512)
    oversized = _event(
        1,
        "tool.call.completed",
        {"tool_call_id": "call_1", "result": {"raw": "x" * 4096}},
    )
    use_case, repository = _build_use_case(_build_run(RunStatus.SUCCEEDED, 1), [oversized])

    with pytest.raises(RunExportError) as export_error:
        use_case.export_run_events(_RUN_ID, _ACTOR_ID)

    assert export_error.value.status_code == 413
    assert repository.recorded_audits == []


def test_real_byte_limit_is_the_documented_size() -> None:
    """文件大小上限就是文档写明的 10 MiB。"""
    assert MAX_RAW_EXPORT_BYTES == 10 * 1024 * 1024
