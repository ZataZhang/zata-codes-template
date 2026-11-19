"""组织 Agent 管理 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.agent_schemas import (
    AdminAgentRunListResponse,
)
from backend.api.dependencies import (
    get_agent_run_use_case,
    get_current_organization_admin,
)
from backend.core.agent import (
    AgentNotFoundError,
    AgentRunUseCase,
)
from backend.core.auth.models import AuthenticatedPrincipal

router = APIRouter(prefix="/admin", tags=["admin-agent-management"])


@router.get("/agent-runs", response_model=AdminAgentRunListResponse)
def list_organization_agent_runs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AdminAgentRunListResponse:
    """列出本组织运行的低敏摘要，不暴露输入、回复或事件载荷。"""
    runs, total = run_use_case.list_organization_runs(
        organization_id=admin.organization_id or "", offset=offset, limit=limit
    )
    return AdminAgentRunListResponse(
        items=[
            {
                "id": run.id,
                "agent_id": run.subject_id,
                "agent_name": run.subject_snapshot.subject_name,
                "owner_id": run.owner_id,
                "status": run.status.value,
                "created_at": run.created_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "event_count": run.last_event_seq,
            }
            for run in runs
        ],
        total=total,
    )


@router.get("/agent-runs/{run_id}/events")
def get_organization_run_events(
    run_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> dict[str, object]:
    """向组织管理员呈现不包含消息正文的 Run 执行轨迹。"""
    try:
        run_events = run_use_case.list_organization_events(
            run_id=run_id,
            organization_id=admin.organization_id or "",
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="run_not_found") from None
    allowed_payload_keys = {
        "started_at",
        "model_call_id",
        "model_name",
        "turn_index",
        "usage",
        "finish_reason",
        "tool_call_id",
        "tool_name",
        "arguments",
        "result_checksum",
        "remote_task_id",
        "error",
        "requested_at",
        "external_stop_confirmed",
    }
    return {
        "items": [
            {
                "seq": run_event.seq,
                "event_type": run_event.event_type,
                "occurred_at": run_event.occurred_at.isoformat(),
                "payload": {
                    key: value
                    for key, value in run_event.payload.items()
                    if key in allowed_payload_keys
                },
            }
            for run_event in run_events
        ]
    }


__all__ = ["router"]
