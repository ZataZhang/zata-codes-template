"""Canonical event catalog、状态机与安全校验。

冻结「哪些事件类型存在、每类允许哪些字段、哪些字段名被视为敏感」这三件事，
使 Run 的事件流成为可校验、可重建的单一事实源。任何携带凭据或隐藏推理字段名
的候选事件都被拒绝，避免诊断功能变成第二个敏感数据仓库。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.core.shared.models.run import (
    SPAN_ID_LENGTH,
    TERMINAL_RUN_STATUSES,
    TRACE_ID_LENGTH,
    RunEventCandidate,
    RunStatus,
)

EVENT_PAYLOAD_KEYS: dict[str, frozenset[str]] = {
    "run.created": frozenset({"subject_id", "subject_snapshot_checksum"}),
    "input.accepted": frozenset({"input_id", "content", "content_checksum", "resources"}),
    "run.started": frozenset({"started_at"}),
    "message.started": frozenset({"message_id", "role"}),
    "message.delta": frozenset({"message_id", "content_index", "delta"}),
    "message.completed": frozenset({"message_id", "content", "content_checksum"}),
    "model.call.started": frozenset({"model_call_id", "model_name", "turn_index"}),
    "model.call.completed": frozenset(
        {"model_call_id", "model_name", "turn_index", "usage", "finish_reason"}
    ),
    "model.call.failed": frozenset({"model_call_id", "model_name", "turn_index", "error"}),
    "tool.call.started": frozenset({"tool_call_id", "tool_name", "arguments"}),
    "tool.call.completed": frozenset({"tool_call_id", "result", "result_checksum"}),
    "tool.call.failed": frozenset({"tool_call_id", "error"}),
    "artifact.created": frozenset(
        {"type", "artifact_id", "filename", "content_type", "size", "checksum"}
    ),
    "run.cancelling": frozenset({"requested_by", "requested_at"}),
    "run.completed": frozenset({"message_id"}),
    "run.failed": frozenset({"error"}),
    "run.cancelled": frozenset({"external_stop_confirmed"}),
    "run.interrupted": frozenset({"reason_code", "lease_expired_at"}),
}
# 可选字段只在这些事件类型上被接受，并且必须与必需字段一起恰好覆盖允许集合：
# 来源能力不足时可以整字段缺席，但不能携带目录之外的字段。
OPTIONAL_PAYLOAD_KEYS: dict[str, frozenset[str]] = {
    "artifact.created": frozenset({"sync_action"}),
    # 只有来源能给出可靠 parent model call ID 时才带上，用于挂到对应模型 span；
    # 缺席即代表"父级来源不可确认"，由投影降级到 Run 根节点。
    "tool.call.started": frozenset({"parent_model_call_id"}),
}
PROVENANCE_KEYS = frozenset({"source_type", "source_event_id"})
SENSITIVE_KEY_PARTS = (
    "api_key",
    "authorization",
    "cookie",
    "password",
    "reasoning",
    "secret",
    "token",
)
_TRACE_ID_PATTERN = re.compile(rf"^[0-9a-f]{{{TRACE_ID_LENGTH}}}$")
_SPAN_ID_PATTERN = re.compile(rf"^[0-9a-f]{{{SPAN_ID_LENGTH}}}$")


class TerminalRunAppendError(ValueError):
    """在已终态的 Run 上追加事件被拒。

    仍然继承 ``ValueError``，既有 ``except ValueError`` 调用点的行为不变；单独
    成类是为了让执行侧能把"这个 Run 已经不归我管了"与真正的 payload / 状态机
    错误区分开——前者是良性结果，后者必须继续往上抛。
    """


@dataclass(frozen=True)
class ProjectionTransition:
    """单条合法事件对 Run projection 的影响。"""

    next_status: RunStatus
    is_terminal: bool


def _contains_sensitive_key(document: Any) -> bool:
    """递归检查可能携带凭据或隐藏思维链的字段名。"""
    if isinstance(document, dict):
        return any(
            any(sensitive_part in str(key).lower() for sensitive_part in SENSITIVE_KEY_PARTS)
            or _contains_sensitive_key(value)
            for key, value in document.items()
        )
    if isinstance(document, list):
        return any(_contains_sensitive_key(value) for value in document)
    return False


def _validate_trace_identifiers(candidate: RunEventCandidate) -> None:
    """校验 candidate 携带的 trace/span 标识格式与配对关系。

    trace ID 与 span ID 必须满足 OpenTelemetry 的固定长度与非全零约束；span ID
    只在同一 trace 内成立，因此不允许单独出现。

    Args:
        candidate (RunEventCandidate): 待校验候选事件。

    Raises:
        ValueError: 标识格式非法或 span 缺少 trace 时抛出。
    """
    if candidate.trace_id is None:
        if candidate.span_id is not None:
            raise ValueError("canonical event span 缺少 trace")
        return
    if not _TRACE_ID_PATTERN.match(candidate.trace_id):
        raise ValueError("canonical event trace_id 格式非法")
    if candidate.span_id is None:
        return
    if not _SPAN_ID_PATTERN.match(candidate.span_id):
        raise ValueError("canonical event span_id 格式非法")


def validate_event_candidate(candidate: RunEventCandidate) -> None:
    """按冻结 catalog 校验 candidate payload、provenance 与 trace 标识。"""
    allowed_payload_keys = EVENT_PAYLOAD_KEYS.get(candidate.event_type)
    if allowed_payload_keys is None:
        raise ValueError("未知 canonical event type")
    optional_payload_keys = OPTIONAL_PAYLOAD_KEYS.get(candidate.event_type, frozenset())
    payload_keys = set(candidate.payload)
    has_valid_payload_keys = allowed_payload_keys.issubset(payload_keys) and payload_keys.issubset(
        allowed_payload_keys | optional_payload_keys
    )
    if not has_valid_payload_keys:
        raise ValueError("canonical event payload 不符合 schema")
    if not set(candidate.provenance).issubset(PROVENANCE_KEYS):
        raise ValueError("canonical event provenance 不符合 schema")
    if _contains_sensitive_key(candidate.payload) or _contains_sensitive_key(candidate.provenance):
        raise ValueError("canonical event 含禁止字段")
    _validate_trace_identifiers(candidate)


def decide_projection_transition(
    current_status: RunStatus, candidate: RunEventCandidate
) -> ProjectionTransition:
    """由 Core 独占裁决状态迁移与终态。"""
    validate_event_candidate(candidate)
    if current_status in TERMINAL_RUN_STATUSES:
        raise TerminalRunAppendError("终态 Run 不可追加事件")
    transition_status = {
        "run.started": RunStatus.RUNNING,
        "run.cancelling": RunStatus.CANCELLING,
        "run.completed": RunStatus.SUCCEEDED,
        "run.failed": RunStatus.FAILED,
        "run.cancelled": RunStatus.CANCELLED,
        "run.interrupted": RunStatus.INTERRUPTED,
    }.get(candidate.event_type, current_status)
    allowed_sources = {
        "run.started": {RunStatus.QUEUED},
        "run.cancelling": {RunStatus.QUEUED, RunStatus.RUNNING},
        "run.completed": {RunStatus.RUNNING},
        "run.failed": {RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.CANCELLING},
        "run.cancelled": {RunStatus.CANCELLING},
        "run.interrupted": {
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.CANCELLING,
        },
    }
    if (
        candidate.event_type in allowed_sources
        and current_status not in allowed_sources[candidate.event_type]
    ):
        raise ValueError("非法 Run 状态迁移")
    return ProjectionTransition(
        next_status=transition_status,
        is_terminal=transition_status in TERMINAL_RUN_STATUSES,
    )
