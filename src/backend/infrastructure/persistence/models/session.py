"""Session / Message ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class ChatSessionModel(Base, TimestampMixin):
    """聊天会话表。"""

    __tablename__ = "chat_session"
    __table_args__ = (
        {
            "comment": "聊天会话表，存储用户与 Agent 的会话元数据。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="会话主键 ID，业务生成的唯一标识。",
    )
    owner_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="会话所属用户 ID。",
    )
    agent_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent.id"),
        nullable=False,
        comment="会话关联的 Agent ID。",
    )
    title: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="新会话",
        comment="会话标题。",
    )

    messages: Mapped[list["ChatMessageModel"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.created_at",
    )


class ChatMessageModel(Base):
    """聊天消息表。"""

    __tablename__ = "chat_message"
    __table_args__ = (
        {
            "comment": "聊天消息表，存储会话中的单条消息。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="消息主键 ID，业务生成的唯一标识。",
    )
    session_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("chat_session.id"),
        nullable=False,
        index=True,
        comment="消息所属会话 ID。",
    )
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="消息角色：user、assistant、system。",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息文本内容。",
    )
    tool_calls: Mapped[list[dict]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="消息附带的工具调用记录。",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="消息创建时间，UTC。",
    )

    session: Mapped["ChatSessionModel"] = relationship(back_populates="messages")
