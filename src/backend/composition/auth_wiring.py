"""public 与 admin 两套认证域装配。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthDomain
from backend.core.auth.registration_policy_service import RegistrationPolicyService
from backend.core.auth.service import AuthService
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.auth.redis_session_store import RedisSessionStore
from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.models.admin_user import AdminUserModel
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from backend.infrastructure.persistence.repos.organization_repo import (
    SqlAlchemyOrganizationRepository,
)
from backend.infrastructure.persistence.repos.system_setting_repo import (
    SqlAlchemySystemSettingRepository,
)
from backend.infrastructure.persistence.repos.user_account_repo import (
    SqlAlchemyUserAccountRepository,
    UserAccountRepositoryMapping,
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
    public_session_store: RedisSessionStore
    admin_session_store: RedisSessionStore
    password_hasher: BcryptPasswordHasher
    organization_repository: SqlAlchemyOrganizationRepository
    system_setting_repository: SqlAlchemySystemSettingRepository
    registration_policy_service: RegistrationPolicyService


def build_auth_components(
    session_factory: Any,
    redis_client: Any,
) -> AuthComponents:
    """创建两套隔离的认证域。

    Args:
        session_factory: SQLAlchemy 会话工厂；账户仓库每个操作使用独立短事务。
        redis_client: 已由 composition root 创建的 Redis 客户端。

    Returns:
        认证域组件集合。
    """

    password_hasher = BcryptPasswordHasher()
    system_setting_repository = SqlAlchemySystemSettingRepository(session_factory=session_factory)
    registration_policy_service = RegistrationPolicyService(system_setting_repository)
    organization_repository = SqlAlchemyOrganizationRepository(session_factory=session_factory)
    public_user_repository = SqlAlchemyUserAccountRepository(
        session_factory=session_factory,
        mapping=UserAccountRepositoryMapping(
            model_class=PublicUserModel,
            identifier_attr="email",
            email_attr="email",
            organization_attr="organization_id",
        ),
    )
    admin_user_repository = SqlAlchemyUserAccountRepository(
        session_factory=session_factory,
        mapping=UserAccountRepositoryMapping(
            model_class=AdminUserModel,
            identifier_attr="username",
            email_attr="email",
            role_attr="role",
            organization_attr="organization_id",
        ),
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
            registration_policy_provider=registration_policy_service,
        ),
        admin_auth_service=AuthService(
            domain=AuthDomain.ADMIN,
            repository=admin_user_repository,
            session_store=admin_session_store,
            password_hasher=password_hasher,
            registration_policy_provider=None,
        ),
        public_user_directory=PublicUserDirectory(
            public_repository=public_user_repository,
            organization_repository=organization_repository,
        ),
        public_user_repository=public_user_repository,
        admin_user_repository=admin_user_repository,
        public_session_store=public_session_store,
        admin_session_store=admin_session_store,
        password_hasher=password_hasher,
        organization_repository=organization_repository,
        system_setting_repository=system_setting_repository,
        registration_policy_service=registration_policy_service,
    )


__all__ = ["AuthComponents", "build_auth_components"]
