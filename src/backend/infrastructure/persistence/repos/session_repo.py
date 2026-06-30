"""Session Repository SQLAlchemy 实现。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.shared.interfaces.session_repository import SessionRepository
from backend.core.shared.models.session import ChatMessage, ChatSession, ToolCall
from backend.infrastructure.persistence.models.session import (
    ChatMessageModel,
    ChatSessionModel,
)


def _to_tool_call(data: dict) -> ToolCall:
    """将字典转换为 ToolCall 领域对象。"""
    return ToolCall(
        id=data.get("id", str(uuid4())),
        tool_name=data["tool_name"],
        arguments=data.get("arguments", {}),
        result=data.get("result"),
        status=data.get("status", "pending"),
    )


def _to_message(model: ChatMessageModel) -> ChatMessage:
    """将 ORM 模型转换为 ChatMessage 领域对象。"""
    return ChatMessage(
        id=model.id,
        session_id=model.session_id,
        role=model.role,
        content=model.content,
        tool_calls=[_to_tool_call(item) for item in (model.tool_calls or [])],
        created_at=model.created_at,
    )


def _to_session(model: ChatSessionModel) -> ChatSession:
    """将 ORM 模型转换为 ChatSession 领域对象。"""
    return ChatSession(
        id=model.id,
        owner_id=model.owner_id,
        agent_id=model.agent_id,
        title=model.title,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemySessionRepository(SessionRepository):
    """基于 SQLAlchemy 的 Session Repository 实现。"""

    def __init__(self, db_session: Session) -> None:
        """Initialize repository with database session."""
        self._session = db_session

    def create_session(self, session: ChatSession) -> ChatSession:
        """创建会话。"""
        now = datetime.now(timezone.utc)
        model = ChatSessionModel(
            id=session.id or str(uuid4()),
            owner_id=session.owner_id,
            agent_id=session.agent_id,
            title=session.title,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        self._session.flush()
        return _to_session(model)

    def get_session_by_id(self, session_id: str) -> ChatSession | None:
        """根据 ID 读取会话。"""
        model = self._session.get(ChatSessionModel, session_id)
        if model is None:
            return None
        return _to_session(model)

    def list_sessions_by_owner(self, owner_id: str) -> Sequence[ChatSession]:
        """读取指定用户的所有会话。"""
        models = (
            self._session.query(ChatSessionModel)
            .filter(ChatSessionModel.owner_id == owner_id)
            .order_by(ChatSessionModel.updated_at.desc())
            .all()
        )
        return [_to_session(model) for model in models]

    def delete_session(self, session_id: str) -> bool:
        """删除会话。"""
        model = self._session.get(ChatSessionModel, session_id)
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True

    def create_message(self, message: ChatMessage) -> ChatMessage:
        """创建消息。"""
        tool_calls_data = [
            {
                "id": tool_call.id,
                "tool_name": tool_call.tool_name,
                "arguments": tool_call.arguments,
                "result": tool_call.result,
                "status": tool_call.status,
            }
            for tool_call in message.tool_calls
        ]
        model = ChatMessageModel(
            id=message.id or str(uuid4()),
            session_id=message.session_id,
            role=message.role,
            content=message.content,
            tool_calls=tool_calls_data,
        )
        self._session.add(model)
        self._session.flush()

        session_model = self._session.get(ChatSessionModel, message.session_id)
        if session_model is not None:
            session_model.updated_at = datetime.now(timezone.utc)
            self._session.flush()

        return _to_message(model)

    def list_messages_by_session(self, session_id: str) -> Sequence[ChatMessage]:
        """读取指定会话的所有消息。"""
        models = (
            self._session.query(ChatMessageModel)
            .filter(ChatMessageModel.session_id == session_id)
            .order_by(ChatMessageModel.created_at.asc())
            .all()
        )
        return [_to_message(model) for model in models]
