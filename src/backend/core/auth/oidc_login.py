"""编排 OIDC 一次性登录事务与宿主账户绑定策略。"""

from __future__ import annotations

import hmac
import secrets
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from zata_oidc import (
    OidcGateway,
    VerifiedOidcIdentity,
    generate_pkce_verifier,
)

# jscpd:ignore-start -- 应用层模块按相同分层导入公共契约，不表示重复认证实现。
from backend.core.auth.models import AuthDomain, AuthenticatedPrincipal
from backend.core.auth.registration_policy_service import RegistrationPolicyUnavailable
from backend.core.shared.interfaces.oidc_transaction_store import (
    OidcLoginTransaction,
    OidcTransactionStore,
)
from backend.core.shared.interfaces.password_hasher import PasswordHasher
from backend.core.shared.interfaces.registration_policy_provider import (
    RegistrationPolicyProvider,
)
from backend.core.shared.interfaces.session_store import ISessionStore
from backend.core.shared.interfaces.user_account_repository import UserAccountRepository
from backend.core.shared.models.organization import DEFAULT_ORGANIZATION_ID
from backend.core.shared.models.user_account import UserAccount

# jscpd:ignore-end

_OIDC_TRANSACTION_TTL_SECONDS: int = 600


class OidcLoginFailure(StrEnum):
    """应用层拒绝 OIDC 登录的安全原因类别。"""

    TRANSACTION_INVALID = "transaction_invalid"
    EMAIL_UNVERIFIED = "email_unverified"
    IDENTITY_NOT_MAPPED = "identity_not_mapped"
    IDENTITY_CONFLICT = "identity_conflict"
    ADMIN_INACTIVE = "admin_inactive"
    USER_INACTIVE = "user_inactive"
    ORGANIZATION_INACTIVE = "organization_inactive"
    USER_ACCOUNT_CONFLICT = "user_account_conflict"
    REGISTRATION_POLICY_UNAVAILABLE = "registration_policy_unavailable"
    REGISTRATION_NOT_ALLOWED = "registration_not_allowed"


class OidcLoginError(RuntimeError):
    """不含协议敏感信息的应用层 OIDC 登录拒绝。"""

    def __init__(self, reason: OidcLoginFailure) -> None:
        """初始化稳定、可记录的失败类别。"""
        super().__init__(reason.value)
        self.reason = reason


class OidcAccountResolver(Protocol):
    """宿主身份解析策略端口。"""

    def resolve(self, identity: VerifiedOidcIdentity) -> UserAccount:
        """把已验证身份映射到宿主用户账户。"""


@dataclass(frozen=True)
class OidcLoginDependencies:
    """一域 OIDC 登录流程所需的协议、策略与存储依赖。"""

    gateway: OidcGateway
    transaction_store: OidcTransactionStore
    account_resolver: OidcAccountResolver
    session_store: ISessionStore
    domain: AuthDomain


class AdminOidcAccountResolver:
    """只允许首绑现有启用管理员的账户解析策略。"""

    def __init__(self, repository: UserAccountRepository) -> None:
        """注入管理员账户仓库。"""
        self._repository = repository

    def resolve(self, identity: VerifiedOidcIdentity) -> UserAccount:
        """已绑定身份优先；未绑定身份按已验证邮箱原子首绑。"""
        account = self._repository.find_by_oidc_identity(identity.issuer, identity.subject)
        if account is not None:
            if not account.is_active:
                raise OidcLoginError(OidcLoginFailure.ADMIN_INACTIVE)
            if account.organization_is_active is False:
                raise OidcLoginError(OidcLoginFailure.ORGANIZATION_INACTIVE)
            return account

        if not identity.email_verified:
            raise OidcLoginError(OidcLoginFailure.EMAIL_UNVERIFIED)
        normalized_email = identity.email.strip().lower()
        if not normalized_email:
            raise OidcLoginError(OidcLoginFailure.IDENTITY_NOT_MAPPED)
        account = self._repository.find_by_email(normalized_email)
        if account is None:
            raise OidcLoginError(OidcLoginFailure.IDENTITY_NOT_MAPPED)
        if not account.is_active:
            raise OidcLoginError(OidcLoginFailure.ADMIN_INACTIVE)
        if account.organization_is_active is False:
            raise OidcLoginError(OidcLoginFailure.ORGANIZATION_INACTIVE)
        if account.oidc_issuer is not None or account.oidc_subject is not None:
            raise OidcLoginError(OidcLoginFailure.IDENTITY_CONFLICT)
        bound_account = self._repository.bind_oidc_identity(
            account.id,
            identity.issuer,
            identity.subject,
        )
        if bound_account is None:
            raise OidcLoginError(OidcLoginFailure.IDENTITY_CONFLICT)
        return bound_account


