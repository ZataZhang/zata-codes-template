"""A2A 1.0 REST Task 投影契约测试。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from backend.api.a2a_support import _read_text_message, _task_document, _task_events
from backend.core.shared.models.run import (
    Run,
    RunEvent,
    RunEventCandidate,
    RunStatus,
    RunSubjectSnapshot,
)
from backend.core.shared.models.run_policy import decide_projection_transition


def _run(status: RunStatus = RunStatus.SUCCEEDED) -> Run:
    """构造不连接数据库的 Canonical Run 夹具。"""
    now = datetime.now(UTC)
    return Run(
        id="run-123",
        owner_id="a2a:credential-1",
        subject_id="agent-1",
        subject_type="agent",
        subject_snapshot=RunSubjectSnapshot("agent", "agent-1", "Helper", "a" * 64),
        subject_snapshot_checksum="a" * 64,
        status=status,
        last_event_seq=2,
        created_at=now,
        organization_id="org-a",
        conversation_id="context-1",
    )


def _event(seq: int, event_type: str, payload: dict[str, object]) -> RunEvent:
    """构造 Run Event 视图。"""
    now = datetime.now(UTC)
    return RunEvent(
        run_id="run-123",
        seq=seq,
        event_type=event_type,
        occurred_at=now,
        recorded_at=now,
        subject_id="agent-1",
        subject_snapshot_checksum="a" * 64,
        payload=payload,
        payload_checksum="b" * 64,
    )


def test_a2a_message_accepts_official_role_and_plain_text_part() -> None:
    """A2A 1.0 使用 ROLE_USER 和无 kind 判别字段的纯文本 Part。"""
    message_id, message_text = _read_text_message(
        {
            "messageId": "message-1",
            "role": "ROLE_USER",
            "parts": [{"text": "hello"}],
        }
    )

    assert (message_id, message_text) == ("message-1", "hello")
    with pytest.raises(HTTPException, match="user_message_required"):
        _read_text_message(
            {
                "messageId": "message-2",
                "role": "user",
                "parts": [{"text": "hello"}],
            }
        )


def test_task_document_uses_task_states_artifacts_and_history_length() -> None:
    """Task 使用规范状态、Artifact 与 historyLength 省略规则。"""
    events = [
        _event(1, "input.accepted", {"content": [{"type": "text", "text": "hello"}]}),
        _event(2, "message.completed", {"content": "world"}),
    ]

    full_task = _task_document(_run(), events)
    compact_task = _task_document(
        _run(), events, include_artifacts=False, history_length=0
    )

    assert full_task["id"] == "run-123"
    assert full_task["status"]["state"] == "TASK_STATE_COMPLETED"
    assert full_task["artifacts"][0]["parts"] == [{"text": "world"}]
    assert len(full_task["history"]) == 2
    assert "artifacts" not in compact_task
    assert "history" not in compact_task


def test_stream_events_are_a2a_streamresponse_variants() -> None:
    """每个流消息只含一个 statusUpdate 或 artifactUpdate 变体。"""
    task_events = _task_events(
        _run(),
        [
            _event(1, "run.started", {"started_at": "2026-11-13T00:00:00Z"}),
            _event(2, "message.delta", {"delta": "world"}),
            _event(3, "message.completed", {"content": "world"}),
            _event(4, "run.completed", {"message_id": "assistant_run-123"}),
        ],
    )

    assert all(len(event) == 1 for event in task_events)
    assert task_events[0]["statusUpdate"]["status"]["state"] == "TASK_STATE_WORKING"
    assert task_events[1]["artifactUpdate"]["append"] is True
    assert task_events[1]["artifactUpdate"]["lastChunk"] is True
    assert task_events[2]["statusUpdate"]["status"]["state"] == "TASK_STATE_COMPLETED"


def test_outbound_task_id_is_allowed_as_low_sensitivity_trace_metadata() -> None:
    """远端 Task ID 可加入工具事件，但凭据仍由敏感字段校验拒绝。"""
    candidate = {
        "tool_call_id": "call-1",
        "result": {"status": "completed"},
        "result_checksum": "c" * 64,
        "remote_task_id": "remote-123",
    }

    assert decide_projection_transition(
        RunStatus.RUNNING, RunEventCandidate("tool.call.completed", candidate)
    ).next_status is RunStatus.RUNNING
    candidate["result"] = {"status": "completed", "api_key": "never-log-this"}
    with pytest.raises(ValueError, match="禁止"):
        decide_projection_transition(
            RunStatus.RUNNING, RunEventCandidate("tool.call.completed", candidate)
        )
