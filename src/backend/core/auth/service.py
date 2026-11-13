"""认证编排服务：两域共享的单一实现，差异通过注入区分。"""

from __future__ import annotations

import uuid

from backend.core.auth.models import AuthDomain, AuthenticatedPrincipal
from backend.core.auth.password_policy import (
    MAX_PASSWORD_UTF8_BYTES,
    is_password_within_byte_limit,
)
from backend.core.shared.interfaces.password_hasher import PasswordHasher
from backend.core.shared.interfaces.registration_policy_provider import (
    RegistrationPolicyProvider,
)
from backend.core.shared.interfaces.session_store import ISessionStore
from backend.core.shared.interfaces.user_account_repository import (
    UserAccountRepository,
)
from backend.core.shared.models.user_account import UserAccount

_MIN_PASSWORD_LENGTH: int = 6


class AuthService:
    """跨域复用的认证用例编排。

    通过注入不同的用户仓库、会话存储与注册策略，同一份编排逻辑即可服务
    public 与 admin 两个相互隔离的认证域。
    """

    def __init__(
        self,
        *,
        domain: AuthDomain,
        repository: UserAccountRepository,
        session_store: ISessionStore,
        password_hasher: PasswordHasher,
        registration_policy_provider: RegistrationPolicyProvider | None,
    ) -> None:
        """初始化认证服务。

        Args:
            domain (AuthDomain): 本服务所属认证域。
            repository (UserAccountRepository): 本域用户仓库。
            session_store (ISessionStore): 本域会话存储（独立命名空间）。
            password_hasher (PasswordHasher): 密码哈希实现。
            registration_policy_provider (RegistrationPolicyProvider | None):
                注册策略端口；admin 域传 None。
        """
        self._domain = domain
        self._repository = repository
        self._session_store = session_store
        self._password_hasher = password_hasher
        self._registration_policy_provider = registration_policy_provider

    def authenticate(self, identifier: str, password: str) -> tuple[str, AuthenticatedPrincipal]:
        """校验凭据并创建会话。

        Args:
            identifier (str): 登录标识（public 邮箱 / admin 用户名）。
            password (str): 明文密码。

        Returns:
            tuple[str, AuthenticatedPrincipal]: (会话 token, 已认证主体)。

        Raises:
            ValueError: 凭据无效或账户被禁用。
        """
        if not is_password_within_byte_limit(password):
            raise ValueError("用户名或密码错误")

        normalized_identifier: str = identifier.strip().lower()
        matched_account: UserAccount | None = self._repository.find_by_identifier(
            normalized_identifier
        )
        if matched_account is None:
            raise ValueError("用户名或密码错误")
        if not self._password_hasher.verify(password, matched_account.password_hash):
            raise ValueError("用户名或密码错误")
        if not matched_account.is_active:
            raise ValueError("账号已被禁用")
        if matched_account.organization_is_active is False:
            raise ValueError("组织已停用，请联系管理员")

        session_token: str = self._session_store.create(matched_account.id)
        return session_token, self._to_principal(matched_account)

    def register(
        self, *, identifier: str, display_name: str, password: str
    ) -> tuple[str, AuthenticatedPrincipal]:
        """注册新账户并自动登录（仅限允许注册的域）。

        Args:
            identifier (str): 登录标识（public 域为邮箱）。
            display_name (str): 展示名称。
            password (str): 明文密码。

        Returns:
            tuple[str, AuthenticatedPrincipal]: (会话 token, 已认证主体)。

        Raises:
            ValueError: 当前域不支持注册、入参非法或标识已被占用。
        """
        if self._registration_policy_provider is None:
            raise ValueError("当前域不支持注册")

        normalized_identifier: str = identifier.strip().lower()
        cleaned_display_name: str = display_name.strip()
        cleaned_password: str = password.strip()
        if not is_password_within_byte_limit(cleaned_password):
            raise ValueError(f"Password must not exceed {MAX_PASSWORD_UTF8_BYTES} UTF-8 bytes")
        if not normalized_identifier:
            raise ValueError("邮箱不能为空")
        if not cleaned_display_name:
            raise ValueError("显示名称不能为空")
        if len(cleaned_password) < _MIN_PASSWORD_LENGTH:
            raise ValueError("密码长度至少 6 位")
        registration_policy = self._registration_policy_provider.get_registration_policy()
        if not registration_policy.allows("password", normalized_identifier):
            if registration_policy.registration_mode in {"closed", "oidc_only"}:
                raise ValueError("registration_not_allowed")
            raise ValueError("email_domain_not_allowed")
        if self._repository.find_by_identifier(normalized_identifier) is not None:
            raise ValueError("邮箱已被注册")

        new_account = UserAccount(
            id=uuid.uuid4().hex,
            identifier=normalized_identifier,
            display_name=cleaned_display_name,
            password_hash=self._password_hasher.hash(cleaned_password),
            is_active=True,
            email=normalized_identifier,
        )
        try:
            created_account: UserAccount = self._repository.create_unique(new_account)
        except ValueError as conflict_error:
            if str(conflict_error) == "email_conflict":
                raise ValueError("邮箱已被注册") from conflict_error
            raise
        session_token: str = self._session_store.create(created_account.id)
        return session_token, self._to_principal(created_account)

    def logout(self, token: str) -> None:
        """销毁指定会话。

        Args:
            token (str): 会话 token。
        """
        self._session_store.delete(token)

    def resolve_session(self, token: str) -> AuthenticatedPrincipal | None:
        """解析会话并滑动续期。

        会在解析后回查账户启用状态，使被禁用账户的既有会话立即失效。

        Args:
            token (str): 会话 token。

        Returns:
            AuthenticatedPrincipal | None: 有效主体；会话无效 / 过期 / 账户被禁用
            时返回 None。
        """
        session_record = self._session_store.slide_expiration(token)
        if session_record is None:
            return None
        account: UserAccount | None = self._repository.get_by_id(session_record.user_id)
        if account is None or not account.is_active or account.organization_is_active is False:
            return None
        return self._to_principal(account)

    def _to_principal(self, account: UserAccount) -> AuthenticatedPrincipal:
        """把账户映射为已认证主体。

        Args:
            account (UserAccount): 账户领域对象。

        Returns:
            AuthenticatedPrincipal: 不含敏感字段的主体。
        """
        return AuthenticatedPrincipal(
            user_id=account.id,
            display_name=account.display_name,
            identifier=account.identifier,
            domain=self._domain,
            role=account.role,
            organization_id=account.organization_id,
            organization_name=account.organization_name,
        )
