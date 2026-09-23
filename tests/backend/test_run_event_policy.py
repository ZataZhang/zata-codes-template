"""Canonical event catalog 与状态机测试。"""

from __future__ import annotations

import pytest

from backend.core.shared.models.run import RunEventCandidate, RunStatus
from backend.core.shared.models.run_policy import (
    TerminalRunAppendError,
    decide_projection_transition,
)


def test_unknown_or_sensitive_event_payload_is_rejected() -> None:
    """验证未知类型、额外字段和凭据/隐藏思维链字段不能入库。"""
    with pytest.raises(ValueError, match="未知"):
        decide_projection_transition(
            RunStatus.RUNNING, RunEventCandidate("reasoning.delta", {"text": "hidden"})
        )
    with pytest.raises(ValueError, match="schema"):
        decide_projection_transition(
            RunStatus.RUNNING,
            RunEventCandidate(
                "message.delta",
                {
                    "message_id": "message",
                    "content_index": 0,
                    "delta": "safe",
                    "api_key": "forbidden",
                },
            ),
        )
    with pytest.raises(ValueError, match="禁止"):
        decide_projection_transition(
            RunStatus.RUNNING,
            RunEventCandidate(
                "tool.call.started",
                {
                    "tool_call_id": "tool",
                    "tool_name": "search",
                    "arguments": {"password": "forbidden"},
                },
            ),
        )


def test_terminal_state_cannot_reopen() -> None:
    """验证唯一终态不可追加或重开，且拒收是可单独识别的类型。

    执行侧要靠这个类型把"Run 已经不归我管了"与真正的 payload / 状态机错误分开：
    前者良性、就地收手，后者必须继续往上抛。
    """
    with pytest.raises(TerminalRunAppendError, match="终态"):
        decide_projection_transition(
            RunStatus.SUCCEEDED,
            RunEventCandidate(
                "message.delta",
                {"message_id": "message", "content_index": 0, "delta": "late"},
            ),
        )


def test_artifact_created_accepts_only_public_metadata() -> None:
    """验证 Artifact 事件可入库，但不允许泄漏物理存储键。"""
    transition = decide_projection_transition(
        RunStatus.RUNNING,
        RunEventCandidate(
            "artifact.created",
            {
                "type": "output",
                "artifact_id": "artifact_1",
                "filename": "quote.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": 100,
                "checksum": "a" * 64,
            },
        ),
    )
    assert transition.next_status is RunStatus.RUNNING
    syncable_transition = decide_projection_transition(
        RunStatus.RUNNING,
        RunEventCandidate(
            "artifact.created",
            {
                "type": "output",
                "artifact_id": "artifact_2",
                "filename": "reviewed.xlsx",
                "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "size": 101,
                "checksum": "b" * 64,
                "sync_action": "sync_rates_to_production",
            },
        ),
    )
    assert syncable_transition.next_status is RunStatus.RUNNING
    with pytest.raises(ValueError, match="schema"):
        decide_projection_transition(
            RunStatus.RUNNING,
            RunEventCandidate(
                "artifact.created",
                {
                    "type": "output",
                    "artifact_id": "artifact_1",
                    "filename": "quote.xlsx",
                    "content_type": (
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    ),
                    "size": 100,
                    "checksum": "a" * 64,
                    "storage_key": "secret.blob",
                },
            ),
        )


def test_run_created_event_uses_generic_subject_keys() -> None:
    """``run.created`` 只接受通用主体字段，不接受业务域字段。"""
    transition = decide_projection_transition(
        RunStatus.QUEUED,
        RunEventCandidate(
            "run.created",
            {"subject_id": "subject_1", "subject_snapshot_checksum": "c" * 64},
        ),
    )
    assert transition.next_status is RunStatus.QUEUED
    with pytest.raises(ValueError, match="schema"):
        decide_projection_transition(
            RunStatus.QUEUED,
            RunEventCandidate(
                "run.created",
                {"agent_id": "agent_1", "agent_snapshot_checksum": "c" * 64},
            ),
        )
