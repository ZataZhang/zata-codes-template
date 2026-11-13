"""A2A 1.0 HTTP+JSON/REST 入站适配器。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.api.a2a_support import (
    _create_task,
    _public_a2a_base_url,
    _read_task,
    _require_version,
    _stream_task_events,
    _task_document,
    _wait_for_run,
    get_current_a2a_credential,
)
from backend.api.dependencies import get_agent_catalog_use_case, get_agent_run_use_case
from backend.core.agent import AgentCatalogUseCase, AgentNotFoundError, AgentRunUseCase
from backend.core.shared.interfaces.agent_types import A2ACredential
from backend.core.shared.models.run import RunStatus

router = APIRouter(prefix="/a2a/agents/{agent_id}", tags=["a2a-1.0"])


@router.get("")
def get_agent_card(
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> dict[str, Any]:
    """返回只对该 Agent 入站凭据可见的 A2A Agent Card。"""
    _require_version(a2a_version)
    agent = catalog.get_agent(credential.organization_id, credential.agent_id)
    agent_url = _public_a2a_base_url() + f"/a2a/agents/{agent.id}"
    return {
        "name": agent.name,
        "description": agent.description,
        "version": "1.0.0",
        "supportedInterfaces": [
            {
                "url": agent_url,
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {"streaming": True, "pushNotifications": False},
        "defaultInputModes": ["text/plain"],
        "defaultOutputModes": ["text/plain"],
        "skills": [
            {
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "tags": [],
                "examples": [],
                "inputModes": ["text/plain"],
                "outputModes": ["text/plain"],
            }
        ],
        "securitySchemes": {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "description": "A2A service credential",
            }
        },
        "securityRequirements": [{"bearerAuth": []}],
    }


@router.post("/message:send")
async def send_message(
    request_document: dict[str, object],
    agent_id: str,
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> dict[str, Any]:
    """接受 A2A Message 并返回其 Canonical Run Task。"""
    _require_version(a2a_version)
    run = await _create_task(
        agent_id=agent_id,
        credential=credential,
        request_document=request_document,
        run_use_case=run_use_case,
    )
    configuration = request_document.get("configuration")
    return_immediately = (
        isinstance(configuration, dict) and configuration.get("returnImmediately") is True
    )
    current_run = (
        run
        if return_immediately
        else await _wait_for_run(run.id, credential, run_use_case) or run
    )
    events = list(
        run_use_case.list_a2a_events(
            run_id=current_run.id,
            organization_id=credential.organization_id,
            agent_id=agent_id,
            credential_id=credential.id,
        )
    )
    return {"task": _task_document(current_run, events)}


@router.post("/message:stream")
async def stream_message(
    request_document: dict[str, object],
    agent_id: str,
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> StreamingResponse:
    """建立任务后从 Canonical Run/Event 以 SSE 返回状态和结果增量。"""
    _require_version(a2a_version)
    run = await _create_task(
        agent_id=agent_id,
        credential=credential,
        request_document=request_document,
        run_use_case=run_use_case,
    )
    return StreamingResponse(
        _stream_task_events(credential=credential, run_id=run.id, run_use_case=run_use_case),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks")
def list_tasks(
    agent_id: str,
    context_id: str | None = Query(default=None, alias="contextId", max_length=64),
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=100),
    page_token: str | None = Query(default=None, alias="pageToken"),
    history_length: int | None = Query(default=None, alias="historyLength", ge=0, le=100),
    status: str | None = Query(default=None),
    include_artifacts: bool = Query(default=False, alias="includeArtifacts"),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> dict[str, Any]:
    """列出当前凭据创建的 Agent Tasks，不暴露其他凭据任务。"""
    _require_version(a2a_version)
    offset = 0
    if page_token:
        try:
            offset = max(0, int(page_token))
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid_page_token") from None
    task_status = {
        "TASK_STATE_SUBMITTED": RunStatus.QUEUED,
        "TASK_STATE_WORKING": RunStatus.RUNNING,
        "TASK_STATE_COMPLETED": RunStatus.SUCCEEDED,
        "TASK_STATE_FAILED": RunStatus.FAILED,
        "TASK_STATE_CANCELED": RunStatus.CANCELLED,
    }.get(status) if status else None
    if status and task_status is None:
        raise HTTPException(status_code=400, detail="invalid_task_status")
    runs, total = run_use_case.list_a2a_runs(
        organization_id=credential.organization_id,
        agent_id=agent_id,
        credential_id=credential.id,
        context_id=context_id,
        status=task_status,
        offset=offset,
        limit=page_size,
    )
    return {
        "tasks": [
            _task_document(
                run,
                list(
                    run_use_case.list_a2a_events(
                        run_id=run.id,
                        organization_id=credential.organization_id,
                        agent_id=agent_id,
                        credential_id=credential.id,
                    )
                ),
                include_artifacts=include_artifacts,
                history_length=history_length,
            )
            for run in runs
        ],
        "nextPageToken": str(offset + len(runs)) if offset + len(runs) < total else "",
        "pageSize": page_size,
        "totalSize": total,
    }


@router.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    agent_id: str,
    history_length: int | None = Query(default=None, alias="historyLength", ge=0, le=100),
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> dict[str, Any]:
    """按 A2A 凭据读取任务状态、消息与结果。"""
    _require_version(a2a_version)
    run, events = _read_task(run_id=task_id, credential=credential, run_use_case=run_use_case)
    task = _task_document(run, events)
    if history_length is not None:
        task["history"] = task["history"][-history_length:] if history_length else []
    return task


@router.post("/tasks/{task_id}:cancel")
async def cancel_task(
    task_id: str,
    agent_id: str,
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> dict[str, Any]:
    """取消当前凭据可见的非终态 Task。"""
    _require_version(a2a_version)
    run, _events = _read_task(run_id=task_id, credential=credential, run_use_case=run_use_case)
    try:
        cancelled_run = await run_use_case.cancel_scoped_run(
            run_id=run.id,
            organization_id=credential.organization_id,
            owner_id=f"a2a:{credential.id}",
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="task_not_found") from None
    events = list(
        run_use_case.list_a2a_events(
            run_id=cancelled_run.id,
            organization_id=credential.organization_id,
            agent_id=agent_id,
            credential_id=credential.id,
        )
    )
    return _task_document(cancelled_run, events)


@router.post("/tasks/{task_id}:subscribe")
def subscribe_task(
    task_id: str,
    agent_id: str,
    a2a_version: str | None = Header(default=None, alias="A2A-Version"),
    credential: A2ACredential = Depends(get_current_a2a_credential),
    run_use_case: AgentRunUseCase = Depends(get_agent_run_use_case),
) -> StreamingResponse:
    """订阅当前凭据可见任务的 SSE 状态事件。"""
    _require_version(a2a_version)
    existing_run, _events = _read_task(
        run_id=task_id, credential=credential, run_use_case=run_use_case
    )
    if existing_run.status in {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
        RunStatus.INTERRUPTED,
    }:
        raise HTTPException(status_code=400, detail="task_not_subscribable")
    return StreamingResponse(
        _stream_task_events(credential=credential, run_id=task_id, run_use_case=run_use_case),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


__all__ = ["router"]
