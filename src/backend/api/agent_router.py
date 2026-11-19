"""组织成员的 Agent 目录与 Canonical Run API。"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from backend.api.agent_schemas import (
    AgentRunAssetListResponse,
    AgentRunAssetResponse,
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
    PUBLIC_SESSION_COOKIE_NAME,
    get_agent_catalog_use_case,
    get_agent_run_use_case,
    get_current_public_user,
    get_public_auth_service,
)
from backend.core.agent import (
    AgentCatalogUseCase,
    AgentNotFoundError,
    AgentRunUseCase,
    AgentUnavailableError,
    CreateAgentRunCommand,
)
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.service import AuthService
from backend.core.shared.models.run import TERMINAL_RUN_STATUSES, Run, RunEvent

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
        skill_version=(
            int(run.execution_snapshot["skill_version"])
            if run.execution_snapshot and run.execution_snapshot.get("skill_version") is not None
            else None
        ),
        skill_version_id=(
            str(run.execution_snapshot["skill_version_id"])
            if run.execution_snapshot and run.execution_snapshot.get("skill_version_id")
            else None
        ),
        unavailable_reason=(
            str(run.error.get("code")) if run.error and run.error.get("code") else None
        ),
    )


def _run_asset_items(
    run: Run, run_events: list[RunEvent] | tuple[RunEvent, ...]
) -> list[AgentRunAssetResponse]:
    """从 Canonical Event 投影资产元数据，不另建任务或资产状态库。"""
    assets: list[AgentRunAssetResponse] = []
    for run_event in run_events:
        if run_event.event_type == "input.accepted":
            resources = run_event.payload.get("resources")
            if isinstance(resources, list):
                assets.extend(
                    AgentRunAssetResponse(
                        id=str(resource.get("id") or f"resource_{run.id}_{run_event.seq}"),
                        run_id=run.id,
                        kind=str(resource.get("kind") or "input"),
                        created_at=run_event.recorded_at.isoformat(),
                    )
                    for resource in resources
                    if isinstance(resource, dict)
                )
        elif run_event.event_type == "artifact.created":
            assets.append(
                AgentRunAssetResponse(
                    id=str(
                        run_event.payload.get("artifact_id") or f"artifact_{run.id}_{run_event.seq}"
                    ),
                    run_id=run.id,
                    kind=str(run_event.payload.get("kind") or "output"),
                    created_at=run_event.recorded_at.isoformat(),
                )
            )
    return assets


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


def _read_run_with_events(
    run_use_case: AgentRunUseCase,
    *,
    run_id: str,
    organization_id: str,
    owner_id: str,
) -> tuple[Run, list[RunEvent] | tuple[RunEvent, ...]]:
    """在同一授权边界读取 Run 与事件，供详情、资产和取消复用。"""
    run = run_use_case.get_scoped_run(
        run_id=run_id,
        organization_id=organization_id,
        owner_id=owner_id,
    )
    run_events = run_use_case.list_scoped_events(
        run_id=run.id,
        organization_id=organization_id,
        owner_id=owner_id,
    )
    return run, run_events


@router.get("/agent-runs/{run_id}", response_model=AgentRunResponse)
def get_agent_run(
    run_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunResponse:
    """独立新请求读取当前成员的 Run、最终回复与持久状态。"""
    try:
        run, run_events = _read_run_with_events(
            run_use_case,
            run_id=run_id,
            organization_id=_require_public_organization(principal),
            owner_id=principal.user_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None
    return _run_detail_response(run, run_events)


@router.get("/agent-runs/{run_id}/assets", response_model=AgentRunAssetListResponse)
def get_agent_run_assets(
    run_id: str,
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> AgentRunAssetListResponse:
    """按所属 Run 的组织和 owner 读取输入资源与产物元数据。"""
    try:
        run, run_events = _read_run_with_events(
            run_use_case,
            run_id=run_id,
            organization_id=_require_public_organization(principal),
            owner_id=principal.user_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None
    return AgentRunAssetListResponse(items=_run_asset_items(run, run_events))


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


@router.get("/agent-runs/{run_id}/events/stream")
def stream_agent_run_events(
    request: Request,
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    principal: AuthenticatedPrincipal = Depends(get_current_public_user),
    auth_service: AuthService = Depends(get_public_auth_service),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> StreamingResponse:
    """通过单个同源 SSE 请求持续读取当前成员的 Canonical Run Events。"""
    organization_id = _require_public_organization(principal)
    session_token = request.cookies.get(PUBLIC_SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
    try:
        run_use_case.get_scoped_run(
            run_id=run_id,
            organization_id=organization_id,
            owner_id=principal.user_id,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None

    async def event_stream() -> AsyncIterator[str]:
        """按事件序号发送增量，并在会话、组织或 Run 终止时关闭流。"""
        last_sequence = after_seq
        last_keepalive_at = time.monotonic()
        while True:
            current_time = time.monotonic()
            current_principal = await asyncio.to_thread(auth_service.resolve_session, session_token)
            if (
                current_principal is None
                or current_principal.user_id != principal.user_id
                or current_principal.organization_id != organization_id
            ):
                return
            try:
                current_run = await asyncio.to_thread(
                    run_use_case.get_scoped_run,
                    run_id=run_id,
                    organization_id=organization_id,
                    owner_id=principal.user_id,
                )
                new_events = await asyncio.to_thread(
                    run_use_case.list_scoped_events,
                    run_id=run_id,
                    organization_id=organization_id,
                    owner_id=principal.user_id,
                    after_seq=last_sequence,
                )
            except AgentNotFoundError:
                return
            for run_event in new_events:
                event_document = AgentRunEventResponse(
                    seq=run_event.seq,
                    event_type=run_event.event_type,
                    occurred_at=run_event.occurred_at.isoformat(),
                    payload=run_event.payload,
                ).model_dump()
                yield (
                    "data: "
                    + json.dumps(event_document, ensure_ascii=False, separators=(",", ":"))
                    + "\n\n"
                )
                last_sequence = run_event.seq
            if current_run.status in TERMINAL_RUN_STATUSES:
                return
            if not new_events and current_time - last_keepalive_at >= 15:
                yield ": keep-alive\n\n"
                last_keepalive_at = current_time
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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
