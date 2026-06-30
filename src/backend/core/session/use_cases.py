"""Session 用例。"""

from __future__ import annotations

from typing import Sequence
from uuid import uuid4

from backend.core.agent.orchestrator.agent_runner import AgentRunner
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.llm_client import LLMClient
from backend.core.shared.interfaces.session_repository import SessionRepository
from backend.core.shared.interfaces.tool_registry import ToolRegistry
from backend.core.shared.models.agent import Agent
from backend.core.shared.models.session import ChatMessage, ChatSession


class SessionUseCase:
    """会话业务用例。"""

    def __init__(
        self,
        session_repository: SessionRepository,
        agent_repository: AgentRepository,
        tool_registry: ToolRegistry,
        llm_client: LLMClient,
    ) -> None:
        """Initialize use case with repositories and clients."""
        self._session_repository = session_repository
        self._agent_repository = agent_repository
        self._tool_registry = tool_registry
        self._llm_client = llm_client

    def create_session(self, owner_id: str, agent_id: str, title: str | None = None) -> ChatSession:
        """创建会话。"""
        agent = self._get_agent(agent_id, owner_id)
        session = ChatSession(
            id=str(uuid4()),
            owner_id=owner_id,
            agent_id=agent_id,
            title=title or f"与 {agent.name} 的对话",
        )
        return self._session_repository.create_session(session)

    def get_session(self, session_id: str, requester_id: str) -> ChatSession:
        """读取会话。"""
        session = self._session_repository.get_session_by_id(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        if session.owner_id != requester_id:
            raise PermissionError("Not authorized to access this session")
        return session

    def list_sessions(self, owner_id: str) -> Sequence[ChatSession]:
        """列出用户的所有会话。"""
        return self._session_repository.list_sessions_by_owner(owner_id)

    def delete_session(self, session_id: str, requester_id: str) -> bool:
        """删除会话。"""
        self.get_session(session_id, requester_id)
        return self._session_repository.delete_session(session_id)

    def send_message(
        self,
        session_id: str,
        requester_id: str,
        content: str,
    ) -> ChatMessage:
        """发送用户消息并生成 assistant 回复。"""
        session = self.get_session(session_id, requester_id)
        agent = self._get_agent(session.agent_id, requester_id)

        user_message = ChatMessage(
            id=str(uuid4()),
            session_id=session_id,
            role="user",
            content=content,
        )
        self._session_repository.create_message(user_message)

        history = self._session_repository.list_messages_by_session(session_id)
        runner = AgentRunner(
            agent=agent,
            tool_registry=self._tool_registry,
            llm_client=self._llm_client,
        )
        assistant_message = runner.run(history=history[:-1], user_message=content)
        assistant_message.session_id = session_id
        return self._session_repository.create_message(assistant_message)

    def list_messages(self, session_id: str, requester_id: str) -> Sequence[ChatMessage]:
        """读取会话消息列表。"""
        self.get_session(session_id, requester_id)
        return self._session_repository.list_messages_by_session(session_id)

    def _get_agent(self, agent_id: str, owner_id: str) -> Agent:
        """读取并校验 Agent 所有权。"""
        agent = self._agent_repository.get_by_id(agent_id)
        if agent is None:
            raise ValueError(f"Agent not found: {agent_id}")
        if agent.owner_id != owner_id:
            raise PermissionError("Not authorized to use this agent")
        return agent
