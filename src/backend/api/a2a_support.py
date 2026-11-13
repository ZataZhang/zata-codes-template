"""A2A 任务授权、Canonical Run 投影与 SSE 支持函数。"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, Header, HTTPException, Path

from backend.api.dependencies import get_agent_catalog_use_case
from backend.core.agent import (
    AgentCatalogUseCase,
    AgentNotFoundError,
    AgentRunUseCase,
    AgentUnavailableError,
    CreateAgentRunCommand,
)
from backend.core.shared.interfaces.agent_types import A2ACredential
from backend.core.shared.models.run import Run, RunEvent, RunStatus
from backend.infrastructure.config.settings import config

_TERMINAL_STATES = {
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
    RunStatus.INTERRUPTED,
}


def _require_version(a2a_version: str | None) -> None:
    """只接受本 API 明确实现的 A2A 协议版本。"""
    if a2a_version != "1.0":
        raise HTTPException(status_code=400, detail="unsupported_a2a_version")


def _public_a2a_base_url() -> str:
    """读取部署方声明的 A2A origin，不采信未验证的 HTTP Host。"""
    public_base_url = config.a2a.public_base_url.strip().rstrip("/")
    parsed_url = urlsplit(public_base_url)
    if (
        parsed_url.scheme not in {"https", "http"}
        or not parsed_url.hostname
        or parsed_url.username
        or parsed_url.password
        or parsed_url.path
        or parsed_url.query
        or parsed_url.fragment
        or (parsed_url.scheme == "http" and not config.a2a.allow_loopback_for_dev)
    ):
        raise HTTPException(status_code=503, detail="a2a_public_base_url_unavailable")
    return public_base_url


def _resolve_credential(
    *,
    authorization: str | None,
    agent_id: str,
    catalog: AgentCatalogUseCase,
) -> A2ACredential:
    """验证 bearer 凭据并确认凭据只绑定路径中的 Agent。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="unauthorized")
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="unauthorized")
    credential = catalog.resolve_a2a_credential(token)
    if credential is None or credential.agent_id != agent_id:
        raise HTTPException(status_code=404, detail="agent_not_found")
    try:
        agent = catalog.get_agent(credential.organization_id, agent_id)
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="agent_not_found") from None
    if not credential.is_active or not agent.is_enabled or not agent.is_published:
        raise HTTPException(status_code=404, detail="agent_not_found")
    return credential


