"""Tool ORM 模型。"""

from __future__ import annotations

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base


class ToolModel(Base):
    """工具表。

    存储平台预置工具的元数据，MVP 阶段可由种子数据填充。
    """

    __tablename__ = "tool"
    __table_args__ = (
        {
            "comment": "工具表，存储平台预置工具的元数据。",
        },
    )

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="工具主键 ID，全局唯一标识。",
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="工具展示名称。",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="工具描述。",
    )
    handler_path: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        comment="工具处理器导入路径，例如 engines.skills.tools.web_search。",
    )
    schema: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="工具参数 JSON Schema。",
    )
