"""共享 SQLAlchemy 声明类 Mixin。

把模型里反复出现的列（例如审计时间字段）抽到 mixin，避免在每个模型中
重复定义。所有 mixin 中的列都必须显式带 ``comment=`` 关键字参数，
由 ``hooks/check_sqlalchemy_model_comments.py`` 在 pre-commit 阶段强制校验。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, text
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """为模型注入 ``created_at`` 与 ``updated_at`` 审计时间字段。

    子类声明时把本 mixin 放在 ``Base`` 之后，例如
    ``class UserProfile(Base, TimestampMixin):``。混入的列会自动落到表结构
    后段，便于人眼区分业务列与审计列。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="记录创建时间，UTC，数据库端默认值。",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=text("CURRENT_TIMESTAMP"),
        nullable=False,
        comment="记录最近一次更新时间，UTC，数据库端自动维护。",
    )
