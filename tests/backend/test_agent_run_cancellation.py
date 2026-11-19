"""跨服务实例取消 Run 的状态与执行器确认测试。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Sequence

import pytest

from backend.core.agent.runs import AgentRunUseCase
from backend.core.shared.interfaces.agent_executor import AgentExecutionResult
from backend.core.shared.interfaces.agent_types import A2APeer
from backend.core.shared.models.run import (
    Run,
    RunEventCandidate,
    RunStatus,
    RunSubjectSnapshot,
)
from backend.core.shared.models.run_policy import decide_projection_transition


class _MemoryRunRepository:
    """为取消测试保留单条 Run projection 和事件顺序。"""

    def __init__(self, run: Run) -> None:
        self.run = run
        self.events: list[RunEventCandidate] = []

    def get_by_id(self, run_id: str) -> Run | None:
        return self.run if run_id == self.run.id else None

    def claim(self, run_id: str, instance_id: str, lease_expires_at: datetime) -> bool:
        if run_id != self.run.id or self.run.status is not RunStatus.QUEUED:
            return False
        self.run.executor_instance_id = instance_id
        self.run.lease_expires_at = lease_expires_at
        return True

    def heartbeat(self, run_id: str, instance_id: str, lease_expires_at: datetime) -> bool:
        if (
            run_id != self.run.id
            or self.run.executor_instance_id != instance_id
            or self.run.status in {RunStatus.CANCELLING, RunStatus.CANCELLED}
        ):
            return False
        self.run.lease_expires_at = lease_expires_at
        return True

    def append_event(self, run_id: str, candidate: RunEventCandidate) -> None:
        assert run_id == self.run.id
        transition = decide_projection_transition(self.run.status, candidate)
        self.events.append(candidate)
        self.run.status = transition.next_status
        self.run.last_event_seq += 1


class _BlockingExecutor:
    """在测试显式释放前保持 Run 执行中的模型请求。"""

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def execute(
        self,
        *,
        snapshot: dict[str, object],
        message: str,
        peers: Sequence[A2APeer],
        callbacks: object | None = None,
    ) -> AgentExecutionResult:
        self.started.set()
        await asyncio.Event().wait()
        return AgentExecutionResult(content="unreachable", model_name="test-model")


def _run(status: RunStatus = RunStatus.QUEUED) -> Run:
    """构造可被两个服务实例共享的 Run projection。"""
    return Run(
        id="run-1",
        owner_id="member-1",
        subject_id="agent-1",
        subject_type="agent",
        subject_snapshot=RunSubjectSnapshot("agent", "agent-1", "Helper", "a" * 64),
        subject_snapshot_checksum="a" * 64,
        status=status,
        last_event_seq=0,
        created_at=datetime.now(UTC),
        organization_id="org-1",
        execution_snapshot={
            "organization_id": "org-1",
            "model_name": "test-model",
            "instructions": "Be helpful.",
            "allowed_peer_ids": [],
        },
        input_content=({"type": "text", "text": "Hello"},),
    )


def _use_case(
    run_repository: _MemoryRunRepository,
    executor: _BlockingExecutor,
    instance_id: str,
) -> AgentRunUseCase:
    """构造仅使用 Run 执行与取消端口的用例。"""
    run_use_case = AgentRunUseCase.__new__(AgentRunUseCase)
    run_use_case._run_repository = run_repository
    run_use_case._executor = executor
    run_use_case._executor_instance_id = instance_id
    run_use_case._active_tasks = {}
    return run_use_case


def test_remote_cancel_stays_cancelling_until_owner_confirms_stop() -> None:
    """没有本地执行任务的 API 实例不能伪报远端 Run 已停止。"""
    run = _run(RunStatus.RUNNING)
    run.executor_instance_id = "worker-a"
    run_repository = _MemoryRunRepository(run)
    cancel_service = _use_case(run_repository, _BlockingExecutor(), "api-b")

    cancelled_run = asyncio.run(
        cancel_service.cancel_scoped_run(
            run_id=run.id,
            organization_id="org-1",
            owner_id="member-1",
        )
    )

    assert cancelled_run.status is RunStatus.CANCELLING
    assert [event.event_type for event in run_repository.events] == ["run.cancelling"]


def test_owner_worker_confirms_remote_cancel_after_stopping_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """持有租约的 Worker 观察持久取消请求并写入取消终态。"""
    from backend.core.agent import runs as runs_module

    monkeypatch.setattr(runs_module, "RUN_EXECUTOR_HEARTBEAT_INTERVAL_SECONDS", 0.001)
    run_repository = _MemoryRunRepository(_run())
    blocking_executor = _BlockingExecutor()
    worker_service = _use_case(run_repository, blocking_executor, "worker-a")
    cancel_service = _use_case(run_repository, blocking_executor, "api-b")

    async def run_cancellation() -> None:
        worker_service.schedule_run("run-1")
        worker_task = worker_service._active_tasks["run-1"]
        await asyncio.wait_for(blocking_executor.started.wait(), timeout=1)
        requested_run = await cancel_service.cancel_scoped_run(
            run_id="run-1",
            organization_id="org-1",
            owner_id="member-1",
        )
        assert requested_run.status is RunStatus.CANCELLING
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(worker_task, timeout=1)

    asyncio.run(run_cancellation())

    assert run_repository.run.status is RunStatus.CANCELLED
    assert [event.event_type for event in run_repository.events][-2:] == [
        "run.cancelling",
        "run.cancelled",
    ]


def test_queued_run_without_an_owner_can_be_cancelled_immediately() -> None:
    """尚未被任何 Worker 认领的排队 Run 不会永久停在 cancelling。"""
    run_repository = _MemoryRunRepository(_run())
    cancel_service = _use_case(run_repository, _BlockingExecutor(), "api-a")

    cancelled_run = asyncio.run(
        cancel_service.cancel_scoped_run(
            run_id="run-1",
            organization_id="org-1",
            owner_id="member-1",
        )
    )

    assert cancelled_run.status is RunStatus.CANCELLED
    assert [event.event_type for event in run_repository.events] == [
        "run.cancelling",
        "run.cancelled",
    ]
