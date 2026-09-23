"""Canonical Run 执行轨迹投影测试。

覆盖根节点唯一性、并行同名工具配对、父级降级、incomplete、重复终态、环防护与
legacy Run；全部直接喂已提交 envelope，因此断言的就是数据库回读后的同一份事实。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.core.run_tracing import project_run_trace
from backend.core.run_tracing.trace_use_cases import (
    _build_tree,
    _new_span,
    _SpanBuilder,
    resolve_tool_parent,
)
from backend.core.shared.models.run import (
    Run,
    RunEvent,
    RunStatus,
    RunSubjectSnapshot,
    RunTraceSpanKind,
    RunTraceSpanStatus,
    RunTraceVisibility,
    derive_root_span_id,
    derive_span_id,
    derive_trace_id,
)

_RUN_ID = "run_trace_fixture"
_BASE_TIME = datetime(2026, 9, 21, 10, 0, 0, tzinfo=UTC)
_TRACE_ID = derive_trace_id(_RUN_ID)
_ROOT_SPAN_ID = derive_root_span_id(_RUN_ID)


def _build_run(status: RunStatus, *, finished_at: datetime | None = None) -> Run:
    """构造最小可用 Run projection。"""
    return Run(
        id=_RUN_ID,
        owner_id="owner_1",
        subject_id="subject_1",
        subject_type="internal",
        subject_snapshot=RunSubjectSnapshot(
            subject_type="internal",
            subject_id="subject_1",
            subject_name="freight-agent",
            snapshot_checksum="c" * 64,
        ),
        subject_snapshot_checksum="c" * 64,
        status=status,
        last_event_seq=0,
        created_at=_BASE_TIME,
        started_at=_BASE_TIME,
        finished_at=finished_at,
    )


def _event(
    seq: int,
    event_type: str,
    payload: dict[str, object],
    *,
    span_id: str | None = _ROOT_SPAN_ID,
    offset_seconds: int = 0,
    trace_id: str | None = _TRACE_ID,
) -> RunEvent:
    """构造一条已提交事件 envelope。"""
    occurred_at = _BASE_TIME + timedelta(seconds=offset_seconds)
    return RunEvent(
        run_id=_RUN_ID,
        seq=seq,
        event_type=event_type,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        subject_id="subject_1",
        subject_snapshot_checksum="c" * 64,
        payload=payload,
        payload_checksum="d" * 64,
        trace_id=trace_id,
        span_id=span_id,
    )


def _model_span_id(model_call_id: str) -> str:
    """按 Core 的派生规则取模型 span ID。"""
    return derive_span_id(_RUN_ID, "model", model_call_id)


def _spans_by_kind(detail_spans: tuple, kind: RunTraceSpanKind) -> list:
    """按类别筛选节点，保持原始顺序。"""
    return [span for span in detail_spans if span.kind is kind]


def test_two_model_turns_and_one_parented_tool_build_a_stable_tree() -> None:
    """两轮模型 + 一次工具调用：根唯一、父子由来源 ID 决定。"""
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(
            2,
            "model.call.started",
            {"model_call_id": "call_1", "model_name": "qwen3.8-max", "turn_index": 0},
            span_id=_model_span_id("call_1"),
        ),
        _event(
            3,
            "tool.call.started",
            {
                "tool_call_id": "tool_1",
                "tool_name": "read_attachment",
                "arguments": {},
                "parent_model_call_id": "call_1",
            },
            span_id=derive_span_id(_RUN_ID, "tool", "source_tool_1"),
            offset_seconds=1,
        ),
        _event(
            4,
            "tool.call.completed",
            {"tool_call_id": "tool_1", "result": "ok", "result_checksum": "e" * 64},
            span_id=derive_span_id(_RUN_ID, "tool", "source_tool_1"),
            offset_seconds=2,
        ),
        _event(
            5,
            "model.call.completed",
            {
                "model_call_id": "call_1",
                "model_name": "qwen3.8-max",
                "turn_index": 0,
                "usage": {"prompt": 100, "completion": 20, "total": 120},
                "finish_reason": "tool_calls",
            },
            span_id=_model_span_id("call_1"),
            offset_seconds=3,
        ),
        _event(
            6,
            "model.call.started",
            {"model_call_id": "call_2", "model_name": "qwen3.8-max", "turn_index": 1},
            span_id=_model_span_id("call_2"),
            offset_seconds=4,
        ),
        _event(
            7,
            "model.call.completed",
            {
                "model_call_id": "call_2",
                "model_name": "qwen3.8-max",
                "turn_index": 1,
                "usage": {"prompt": 200, "completion": 40, "total": 240},
                "finish_reason": "stop",
            },
            span_id=_model_span_id("call_2"),
            offset_seconds=5,
        ),
        _event(8, "run.completed", {"message_id": "message_1"}, offset_seconds=6),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED, finished_at=_BASE_TIME), events)

    assert detail.root_span_id == _ROOT_SPAN_ID
    assert detail.summary.trace_id == _TRACE_ID
    assert detail.summary.visibility is RunTraceVisibility.FULL
    root_spans = _spans_by_kind(detail.spans, RunTraceSpanKind.ROOT)
    assert len(root_spans) == 1
    assert root_spans[0].parent_span_id is None

    model_spans = _spans_by_kind(detail.spans, RunTraceSpanKind.MODEL)
    assert [span.turn_index for span in model_spans] == [0, 1]
    assert all(span.parent_span_id == _ROOT_SPAN_ID for span in model_spans)
    assert all("unknown_parent" not in span.diagnostics for span in model_spans)
    assert all(span.status is RunTraceSpanStatus.COMPLETED for span in model_spans)
    assert model_spans[0].duration_ms == 3000
    assert detail.summary.model_call_count == 2
    assert detail.summary.usage == {"prompt": 300, "completion": 60, "total": 360}

    tool_spans = _spans_by_kind(detail.spans, RunTraceSpanKind.TOOL)
    assert len(tool_spans) == 1
    assert tool_spans[0].parent_span_id == _model_span_id("call_1")
    assert tool_spans[0].result_checksum == "e" * 64
    assert tool_spans[0].result_length == 2
    assert tool_spans[0].diagnostics == ()

    assert all(diagnostic.code != "parent_source_unavailable" for diagnostic in detail.diagnostics)

    root_node = detail.tree[0]
    assert root_node.span.span_id == _ROOT_SPAN_ID
    assert {child.span.span_id for child in root_node.children} == {
        _model_span_id("call_1"),
        _model_span_id("call_2"),
    }
    first_model_node = next(
        child for child in root_node.children if child.span.span_id == _model_span_id("call_1")
    )
    assert [child.span.span_id for child in first_model_node.children] == [
        derive_span_id(_RUN_ID, "tool", "source_tool_1")
    ]


def test_parallel_same_name_tools_are_paired_by_call_id() -> None:
    """并行同名工具按调用 ID 分开，不按工具名串线。"""
    first_span_id = derive_span_id(_RUN_ID, "tool", "source_a")
    second_span_id = derive_span_id(_RUN_ID, "tool", "source_b")
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(
            2,
            "tool.call.started",
            {"tool_call_id": "tool_a", "tool_name": "lookup_rate", "arguments": {}},
            span_id=first_span_id,
        ),
        _event(
            3,
            "tool.call.started",
            {"tool_call_id": "tool_b", "tool_name": "lookup_rate", "arguments": {}},
            span_id=second_span_id,
        ),
        _event(
            4,
            "tool.call.completed",
            {"tool_call_id": "tool_a", "result": "a", "result_checksum": "a" * 64},
            span_id=first_span_id,
        ),
        _event(
            5,
            "tool.call.completed",
            {"tool_call_id": "tool_b", "result": "bb", "result_checksum": "b" * 64},
            span_id=second_span_id,
        ),
        _event(6, "run.completed", {"message_id": "message_1"}),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    tool_spans = _spans_by_kind(detail.spans, RunTraceSpanKind.TOOL)
    assert len(tool_spans) == 2
    assert {span.tool_call_id for span in tool_spans} == {"tool_a", "tool_b"}
    assert {span.result_checksum for span in tool_spans} == {"a" * 64, "b" * 64}
    assert {span.result_length for span in tool_spans} == {1, 2}
    # 来源没有给出父级模型调用：两次调用都显式降级到根节点。
    assert all(span.parent_span_id == _ROOT_SPAN_ID for span in tool_spans)
    assert all("parent_source_unavailable" in span.diagnostics for span in tool_spans)


def test_unresolvable_parent_degrades_to_run_root_with_diagnostic() -> None:
    """来源声明了不存在的父级时降级到根，并给出稳定诊断 code。"""
    tool_span_id = derive_span_id(_RUN_ID, "tool", "source_tool_1")
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(
            2,
            "tool.call.started",
            {
                "tool_call_id": "tool_1",
                "tool_name": "lookup_rate",
                "arguments": {},
                "parent_model_call_id": "missing_call",
            },
            span_id=tool_span_id,
        ),
        _event(3, "run.completed", {"message_id": "message_1"}),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    tool_span = _spans_by_kind(detail.spans, RunTraceSpanKind.TOOL)[0]
    assert tool_span.parent_span_id == _ROOT_SPAN_ID
    assert "unknown_parent" in tool_span.diagnostics
    assert any(diagnostic.code == "unknown_parent" for diagnostic in detail.diagnostics)


def test_started_without_completion_becomes_incomplete_on_terminal_run() -> None:
    """终态 Run 上未收到完成的 started 节点显示为 incomplete，而不是消失。"""
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(
            2,
            "model.call.started",
            {"model_call_id": "call_1", "model_name": "qwen3.8-max", "turn_index": 0},
            span_id=_model_span_id("call_1"),
        ),
        _event(3, "run.failed", {"error": {"code": "provider_timeout", "message": "timeout"}}),
    ]

    detail = project_run_trace(_build_run(RunStatus.FAILED, finished_at=_BASE_TIME), events)

    model_span = _spans_by_kind(detail.spans, RunTraceSpanKind.MODEL)[0]
    assert model_span.status is RunTraceSpanStatus.INCOMPLETE
    assert "started_without_completion" in model_span.diagnostics
    root_span = _spans_by_kind(detail.spans, RunTraceSpanKind.ROOT)[0]
    assert root_span.status is RunTraceSpanStatus.FAILED
    assert root_span.error_code == "provider_timeout"
    assert detail.summary.error_count == 1


def test_duplicate_completion_keeps_first_result() -> None:
    """同一节点收到多次终态事件时保留首次结果并给出诊断。"""
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(
            2,
            "model.call.started",
            {"model_call_id": "call_1", "model_name": "m", "turn_index": 0},
            span_id=_model_span_id("call_1"),
        ),
        _event(
            3,
            "model.call.completed",
            {
                "model_call_id": "call_1",
                "model_name": "m",
                "turn_index": 0,
                "usage": {"total": 5},
                "finish_reason": "stop",
            },
            span_id=_model_span_id("call_1"),
            offset_seconds=1,
        ),
        _event(
            4,
            "model.call.completed",
            {
                "model_call_id": "call_1",
                "model_name": "m",
                "turn_index": 0,
                "usage": {"total": 999},
                "finish_reason": "stop",
            },
            span_id=_model_span_id("call_1"),
            offset_seconds=2,
        ),
        _event(5, "run.completed", {"message_id": "message_1"}),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    model_span = _spans_by_kind(detail.spans, RunTraceSpanKind.MODEL)[0]
    assert model_span.usage == {"total": 5}
    assert model_span.finish_reason == "stop"
    assert "duplicate_completion" in model_span.diagnostics


def test_parent_resolution_rejects_missing_unknown_and_self_parents() -> None:
    """父级裁决只接受可靠来源：缺失、未知与 self-parent 全部降级到根节点。"""
    model_span_id = _model_span_id("call_1")
    model_index = {"call_1": model_span_id}

    resolved, diagnostic_code = resolve_tool_parent(
        tool_span_id="a" * 16,
        requested_parent_model_call_id="call_1",
        model_span_id_by_call_id=model_index,
        root_span_id=_ROOT_SPAN_ID,
    )
    assert (resolved, diagnostic_code) == (model_span_id, None)

    resolved, diagnostic_code = resolve_tool_parent(
        tool_span_id="a" * 16,
        requested_parent_model_call_id=None,
        model_span_id_by_call_id=model_index,
        root_span_id=_ROOT_SPAN_ID,
    )
    assert (resolved, diagnostic_code) == (_ROOT_SPAN_ID, "parent_source_unavailable")

    resolved, diagnostic_code = resolve_tool_parent(
        tool_span_id="a" * 16,
        requested_parent_model_call_id="missing_call",
        model_span_id_by_call_id=model_index,
        root_span_id=_ROOT_SPAN_ID,
    )
    assert (resolved, diagnostic_code) == (_ROOT_SPAN_ID, "unknown_parent")

    resolved, diagnostic_code = resolve_tool_parent(
        tool_span_id=model_span_id,
        requested_parent_model_call_id="call_1",
        model_span_id_by_call_id=model_index,
        root_span_id=_ROOT_SPAN_ID,
    )
    assert (resolved, diagnostic_code) == (_ROOT_SPAN_ID, "self_parent")


def test_cyclic_parent_chain_is_broken_instead_of_looping() -> None:
    """父子关系成环或指向缺失节点时，节点降级到根并给出诊断，不进入无限递归。"""
    root_builder = _SpanBuilder(
        span=_new_span(
            span_id=_ROOT_SPAN_ID, kind=RunTraceSpanKind.ROOT, name="RUN ROOT", event_seq=0
        )
    )
    first_cycle_builder = _SpanBuilder(
        span=_new_span(
            span_id="f" * 16, kind=RunTraceSpanKind.TOOL, name="cycle_first", event_seq=1
        ),
        resolved_parent_span_id="d" * 16,
    )
    second_cycle_builder = _SpanBuilder(
        span=_new_span(
            span_id="d" * 16, kind=RunTraceSpanKind.TOOL, name="cycle_second", event_seq=2
        ),
        resolved_parent_span_id="f" * 16,
    )
    orphan_builder = _SpanBuilder(
        span=_new_span(span_id="e" * 16, kind=RunTraceSpanKind.TOOL, name="orphan", event_seq=3),
        resolved_parent_span_id="9" * 16,
    )
    builders = {
        _ROOT_SPAN_ID: root_builder,
        "f" * 16: first_cycle_builder,
        "d" * 16: second_cycle_builder,
        "e" * 16: orphan_builder,
    }

    tree, tree_diagnostics = _build_tree(builders, _ROOT_SPAN_ID)

    assert [node.span.span_id for node in tree] == [_ROOT_SPAN_ID]
    assert {node.span.span_id for node in tree[0].children} == {"f" * 16, "d" * 16, "e" * 16}
    assert "cyclic_parent" in first_cycle_builder.diagnostics
    assert "cyclic_parent" in second_cycle_builder.diagnostics
    assert "unknown_parent" in orphan_builder.diagnostics
    assert {diagnostic.code for diagnostic in tree_diagnostics} == {
        "cyclic_parent",
        "unknown_parent",
    }


def test_legacy_run_without_tracing_events_is_limited() -> None:
    """没有 tracing 事件的历史 Run 显示为受限，不伪造任何节点。"""
    events = [
        _event(
            1, "run.started", {"started_at": _BASE_TIME.isoformat()}, span_id=None, trace_id=None
        ),
        _event(
            2,
            "message.completed",
            {"message_id": "m", "content": "x", "content_checksum": "z"},
            span_id=None,
            trace_id=None,
        ),
        _event(3, "run.completed", {"message_id": "m"}, span_id=None, trace_id=None),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    assert detail.summary.visibility is RunTraceVisibility.LIMITED
    assert detail.root_span_id is None
    assert detail.spans == ()
    assert detail.tree == ()
    assert any(diagnostic.code == "no_tracing_events" for diagnostic in detail.diagnostics)
    # trace ID 仍可确定性重建，但它不是从事件里回填出来的。
    assert detail.summary.trace_id == _TRACE_ID


def test_trace_and_root_span_ids_are_reproducible_across_projections() -> None:
    """同一 Run 重复投影得到同一 trace/root span，重启后仍可重建。"""
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(2, "run.completed", {"message_id": "message_1"}),
    ]

    first_detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)
    second_detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    assert first_detail.root_span_id == second_detail.root_span_id == _ROOT_SPAN_ID
    assert first_detail.summary.trace_id == second_detail.summary.trace_id == _TRACE_ID
    assert [span.span_id for span in first_detail.spans] == [
        span.span_id for span in second_detail.spans
    ]


def test_span_less_tracing_events_are_derived_and_marked() -> None:
    """来源没写 span_id 的模型/工具事件仍进树：按调用 ID 派生并标记 missing_span_id。

    整条跳过会让本地诊断静默丢节点，并与会自行派生的 OTLP 导出产生不一致的树。
    """
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}, span_id=None),
        _event(
            2,
            "model.call.started",
            {"model_call_id": "call_1", "model_name": "qwen3.8-max", "turn_index": 0},
            span_id=None,
        ),
        _event(
            3,
            "tool.call.started",
            {
                "tool_call_id": "tool_1",
                "tool_name": "lookup_rate",
                "arguments": {},
                "parent_model_call_id": "call_1",
            },
            span_id=None,
        ),
        _event(
            4,
            "run.completed",
            {"message_id": "message_1"},
            span_id=None,
        ),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    derived_model_span_id = derive_span_id(_RUN_ID, "model", "call_1")
    derived_tool_span_id = derive_span_id(_RUN_ID, "tool", "tool_1")
    span_ids = {span.span_id for span in detail.spans}
    assert derived_model_span_id in span_ids
    assert derived_tool_span_id in span_ids
    assert detail.summary.visibility is RunTraceVisibility.FULL

    model_span = next(span for span in detail.spans if span.span_id == derived_model_span_id)
    tool_span = next(span for span in detail.spans if span.span_id == derived_tool_span_id)
    assert "missing_span_id" in model_span.diagnostics
    assert "missing_span_id" in tool_span.diagnostics
    # 根由终态事件补出，且工具父级仍按来源声明解析到模型 span。
    assert detail.root_span_id == _ROOT_SPAN_ID
    assert tool_span.parent_span_id == derived_model_span_id
    assert any(diagnostic.code == "missing_span_id" for diagnostic in detail.diagnostics)


def test_artifact_node_stays_completed_and_marks_span_less_events() -> None:
    """产物节点天生是已完成快照：不得被终结 Run 误翻成 incomplete。"""
    events = [
        _event(1, "run.started", {"started_at": _BASE_TIME.isoformat()}),
        _event(
            2,
            "artifact.created",
            {
                "type": "output",
                "artifact_id": "artifact_1",
                "filename": "quote.xlsx",
                "content_type": "application/vnd.ms-excel",
                "size": 10,
                "checksum": "a" * 64,
            },
            span_id=None,
        ),
        _event(3, "run.completed", {"message_id": "message_1"}),
    ]

    detail = project_run_trace(_build_run(RunStatus.SUCCEEDED), events)

    artifact_span = next(span for span in detail.spans if span.kind is RunTraceSpanKind.ARTIFACT)
    assert artifact_span.status is RunTraceSpanStatus.COMPLETED
    assert "started_without_completion" not in artifact_span.diagnostics
    # 来源没写 span_id 时与模型/工具节点一致地标记降级。
    assert "missing_span_id" in artifact_span.diagnostics
    assert artifact_span.parent_span_id == _ROOT_SPAN_ID
    assert "unknown_parent" not in artifact_span.diagnostics
