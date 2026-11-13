"""提供与应用无关的 OIDC 契约与协议值对象。"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

_PKCE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")


class OidcFailureReason(str, Enum):
    """协议错误的安全原因类别，不包含令牌等敏感内容。"""

    CONFIGURATION_INCOMPLETE = "configuration_incomplete"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TOKEN_EXCHANGE_FAILED = "token_exchange_failed"
    TOKEN_VALIDATION = "token_validation"


class OidcAuthenticationError(RuntimeError):
    """不携带敏感令牌或声明内容的 OIDC 协议拒绝异常。"""

    def __init__(self, message: str, *, reason: OidcFailureReason) -> None:
        """创建仅携带安全失败类别的协议异常。

        Args:
            message: 不包含协议敏感信息的通用提示。
            reason: 可供宿主应用记录的稳定失败类别。
        """

        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class VerifiedOidcIdentity:
    """经过 OIDC 协议客户端验证的身份声明。

    Attributes:
        issuer: 与配置核对过的签发者声明。
        subject: 在该签发者范围内稳定的身份键。
        email: 邮箱声明；提供方未返回时为空字符串。
        email_verified: 仅当已签名声明的值是布尔 true 时为真。
        name: 已签名令牌中的可选显示名称。
    """

    issuer: str
    subject: str
    email: str
    email_verified: bool
    name: str


class OidcGateway(Protocol):
    """宿主应用核心使用的服务端 OIDC 协议契约。"""

    @property
    def issuer(self) -> str:
        """返回配置的签发者 URL。"""

    def build_authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        """构造使用固定回调地址与 PKCE S256 的授权码 URL。"""

    def exchange_and_verify_authorization_code(
        self,
        *,
        code: str,
        code_verifier: str,
        nonce: str,
    ) -> VerifiedOidcIdentity:
        """交换授权码并返回已验证的 ID Token 身份。"""


def generate_pkce_verifier() -> str:
    """生成符合 RFC 7636 的密码学随机 code verifier。"""

    return secrets.token_urlsafe(64)


def build_pkce_s256_challenge(code_verifier: str) -> str:
    """计算不带填充的 base64url PKCE S256 challenge。

    Args:
        code_verifier: 符合 RFC 7636 的 verifier，含 43–128 个非保留字符。

    Returns:
        不带填充的 base64url 编码 SHA-256 摘要。

    Raises:
        ValueError: verifier 长度或字符不符合规范。
    """

    if not _PKCE_VERIFIER_PATTERN.fullmatch(code_verifier):
        raise ValueError("PKCE verifier must contain 43–128 unreserved characters.")
    verifier_digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(verifier_digest).decode("ascii").rstrip("=")


__all__ = [
    "OidcAuthenticationError",
    "OidcFailureReason",
    "OidcGateway",
    "VerifiedOidcIdentity",
    "build_pkce_s256_challenge",
    "generate_pkce_verifier",
]
