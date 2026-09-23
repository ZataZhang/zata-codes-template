"""Admin 域：Canonical Run 执行轨迹诊断路由。

所有端点都经过 admin 认证依赖；跨 owner 回看是管理诊断的既定能力，因此不复用
public owner 作用域的 Run API，也不接受 public 身份。
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from backend.api.admin.run_trace_schemas import (
    RunTraceDetailResponse,
    RunTraceDiagnosticResponse,
    RunTraceListResponse,
    RunTraceSpanResponse,
    RunTraceSummaryResponse,
    RunTraceTreeNodeResponse,
)
from backend.api.dependencies import get_current_admin_user, get_run_trace_use_case
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.run_tracing import RunExportError, RunTraceUseCase
from backend.core.shared.models.run import (
    RunQuery,
    RunStatus,
    RunTraceDetail,
    RunTraceDiagnostic,
    RunTraceSpan,
    RunTraceSummary,
    RunTraceTreeNode,
)

router = APIRouter(prefix="/admin/run-traces", tags=["admin-run-traces"])


def _isoformat_or_none(moment: datetime | None) -> str | None:
    """把可选时间点序列化为 ISO 8601。"""
    return moment.isoformat() if moment is not None else None


def _to_utc(moment: datetime | None) -> datetime | None:
    """把查询时间统一到 UTC，避免无时区输入与带时区列比较时报错。"""
    if moment is None:
        return None
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def _span_response(span: RunTraceSpan) -> RunTraceSpanResponse:
    """映射单个节点为低敏 DTO。"""
    return RunTraceSpanResponse(
        span_id=span.span_id,
        parent_span_id=span.parent_span_id,
        kind=span.kind.value,
        name=span.name,
        status=span.status.value,
        started_at=_isoformat_or_none(span.started_at),
        finished_at=_isoformat_or_none(span.finished_at),
        duration_ms=span.duration_ms,
        model_call_id=span.model_call_id,
        model_name=span.model_name,
        turn_index=span.turn_index,
        usage=span.usage,
        finish_reason=span.finish_reason,
        tool_call_id=span.tool_call_id,
        tool_name=span.tool_name,
        result_checksum=span.result_checksum,
        result_length=span.result_length,
        error_code=span.error_code,
        error_message=span.error_message,
        diagnostics=list(span.diagnostics),
    )


def _tree_node_response(node: RunTraceTreeNode) -> RunTraceTreeNodeResponse:
    """递归映射节点树为低敏 DTO。"""
    return RunTraceTreeNodeResponse(
        span=_span_response(node.span),
        children=[_tree_node_response(child) for child in node.children],
    )


def _diagnostic_response(diagnostic: RunTraceDiagnostic) -> RunTraceDiagnosticResponse:
    """映射诊断项。"""
    return RunTraceDiagnosticResponse(
        code=diagnostic.code,
        message=diagnostic.message,
        span_id=diagnostic.span_id,
    )


def _summary_response(summary: RunTraceSummary) -> RunTraceSummaryResponse:
    """映射 Run 级摘要。"""
    return RunTraceSummaryResponse(
        run_id=summary.run_id,
        subject_id=summary.subject_id,
        subject_name=summary.subject_name,
        owner_id=summary.owner_id,
        status=summary.status.value,
        created_at=summary.created_at.isoformat(),
        started_at=_isoformat_or_none(summary.started_at),
        finished_at=_isoformat_or_none(summary.finished_at),
        duration_ms=summary.duration_ms,
        trace_id=summary.trace_id,
        visibility=summary.visibility.value,
        model_call_count=summary.model_call_count,
        tool_call_count=summary.tool_call_count,
        usage=summary.usage,
        error_count=summary.error_count,
    )


def _detail_response(detail: RunTraceDetail) -> RunTraceDetailResponse:
    """映射 Run 诊断详情。"""
    return RunTraceDetailResponse(
        summary=_summary_response(detail.summary),
        root_span_id=detail.root_span_id,
        spans=[_span_response(span) for span in detail.spans],
        tree=[_tree_node_response(node) for node in detail.tree],
        diagnostics=[_diagnostic_response(diagnostic) for diagnostic in detail.diagnostics],
        content_policy=detail.content_policy,
    )


@router.get("", response_model=RunTraceListResponse)
async def list_run_traces(
    run_id: str | None = Query(None, description="按 Run ID 精确匹配。"),
    subject_id: str | None = Query(None, description="按执行主体 ID 过滤。"),
    status: RunStatus | None = Query(None, description="按 Run 状态过滤。"),
    created_after: datetime | None = Query(None, description="创建时间下界（ISO 8601）。"),
    created_before: datetime | None = Query(None, description="创建时间上界（ISO 8601）。"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    _admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    trace_use_case: RunTraceUseCase = Depends(get_run_trace_use_case),
) -> RunTraceListResponse:
    """分页列出最近 Run 的执行轨迹摘要。"""
    summaries, total = trace_use_case.list_run_summaries(
        RunQuery(
            run_id=run_id,
            subject_id=subject_id,
            status=status,
            created_after=_to_utc(created_after),
            created_before=_to_utc(created_before),
            offset=(page - 1) * page_size,
            limit=page_size,
        )
    )
    return RunTraceListResponse(
        items=[_summary_response(summary) for summary in summaries],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=RunTraceDetailResponse)
async def get_run_trace(
    run_id: str,
    _admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    trace_use_case: RunTraceUseCase = Depends(get_run_trace_use_case),
) -> RunTraceDetailResponse:
    """读取单个 Run 的执行轨迹详情。"""
    try:
        detail = trace_use_case.get_run_trace(run_id)
    except LookupError as lookup_error:
        raise HTTPException(status_code=404, detail="Run 不存在") from lookup_error
    return _detail_response(detail)


@router.get("/{run_id}/export")
async def export_run_trace(
    run_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    trace_use_case: RunTraceUseCase = Depends(get_run_trace_use_case),
) -> Response:
    """下载单个已终结 Run 的原始事件 JSON；管理员下载会留存低敏审计。"""
    try:
        export_bytes = trace_use_case.export_run_events(run_id, admin.user_id)
    except LookupError as lookup_error:
        raise HTTPException(status_code=404, detail="Run 不存在") from lookup_error
    except RunExportError as export_error:
        raise HTTPException(
            status_code=export_error.status_code, detail=str(export_error)
        ) from export_error
    return Response(
        content=export_bytes,
        media_type="application/json; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="run-{run_id}.json"',
        },
    )


__all__ = ["router"]
