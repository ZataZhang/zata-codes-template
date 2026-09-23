"""Admin 域 Run 执行轨迹诊断的响应契约。

这些 DTO 是低敏边界的一部分：只承载模型/工具名、轮次、usage 计数、耗时、状态、
长度与 checksum，不包含 prompt、隐藏推理、正文内容或工具原始参数/结果。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RunTraceSpanResponse(BaseModel):
    """执行轨迹中的单个节点。"""

    span_id: str = Field(description="稳定 span ID。")
    parent_span_id: str | None = Field(default=None, description="已裁决的父 span；根节点为空。")
    kind: str = Field(description="节点类别：root / model / tool / artifact。")
    name: str = Field(description="节点展示名。")
    status: str = Field(description="节点状态：running / completed / failed / incomplete。")
    started_at: str | None = Field(default=None, description="已知开始时间（ISO 8601）。")
    finished_at: str | None = Field(default=None, description="已知结束时间（ISO 8601）。")
    duration_ms: int | None = Field(default=None, description="已确认耗时（毫秒）。")
    model_call_id: str | None = Field(default=None, description="模型调用 ID。")
    model_name: str | None = Field(default=None, description="模型标识。")
    turn_index: int | None = Field(default=None, description="模型轮次。")
    usage: dict[str, int] | None = Field(default=None, description="低敏 usage 计数。")
    finish_reason: str | None = Field(default=None, description="模型完成原因。")
    tool_call_id: str | None = Field(default=None, description="工具调用 ID。")
    tool_name: str | None = Field(default=None, description="工具名。")
    result_checksum: str | None = Field(default=None, description="结果或产物 checksum。")
    result_length: int | None = Field(default=None, description="结果字符数，不含内容本身。")
    error_code: str | None = Field(default=None, description="失败码。")
    error_message: str | None = Field(default=None, description="失败描述。")
    diagnostics: list[str] = Field(default_factory=list, description="挂在该节点上的诊断 code。")


class RunTraceTreeNodeResponse(BaseModel):
    """按父子关系嵌套的节点。"""

    span: RunTraceSpanResponse = Field(description="节点内容。")
    children: list[RunTraceTreeNodeResponse] = Field(default_factory=list, description="子节点。")


class RunTraceDiagnosticResponse(BaseModel):
    """整棵轨迹上的稳定诊断项。"""

    code: str = Field(description="稳定诊断 code。")
    message: str = Field(description="低敏说明。")
    span_id: str | None = Field(default=None, description="相关节点；整 Run 级诊断为空。")


class RunTraceSummaryResponse(BaseModel):
    """Run 级诊断摘要。"""

    run_id: str = Field(description="Canonical Run ID。")
    subject_id: str = Field(description="执行主体 ID。")
    subject_name: str = Field(description="执行主体名称。")
    owner_id: str = Field(description="Run 归属主体 ID。")
    status: str = Field(description="Run 状态。")
    created_at: str = Field(description="创建时间（ISO 8601）。")
    started_at: str | None = Field(default=None, description="开始时间（ISO 8601）。")
    finished_at: str | None = Field(default=None, description="结束时间（ISO 8601）。")
    duration_ms: int | None = Field(default=None, description="耗时（毫秒）。")
    trace_id: str = Field(description="稳定 trace ID。")
    visibility: str = Field(description="full 表示有 tracing 事件；limited 表示历史受限。")
    model_call_count: int = Field(description="模型调用数。")
    tool_call_count: int = Field(description="工具调用数。")
    usage: dict[str, int] | None = Field(default=None, description="低敏 usage 汇总。")
    error_count: int = Field(description="失败节点数。")


class RunTraceListResponse(BaseModel):
    """分页的 Run 诊断摘要列表。"""

    items: list[RunTraceSummaryResponse] = Field(description="当前页摘要。")
    total: int = Field(description="命中总数。")
    page: int = Field(description="当前页码，从 1 开始。")
    page_size: int = Field(description="每页条数。")


class RunTraceDetailResponse(BaseModel):
    """单个 Run 的完整诊断投影。"""

    summary: RunTraceSummaryResponse = Field(description="Run 级摘要。")
    root_span_id: str | None = Field(
        default=None, description="Run 根 span；无 tracing 事件时为空。"
    )
    spans: list[RunTraceSpanResponse] = Field(description="扁平节点列表，根节点在最前。")
    tree: list[RunTraceTreeNodeResponse] = Field(description="按父子关系嵌套的节点树。")
    diagnostics: list[RunTraceDiagnosticResponse] = Field(description="整棵轨迹的诊断项。")
    content_policy: str = Field(description="内容策略标识，固定为 metadata-only。")


__all__ = [
    "RunTraceDetailResponse",
    "RunTraceDiagnosticResponse",
    "RunTraceListResponse",
    "RunTraceSpanResponse",
    "RunTraceSummaryResponse",
    "RunTraceTreeNodeResponse",
]
