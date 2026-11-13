"""跨认证域复用的 SQLAlchemy 用户账户仓库。

同一份实现通过注入 ORM 模型类与标识列名，绑定到 ``public_user`` 或
``admin_user`` 表，从而避免为两域复制两套近似的数据访问代码。仓库只持有
``sessionmaker``，每个方法在独立短事务内完成读写：读连接用完即还，写事务
随 ``begin()`` 上下文提交，避免长生命周期会话把连接占成 ``idle in
transaction``。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.shared.interfaces.user_account_repository import (
    UserAccountRepository,
)
from backend.core.shared.models.account_list_filter import AccountListFilter
from backend.core.shared.models.user_account import UserAccount

_STATUS_ACTIVE: str = "active"
_STATUS_DISABLED: str = "disabled"
_ROLE_PLATFORM: str = "platform"


@dataclass(frozen=True)
class UserAccountRepositoryMapping:
    """声明账户仓库对应的 ORM 模型与可选投影列。"""

    model_class: type[Any]
    identifier_attr: str
    email_attr: str | None = None
    role_attr: str | None = None
    organization_attr: str | None = None


class SqlAlchemyUserAccountRepository(UserAccountRepository):
    """绑定到单张用户表的账户仓库实现。

    每个认证域实例化一次（注入各自的模型类与标识列），实例之间不共享任何表，
    从而在数据层维持两套用户体系的隔离。
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        mapping: UserAccountRepositoryMapping,
    ) -> None:
        """初始化仓库。

        Args:
            session_factory (sessionmaker[Session]): 会话工厂；每个方法在独立
                短事务中使用，不长期占用连接。
            mapping (UserAccountRepositoryMapping): 指定模型、标识列、角色与组织投影。
        """
        self._session_factory = session_factory
        self._mapping = mapping
        self._model_class = mapping.model_class
        self._identifier_attr = mapping.identifier_attr
        self._email_attr = mapping.email_attr

    def find_by_identifier(self, identifier: str) -> UserAccount | None:
        """按登录标识查账户。"""
        identifier_column = getattr(self._model_class, self._identifier_attr)
        with self._session_factory() as session:
            model: Any | None = (
                session.query(self._model_class).filter(identifier_column == identifier).first()
            )
            return self._to_account(model) if model is not None else None

    def get_by_id(self, account_id: str) -> UserAccount | None:
        """按主键查账户。"""
        with self._session_factory() as session:
            model: Any | None = session.get(self._model_class, account_id)
            return self._to_account(model) if model is not None else None

    def create(self, account: UserAccount) -> UserAccount:
        """持久化新账户并提交；同标识账户已存在时幂等返回既有账户。"""
        return self._persist_account(account, idempotent=True)

    def create_unique(self, account: UserAccount) -> UserAccount:
        """严格创建账户，检测到唯一键冲突时抛出稳定 ``ValueError``。"""
        return self._persist_account(account, idempotent=False)

    def _persist_account(self, account: UserAccount, *, idempotent: bool) -> UserAccount:
        """共用账户插入路径，按调用场景选择种子幂等或业务严格语义。"""
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
        if (
            self._email_attr
            and self._email_attr != self._identifier_attr
            and hasattr(self._model_class, self._email_attr)
        ):
            setattr(model, self._email_attr, account.email)
        account_role = (
            _ROLE_PLATFORM
            if self._identifier_attr == "username" and account.role == "user"
            else account.role
        )
        if self._mapping.role_attr and hasattr(self._model_class, self._mapping.role_attr):
            setattr(model, self._mapping.role_attr, account_role)
        if self._mapping.organization_attr and hasattr(
            self._model_class, self._mapping.organization_attr
        ):
            organization_id = account.organization_id
            if self._identifier_attr == "username" and account_role == _ROLE_PLATFORM:
                organization_id = None
            setattr(model, self._mapping.organization_attr, organization_id)
        if hasattr(self._model_class, "oidc_issuer"):
            model.oidc_issuer = account.oidc_issuer
            model.oidc_subject = account.oidc_subject
        try:
            with self._session_factory.begin() as session:
                session.add(model)
                session.flush()
                return self._to_account(model)
        except IntegrityError:
            # 并发种子场景下另一进程/线程已先行插入同标识账户，事务已随
            # 上下文回滚；转为查询已存在账户返回，保证幂等。
            if (
                not idempotent
                and account.oidc_issuer is not None
                and account.oidc_subject is not None
                and self.find_by_oidc_identity(account.oidc_issuer, account.oidc_subject)
                is not None
            ):
                raise ValueError("identity_conflict") from None
            existing = self.find_by_identifier(account.identifier)
            if existing is not None:
                if idempotent:
                    return existing
                raise ValueError(f"{self._identifier_attr}_conflict") from None
            if not idempotent and account.email and self.find_by_email(account.email) is not None:
                raise ValueError("email_conflict") from None
            raise

    def set_active(
        self,
        account_id: str,
        is_active: bool,
        *,
        organization_id: str | None = None,
    ) -> UserAccount | None:
        """以单条条件更新修改账户状态，可同时检查组织范围。"""
        with self._session_factory.begin() as session:
            update_statement = update(self._model_class).where(self._model_class.id == account_id)
            if organization_id is not None and self._mapping.organization_attr:
                organization_column = getattr(self._model_class, self._mapping.organization_attr)
                update_statement = update_statement.where(organization_column == organization_id)
            update_result = session.execute(
                update_statement.values(
                    is_active=is_active,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            if update_result.rowcount != 1:
                return None
            session.expire_all()
            model: Any | None = session.get(self._model_class, account_id)
            if model is None:
                return None
            return self._to_account(model)

    def set_active_with_platform_guard(
        self, account_id: str, is_active: bool
    ) -> UserAccount | None:
        """以事务锁保证最后一名启用平台管理员不会被禁用。"""
        role_column = (
            getattr(self._model_class, self._mapping.role_attr) if self._mapping.role_attr else None
        )
        with self._session_factory.begin() as session:
            if not is_active and role_column is not None:
                active_platform_admins = session.scalars(
                    select(self._model_class)
                    .where(role_column == _ROLE_PLATFORM, self._model_class.is_active.is_(True))
                    .order_by(self._model_class.id)
                    .with_for_update(of=self._model_class)
                ).all()
                target_is_active_platform_admin = any(
                    model.id == account_id for model in active_platform_admins
                )
                if target_is_active_platform_admin and len(active_platform_admins) <= 1:
                    raise ValueError("last_platform_admin")

            model: Any | None = session.scalar(
                select(self._model_class)
                .where(self._model_class.id == account_id)
                .with_for_update(of=self._model_class)
            )
            if model is None:
                return None
            model.is_active = is_active
            model.updated_at = datetime.now(timezone.utc)
            return self._to_account(model)

    def unbind_oidc_identity(self, account_id: str) -> UserAccount | None:
        """仅在已有绑定时原子清空 OIDC 身份列。"""
        return self._update_oidc_identity(
            account_id,
            (None, None),
            must_be_bound=True,
        )

    def set_organization(self, account_id: str, organization_id: str) -> UserAccount | None:
        """更新账户组织归属。"""
        return self._set_mapped_account_values(
            account_id,
            (("organization_attr", organization_id),),
        )

    def set_role_and_organization(
        self,
        account_id: str,
        role: str,
        organization_id: str | None,
    ) -> UserAccount | None:
        """更新角色及组织归属，供应急种子和管理员工作流使用。"""
        return self._set_mapped_account_values(
            account_id,
            (("role_attr", role), ("organization_attr", organization_id)),
        )

    def set_password(self, account_id: str, password_hash: str) -> UserAccount | None:
        """更新账户密码哈希并提交。"""
        with self._session_factory.begin() as session:
            model: Any | None = session.get(self._model_class, account_id)
            if model is None:
                return None
            model.password_hash = password_hash
            model.updated_at = datetime.now(timezone.utc)
            return self._to_account(model)

    def find_by_oidc_identity(self, issuer: str, subject: str) -> UserAccount | None:
        """按 OIDC 身份组合查找已绑定账户。"""
        if not hasattr(self._model_class, "oidc_issuer"):
            return None
        with self._session_factory() as session:
            model: Any | None = (
                session.query(self._model_class)
                .filter(
                    self._model_class.oidc_issuer == issuer,
                    self._model_class.oidc_subject == subject,
                )
                .first()
            )
            return self._to_account(model) if model is not None else None

    def find_by_email(self, email: str) -> UserAccount | None:
        """按邮箱查找账户，调用方传入归一化地址。"""
        if self._email_attr is None:
            return None
        email_column = getattr(self._model_class, self._email_attr)
        with self._session_factory() as session:
            model: Any | None = (
                session.query(self._model_class).filter(email_column == email).one_or_none()
            )
            return self._to_account(model) if model is not None else None

    def bind_oidc_identity(self, account_id: str, issuer: str, subject: str) -> UserAccount | None:
        """仅当账户尚未绑定时原子绑定 OIDC 身份；冲突时返回 None。"""
        try:
            return self._update_oidc_identity(
                account_id,
                (issuer, subject),
                must_be_bound=False,
            )
        except IntegrityError:
            return None

    def _update_oidc_identity(
        self,
        account_id: str,
        oidc_identity: tuple[str | None, str | None],
        *,
        must_be_bound: bool,
    ) -> UserAccount | None:
        """按当前绑定状态原子更新 OIDC 身份并返回持久化账户。"""
        if not hasattr(self._model_class, "oidc_issuer"):
            return None
        identity_filter = (
            self._model_class.oidc_issuer.is_not(None)
            if must_be_bound
            else self._model_class.oidc_issuer.is_(None)
        )
        subject_filter = (
            self._model_class.oidc_subject.is_not(None)
            if must_be_bound
            else self._model_class.oidc_subject.is_(None)
        )
        with self._session_factory.begin() as session:
            result = session.execute(
                update(self._model_class)
                .where(
                    self._model_class.id == account_id,
                    identity_filter,
                    subject_filter,
                )
                .values(
                    oidc_issuer=oidc_identity[0],
                    oidc_subject=oidc_identity[1],
                    updated_at=datetime.now(timezone.utc),
                )
            )
            if result.rowcount != 1:
                return None
            model: Any | None = session.get(self._model_class, account_id)
            return self._to_account(model) if model is not None else None

    def _set_mapped_account_values(
        self,
        account_id: str,
        mapped_values: tuple[tuple[str, Any], ...],
    ) -> UserAccount | None:
        """在一个事务内更新映射列并返回账户投影。"""
        resolved_values: list[tuple[str, Any]] = []
        for mapping_attribute, attribute_value in mapped_values:
            model_attribute = getattr(self._mapping, mapping_attribute, None)
            if model_attribute is None:
                return None
            resolved_values.append((model_attribute, attribute_value))

        with self._session_factory.begin() as session:
            model: Any | None = session.get(self._model_class, account_id)
            if model is None:
                return None
            for model_attribute, attribute_value in resolved_values:
                setattr(model, model_attribute, attribute_value)
            model.updated_at = datetime.now(timezone.utc)
            session.flush()
            return self._to_account(model)

    def set_email(self, account_id: str, email: str) -> UserAccount | None:
        """更新账户首绑邮箱；邮箱唯一冲突保持原值。"""
        if self._email_attr is None:
            return None
        try:
            with self._session_factory.begin() as session:
                model: Any | None = session.get(self._model_class, account_id)
                if model is None:
                    return None
                setattr(model, self._email_attr, email)
                model.updated_at = datetime.now(timezone.utc)
                session.flush()
                return self._to_account(model)
        except IntegrityError:
            return None

    def list_accounts(
        self,
        *,
        offset: int,
        limit: int,
        filters: AccountListFilter,
    ) -> tuple[Sequence[UserAccount], int]:
        """分页列出账户并返回总数。"""
        identifier_column = getattr(self._model_class, self._identifier_attr)
        with self._session_factory() as session:
            query = session.query(self._model_class)
            if filters.organization_id is not None and self._mapping.organization_attr:
                query = query.filter(
                    getattr(self._model_class, self._mapping.organization_attr)
                    == filters.organization_id
                )
            if filters.status == _STATUS_ACTIVE:
                query = query.filter(self._model_class.is_active.is_(True))
            elif filters.status == _STATUS_DISABLED:
                query = query.filter(self._model_class.is_active.is_(False))
            if filters.keyword and filters.keyword.strip():
                like_pattern: str = f"%{filters.keyword.strip()}%"
                query = query.filter(
                    or_(
                        identifier_column.ilike(like_pattern),
                        self._model_class.display_name.ilike(like_pattern),
                    )
                )
            total: int = query.count()
            models: list[Any] = (
                query.order_by(self._model_class.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
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
            email=getattr(model, self._email_attr, None) if self._email_attr else None,
            oidc_issuer=getattr(model, "oidc_issuer", None),
            oidc_subject=getattr(model, "oidc_subject", None),
            role=(
                getattr(model, self._mapping.role_attr)
                if self._mapping.role_attr and hasattr(self._model_class, self._mapping.role_attr)
                else (_ROLE_PLATFORM if self._identifier_attr == "username" else "user")
            ),
            organization_id=(
                getattr(model, self._mapping.organization_attr)
                if self._mapping.organization_attr
                and hasattr(self._model_class, self._mapping.organization_attr)
                else None
            ),
            organization_name=(
                model.organization.name
                if getattr(model, "organization", None) is not None
                else None
            ),
            organization_is_active=(
                model.organization.is_active
                if getattr(model, "organization", None) is not None
                else None
            ),
        )
