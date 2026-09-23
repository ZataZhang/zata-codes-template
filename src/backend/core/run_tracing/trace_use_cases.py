"""Canonical Run 执行轨迹只读投影。

诊断树不是第二套事实源：它只读取已经提交的 ``(run_id, seq)`` 事件，把模型轮次、
工具调用、产物与终态归并成带稳定诊断 code 的树。任何关系裁决都只接受事件里显式
写下的信息——缺父级就降级到 Run 根节点，绝不按工具名、时间邻近或完成顺序猜测。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from uuid import uuid4

from backend.core.shared.interfaces.run_repository import RunRepository
from backend.core.shared.models.run import (
    Run,
    RunEvent,
    RunExportAudit,
    RunQuery,
    RunStatus,
    RunTraceActivity,
    RunTraceDetail,
    RunTraceDiagnostic,
    RunTraceSpan,
    RunTraceSpanKind,
    RunTraceSpanStatus,
    RunTraceSummary,
    RunTraceTreeNode,
    RunTraceVisibility,
    derive_root_span_id,
    derive_span_id,
    derive_trace_id,
)

# 默认响应只带低敏元数据：不返回 prompt、隐藏推理、邮件正文或工具原始参数/结果。
CONTENT_POLICY_METADATA_ONLY = "metadata-only"
MAX_RAW_EXPORT_EVENTS = 10_000
MAX_RAW_EXPORT_BYTES = 10 * 1024 * 1024


class RunExportError(Exception):
    """原始事件导出因 Run 状态或文件规模被拒绝。"""

    def __init__(self, status_code: int, message: str) -> None:
        """保存可映射到 HTTP 的拒绝原因。"""
        super().__init__(message)
        self.status_code = status_code


DIAGNOSTIC_PARENT_SOURCE_UNAVAILABLE = "parent_source_unavailable"
DIAGNOSTIC_UNKNOWN_PARENT = "unknown_parent"
DIAGNOSTIC_SELF_PARENT = "self_parent"
DIAGNOSTIC_CYCLIC_PARENT = "cyclic_parent"
DIAGNOSTIC_STARTED_WITHOUT_COMPLETION = "started_without_completion"
DIAGNOSTIC_COMPLETION_WITHOUT_START = "completion_without_start"
DIAGNOSTIC_DUPLICATE_COMPLETION = "duplicate_completion"
DIAGNOSTIC_MISSING_SPAN_ID = "missing_span_id"
DIAGNOSTIC_NO_TRACING_EVENTS = "no_tracing_events"

_DIAGNOSTIC_MESSAGES: dict[str, str] = {
    DIAGNOSTIC_PARENT_SOURCE_UNAVAILABLE: "工具调用的父级来源不可确认，已挂到 Run 根节点。",
    DIAGNOSTIC_UNKNOWN_PARENT: "事件声明的父级节点不存在，已降级挂到 Run 根节点。",
    DIAGNOSTIC_SELF_PARENT: "节点被声明为自身的父级，已降级挂到 Run 根节点。",
    DIAGNOSTIC_CYCLIC_PARENT: "节点父子关系存在环，已降级挂到 Run 根节点。",
    DIAGNOSTIC_STARTED_WITHOUT_COMPLETION: "Run 已终结但该步骤没有收到完成事件。",
    DIAGNOSTIC_COMPLETION_WITHOUT_START: "只收到完成事件，没有对应的开始事件。",
    DIAGNOSTIC_DUPLICATE_COMPLETION: "同一节点收到多次终态事件，保留首次结果。",
    DIAGNOSTIC_MISSING_SPAN_ID: "事件没有携带 span 标识，已按来源调用 ID 派生。",
    DIAGNOSTIC_NO_TRACING_EVENTS: "该 Run 没有模型或工具 tracing 事件，诊断视图受限。",
}

_TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    }
)
_FAILED_RUN_STATUSES = frozenset({RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED})

_ROOT_SPAN_NAME = "RUN ROOT"

_MODEL_EVENT_TYPES = frozenset({"model.call.started", "model.call.completed", "model.call.failed"})
_TOOL_EVENT_TYPES = frozenset({"tool.call.started", "tool.call.completed", "tool.call.failed"})
_TERMINAL_EVENT_TYPES = frozenset(
    {"run.completed", "run.failed", "run.cancelled", "run.interrupted"}
)
# Run 级事件由根节点承载：run.created / input.accepted 属于历史数据，message.* 是
# 文本流，它们都不单独成为诊断节点。
_RUN_LEVEL_EVENT_TYPES = frozenset(
    {
        "run.created",
        "input.accepted",
        "run.started",
        "run.cancelling",
        "message.started",
        "message.delta",
        "message.completed",
    }
)
_TERMINAL_SPAN_STATUSES: dict[str, RunTraceSpanStatus] = {
    "run.completed": RunTraceSpanStatus.COMPLETED,
    "run.failed": RunTraceSpanStatus.FAILED,
    "run.cancelled": RunTraceSpanStatus.INCOMPLETE,
    "run.interrupted": RunTraceSpanStatus.INCOMPLETE,
}


def _new_span(
    *,
    span_id: str,
    kind: RunTraceSpanKind,
    name: str,
    event_seq: int,
    started_at: datetime | None = None,
) -> RunTraceSpan:
    """创建一个尚未完成、也没有父级的节点。"""
    return RunTraceSpan(
        span_id=span_id,
        parent_span_id=None,
        kind=kind,
        name=name,
        status=RunTraceSpanStatus.RUNNING,
        started_at=started_at,
        finished_at=None,
        duration_ms=None,
        event_seq=event_seq,
    )


def _elapsed_ms(started_at: datetime | None, finished_at: datetime | None) -> int | None:
    """计算两端点之间的毫秒数，缺少任一端点时返回空。"""
    if started_at is None or finished_at is None:
        return None
    return max(int((finished_at - started_at).total_seconds() * 1000), 0)


def _is_plain_int(value: object) -> bool:
    """判断是否为非布尔整数。"""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass
class _SpanBuilder:
    """投影过程中可变的节点累积外壳。

    节点形状的唯一定义在冻结的 :class:`RunTraceSpan` 上；这里只持有它以及投影
    自己需要的裁决记账（请求的父级、已裁决的父级、诊断 code），字段更新统一走
    :meth:`update`，避免同一份字段清单出现两遍。
    """

    span: RunTraceSpan
    requested_parent_model_call_id: str | None = None
    resolved_parent_span_id: str | None = None
    terminal_seen: bool = False
    diagnostics: list[str] = field(default_factory=list)

    @property
    def span_id(self) -> str:
        """返回节点 span ID。"""
        return self.span.span_id

    @property
    def kind(self) -> RunTraceSpanKind:
        """返回节点类别。"""
        return self.span.kind

    @property
    def name(self) -> str:
        """返回节点展示名。"""
        return self.span.name

    @property
    def started_at(self) -> datetime | None:
        """返回已知开始时间。"""
        return self.span.started_at

    def update(self, **span_changes: object) -> None:
        """替换节点上的不可变字段。"""
        self.span = replace(self.span, **span_changes)

    def add_diagnostic(self, code: str) -> None:
        """追加一个稳定诊断 code；重复项在冻结时会被去重。"""
        self.diagnostics.append(code)

    def mark_terminal(self, status: RunTraceSpanStatus, finished_at: datetime) -> bool:
        """记录终态；重复终态时保留首次结果。

        Args:
            status (RunTraceSpanStatus): 目标终态。
            finished_at (datetime): 终态事件时间。

        Returns:
            bool: 是否是首次进入终态。
        """
        if self.terminal_seen:
            self.add_diagnostic(DIAGNOSTIC_DUPLICATE_COMPLETION)
            return False
        self.terminal_seen = True
        self.update(status=status, finished_at=finished_at)
        return True


def _sort_key(builder: _SpanBuilder) -> tuple[bool, datetime, int, str]:
    """缺少开始时间的节点排在最后，其余按开始时间与事件序号稳定排序。"""
    span = builder.span
    if span.started_at is None:
        return (True, datetime.min, span.event_seq, span.span_id)
    return (False, span.started_at, span.event_seq, span.span_id)


class RunTraceUseCase:
    """从已提交 Canonical Run/Event 构建管理端诊断投影。"""

    def __init__(self, repository: RunRepository) -> None:
        """初始化投影用例。

        Args:
            repository (RunRepository): 只读 Run/Event 端口。
        """
        self._repository = repository

    def list_run_summaries(self, query: RunQuery) -> tuple[list[RunTraceSummary], int]:
        """分页列出 Run 诊断摘要。

        Args:
            query (RunQuery): 过滤与分页条件。

        Returns:
            tuple[list[RunTraceSummary], int]: 当前页摘要与命中总数。
        """
        page = self._repository.query_runs_page(query)
        activity_by_run_id = self._repository.summarize_trace_activity(
            [run.id for run in page.runs]
        )
        summaries = [
            _build_summary(run, activity_by_run_id.get(run.id, RunTraceActivity()))
            for run in page.runs
        ]
        return summaries, page.total

    def get_run_trace(self, run_id: str) -> RunTraceDetail:
        """构建单个 Run 的完整诊断投影。

        读取路径完全不依赖进程内缓存：模型/工具父子关系和状态都从数据库事件重新
        裁决，因此刷新浏览器或换一个后端实例都得到同一棵树。

        Args:
            run_id (str): Canonical Run ID。

        Returns:
            RunTraceDetail: 含根节点、扁平节点、树与诊断的投影。

        Raises:
            LookupError: Run 不存在时抛出。
        """
        run = self._repository.get_by_id(run_id)
        if run is None:
            raise LookupError("Run 不存在")
        events = self._repository.list_events(run_id, 0)
        return project_run_trace(run, events)

    def export_run_events(self, run_id: str, actor_id: str) -> bytes:
        """导出单个已终结 Run 的完整已提交事件，并持久记录下载审计。

        Args:
            run_id (str): Canonical Run ID。
            actor_id (str): 已认证管理员 ID。

        Returns:
            bytes: UTF-8 JSON 文件内容。

        Raises:
            LookupError: Run 不存在。
            RunExportError: Run 未终结、事件不完整或超过大小上限。
        """
        run = self._repository.get_by_id(run_id)
        if run is None:
            raise LookupError("Run 不存在")
        if run.status not in _TERMINAL_RUN_STATUSES:
            raise RunExportError(409, "Run 尚未终结，请稍后下载")
        if run.last_event_seq > MAX_RAW_EXPORT_EVENTS:
            raise RunExportError(413, "事件数量超过下载上限")
        events = self._repository.list_events(run_id, 0)
        if len(events) != run.last_event_seq or any(
            event.seq != index for index, event in enumerate(events, start=1)
        ):
            raise RunExportError(409, "Run 事件不完整，请稍后重试")
        serialized_events = []
        serialized_bytes = 0
        for event in events:
            serialized_event = asdict(event)
            serialized_event["occurred_at"] = event.occurred_at.isoformat()
            serialized_event["recorded_at"] = event.recorded_at.isoformat()
            serialized_events.append(serialized_event)
            # 边序列化边累计：单条事件就可能把文件推过上限，先拒绝再堆出整份文档。
            serialized_bytes += len(
                json.dumps(serialized_event, ensure_ascii=False, separators=(",", ":")).encode(
                    "utf-8"
                )
            )
            if serialized_bytes > MAX_RAW_EXPORT_BYTES:
                raise RunExportError(413, "文件大小超过下载上限")
        export_document = {
            "schema_version": 1,
            "run_id": run.id,
            "trace_id": next((event.trace_id for event in events if event.trace_id), None)
            or derive_trace_id(run.id),
            "status": run.status.value,
            "event_count": len(events),
            "events": serialized_events,
        }
        export_bytes = json.dumps(
            export_document, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        if len(export_bytes) > MAX_RAW_EXPORT_BYTES:
            raise RunExportError(413, "文件大小超过下载上限")
        self._repository.record_export_audit(
            RunExportAudit(
                id=f"export_{uuid4().hex}",
                run_id=run.id,
                actor_id=actor_id,
                event_count=len(events),
                byte_count=len(export_bytes),
            )
        )
        return export_bytes


def project_run_trace(run: Run, events: Sequence[RunEvent]) -> RunTraceDetail:
    """把 Run projection 与已提交事件归并成诊断树。

    Args:
        run (Run): Run projection。
        events (Sequence[RunEvent]): 按 ``seq`` 升序的已提交事件。

    Returns:
        RunTraceDetail: 诊断投影。
    """
    committed_trace_id = next((event.trace_id for event in events if event.trace_id), None)
    trace_id = committed_trace_id or derive_trace_id(run.id)
    derived_root_span_id = derive_root_span_id(run.id)
    activity = _activity_from_events(events)

    diagnostics: list[RunTraceDiagnostic] = []
    builders: dict[str, _SpanBuilder] = {}
    root_span_id: str | None = None
    is_terminal_run = run.status in _TERMINAL_RUN_STATUSES

    for event in events:
        if event.event_type in _RUN_LEVEL_EVENT_TYPES:
            # Run 级事件由根节点承载，不单独成节点；它们不带 span 时无需进入视图。
            if event.span_id is None:
                continue
            if event.event_type == "run.started":
                root_span_id = event.span_id
                builders.setdefault(
                    root_span_id,
                    _SpanBuilder(
                        span=_new_span(
                            span_id=root_span_id,
                            kind=RunTraceSpanKind.ROOT,
                            name=_ROOT_SPAN_NAME,
                            event_seq=event.seq,
                            started_at=event.occurred_at,
                        )
                    ),
                )
            continue
        if event.event_type in _MODEL_EVENT_TYPES:
            # 模型/工具事件即使来源没写 span_id 也要进树：按来源调用 ID 派生并显式
            # 标记 missing_span_id。整条跳过会让本地诊断静默丢节点，并与 OTLP 导出
            # （它会派生）产生不一致的树。
            _apply_model_event(builders, event, run.id)
        elif event.event_type in _TOOL_EVENT_TYPES:
            _apply_tool_event(builders, event, run.id)
        elif event.event_type == "artifact.created":
            _apply_artifact_event(builders, event, run.id)
        elif event.event_type in _TERMINAL_EVENT_TYPES:
            if event.span_id is None and not builders:
                # 历史 Run：没有 tracing 节点就不合成根，保持 limited 判定。
                continue
            root_span_id = _apply_terminal_event(builders, event, run)

    if not builders:
        diagnostics.append(_diagnostic(DIAGNOSTIC_NO_TRACING_EVENTS))
        return RunTraceDetail(
            summary=_build_summary(run, activity, trace_id=trace_id),
            root_span_id=None,
            spans=(),
            tree=(),
            diagnostics=tuple(diagnostics),
            content_policy=CONTENT_POLICY_METADATA_ONLY,
        )

    if root_span_id is None:
        # 异常数据：有节点但没有 run.started。补一个根，让树仍可读。
        root_span_id = derived_root_span_id
        root_builder = _SpanBuilder(
            span=_new_span(
                span_id=root_span_id,
                kind=RunTraceSpanKind.ROOT,
                name=_ROOT_SPAN_NAME,
                event_seq=0,
                started_at=run.started_at or run.created_at,
            )
        )
        builders[root_span_id] = root_builder
        if is_terminal_run:
            root_builder.mark_terminal(_root_status_for(run), run.finished_at or run.created_at)

    _resolve_parents(builders, root_span_id)
    _settle_statuses(builders, run, is_terminal_run)

    ordered_spans = _order_spans(builders, root_span_id)
    tree, tree_diagnostics = _build_tree(builders, root_span_id)
    diagnostics.extend(tree_diagnostics)
    diagnostics.extend(_span_diagnostics(builders))

    spans = tuple(_finish_span(builder) for builder in ordered_spans)
    return RunTraceDetail(
        summary=_build_summary(
            run, activity, trace_id=trace_id, usage=_aggregate_usage(ordered_spans)
        ),
        root_span_id=root_span_id,
        spans=spans,
        tree=tree,
        diagnostics=tuple(diagnostics),
        content_policy=CONTENT_POLICY_METADATA_ONLY,
    )


def _apply_terminal_event(
    builders: dict[str, _SpanBuilder],
    event: RunEvent,
    run: Run,
) -> str:
    """把终态事件落到根节点，返回该根节点 ID。"""
    root_span_id = event.span_id or derive_root_span_id(run.id)
    root_builder = builders.get(root_span_id)
    if root_builder is None:
        root_builder = _SpanBuilder(
            span=_new_span(
                span_id=root_span_id,
                kind=RunTraceSpanKind.ROOT,
                name=_ROOT_SPAN_NAME,
                event_seq=event.seq,
                started_at=run.started_at,
            )
        )
        builders[root_span_id] = root_builder
    root_builder.mark_terminal(_TERMINAL_SPAN_STATUSES[event.event_type], event.occurred_at)
    if event.event_type == "run.failed":
        root_builder.update(
            error_code=_error_field(event.payload, "code"),
            error_message=_error_field(event.payload, "message"),
        )
    return root_span_id


def _apply_model_event(
    builders: dict[str, _SpanBuilder],
    event: RunEvent,
    run_id: str,
) -> None:
    """把一条模型生命周期事件并入节点累积状态。"""
    model_call_id = str(event.payload.get("model_call_id") or "")
    if not model_call_id:
        return
    span_id = event.span_id or derive_span_id(run_id, "model", model_call_id)
    builder = builders.get(span_id)
    if builder is None:
        builder = _SpanBuilder(
            span=_new_span(
                span_id=span_id,
                kind=RunTraceSpanKind.MODEL,
                name=str(event.payload.get("model_name") or "model"),
                event_seq=event.seq,
                started_at=event.occurred_at if event.event_type == "model.call.started" else None,
            )
        )
        if event.span_id is None:
            builder.add_diagnostic(DIAGNOSTIC_MISSING_SPAN_ID)
        if event.event_type != "model.call.started":
            builder.add_diagnostic(DIAGNOSTIC_COMPLETION_WITHOUT_START)
        builders[span_id] = builder
    model_name = str(event.payload.get("model_name") or builder.name)
    turn_index = event.payload.get("turn_index")
    span_changes: dict[str, object] = {"model_call_id": model_call_id, "model_name": model_name}
    if builder.name != model_name:
        span_changes["name"] = model_name
    if _is_plain_int(turn_index):
        span_changes["turn_index"] = turn_index
    if event.event_type == "model.call.started" and builder.started_at is None:
        span_changes["started_at"] = event.occurred_at
    builder.update(**span_changes)
    if event.event_type == "model.call.started":
        return
    if event.event_type == "model.call.completed":
        if builder.mark_terminal(RunTraceSpanStatus.COMPLETED, event.occurred_at):
            finish_reason = event.payload.get("finish_reason")
            builder.update(
                usage=_normalized_usage(event.payload.get("usage")),
                finish_reason=str(finish_reason) if finish_reason else None,
            )
        return
    if builder.mark_terminal(RunTraceSpanStatus.FAILED, event.occurred_at):
        builder.update(
            error_code=_error_field(event.payload, "code"),
            error_message=_error_field(event.payload, "message"),
        )


def _apply_tool_event(
    builders: dict[str, _SpanBuilder],
    event: RunEvent,
    run_id: str,
) -> None:
    """把一条工具生命周期事件并入节点累积状态。"""
    tool_call_id = str(event.payload.get("tool_call_id") or "")
    if not tool_call_id:
        return
    span_id = event.span_id or derive_span_id(run_id, "tool", tool_call_id)
    builder = builders.get(span_id)
    if builder is None:
        builder = _SpanBuilder(
            span=_new_span(
                span_id=span_id,
                kind=RunTraceSpanKind.TOOL,
                name=str(event.payload.get("tool_name") or "tool"),
                event_seq=event.seq,
                started_at=event.occurred_at if event.event_type == "tool.call.started" else None,
            )
        )
        if event.span_id is None:
            builder.add_diagnostic(DIAGNOSTIC_MISSING_SPAN_ID)
        if event.event_type != "tool.call.started":
            builder.add_diagnostic(DIAGNOSTIC_COMPLETION_WITHOUT_START)
        builders[span_id] = builder
    tool_name = str(event.payload.get("tool_name") or builder.name)
    span_changes = {"tool_call_id": tool_call_id, "tool_name": tool_name}
    if builder.name != tool_name:
        span_changes["name"] = tool_name
    if event.event_type == "tool.call.started" and builder.started_at is None:
        span_changes["started_at"] = event.occurred_at
    builder.update(**span_changes)
    if event.event_type == "tool.call.started":
        parent_model_call_id = event.payload.get("parent_model_call_id")
        builder.requested_parent_model_call_id = (
            str(parent_model_call_id) if parent_model_call_id else None
        )
        return
    if event.event_type == "tool.call.completed":
        if builder.mark_terminal(RunTraceSpanStatus.COMPLETED, event.occurred_at):
            result_checksum = event.payload.get("result_checksum")
            raw_result = event.payload.get("result")
            builder.update(
                result_checksum=str(result_checksum) if result_checksum else None,
                result_length=len(raw_result) if isinstance(raw_result, str) else None,
            )
        return
    if builder.mark_terminal(RunTraceSpanStatus.FAILED, event.occurred_at):
        builder.update(
            error_code=_error_field(event.payload, "code"),
            error_message=_error_field(event.payload, "message"),
        )


def _apply_artifact_event(
    builders: dict[str, _SpanBuilder],
    event: RunEvent,
    run_id: str,
) -> None:
    """把一条产物事件并入节点累积状态。"""
    artifact_id = str(event.payload.get("artifact_id") or "")
    if not artifact_id:
        return
    span_id = event.span_id or derive_span_id(run_id, "artifact", artifact_id)
    if span_id in builders:
        return
    filename = event.payload.get("filename")
    artifact_checksum = event.payload.get("checksum")
    builder = _SpanBuilder(
        span=RunTraceSpan(
            span_id=span_id,
            parent_span_id=None,
            kind=RunTraceSpanKind.ARTIFACT,
            name=str(filename or artifact_id),
            status=RunTraceSpanStatus.COMPLETED,
            started_at=event.occurred_at,
            finished_at=event.occurred_at,
            duration_ms=0,
            event_seq=event.seq,
            result_checksum=str(artifact_checksum) if artifact_checksum else None,
        ),
        # 产物事件本身就是"已完成"的快照，必须登记终态：否则终结 Run 时
        # _settle_statuses 会把它误翻转成 incomplete 并挂上 started_without_completion。
        terminal_seen=True,
    )
    if event.span_id is None:
        builder.add_diagnostic(DIAGNOSTIC_MISSING_SPAN_ID)
    builders[span_id] = builder


def resolve_tool_parent(
    *,
    tool_span_id: str,
    requested_parent_model_call_id: str | None,
    model_span_id_by_call_id: dict[str, str],
    root_span_id: str,
) -> tuple[str, str | None]:
    """裁决单个工具节点的父 span。

    只接受来源写下的可靠父级模型调用 ID；缺少声明、指向不存在的调用、或指向自己
    时都降级到 Run 根节点并返回稳定诊断 code，绝不按工具名或时间邻近猜测。

    Args:
        tool_span_id (str): 该工具节点的 span ID。
        requested_parent_model_call_id (str | None): 来源声明的父级模型调用 ID。
        model_span_id_by_call_id (dict[str, str]): 模型调用 ID 到 span ID 的索引。
        root_span_id (str): Run 根 span ID。

    Returns:
        tuple[str, str | None]: 裁决后的父 span ID 与诊断 code（无降级时为空）。
    """
    if requested_parent_model_call_id is None:
        return root_span_id, DIAGNOSTIC_PARENT_SOURCE_UNAVAILABLE
    resolved_parent_span_id = model_span_id_by_call_id.get(requested_parent_model_call_id)
    if resolved_parent_span_id is None:
        return root_span_id, DIAGNOSTIC_UNKNOWN_PARENT
    if resolved_parent_span_id == tool_span_id:
        return root_span_id, DIAGNOSTIC_SELF_PARENT
    return resolved_parent_span_id, None


def _resolve_parents(builders: dict[str, _SpanBuilder], root_span_id: str) -> None:
    """把模型与产物挂到 Run 根，并裁决工具节点声明的模型父级。"""
    model_span_id_by_call_id = {
        builder.span.model_call_id: builder.span_id
        for builder in builders.values()
        if builder.kind is RunTraceSpanKind.MODEL and builder.span.model_call_id
    }
    for builder in builders.values():
        if builder.kind in {RunTraceSpanKind.MODEL, RunTraceSpanKind.ARTIFACT}:
            builder.resolved_parent_span_id = root_span_id
            continue
        if builder.kind is not RunTraceSpanKind.TOOL:
            continue
        resolved_parent_span_id, diagnostic_code = resolve_tool_parent(
            tool_span_id=builder.span_id,
            requested_parent_model_call_id=builder.requested_parent_model_call_id,
            model_span_id_by_call_id=model_span_id_by_call_id,
            root_span_id=root_span_id,
        )
        builder.resolved_parent_span_id = resolved_parent_span_id
        if diagnostic_code is not None:
            builder.add_diagnostic(diagnostic_code)


def _settle_statuses(
    builders: dict[str, _SpanBuilder],
    run: Run,
    is_terminal_run: bool,
) -> None:
    """终结 Run 上仍未完成的 started 节点标记为 incomplete。"""
    if not is_terminal_run:
        return
    terminal_finished_at = run.finished_at or run.created_at
    for builder in builders.values():
        if builder.kind is RunTraceSpanKind.ROOT or builder.terminal_seen:
            continue
        builder.terminal_seen = True
        builder.update(
            status=RunTraceSpanStatus.INCOMPLETE,
            finished_at=builder.span.finished_at or terminal_finished_at,
        )
        builder.add_diagnostic(DIAGNOSTIC_STARTED_WITHOUT_COMPLETION)


def _order_spans(builders: dict[str, _SpanBuilder], root_span_id: str) -> list[_SpanBuilder]:
    """返回按开始时间与事件序号稳定排序的节点，根节点始终在最前。"""
    ordered_spans = sorted(
        (builder for builder in builders.values() if builder.span_id != root_span_id),
        key=_sort_key,
    )
    root_builder = builders.get(root_span_id)
    return ([root_builder] if root_builder is not None else []) + ordered_spans


def _build_tree(
    builders: dict[str, _SpanBuilder], root_span_id: str
) -> tuple[tuple[RunTraceTreeNode, ...], list[RunTraceDiagnostic]]:
    """按已裁决的父子关系构建树，并拦截环与孤立节点。"""
    diagnostics: list[RunTraceDiagnostic] = []
    children_by_parent: dict[str, list[str]] = {}
    for builder in builders.values():
        if builder.span_id == root_span_id:
            continue
        parent_span_id = builder.resolved_parent_span_id
        if parent_span_id is None or parent_span_id not in builders:
            parent_span_id = root_span_id
            builder.resolved_parent_span_id = root_span_id
            builder.add_diagnostic(DIAGNOSTIC_UNKNOWN_PARENT)
            diagnostics.append(
                _diagnostic(
                    DIAGNOSTIC_UNKNOWN_PARENT,
                    span_id=builder.span_id,
                    node_name=builder.name,
                )
            )
        children_by_parent.setdefault(parent_span_id, []).append(builder.span_id)

    reachable_span_ids: set[str] = set()
    pending_span_ids = [root_span_id]
    while pending_span_ids:
        current_span_id = pending_span_ids.pop()
        if current_span_id in reachable_span_ids:
            continue
        reachable_span_ids.add(current_span_id)
        pending_span_ids.extend(children_by_parent.get(current_span_id, []))

    for builder in builders.values():
        if builder.span_id in reachable_span_ids:
            continue
        # 环里的节点永远不会从根节点被访问到，就地降级到根并保留诊断 code。
        builder.resolved_parent_span_id = root_span_id
        builder.add_diagnostic(DIAGNOSTIC_CYCLIC_PARENT)
        children_by_parent.setdefault(root_span_id, []).append(builder.span_id)
        diagnostics.append(
            _diagnostic(
                DIAGNOSTIC_CYCLIC_PARENT,
                span_id=builder.span_id,
                node_name=builder.name,
            )
        )

    def build_node(span_id: str, ancestor_span_ids: frozenset[str]) -> RunTraceTreeNode:
        """递归构建节点，``ancestor_span_ids`` 兜住异常数据造成的无限递归。"""
        builder = builders[span_id]
        child_span_ids = [
            child_span_id
            for child_span_id in children_by_parent.get(span_id, [])
            if child_span_id not in ancestor_span_ids
        ]
        child_nodes = tuple(
            build_node(child_span_id, ancestor_span_ids | {child_span_id})
            for child_span_id in sorted(
                child_span_ids, key=lambda child_id: _sort_key(builders[child_id])
            )
        )
        return RunTraceTreeNode(span=_finish_span(builder), children=child_nodes)

    return (build_node(root_span_id, frozenset({root_span_id})),), diagnostics


def _span_diagnostics(builders: dict[str, _SpanBuilder]) -> list[RunTraceDiagnostic]:
    """把每个节点上的诊断 code 汇总成整树级诊断项。"""
    seen_keys: set[tuple[str, str]] = set()
    diagnostics: list[RunTraceDiagnostic] = []
    for builder in builders.values():
        for code in dict.fromkeys(builder.diagnostics):
            diagnostic_key = (code, builder.span_id)
            if diagnostic_key in seen_keys:
                continue
            seen_keys.add(diagnostic_key)
            diagnostics.append(_diagnostic(code, span_id=builder.span_id, node_name=builder.name))
    return diagnostics


def _finish_span(builder: _SpanBuilder) -> RunTraceSpan:
    """把累积状态固化为最终节点：补算耗时、父级与去重后的诊断。"""
    span = builder.span
    is_root = span.kind is RunTraceSpanKind.ROOT
    return replace(
        span,
        parent_span_id=None if is_root else builder.resolved_parent_span_id,
        duration_ms=_elapsed_ms(span.started_at, span.finished_at),
        diagnostics=tuple(dict.fromkeys(builder.diagnostics)),
    )


def _root_status_for(run: Run) -> RunTraceSpanStatus:
    """把 Run 终态映射为根节点状态。"""
    if run.status is RunStatus.FAILED:
        return RunTraceSpanStatus.FAILED
    if run.status is RunStatus.SUCCEEDED:
        return RunTraceSpanStatus.COMPLETED
    return RunTraceSpanStatus.INCOMPLETE


def _build_summary(
    run: Run,
    activity: RunTraceActivity,
    trace_id: str | None = None,
    usage: dict[str, int] | None = None,
) -> RunTraceSummary:
    """由 Run projection 与 tracing 计数构建列表/详情摘要。"""
    return RunTraceSummary(
        run_id=run.id,
        subject_id=run.subject_id,
        subject_name=run.subject_snapshot.subject_name,
        owner_id=run.owner_id,
        status=run.status,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=_elapsed_ms(run.started_at or run.created_at, run.finished_at),
        trace_id=trace_id or derive_trace_id(run.id),
        visibility=(
            RunTraceVisibility.FULL if activity.has_tracing_events else RunTraceVisibility.LIMITED
        ),
        model_call_count=activity.model_call_count,
        tool_call_count=activity.tool_call_count,
        usage=usage,
        error_count=1 if run.status in _FAILED_RUN_STATUSES else 0,
    )


def _aggregate_usage(ordered_spans: Sequence[_SpanBuilder]) -> dict[str, int] | None:
    """汇总各模型节点的 usage 计数。"""
    total_usage: dict[str, int] = {}
    for builder in ordered_spans:
        if not builder.span.usage:
            continue
        for usage_key, usage_value in builder.span.usage.items():
            total_usage[usage_key] = total_usage.get(usage_key, 0) + usage_value
    return total_usage or None


def _activity_from_events(events: Sequence[RunEvent]) -> RunTraceActivity:
    """从事件流统计模型、工具与产物事件条数。"""
    model_call_ids: set[str] = set()
    tool_call_ids: set[str] = set()
    artifact_count = 0
    for event in events:
        if event.event_type == "model.call.started":
            model_call_ids.add(str(event.payload.get("model_call_id") or ""))
        elif event.event_type == "tool.call.started":
            tool_call_ids.add(str(event.payload.get("tool_call_id") or ""))
        elif event.event_type == "artifact.created":
            artifact_count += 1
    return RunTraceActivity(
        model_call_count=len(model_call_ids - {""}),
        tool_call_count=len(tool_call_ids - {""}),
        artifact_count=artifact_count,
    )


def _normalized_usage(raw_usage: object) -> dict[str, int] | None:
    """只保留低敏 usage 计数并归一为整数。"""
    if not isinstance(raw_usage, dict) or not raw_usage:
        return None
    normalized_usage: dict[str, int] = {}
    for usage_key, usage_value in raw_usage.items():
        if _is_plain_int(usage_value):
            normalized_usage[str(usage_key)] = usage_value
    return normalized_usage or None


def _error_field(payload: dict[str, object], field_name: str) -> str | None:
    """从 error 载荷中提取单字段描述。"""
    error_payload = payload.get("error")
    if not isinstance(error_payload, dict):
        return None
    error_value = error_payload.get(field_name)
    return str(error_value) if error_value else None


def _diagnostic(
    code: str,
    *,
    span_id: str | None = None,
    node_name: str | None = None,
) -> RunTraceDiagnostic:
    """构造稳定诊断项。"""
    message = _DIAGNOSTIC_MESSAGES.get(code, code)
    if node_name:
        message = f"{message}（节点：{node_name}）"
    return RunTraceDiagnostic(code=code, message=message, span_id=span_id)


__all__ = [
    "CONTENT_POLICY_METADATA_ONLY",
    "DIAGNOSTIC_COMPLETION_WITHOUT_START",
    "DIAGNOSTIC_CYCLIC_PARENT",
    "DIAGNOSTIC_DUPLICATE_COMPLETION",
    "DIAGNOSTIC_MISSING_SPAN_ID",
    "DIAGNOSTIC_NO_TRACING_EVENTS",
    "DIAGNOSTIC_PARENT_SOURCE_UNAVAILABLE",
    "DIAGNOSTIC_SELF_PARENT",
    "DIAGNOSTIC_STARTED_WITHOUT_COMPLETION",
    "DIAGNOSTIC_UNKNOWN_PARENT",
    "RunExportError",
    "RunTraceUseCase",
    "project_run_trace",
    "resolve_tool_parent",
]