class UserOidcAccountResolver:
    """通过策略允许的新身份建号，并拒绝接管已有密码账户。"""

    def __init__(
        self,
        *,
        repository: UserAccountRepository,
        registration_policy_provider: RegistrationPolicyProvider,
        password_hasher: PasswordHasher,
    ) -> None:
        """初始化 public 域账户与注册策略依赖。"""
        self._repository = repository
        self._registration_policy_provider = registration_policy_provider
        self._password_hasher = password_hasher

    def resolve(self, identity: VerifiedOidcIdentity) -> UserAccount:
        """返回已绑定账户，或根据验证邮箱与策略安全创建新账户。"""
        matched_account = self._repository.find_by_oidc_identity(
            identity.issuer,
            identity.subject,
        )
        if matched_account is not None:
            self._require_active_account(matched_account)
            return matched_account

        if not identity.email_verified:
            raise OidcLoginError(OidcLoginFailure.EMAIL_UNVERIFIED)
        normalized_email = identity.email.strip().lower()
        if normalized_email.count("@") != 1:
            raise OidcLoginError(OidcLoginFailure.IDENTITY_NOT_MAPPED)
        if self._repository.find_by_email(normalized_email) is not None:
            raise OidcLoginError(OidcLoginFailure.USER_ACCOUNT_CONFLICT)

        try:
            registration_policy = self._registration_policy_provider.get_registration_policy()
        except RegistrationPolicyUnavailable:
            raise OidcLoginError(OidcLoginFailure.REGISTRATION_POLICY_UNAVAILABLE) from None
        if not registration_policy.allows("oidc", normalized_email):
            raise OidcLoginError(OidcLoginFailure.REGISTRATION_NOT_ALLOWED)

        display_name = identity.name.strip() or normalized_email.split("@", maxsplit=1)[0]
        oidc_user_account = UserAccount(
            id=uuid.uuid4().hex,
            identifier=normalized_email,
            display_name=display_name,
            password_hash=self._password_hasher.hash(secrets.token_urlsafe(48)),
            is_active=True,
            email=normalized_email,
            oidc_issuer=identity.issuer,
            oidc_subject=identity.subject,
            role="user",
            organization_id=DEFAULT_ORGANIZATION_ID,
        )
        try:
            return self._repository.create_unique(oidc_user_account)
        except ValueError as create_error:
            if str(create_error) == "identity_conflict":
                raise OidcLoginError(OidcLoginFailure.IDENTITY_CONFLICT) from None
            if str(create_error) in {"email_conflict", "email_conflict"}:
                raise OidcLoginError(OidcLoginFailure.USER_ACCOUNT_CONFLICT) from None
            raise

    @staticmethod
    def _require_active_account(account: UserAccount) -> None:
        """拒绝被禁用账户或其组织已停用的账户。"""
        if not account.is_active:
            raise OidcLoginError(OidcLoginFailure.USER_INACTIVE)
        if account.organization_is_active is False:
            raise OidcLoginError(OidcLoginFailure.ORGANIZATION_INACTIVE)


class OidcLoginService:
    """共用 OIDC 登录流程，并通过宿主仓库执行账号匹配和会话签发。"""

    def __init__(self, *, dependencies: OidcLoginDependencies) -> None:
        """注入协议客户端、账户解析策略、事务端口与会话存储。"""
        self._dependencies = dependencies
        self._gateway = dependencies.gateway
        self._transaction_store = dependencies.transaction_store
        self._account_resolver = dependencies.account_resolver
        self._session_store = dependencies.session_store
        self._domain = dependencies.domain

    def begin_login(self) -> tuple[str, str]:
        """创建一次性事务并返回事务编号与 IdP 授权 URL。"""
        transaction_id = secrets.token_urlsafe(32)
        transaction = OidcLoginTransaction(
            state=secrets.token_urlsafe(32),
            nonce=secrets.token_urlsafe(32),
            code_verifier=generate_pkce_verifier(),
        )
        if not self._transaction_store.save(
            transaction_id,
            transaction,
            ttl_seconds=_OIDC_TRANSACTION_TTL_SECONDS,
        ):
            raise OidcLoginError(OidcLoginFailure.TRANSACTION_INVALID)
        authorization_url = self._gateway.build_authorization_url(
            state=transaction.state,
            nonce=transaction.nonce,
            code_verifier=transaction.code_verifier,
        )
        return transaction_id, authorization_url

    def complete_login(
        self,
        *,
        transaction_id: str,
        state: str,
        code: str,
    ) -> tuple[str, AuthenticatedPrincipal]:
        """消费事务、校验身份并按宿主策略签发会话。"""
        transaction = self._transaction_store.pop(transaction_id)
        if transaction is None or not hmac.compare_digest(transaction.state, state):
            raise OidcLoginError(OidcLoginFailure.TRANSACTION_INVALID)
        identity = self._gateway.exchange_and_verify_authorization_code(
            code=code,
            code_verifier=transaction.code_verifier,
            nonce=transaction.nonce,
        )
        account = self._account_resolver.resolve(identity)
        session_token = self._session_store.create(account.id)
        principal = AuthenticatedPrincipal(
            user_id=account.id,
            display_name=account.display_name,
            identifier=account.identifier,
            domain=self._domain,
            role=account.role,
            organization_id=account.organization_id,
            organization_name=account.organization_name,
        )
        return session_token, principal


__all__ = [
    "AdminOidcAccountResolver",
    "OidcLoginDependencies",
    "OidcLoginError",
    "OidcLoginFailure",
    "OidcLoginService",
    "UserOidcAccountResolver",
]
