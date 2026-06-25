"""Agent ORM 模型。"""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class AgentModel(Base, TimestampMixin):
    """Agent 表。

    存储用户创建的 Agent 配置信息。
    """

    __tablename__ = "agent"
    __table_args__ = (
        {
            "comment": "Agent 表，存储用户创建的 Agent 配置信息。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="Agent 主键 ID，业务生成的唯一标识。",
    )
    owner_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="Agent 所属用户 ID。",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Agent 展示名称。",
    )
    description: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="",
        comment="Agent 描述。",
    )
    system_prompt: Mapped[str] = mapped_column(
        String(4096),
        nullable=False,
        comment="Agent 系统提示词。",
    )
    model: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Agent 使用的模型标识，例如 openai/gpt-4o。",
    )
    tool_ids: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Agent 启用的工具 ID 列表。",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="idle",
        comment="Agent 状态：idle、running、error、offline。",
    )
