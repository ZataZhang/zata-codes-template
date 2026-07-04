"""跨认证域复用的 SQLAlchemy 用户账户仓库。

同一份实现通过注入 ORM 模型类与标识列名，绑定到 ``public_user`` 或
``admin_user`` 表，从而避免为两域复制两套近似的数据访问代码。仓库复用与
业务仓库相同的共享数据库会话；写操作显式提交以持久化注册 / 种子 / 启停。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.shared.interfaces.user_account_repository import (
    UserAccountRepository,
)
from backend.core.shared.models.user_account import UserAccount

_STATUS_ACTIVE: str = "active"
_STATUS_DISABLED: str = "disabled"


class SqlAlchemyUserAccountRepository(UserAccountRepository):
    """绑定到单张用户表的账户仓库实现。

    每个认证域实例化一次（注入各自的模型类与标识列），实例之间不共享任何表，
    从而在数据层维持两套用户体系的隔离。
    """

    def __init__(
        self,
        *,
        session: Session,
        model_class: type[Any],
        identifier_attr: str,
    ) -> None:
        """初始化仓库。

        Args:
            session (Session): 共享数据库会话（与业务仓库一致）。
            model_class (type[Any]): 绑定的 ORM 模型类（含 ``id`` / 标识列 /
                ``display_name`` / ``password_hash`` / ``is_active``）。
            identifier_attr (str): 登录标识所在的列属性名（public 为 ``email``，
                admin 为 ``username``）。
        """
        self._session = session
        self._model_class = model_class
        self._identifier_attr = identifier_attr

    def find_by_identifier(self, identifier: str) -> UserAccount | None:
        """按登录标识查账户。"""
        identifier_column = getattr(self._model_class, self._identifier_attr)
        model: Any | None = (
            self._session.query(self._model_class).filter(identifier_column == identifier).first()
        )
        return self._to_account(model) if model is not None else None

    def get_by_id(self, account_id: str) -> UserAccount | None:
        """按主键查账户。"""
        model: Any | None = self._session.get(self._model_class, account_id)
        return self._to_account(model) if model is not None else None

    def create(self, account: UserAccount) -> UserAccount:
        """持久化新账户并提交。"""
        now: datetime = datetime.now(timezone.utc)
        model = self._model_class(
            id=account.id,
            display_name=account.display_name,
            password_hash=account.password_hash,
            is_active=account.is_active,
            created_at=now,
            updated_at=now,
            **{self._identifier_attr: account.identifier},
        )
        self._session.add(model)
        try:
            self._session.commit()
        except IntegrityError:
            # 并发种子场景下另一进程/线程已先行插入同标识账户，回滚后
            # 转为查询已存在账户返回，保证幂等。
            self._session.rollback()
            existing = self.find_by_identifier(account.identifier)
            if existing is not None:
                return existing
            raise
        self._session.refresh(model)
        return self._to_account(model)

    def set_active(self, account_id: str, is_active: bool) -> UserAccount | None:
        """更新账户启用状态并提交。"""
        model: Any | None = self._session.get(self._model_class, account_id)
        if model is None:
            return None
        model.is_active = is_active
        model.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(model)
        return self._to_account(model)

    def set_password(self, account_id: str, password_hash: str) -> UserAccount | None:
        """更新账户密码哈希并提交。"""
        model: Any | None = self._session.get(self._model_class, account_id)
        if model is None:
            return None
        model.password_hash = password_hash
        model.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(model)
        return self._to_account(model)

    def list_accounts(
        self,
        *,
        offset: int,
        limit: int,
        status_filter: str | None,
        keyword: str | None,
    ) -> tuple[Sequence[UserAccount], int]:
        """分页列出账户并返回总数。"""
        identifier_column = getattr(self._model_class, self._identifier_attr)
        query = self._session.query(self._model_class)
        if status_filter == _STATUS_ACTIVE:
            query = query.filter(self._model_class.is_active.is_(True))
        elif status_filter == _STATUS_DISABLED:
            query = query.filter(self._model_class.is_active.is_(False))
        if keyword and keyword.strip():
            like_pattern: str = f"%{keyword.strip()}%"
            query = query.filter(
                or_(
                    identifier_column.ilike(like_pattern),
                    self._model_class.display_name.ilike(like_pattern),
                )
            )
        total: int = query.count()
        models: list[Any] = (
            query.order_by(self._model_class.created_at.desc()).offset(offset).limit(limit).all()
        )
        return [self._to_account(model) for model in models], total

    def _to_account(self, model: Any) -> UserAccount:
        """把 ORM 模型转换为领域账户对象。"""
        return UserAccount(
            id=model.id,
            identifier=getattr(model, self._identifier_attr),
            display_name=model.display_name,
            password_hash=model.password_hash,
            is_active=model.is_active,
            created_at=model.created_at,
        )