def get_current_a2a_credential(
    agent_id: str = Path(...),
    authorization: str | None = Header(default=None),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> A2ACredential:
    """从 A2A Bearer 头解析凭据，并通过路径 Agent ID 进行目标授权。"""
    return _resolve_credential(
        authorization=authorization,
        agent_id=agent_id,
        catalog=catalog,
    )


def _read_text_message(message_document: object) -> tuple[str, str]:
    """校验 A2A Message 的角色和纯文本输入，并返回 messageId 与内容。"""
    if not isinstance(message_document, dict) or message_document.get("role") != "ROLE_USER":
        raise HTTPException(status_code=422, detail="user_message_required")
    message_id = message_document.get("messageId")
    if not isinstance(message_id, str) or not message_id.strip() or len(message_id) > 128:
        raise HTTPException(status_code=422, detail="message_id_required")
    parts = message_document.get("parts")
    if not isinstance(parts, list):
        raise HTTPException(status_code=422, detail="text_message_required")
    if not parts or any(
        not isinstance(part, dict)
        or not isinstance(part.get("text"), str)
        or sum(key in part for key in ("text", "raw", "url", "data")) != 1
        for part in parts
    ):
        raise HTTPException(status_code=422, detail="text_message_required")
    text_parts = [str(part["text"]) for part in parts]
    message_text = "\n".join(part for part in text_parts if part.strip()).strip()
    if not message_text or len(message_text) > 32_000:
        raise HTTPException(status_code=422, detail="text_message_required")
    return message_id, message_text


def _task_state(run: Run) -> str:
    """映射 Canonical Run 状态到 A2A Task 状态。"""
    return {
        RunStatus.QUEUED: "TASK_STATE_SUBMITTED",
        RunStatus.RUNNING: "TASK_STATE_WORKING",
        RunStatus.CANCELLING: "TASK_STATE_WORKING",
        RunStatus.SUCCEEDED: "TASK_STATE_COMPLETED",
        RunStatus.FAILED: "TASK_STATE_FAILED",
        RunStatus.CANCELLED: "TASK_STATE_CANCELED",
        RunStatus.INTERRUPTED: "TASK_STATE_FAILED",
    }[run.status]


def _task_document(
    run: Run,
    run_events: list[RunEvent] | tuple[RunEvent, ...],
    *,
    include_artifacts: bool = True,
    history_length: int | None = None,
) -> dict[str, Any]:
    """把既有 Run/Event 投影为 A2A Task，不创建第二套任务状态。"""
    input_message: dict[str, Any] | None = None
    result_message: dict[str, Any] | None = None
    for run_event in run_events:
        if run_event.event_type == "input.accepted":
            text_value = ""
            content = run_event.payload.get("content")
            if isinstance(content, list):
                text_value = "\n".join(
                    str(part.get("text", ""))
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            elif isinstance(content, str):
                text_value = content
            input_message = {
                "messageId": f"input_{run.id}",
                "taskId": run.id,
                "contextId": run.conversation_id,
                "role": "ROLE_USER",
                "parts": [{"text": text_value}],
            }
        elif run_event.event_type == "message.completed":
            assistant_text = run_event.payload.get("content")
            if isinstance(assistant_text, str):
                result_message = {
                    "messageId": f"assistant_{run.id}",
                    "taskId": run.id,
                    "contextId": run.conversation_id,
                    "role": "ROLE_AGENT",
                    "parts": [{"text": assistant_text}],
                }
    artifacts = []
    if result_message is not None:
        artifacts.append(
            {
                "artifactId": f"artifact_{run.id}",
                "name": "response",
                "parts": result_message["parts"],
            }
        )
    task: dict[str, Any] = {
        "id": run.id,
        "contextId": run.conversation_id,
        "status": {
            "state": _task_state(run),
            "timestamp": (run.finished_at or run.started_at or run.created_at).isoformat(),
        },
    }
    if include_artifacts:
        task["artifacts"] = artifacts
    history = [message for message in (input_message, result_message) if message]
    if history_length != 0:
        task["history"] = history[-history_length:] if history_length else history
    if run.error:
        task["status"]["message"] = {
            "messageId": f"failure_{run.id}",
            "taskId": run.id,
            "contextId": run.conversation_id,
            "role": "ROLE_AGENT",
            "parts": [{"text": "The agent could not complete this task."}],
        }
    return task


def _task_events(
    run: Run, run_events: list[RunEvent] | tuple[RunEvent, ...]
) -> list[dict[str, Any]]:
    """映射已持久化消息片段和状态为 A2A 流事件。"""
    task_events: list[dict[str, Any]] = []
    for run_event in run_events:
        if run_event.event_type == "message.delta":
            delta_text = run_event.payload.get("delta")
            if isinstance(delta_text, str):
                task_events.append(
                    {
                        "artifactUpdate": {
                            "taskId": run.id,
                            "contextId": run.conversation_id,
                            "artifact": {
                                "artifactId": f"artifact_{run.id}",
                                "parts": [{"text": delta_text}],
                            },
                            "append": True,
                        },
                    }
                )
        elif run_event.event_type in {
            "run.started",
            "run.completed",
            "run.failed",
            "run.cancelled",
        }:
            current_run_state = {
                "run.completed": "TASK_STATE_COMPLETED",
                "run.failed": "TASK_STATE_FAILED",
                "run.cancelled": "TASK_STATE_CANCELED",
            }.get(run_event.event_type, "TASK_STATE_WORKING")
            task_events.append(
                {
                    "statusUpdate": {
                        "taskId": run.id,
                        "contextId": run.conversation_id,
                        "status": {
                            "state": current_run_state,
                            "timestamp": run_event.recorded_at.isoformat(),
                        },
                    },
                }
            )
        elif run_event.event_type == "message.completed":
            last_artifact_event = next(
                (
                    task_event.get("artifactUpdate")
                    for task_event in reversed(task_events)
                    if isinstance(task_event.get("artifactUpdate"), dict)
                ),
                None,
            )
            if isinstance(last_artifact_event, dict):
                last_artifact_event["lastChunk"] = True
    return task_events


def _read_task(
    *,
    run_id: str,
    credential: A2ACredential,
    run_use_case: AgentRunUseCase,
    after_seq: int = 0,
) -> tuple[Run, list[RunEvent]]:
    """按当前服务凭据读取同组织、同 Agent 的任务和事件。"""
    try:
        run = run_use_case.get_a2a_run(
            run_id=run_id,
            organization_id=credential.organization_id,
            agent_id=credential.agent_id,
            credential_id=credential.id,
        )
        events = run_use_case.list_a2a_events(
            run_id=run_id,
            organization_id=credential.organization_id,
            agent_id=credential.agent_id,
            credential_id=credential.id,
            after_seq=after_seq,
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="task_not_found") from None
    return run, list(events)


async def _wait_for_run(
    run_id: str,
    credential: A2ACredential,
    run_use_case: AgentRunUseCase,
) -> Run | None:
    """按 SendMessage 的 returnImmediately=false 语义等待任务终态。"""
    while True:
        try:
            current_run = run_use_case.get_a2a_run(
                run_id=run_id,
                organization_id=credential.organization_id,
                agent_id=credential.agent_id,
                credential_id=credential.id,
            )
        except AgentNotFoundError:
            return None
        if current_run is None or current_run.status in _TERMINAL_STATES:
            return current_run
        await asyncio.sleep(0.1)


async def _create_task(
    *,
    agent_id: str,
    credential: A2ACredential,
    request_document: dict[str, object],
    run_use_case: AgentRunUseCase,
) -> Run:
    """从 A2A Message 创建同一 Canonical Run。"""
    message_id, message_text = _read_text_message(request_document.get("message"))
    message_document = request_document.get("message")
    context_id = message_document.get("contextId") if isinstance(message_document, dict) else None
    try:
        run = run_use_case.create_run(
            CreateAgentRunCommand(
                organization_id=credential.organization_id,
                owner_id=f"a2a:{credential.id}",
                agent_id=agent_id,
                message=message_text,
                idempotency_key=f"a2a:{message_id}",
                conversation_id=context_id if isinstance(context_id, str) else None,
            )
        )
    except AgentNotFoundError:
        raise HTTPException(status_code=404, detail="agent_or_context_not_found") from None
    except AgentUnavailableError as unavailable_error:
        raise HTTPException(status_code=409, detail=str(unavailable_error)) from None
    except ValueError as request_error:
        raise HTTPException(status_code=422, detail=str(request_error)) from None
    except Exception:
        raise HTTPException(status_code=503, detail="agent_unavailable") from None
    run_use_case.schedule_run(run.id)
    return run


async def _stream_task_events(
    *, credential: A2ACredential, run_id: str, run_use_case: AgentRunUseCase
) -> AsyncIterator[str]:
    """轮询 canonical event store 并以 SSE 发出 A2A Task 增量。"""
    last_sequence = 0
    send_initial_task = True
    while True:
        try:
            run, events = await asyncio.to_thread(
                _read_task,
                run_id=run_id,
                credential=credential,
                run_use_case=run_use_case,
                after_seq=last_sequence,
            )
        except HTTPException:
            return
        if send_initial_task:
            initial_task = json.dumps(
                {"task": _task_document(run, events)},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"data: {initial_task}\n\n"
            send_initial_task = False
            last_sequence = run.last_event_seq
            if run.status in _TERMINAL_STATES:
                return
            await asyncio.sleep(0.2)
            continue
        for run_event in events:
            last_sequence = max(last_sequence, run_event.seq)
        for task_event in _task_events(run, events):
            event_data = json.dumps(task_event, ensure_ascii=False, separators=(",", ":"))
            yield f"data: {event_data}\n\n"
        if run.status in _TERMINAL_STATES:
            return
        await asyncio.sleep(0.2)


__all__ = [
    "_require_version",
    "_public_a2a_base_url",
    "_resolve_credential",
    "get_current_a2a_credential",
    "_read_text_message",
    "_task_state",
    "_task_document",
    "_task_events",
    "_read_task",
    "_wait_for_run",
    "_create_task",
    "_stream_task_events",
]
