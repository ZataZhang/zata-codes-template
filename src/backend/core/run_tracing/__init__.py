"""Run 执行轨迹核心编排子包。

把已提交的 Canonical Run/Event 投影成管理端可读的诊断树：模型轮次、工具调用、
产物与终态归并成带稳定诊断 code 的树，父子关系只接受事件里显式写下的信息。
本子包只依赖 ``core/shared`` 中的端口与模型，遵循依赖向内原则。
"""

from __future__ import annotations

from backend.core.run_tracing.trace_use_cases import (
    CONTENT_POLICY_METADATA_ONLY,
    DIAGNOSTIC_COMPLETION_WITHOUT_START,
    DIAGNOSTIC_CYCLIC_PARENT,
    DIAGNOSTIC_DUPLICATE_COMPLETION,
    DIAGNOSTIC_MISSING_SPAN_ID,
    DIAGNOSTIC_NO_TRACING_EVENTS,
    DIAGNOSTIC_PARENT_SOURCE_UNAVAILABLE,
    DIAGNOSTIC_SELF_PARENT,
    DIAGNOSTIC_STARTED_WITHOUT_COMPLETION,
    DIAGNOSTIC_UNKNOWN_PARENT,
    RunExportError,
    RunTraceUseCase,
    project_run_trace,
    resolve_tool_parent,
)

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
