"""组织成员的 Agent 目录与 Canonical Run API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from backend.api.agent_schemas import (
    AgentRunCreateRequest,
    AgentRunEventResponse,
    AgentRunEventsResponse,
    AgentRunListItem,
    AgentRunListResponse,
    AgentRunResponse,
    MemberAgentListResponse,
    MemberAgentResponse,
)
from backend.api.dependencies import (
    get_agent_catalog_use_case,
    get_agent_run_use_case,
    get_current_public_user,
)
from backend.core.agent import (
    AgentCatalogUseCase,
    AgentNotFoundError,
    AgentRunUseCase,
    AgentUnavailableError,
    CreateAgentRunCommand,
)
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.shared.models.run import Run, RunEvent

router = APIRouter(tags=["agents"])


def _require_public_organization(principal: AuthenticatedPrincipal) -> str:
    """拒绝没有服务端组织归属的 public 会话。"""
    if not principal.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="organization_scope_required"
        )
    return principal.organization_id


def _agent_run_item(run: Run) -> AgentRunListItem:
    """映射一条 Run 为成员历史列表项。"""
    return AgentRunListItem(
        id=run.id,
        conversation_id=run.conversation_id,
        agent_id=run.subject_id,
        agent_name=run.subject_snapshot.subject_name,
        status=run.status.value,
        created_at=run.created_at.isoformat(),
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
    )


def _event_text(run_events: list[RunEvent] | tuple[RunEvent, ...]) -> tuple[str, str | None]:
    """从 Canonical Event 中读取成员自己的输入与最终回复。"""
    input_message = ""
    assistant_message: str | None = None
    for run_event in run_events:
        if run_event.event_type == "input.accepted":
            accepted_content = run_event.payload.get("content")
            if isinstance(accepted_content, str):
                input_message = accepted_content
            elif isinstance(accepted_content, list):
                input_message = " ".join(
                    str(content_part.get("text", ""))
                    for content_part in accepted_content
                    if isinstance(content_part, dict) and content_part.get("type") == "text"
                )
        elif run_event.event_type == "message.completed":
            completed_content = run_event.payload.get("content")
            if isinstance(completed_content, str):
                assistant_message = completed_content
    return input_message, assistant_message


def _run_detail_response(
    run: Run, run_events: list[RunEvent] | tuple[RunEvent, ...]
) -> AgentRunResponse:
    """生成 Run 详情，并只向已授权 owner 返回消息正文。"""
    input_message, assistant_message = _event_text(run_events)
    return AgentRunResponse(
        **_agent_run_item(run).model_dump(),
        input_message=input_message,
        assistant_message=assistant_message,
        unavailable_reason=(
            str(run.error.get("code")) if run.error and run.error.get("code") else None
        ),
    )


@router.get("/agents", response_model=MemberAgentListResponse)
def list_member_agents(
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> MemberAgentListResponse:
    """列出当前组织已发布 Agent，并报告模型或启用状态。"""
    organization_id = _require_public_organization(principal)
    return MemberAgentListResponse(
        items=[
            MemberAgentResponse(
                id=entry.agent.id,
                name=entry.agent.name,
                description=entry.agent.description,
                is_enabled=entry.agent.is_enabled,
                is_runnable=entry.is_runnable,
                unavailable_reason=entry.unavailable_reason,
            )
            for entry in catalog.list_agents(organization_id, published_only=True)
        ]
    )


@router.post("/agent-runs", response_model=AgentRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_agent_run(
    request: AgentRunCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunResponse:
    """以当前 public 会话组织和 owner 创建并调度 Agent Run。"""
    organization_id = _require_public_organization(principal)
    try:
        run = run_use_case.create_run(
            CreateAgentRunCommand(
                organization_id=organization_id,
                owner_id=principal.user_id,
                agent_id=request.agent_id,
                message=request.message,
                idempotency_key=idempotency_key or "",
                conversation_id=request.conversation_id,
            )
        )
    except AgentUnavailableError as unavailable_error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(unavailable_error)
        ) from None
    except AgentNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agent or conversation not found"
        ) from None
    except ValueError as invalid_request:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(invalid_request)
        ) from None
    run_use_case.schedule_run(run.id)
    run_events = run_use_case.list_scoped_events(
        run_id=run.id,
        organization_id=organization_id,
        owner_id=principal.user_id,
    )
    return _run_detail_response(run, run_events)


@router.get("/agent-runs", response_model=AgentRunListResponse)
def list_agent_runs(
    conversation_id: str | None = Query(default=None, max_length=64),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunListResponse:
    """按当前用户与组织读取可重开的历史 Run。"""
    organization_id = _require_public_organization(principal)
    runs, total = run_use_case.list_scoped_runs(
        organization_id=organization_id,
        owner_id=principal.user_id,
        conversation_id=conversation_id,
        offset=offset,
        limit=limit,
    )
    return AgentRunListResponse(items=[_agent_run_item(run) for run in runs], total=total)


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(
    run_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunResponse:
    """独立新请求读取当前成员的 Run、最终回复与持久状态。"""
    organization_id = _require_public_organization(principal)
    try:
        run = run_use_case.get_scoped_run(
            run_id=run_id,
            organization_id=organization_id,
            owner_id=principal.user_id,
        )
        run_events = run_use_case.list_scoped_events(
            run_id=run.id,
            organization_id=organization_id,
            owner_id=principal.user_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None
    return _run_detail_response(run, run_events)


@router.get("/agent-runs/{run_id}/events", response_model=AgentRunEventsResponse)
def get_agent_run_events(
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunEventsResponse:
    """返回当前 owner 可见的 canonical event 增量。"""
    organization_id = _require_public_organization(principal)
    try:
        run_events = run_use_case.list_scoped_events(
            run_id=run_id,
            organization_id=organization_id,
            owner_id=principal.user_id,
            after_seq=after_seq,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None
    return AgentRunEventsResponse(
        items=[
            AgentRunEventResponse(
                seq=run_event.seq,
                event_type=run_event.event_type,
                occurred_at=run_event.occurred_at.isoformat(),
                payload=run_event.payload,
            )
            for run_event in run_events
        ],
        next_after_seq=run_events[-1].seq if run_events else after_seq,
    )


@router.post("/agent-runs/{run_id}/cancel", response_model=AgentRunResponse)
async def cancel_agent_run(
    run_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunResponse:
    """仅允许当前 owner 取消当前组织的 Run。"""
    organization_id = _require_public_organization(principal)
    try:
        run = await run_use_case.cancel_scoped_run(
            run_id=run_id,
            organization_id=organization_id,
            owner_id=principal.user_id,
        )
        run_events = run_use_case.list_scoped_events(
            run_id=run.id,
            organization_id=organization_id,
            owner_id=principal.user_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None
    return _run_detail_response(run, run_events)


__all__ = ["router"]
