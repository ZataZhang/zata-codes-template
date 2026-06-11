"""SQLAlchemy ORM 模型定义。

本目录集中存放所有 SQLAlchemy 数据表模型（``Base`` 子类），供
``src/backend/infrastructure/persistence/database.py`` 中的 ``Base`` 统一注册
到 ``Base.metadata``，并由 Alembic 在 ``alembic/env.py`` 中自动发现。

约束（由 ``hooks/check_sqlalchemy_model_comments.py`` 在 pre-commit 阶段强制）：

- 每个具体表类（即含 ``__tablename__`` 的类）
  必须通过 ``__table_args__`` 提供 ``comment`` 字段，作为数据库表备注。
- 每个 ``Column(...)`` 或 ``mapped_column(...)`` 调用都必须显式带
  ``comment="..."`` 关键字参数，作为该列字段备注。

新增模型时，请：

1. 在本目录新建模块文件，例如 ``user_profile.py``。
2. 在本 ``__init__`` 末尾追加 ``from .user_profile import UserProfile``
   以保证模型被 ``Base`` 注册（Alembic autogenerate 才能识别）。
3. 复用 ``base.py`` 中的共享 mixin（如 ``TimestampMixin``）来注入
   ``created_at`` / ``updated_at`` 等通用列，避免重复定义。
"""

from .base import TimestampMixin
from .user_profile import UserProfile

__all__ = [
    "TimestampMixin",
    "UserProfile",
]
