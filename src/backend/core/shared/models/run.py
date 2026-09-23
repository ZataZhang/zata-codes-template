"""Canonical Run 领域模型与执行轨迹投影类型。

本模块是「Run 执行轨迹」子系统的领域层：Run/RunEvent envelope、由稳定 ID
确定性派生 trace/span 标识的算法，以及管理端只读诊断投影所需的类型。它不含
任何业务域字段与业务外键，派生项目在自己的执行器里构造 Run 与候选事件。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class RunStatus(str, Enum):
    """Canonical Run 状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    }
)


@dataclass(frozen=True)
class RunSubjectSnapshot:
    """创建 Run 时冻结的执行主体 provenance。

    执行主体是「这条 Run 由谁发起」的通用抽象：可以是一个业务 Agent、一个
    工作流定义或任何派生项目自定义的执行单元。模板不解释 ``subject_type``
    的取值，只保证它在 Run 生命周期内保持稳定，并作为 tracing 摘要的展示来源。

    Attributes:
        subject_type (str): 主体类型判别符，供派生项目的执行器路由使用。
        subject_id (str): 主体稳定标识。
        subject_name (str): 主体展示名（写入诊断摘要）。
        snapshot_checksum (str): 主体定义快照校验值，用于回溯当时版本。
    """

    subject_type: str
    subject_id: str
    subject_name: str
    snapshot_checksum: str


@dataclass
class Run:
    """可由事件重建的 Run projection。"""

    id: str
    owner_id: str
    subject_id: str
    subject_type: str
    subject_snapshot: RunSubjectSnapshot
    subject_snapshot_checksum: str
    status: RunStatus
    last_event_seq: int
    created_at: datetime
    input_content: tuple[dict[str, object], ...] = ()
    started_at: datetime | None = None
    finished_at: datetime | None = None
    final_message_id: str | None = None
    error: dict[str, Any] | None = None
    executor_instance_id: str | None = None
    lease_expires_at: datetime | None = None


@dataclass(frozen=True)
class RunEvent:
    """数据库提交后的 canonical event envelope。"""

    run_id: str
    seq: int
    event_type: str
    occurred_at: datetime
    recorded_at: datetime
    subject_id: str
    subject_snapshot_checksum: str
    payload: dict[str, Any]
    payload_checksum: str
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: int = 1
    trace_id: str | None = None
    span_id: str | None = None


@dataclass(frozen=True)
class RunExportAudit:
    """原始 Run 事件导出的低敏审计记录。"""

    id: str
    run_id: str
    actor_id: str
    event_count: int
    byte_count: int


@dataclass(frozen=True)
class RunEventCandidate:
    """执行器提交、尚未分配序号的候选事件。

    Attributes:
        event_type (str): canonical event 类型，必须命中事件目录。
        payload (dict[str, Any]): 事件载荷，只允许目录声明的字段。
        occurred_at (datetime | None): 业务发生时间；为空时由 repository 用提交时间补齐。
        provenance (dict[str, Any]): 来源描述，只允许目录声明的字段。
        trace_id (str | None): 本条事件所属 Run trace；为空表示该事件不参与 tracing。
        span_id (str | None): 本条事件归属的 span；started/completed/failed 使用同一 ID。
    """

    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None


TRACE_ID_LENGTH = 32
SPAN_ID_LENGTH = 16
# 派生算法带版本号：换算法时旧 Run 已提交的 ID 仍可原样回读，不会被重新解释。
_TRACE_ID_DERIVATION_VERSION = "v1"
_ALL_ZERO_TRACE_ID = "0" * TRACE_ID_LENGTH
_ALL_ZERO_SPAN_ID = "0" * SPAN_ID_LENGTH


def _derive_identifier(discriminator: str, source_identifier: str, length: int) -> str:
    """按版本化算法派生固定长度小写十六进制标识。

    Args:
        discriminator (str): 区分同一来源在不同用途下派生的 ID。
        source_identifier (str): 稳定来源标识（如 run_id 或模型调用 ID）。
        length (int): 目标十六进制字符数。

    Returns:
        str: 定长十六进制 ID。
    """
    identifier_material = f"{_TRACE_ID_DERIVATION_VERSION}:{discriminator}:{source_identifier}"
    return hashlib.sha256(identifier_material.encode("utf-8")).hexdigest()[:length]


def derive_trace_id(run_id: str) -> str:
    """从稳定 run_id 派生该 Run 的 trace ID。

    OTel 要求 trace ID 非全零；哈希碰撞到全零时退化为末位 1，保证同一 run_id
    在任何进程、任何重启后都得到同一结果。

    Args:
        run_id (str): Canonical Run ID。

    Returns:
        str: 32 位十六进制 trace ID。
    """
    trace_id = _derive_identifier("run-trace", run_id, TRACE_ID_LENGTH)
    return trace_id if trace_id != _ALL_ZERO_TRACE_ID else f"{'0' * 31}1"


def derive_root_span_id(run_id: str) -> str:
    """从稳定 run_id 派生 Run 根 span ID。

    Args:
        run_id (str): Canonical Run ID。

    Returns:
        str: 16 位十六进制 span ID。
    """
    root_span_id = _derive_identifier("run-root-span", run_id, SPAN_ID_LENGTH)
    return root_span_id if root_span_id != _ALL_ZERO_SPAN_ID else f"{'0' * 15}1"


