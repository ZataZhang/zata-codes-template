"""Canonical Run 驱动的 Agent 消息执行与 A2A Task 查询。"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Sequence

from backend.core.agent.catalog import AgentNotFoundError, AgentUnavailableError
from backend.core.agent.helpers import _checksum
from backend.core.shared.interfaces.agent_executor import AgentExecutor
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.agent_types import (
    A2APeer,
    AgentExecutionSnapshot,
    SkillRevision,
)
from backend.core.shared.interfaces.run_repository import RunRepository
from backend.core.shared.models.organization import DEFAULT_ORGANIZATION_ID
from backend.core.shared.models.run import (
    Run,
    RunEvent,
    RunEventCandidate,
    RunQuery,
    RunStatus,
    RunSubjectSnapshot,
    derive_root_span_id,
    derive_span_id,
    derive_trace_id,
)


@dataclass(frozen=True)
class CreateAgentRunCommand:
    """创建成员 Agent Run 的命令。"""

    organization_id: str
    owner_id: str
    agent_id: str
    message: str
    idempotency_key: str
    conversation_id: str | None = None


class AgentRunUseCase:
    """通过 Canonical Run/Event 创建、执行与查询 Agent 消息。"""

    def __init__(
        self,
        *,
        agent_repository: AgentRepository,
        run_repository: RunRepository,
        executor: AgentExecutor,
    ) -> None:
        """初始化在线 Run 用例。

        Args:
            agent_repository (AgentRepository): Agent、Skill 与 A2A 目录。
            run_repository (RunRepository): 现有 Canonical Run/Event 仓库。
            executor (AgentExecutor): 受控模型与 A2A 执行适配器。
        """
        self._agent_repository = agent_repository
        self._run_repository = run_repository
        self._executor = executor
        self._active_tasks: dict[str, asyncio.Task[None]] = {}
        self._executor_instance_id = uuid.uuid4().hex

    def create_run(self, command: CreateAgentRunCommand) -> Run:
        """校验组织授权后创建 Canonical Run 和输入事件。

        Args:
            command (CreateAgentRunCommand): 成员消息与组织 scope。

        Returns:
            Run: 持久化后可重新读取的 Run。

        Raises:
            AgentUnavailableError: Agent 或所需模型不可用时抛出。
            AgentNotFoundError: Agent 不属于当前组织或未发布时抛出。
            ValueError: 消息、会话或幂等输入非法时抛出。
        """
        message = command.message.strip()
        if not message or len(message) > 32_000:
            raise ValueError("message_required_or_too_large")
        if not command.idempotency_key.strip():
            raise ValueError("idempotency_key_required")
        agent = self._agent_repository.get_agent(command.organization_id, command.agent_id)
        if agent is None or not agent.is_published:
            raise AgentNotFoundError("Agent 不存在")
        if not agent.is_enabled:
            raise AgentUnavailableError("agent_disabled")
        if not self._executor.is_available:
            raise AgentUnavailableError(self._executor.unavailable_reason or "model_unavailable")
        model_name = agent.model_name or self._executor.default_model_name
        if not model_name:
            raise AgentUnavailableError("model_not_configured")
        if command.conversation_id:
            matching_runs = self._run_repository.query_runs_page(
                RunQuery(
                    organization_id=command.organization_id,
                    owner_id=command.owner_id,
                    conversation_id=command.conversation_id,
                    limit=1,
                )
            )
            if not matching_runs.runs or matching_runs.runs[0].subject_id != agent.id:
                raise AgentNotFoundError("Conversation 不存在")

        skill_revision: SkillRevision | None = None
        if agent.skill_id:
            resolved_skill = self._agent_repository.resolve_skill(
                command.organization_id, agent.skill_id
            )
            if resolved_skill is None:
                raise AgentUnavailableError("skill_unavailable")
            _, skill_revision = resolved_skill
        execution_snapshot = AgentExecutionSnapshot(
            agent_id=agent.id,
            organization_id=command.organization_id,
            agent_name=agent.name,
            instructions=agent.instructions,
            model_name=model_name,
            skill_id=agent.skill_id,
            skill_version_id=skill_revision.id if skill_revision else None,
            skill_version=skill_revision.version if skill_revision else None,
            skill_body=skill_revision.body if skill_revision else None,
        )
        snapshot_document: dict[str, object] = asdict(execution_snapshot)
        run_id = uuid.uuid4().hex
        conversation_id = command.conversation_id or uuid.uuid4().hex
        prior_conversation_runs = self._run_repository.query_runs_page(
            RunQuery(
                organization_id=command.organization_id,
                owner_id=command.owner_id,
                conversation_id=conversation_id,
                limit=20,
            )
        )
        conversation_history = self._conversation_history(prior_conversation_runs.runs)
        snapshot_document["conversation_history"] = conversation_history
        snapshot_checksum = _checksum(snapshot_document)
        run = Run(
            id=run_id,
            owner_id=command.owner_id,
            subject_id=agent.id,
            subject_type="agent",
            subject_snapshot=RunSubjectSnapshot(
                subject_type="agent",
                subject_id=agent.id,
                subject_name=agent.name,
                snapshot_checksum=snapshot_checksum,
            ),
            subject_snapshot_checksum=snapshot_checksum,
            status=RunStatus.QUEUED,
            last_event_seq=0,
            created_at=datetime.now(UTC),
            organization_id=command.organization_id,
            conversation_id=conversation_id,
            execution_snapshot=snapshot_document,
            input_content=({"type": "text", "text": message},),
        )
        scoped_key_hash = hashlib.sha256(
            f"{command.organization_id}:{command.owner_id}:{command.idempotency_key}".encode(
                "utf-8"
            )
        ).hexdigest()
        request_checksum = _checksum(
            {
                "agent_id": agent.id,
                "conversation_id": command.conversation_id,
                "message": message,
            }
        )
        existing_run = self._run_repository.get_by_idempotency(command.owner_id, scoped_key_hash)
        if existing_run is not None:
            prior_run, prior_checksum = existing_run
            if prior_checksum != request_checksum:
                raise ValueError("idempotency_key_reused_with_different_request")
            if prior_run.organization_id != command.organization_id:
                raise AgentNotFoundError("Run 不存在")
            return prior_run
        return self._run_repository.create_run(
            run,
            idempotency_key_hash=scoped_key_hash,
            request_checksum=request_checksum,
            input_text=message,
        )

    def schedule_run(self, run_id: str) -> None:
        """在当前服务事件循环调度一次 Run；相同 Run 不会重复启动。"""
        current_task = self._active_tasks.get(run_id)
        if current_task is not None and not current_task.done():
            return
        task = asyncio.create_task(self.execute_run(run_id))
        self._active_tasks[run_id] = task
        task.add_done_callback(lambda finished_task: self._active_tasks.pop(run_id, None))

    def recover_expired_runs(self) -> None:
        """恢复未开始的过期队列并将失去租约的执行明确标记为中断。"""
        current_time = datetime.now(UTC)
        for expired_run in self._run_repository.list_expired(current_time):
            if expired_run.status is RunStatus.QUEUED:
                self.schedule_run(expired_run.id)
            else:
                self._run_repository.interrupt_expired(expired_run.id, current_time)

    async def execute_run(self, run_id: str) -> None:
        """执行已提交 Run 并只向 Canonical Run/Event 写入状态。

        Args:
            run_id (str): 已持久化 Run ID。
        """
        if not self._run_repository.claim(
            run_id,
            self._executor_instance_id,
            datetime.now(UTC) + timedelta(seconds=30),
        ):
            return
        run = self._run_repository.get_by_id(run_id)
        if run is None or run.status is not RunStatus.QUEUED or not run.execution_snapshot:
            return
        snapshot_document = run.execution_snapshot
        input_message = next(
            (
                str(content_part.get("text", ""))
                for content_part in run.input_content
                if content_part.get("type") == "text"
            ),
            "",
        )
        run_trace_id = derive_trace_id(run.id)
        root_span_id = derive_root_span_id(run.id)
        model_call_id = uuid.uuid4().hex
        model_name = str(snapshot_document["model_name"])
        model_span_id = derive_span_id(run.id, "model", model_call_id)
        heartbeat_task = asyncio.create_task(self._maintain_execution_lease(run.id))
        try:
            self._run_repository.append_event(
                run.id,
                RunEventCandidate("run.started", {"started_at": datetime.now(UTC).isoformat()}),
            )
            self._run_repository.append_event(
                run.id,
                RunEventCandidate(
                    "message.started",
                    {"message_id": f"assistant_{run.id}", "role": "assistant"},
                    trace_id=run_trace_id,
                    span_id=root_span_id,
                ),
            )
            self._run_repository.append_event(
                run.id,
                RunEventCandidate(
                    "model.call.started",
                    {"model_call_id": model_call_id, "model_name": model_name, "turn_index": 0},
                    trace_id=run_trace_id,
                    span_id=model_span_id,
                ),
            )
            peers = self._approved_peers_for_run(run)
            execution_result = await self._executor.execute(
                snapshot={**snapshot_document, "run_id": run.id},
                message=input_message,
                peers=peers,
            )
            for external_call in execution_result.external_calls:
                tool_call_id = uuid.uuid4().hex
                tool_span_id = derive_span_id(run.id, "tool", tool_call_id)
                self._run_repository.append_event(
                    run.id,
                    RunEventCandidate(
                        "tool.call.started",
                        {
                            "tool_call_id": tool_call_id,
                            "tool_name": "a2a.call",
                            "arguments": {
                                "peer_id": external_call.peer_id,
                                "input_length": external_call.input_length,
                            },
                            "parent_model_call_id": model_call_id,
                        },
                        trace_id=run_trace_id,
                        span_id=tool_span_id,
                    ),
                )
                self._run_repository.append_event(
                    run.id,
                    RunEventCandidate(
                        "tool.call.completed",
                        {
                            "tool_call_id": tool_call_id,
                            "result": {"status": "completed"},
                            "result_checksum": external_call.result_checksum,
                            "remote_task_id": external_call.remote_task_id,
                        },
                        trace_id=run_trace_id,
                        span_id=tool_span_id,
                    ),
                )
            self._run_repository.append_event(
                run.id,
                RunEventCandidate(
                    "model.call.completed",
                    {
                        "model_call_id": model_call_id,
                        "model_name": execution_result.model_name,
                        "turn_index": 0,
                        "usage": {},
                        "finish_reason": "stop",
                    },
                    trace_id=run_trace_id,
                    span_id=model_span_id,
                ),
            )
            final_text = execution_result.content.strip()
            if not final_text:
                raise ValueError("empty_model_response")
            for delta_text in _split_message(final_text):
                self._run_repository.append_event(
                    run.id,
                    RunEventCandidate(
                        "message.delta",
                        {
                            "message_id": f"assistant_{run.id}",
                            "content_index": 0,
                            "delta": delta_text,
                        },
                        trace_id=run_trace_id,
                        span_id=root_span_id,
                    ),
                )
            message_checksum = _checksum(final_text)
            self._run_repository.append_event(
                run.id,
                RunEventCandidate(
                    "message.completed",
                    {
                        "message_id": f"assistant_{run.id}",
                        "content": final_text,
                        "content_checksum": message_checksum,
                    },
                    trace_id=run_trace_id,
                    span_id=root_span_id,
                ),
            )
            self._run_repository.append_event(
                run.id,
                RunEventCandidate(
                    "run.completed",
                    {"message_id": f"assistant_{run.id}"},
                    trace_id=run_trace_id,
                    span_id=root_span_id,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            current_run = self._run_repository.get_by_id(run.id)
            if current_run is None or current_run.status in {
                RunStatus.CANCELLING,
                RunStatus.CANCELLED,
                RunStatus.FAILED,
                RunStatus.SUCCEEDED,
                RunStatus.INTERRUPTED,
            }:
                return
            try:
                self._run_repository.append_event(
                    run.id,
                    RunEventCandidate(
                        "model.call.failed",
                        {
                            "model_call_id": model_call_id,
                            "model_name": model_name,
                            "turn_index": 0,
                            "error": {"code": "model_execution_failed"},
                        },
                        trace_id=run_trace_id,
                        span_id=model_span_id,
                    ),
                )
                self._run_repository.append_event(
                    run.id,
                    RunEventCandidate("run.failed", {"error": {"code": "agent_execution_failed"}}),
                )
            except ValueError:
                return
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _maintain_execution_lease(self, run_id: str) -> None:
        """为当前实例续租，避免长模型请求被另一实例误判为失联。"""
        while True:
            await asyncio.sleep(10)
            lease_expires_at = datetime.now(UTC) + timedelta(seconds=30)
            if not self._run_repository.heartbeat(
                run_id, self._executor_instance_id, lease_expires_at
            ):
                return

    def get_scoped_run(
        self, *, run_id: str, organization_id: str, owner_id: str | None = None
    ) -> Run:
        """读取只对当前组织和可选 owner 可见的 Run。"""
        run = self._run_repository.get_by_id(run_id)
        if (
            run is None
            or run.organization_id != organization_id
            or (owner_id is not None and run.owner_id != owner_id)
        ):
            raise AgentNotFoundError("Run 不存在")
        return run

    def list_scoped_runs(
        self,
        *,
        organization_id: str,
        owner_id: str,
        conversation_id: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Run], int]:
        """分页列出成员当前组织内的历史 Run。"""
        page = self._run_repository.query_runs_page(
            RunQuery(
                organization_id=organization_id,
                owner_id=owner_id,
                conversation_id=conversation_id,
                offset=offset,
                limit=limit,
            )
        )
        return page.runs, page.total

    def list_organization_runs(
        self,
        *,
        organization_id: str,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Run], int]:
        """列出创建于当前组织的所有成员 Run，供组织管理员诊断。"""
        page = self._run_repository.query_runs_page(
            RunQuery(
                organization_id=organization_id,
                offset=offset,
                limit=limit,
            )
        )
        return page.runs, page.total

    def list_a2a_runs(
        self,
        *,
        organization_id: str,
        agent_id: str,
        credential_id: str,
        context_id: str | None = None,
        status: RunStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Run], int]:
        """仅列出同组织、同 Agent、同凭据创建的 A2A Tasks。"""
        page = self._run_repository.query_runs_page(
            RunQuery(
                organization_id=organization_id,
                owner_id=f"a2a:{credential_id}",
                subject_id=agent_id,
                conversation_id=context_id,
                status=status,
                offset=offset,
                limit=limit,
            )
        )
        return page.runs, page.total

    def get_a2a_run(
        self,
        *,
        run_id: str,
        organization_id: str,
        agent_id: str,
        credential_id: str,
    ) -> Run:
        """按组织、目标 Agent 与凭据 owner 隔离 A2A Task。"""
        run = self._run_repository.get_by_id(run_id)
        if (
            run is None
            or run.organization_id != organization_id
            or run.subject_id != agent_id
            or run.owner_id != f"a2a:{credential_id}"
        ):
            raise AgentNotFoundError("Task 不存在")
        return run

    def list_a2a_events(
        self,
        *,
        run_id: str,
        organization_id: str,
        agent_id: str,
        credential_id: str,
        after_seq: int = 0,
    ) -> Sequence[RunEvent]:
        """先按服务凭据校验 Task scope，再读取 canonical events。"""
        run = self.get_a2a_run(
            run_id=run_id,
            organization_id=organization_id,
            agent_id=agent_id,
            credential_id=credential_id,
        )
        return self._run_repository.list_events(run.id, after_seq)

    def list_scoped_events(
        self, *, run_id: str, organization_id: str, owner_id: str, after_seq: int = 0
    ) -> Sequence[RunEvent]:
        """先验证 Run 组织和 owner，再读取游标后的持久事件。"""
        scoped_run = self.get_scoped_run(
            run_id=run_id, organization_id=organization_id, owner_id=owner_id
        )
        return self._run_repository.list_events(scoped_run.id, after_seq)

    def list_organization_events(
        self, *, run_id: str, organization_id: str, after_seq: int = 0
    ) -> Sequence[RunEvent]:
        """组织管理员按 Run 创建时归属读取 Canonical Events。"""
        scoped_run = self.get_scoped_run(
            run_id=run_id,
            organization_id=organization_id,
        )
        return self._run_repository.list_events(scoped_run.id, after_seq)

    async def cancel_scoped_run(self, *, run_id: str, organization_id: str, owner_id: str) -> Run:
        """取消当前成员可见的非终态 Run。"""
        scoped_run = self.get_scoped_run(
            run_id=run_id, organization_id=organization_id, owner_id=owner_id
        )
        if scoped_run.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
            RunStatus.INTERRUPTED,
        }:
            return scoped_run
        self._run_repository.append_event(
            scoped_run.id,
            RunEventCandidate(
                "run.cancelling",
                {"requested_by": owner_id, "requested_at": datetime.now(UTC).isoformat()},
            ),
        )
        active_task = self._active_tasks.get(scoped_run.id)
        if active_task is not None and not active_task.done():
            active_task.cancel()
            try:
                await active_task
            except asyncio.CancelledError:
                pass
        current_run = self._run_repository.get_by_id(scoped_run.id)
        if current_run is not None and current_run.status is RunStatus.CANCELLING:
            self._run_repository.append_event(
                scoped_run.id,
                RunEventCandidate("run.cancelled", {"external_stop_confirmed": True}),
            )
        return self.get_scoped_run(
            run_id=scoped_run.id, organization_id=organization_id, owner_id=owner_id
        )

    def _approved_peers_for_run(self, run: Run) -> Sequence[A2APeer]:
        """按 Run 创建时组织读取已批准对端。"""
        organization_id = run.organization_id or DEFAULT_ORGANIZATION_ID
        return tuple(
            peer
            for peer in self._agent_repository.list_a2a_peers(organization_id)
            if peer.is_approved and peer.is_enabled
        )

    def _conversation_history(self, prior_runs: Sequence[Run]) -> list[dict[str, str]]:
        """从同组织、同 owner、同会话的已提交事件重建消息上下文。"""
        messages_by_time: list[tuple[datetime, int, dict[str, str]]] = []
        for prior_run in prior_runs:
            for run_event in self._run_repository.list_events(prior_run.id, 0):
                if run_event.event_type == "input.accepted":
                    accepted_content = run_event.payload.get("content")
                    if isinstance(accepted_content, str):
                        input_text = accepted_content
                    elif isinstance(accepted_content, list):
                        input_text = " ".join(
                            str(content_part.get("text", ""))
                            for content_part in accepted_content
                            if isinstance(content_part, dict) and content_part.get("type") == "text"
                        )
                    else:
                        input_text = ""
                    if input_text:
                        messages_by_time.append(
                            (
                                prior_run.created_at,
                                run_event.seq,
                                {"role": "user", "content": input_text},
                            )
                        )
                elif run_event.event_type == "message.completed":
                    completed_text = run_event.payload.get("content")
                    if isinstance(completed_text, str) and completed_text:
                        messages_by_time.append(
                            (
                                run_event.recorded_at,
                                run_event.seq,
                                {"role": "assistant", "content": completed_text},
                            )
                        )
        messages_by_time.sort(key=lambda message_record: (message_record[0], message_record[1]))
        return [message for _, _, message in messages_by_time]


def _split_message(message: str, chunk_size: int = 180) -> tuple[str, ...]:
    """把最终内容分成可持久化的增量事件。"""
    return tuple(
        message[index : index + chunk_size] for index in range(0, len(message), chunk_size)
    )
