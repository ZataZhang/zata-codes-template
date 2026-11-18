"""Agent Run 冻结的 A2A 对端授权测试。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from backend.core.agent.runs import AgentRunUseCase
from backend.core.shared.interfaces.agent_types import A2APeer, AgentDefinition
from backend.core.shared.models.run import Run, RunStatus, RunSubjectSnapshot


class _AgentRepository:
    """提供可变 Agent 绑定与受批准对端目录。"""

    def __init__(self, agent: AgentDefinition, peers: Sequence[A2APeer]) -> None:
        self.agent = agent
        self.peers = peers

    def get_agent(self, _organization_id: str, _agent_id: str) -> AgentDefinition:
        return self.agent

    def list_a2a_peers(self, _organization_id: str) -> Sequence[A2APeer]:
        return self.peers


def _agent(allowed_peer_ids: tuple[str, ...]) -> AgentDefinition:
    """构造带有给定当前对端绑定的 Agent。"""
    now = datetime.now(UTC)
    return AgentDefinition(
        id="agent-1",
        organization_id="org-1",
        created_by="admin-1",
        name="Helper",
        description="Test agent",
        instructions="Help",
        model_name="test-model",
        skill_id=None,
        is_enabled=True,
        is_published=True,
        created_at=now,
        updated_at=now,
        allowed_peer_ids=allowed_peer_ids,
    )


def _peer(peer_id: str) -> A2APeer:
    """构造当前已批准并启用的组织对端。"""
    now = datetime.now(UTC)
    return A2APeer(
        id=peer_id,
        organization_id="org-1",
        created_by="admin-1",
        name=peer_id,
        card_url=f"https://{peer_id}.example/card",
        endpoint_url=f"https://{peer_id}.example/a2a",
        is_approved=True,
        is_enabled=True,
        approved_by="platform-admin-1",
        created_at=now,
        updated_at=now,
    )


def _queued_run(allowed_peer_ids: list[str]) -> Run:
    """构造持久化快照中的排队 Run。"""
    return Run(
        id="run-1",
        owner_id="member-1",
        subject_id="agent-1",
        subject_type="agent",
        subject_snapshot=RunSubjectSnapshot("agent", "agent-1", "Helper", "a" * 64),
        subject_snapshot_checksum="a" * 64,
        status=RunStatus.QUEUED,
        last_event_seq=0,
        created_at=datetime.now(UTC),
        organization_id="org-1",
        execution_snapshot={"allowed_peer_ids": allowed_peer_ids},
    )


def test_queued_run_does_not_inherit_a_later_agent_peer_binding() -> None:
    """运行创建后新增的 Agent 对端绑定不会进入既有 Run。"""
    old_peer = _peer("peer-old")
    new_peer = _peer("peer-new")
    agent_repository = _AgentRepository(
        _agent((old_peer.id, new_peer.id)),
        (old_peer, new_peer),
    )
    run_use_case = AgentRunUseCase.__new__(AgentRunUseCase)
    run_use_case._agent_repository = agent_repository

    allowed_peers = run_use_case._approved_peers_for_run(_queued_run([old_peer.id]))

    assert [peer.id for peer in allowed_peers] == [old_peer.id]


def test_removed_agent_binding_revokes_a_peer_for_a_queued_run() -> None:
    """执行前移除 Agent 绑定后，已排队 Run 也不能再调用该对端。"""
    old_peer = _peer("peer-old")
    agent_repository = _AgentRepository(_agent(()), (old_peer,))
    run_use_case = AgentRunUseCase.__new__(AgentRunUseCase)
    run_use_case._agent_repository = agent_repository

    assert run_use_case._approved_peers_for_run(_queued_run([old_peer.id])) == ()
