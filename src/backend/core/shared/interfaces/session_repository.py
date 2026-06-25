"""Session / Message Repository 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from backend.core.shared.models.session import ChatMessage, ChatSession


class SessionRepository(ABC):
    """会话与消息数据访问抽象端口。"""

    @abstractmethod
    def create_session(self, session: ChatSession) -> ChatSession:
        """创建会话。"""

    @abstractmethod
    def get_session_by_id(self, session_id: str) -> ChatSession | None:
        """根据 ID 读取会话。"""

    @abstractmethod
    def list_sessions_by_owner(self, owner_id: str) -> Sequence[ChatSession]:
        """读取指定用户的所有会话。"""

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """删除会话，返回是否成功。"""

    @abstractmethod
    def create_message(self, message: ChatMessage) -> ChatMessage:
        """创建消息。"""

    @abstractmethod
    def list_messages_by_session(self, session_id: str) -> Sequence[ChatMessage]:
        """读取指定会话的所有消息，按时间正序。"""
