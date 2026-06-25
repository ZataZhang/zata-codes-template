"""示例：用户档案 ORM 模型。

仅作为 ``persistence/models`` 目录的最小合规样例，用于：

1. 演示 SQLAlchemy 2.x 声明式风格与 ``__table_args__`` 表备注写法；
2. 让 ``hooks/check_schema_conventions.py`` 有可执行的验证目标。

真正接入业务前，请删除或替换为本项目实际需要的模型。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class UserProfile(Base, TimestampMixin):
    """用户档案表。

    存储系统用户的基础身份信息与展示字段，由认证链路读取。
    """

    __tablename__ = "user_profile"
    __table_args__ = (
        {
            "comment": "用户档案表，存储系统用户的基础身份信息与展示字段。",
        },
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="用户档案主键 ID，自增。",
    )
    username: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        comment="登录用户名，全局唯一，长度 1~64。",
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        comment="用户展示名，允许为空。",
    )
    birth_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="用户出生日期，可为空。",
    )
