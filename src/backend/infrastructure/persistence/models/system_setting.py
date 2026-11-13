"""系统设置表 SQLAlchemy ORM 模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base


class SystemSettingModel(Base):
    """保存可由管理端实时更新的系统级 JSON 设置。"""

    __tablename__ = "system_settings"
    __table_args__ = {"comment": "系统级键值设置，以 JSON 文本保存每项配置。"}

    key: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
        comment="设置键，例如 registration_policy。",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="设置值的 JSON 文本。",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="设置最近更新时间，UTC，数据库端默认值。",
    )


__all__ = ["SystemSettingModel"]