def derive_span_id(run_id: str, span_kind: str, source_call_id: str) -> str:
    """从来源调用 ID 确定性地派生 span ID。

    只在来源提供稳定调用 ID 时使用；来源不给 ID 的执行器应在第一次 started
    时自行生成并配对，恢复后以已落库的 span_id 为准。

    Args:
        run_id (str): Canonical Run ID。
        span_kind (str): span 类别（``model``/``tool``/``artifact`` 等）。
        source_call_id (str): 来源提供的稳定调用标识。

    Returns:
        str: 16 位十六进制 span ID。
    """
    span_id = _derive_identifier(f"span:{span_kind}", f"{run_id}:{source_call_id}", SPAN_ID_LENGTH)
    return span_id if span_id != _ALL_ZERO_SPAN_ID else f"{'0' * 15}1"


class RunTraceSpanKind(str, Enum):
    """执行轨迹节点类别。"""

    ROOT = "root"
    MODEL = "model"
    TOOL = "tool"
    ARTIFACT = "artifact"


class RunTraceSpanStatus(str, Enum):
    """执行轨迹节点状态。"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INCOMPLETE = "incomplete"


class RunTraceVisibility(str, Enum):
    """Run 的 tracing 可见度。"""

    FULL = "full"
    LIMITED = "limited"


@dataclass(frozen=True)
class RunTraceSpan:
    """投影后的单个执行轨迹节点（只含低敏元数据）。

    Attributes:
        span_id (str): 稳定 span ID。
        parent_span_id (str | None): 已裁决的父 span；根节点为空。
        kind (RunTraceSpanKind): 节点类别。
        name (str): 展示名（Run 根 / 模型名 / 工具名）。
        status (RunTraceSpanStatus): 节点状态。
        started_at (datetime | None): 已知开始时间。
        finished_at (datetime | None): 已知结束时间。
        duration_ms (int | None): 已确认耗时；缺少任一端点时为空。
        event_seq (int): 建立该节点的首个事件序号，用于稳定排序。
        model_call_id (str | None): 模型调用 ID（模型节点）。
        model_name (str | None): 模型标识。
        turn_index (int | None): 模型轮次。
        usage (dict[str, int] | None): 低敏 usage 计数。
        finish_reason (str | None): 完成原因。
        tool_call_id (str | None): 工具调用 ID（工具节点）。
        tool_name (str | None): 工具名。
        result_checksum (str | None): 工具结果 checksum。
        result_length (int | None): 工具结果字符数。
        error_code (str | None): 失败码。
        error_message (str | None): 失败描述。
        diagnostics (tuple[str, ...]): 挂在节点上的稳定诊断 code。
    """

    span_id: str
    parent_span_id: str | None
    kind: RunTraceSpanKind
    name: str
    status: RunTraceSpanStatus
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    event_seq: int
    model_call_id: str | None = None
    model_name: str | None = None
    turn_index: int | None = None
    usage: dict[str, int] | None = None
    finish_reason: str | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    result_checksum: str | None = None
    result_length: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class RunTraceDiagnostic:
    """整棵轨迹上的稳定诊断项。

    Attributes:
        code (str): 稳定诊断 code，供前端映射文案。
        message (str): 面向管理员的低敏说明。
        span_id (str | None): 相关节点；整 Run 级诊断为空。
    """

    code: str
    message: str
    span_id: str | None = None


@dataclass(frozen=True)
class RunTraceTreeNode:
    """按父子关系嵌套的轨迹节点。"""

    span: RunTraceSpan
    children: tuple[RunTraceTreeNode, ...] = ()


@dataclass(frozen=True)
class RunTraceSummary:
    """Run 级诊断摘要，用于列表与详情头部。"""

    run_id: str
    subject_id: str
    subject_name: str
    owner_id: str
    status: RunStatus
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    trace_id: str
    visibility: RunTraceVisibility
    model_call_count: int
    tool_call_count: int
    usage: dict[str, int] | None
    error_count: int


@dataclass(frozen=True)
class RunTraceDetail:
    """单个 Run 的完整诊断投影（只读，可随时从事件重建）。"""

    summary: RunTraceSummary
    root_span_id: str | None
    spans: tuple[RunTraceSpan, ...]
    tree: tuple[RunTraceTreeNode, ...]
    diagnostics: tuple[RunTraceDiagnostic, ...]
    content_policy: str


@dataclass(frozen=True)
class RunTraceActivity:
    """按 run 聚合的 tracing 事件计数，用于列表页而不必读取全部事件。"""

    model_call_count: int = 0
    tool_call_count: int = 0
    artifact_count: int = 0

    @property
    def has_tracing_events(self) -> bool:
        """是否已写入任何模型、工具或产物 tracing 事件。"""
        return (self.model_call_count + self.tool_call_count + self.artifact_count) > 0


@dataclass(frozen=True)
class RunQuery:
    """Admin 诊断用的 Run 分页查询条件。"""

    run_id: str | None = None
    subject_id: str | None = None
    status: RunStatus | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    offset: int = 0
    limit: int = 50


@dataclass(frozen=True)
class RunPage:
    """一页 Run projection 与命中总数。"""

    runs: tuple[Run, ...]
    total: int
