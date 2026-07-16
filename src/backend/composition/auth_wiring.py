"""public 与 admin 两套认证域装配。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthDomain
from backend.core.auth.service import AuthService
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.auth.redis_session_store import RedisSessionStore
from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.models.admin_user import AdminUserModel
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from backend.infrastructure.persistence.repos.user_account_repo import (
    SqlAlchemyUserAccountRepository,
)

_PUBLIC_SESSION_PREFIX = "public:session:"
_ADMIN_SESSION_PREFIX = "admin:session:"


@dataclass(frozen=True)
class AuthComponents:
    """认证域装配结果。"""

    public_auth_service: AuthService
    admin_auth_service: AuthService
    public_user_directory: PublicUserDirectory
    public_user_repository: SqlAlchemyUserAccountRepository
    admin_user_repository: SqlAlchemyUserAccountRepository
    password_hasher: BcryptPasswordHasher


def build_auth_components(
    database_session: Any,
    redis_client_factory: Callable[[str], Any],
) -> AuthComponents:
    """创建两套隔离的认证域。

    Args:
        database_session: SQLAlchemy 数据库会话。
        redis_client_factory: Redis 客户端工厂。

    Returns:
        认证域组件集合。
    """

    redis_client = redis_client_factory(config.redis.url)
    password_hasher = BcryptPasswordHasher()
    public_user_repository = SqlAlchemyUserAccountRepository(
        session=database_session,
        model_class=PublicUserModel,
        identifier_attr="email",
    )
    admin_user_repository = SqlAlchemyUserAccountRepository(
        session=database_session,
        model_class=AdminUserModel,
        identifier_attr="username",
    )
    public_session_store = RedisSessionStore(
        redis_client=redis_client,
        key_prefix=_PUBLIC_SESSION_PREFIX,
        sliding_window_days=config.auth.session_sliding_days,
        absolute_max_days=config.auth.session_absolute_days,
    )
    admin_session_store = RedisSessionStore(
        redis_client=redis_client,
        key_prefix=_ADMIN_SESSION_PREFIX,
        sliding_window_days=config.auth.session_sliding_days,
        absolute_max_days=config.auth.session_absolute_days,
    )
    return AuthComponents(
        public_auth_service=AuthService(
            domain=AuthDomain.PUBLIC,
            repository=public_user_repository,
            session_store=public_session_store,
            password_hasher=password_hasher,
            allow_registration=True,
        ),
        admin_auth_service=AuthService(
            domain=AuthDomain.ADMIN,
            repository=admin_user_repository,
            session_store=admin_session_store,
            password_hasher=password_hasher,
            allow_registration=False,
        ),
        public_user_directory=PublicUserDirectory(public_repository=public_user_repository),
        public_user_repository=public_user_repository,
        admin_user_repository=admin_user_repository,
        password_hasher=password_hasher,
    )


__all__ = ["AuthComponents", "build_auth_components"]
