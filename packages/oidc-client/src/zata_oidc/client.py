"""为 confidential client 授权码流程提供 HTTP OIDC 客户端。"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet, RSAKey
from joserfc.jwt import JWTClaimsRegistry

from zata_oidc.contracts import (
    OidcAuthenticationError,
    OidcFailureReason,
    VerifiedOidcIdentity,
    build_pkce_s256_challenge,
)

_DISCOVERY_SUFFIX = "/.well-known/openid-configuration"
_DEFAULT_SCOPE = "openid email"
_SUPPORTED_ALGORITHMS = ("RS256",)
_HTTP_TIMEOUT_SECONDS = 10.0
_DISCOVERY_CACHE_TTL_SECONDS = 300
_JWKS_CACHE_TTL_SECONDS = 300
_CLAIMS_LEEWAY_SECONDS = 60


@dataclass(frozen=True)
class OidcClientSettings:
    """宿主应用显式提供的 OIDC 客户端配置。

    Attributes:
        issuer: IdP 注册的签发者 URL。
        client_id: Confidential client 标识。
        client_secret: 仅用于兑换授权码的密钥。
        callback_uri: IdP 注册的精确回调 URL。
        scope: 发送给授权端点的 OIDC scope。
    """

    issuer: str
    client_id: str
    client_secret: str
    callback_uri: str
    scope: str = _DEFAULT_SCOPE


class HttpOidcClient:
    """使用 discovery、JWKS、授权码交换和 ID Token 校验的 OIDC 网关。"""

    def __init__(
        self,
        settings: OidcClientSettings,
        http_client: httpx.Client | None = None,
    ) -> None:
        """使用显式配置和可选的外部 HTTP 客户端创建协议客户端。

        Args:
            settings: 宿主提供的 IdP 与 confidential client 配置。
            http_client: 可选的调用方 HTTP 客户端，主要用于注入传输适配器。

        Raises:
            OidcAuthenticationError: 必填配置缺失或格式错误。
        """

        normalized_issuer = settings.issuer.strip().rstrip("/")
        if (
            not normalized_issuer
            or not settings.client_id.strip()
            or not settings.client_secret
            or not settings.callback_uri.strip()
            or not normalized_issuer.startswith(("https://", "http://"))
        ):
            raise OidcAuthenticationError(
                "OIDC client configuration is incomplete.",
                reason=OidcFailureReason.CONFIGURATION_INCOMPLETE,
            )
        self._issuer = normalized_issuer
        self._client_id = settings.client_id.strip()
        self._client_secret = settings.client_secret
        self._callback_uri = settings.callback_uri.strip()
        self._scope = settings.scope.strip() or _DEFAULT_SCOPE
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=_HTTP_TIMEOUT_SECONDS)
        self._cache_lock = threading.Lock()
        self._discovery_cache: dict[str, Any] | None = None
        self._discovery_cached_at = 0.0
        self._jwks_cache: KeySet | None = None
        self._jwks_cached_at = 0.0

    @property
    def issuer(self) -> str:
        """返回去除尾斜杠后的签发者 URL。"""

        return self._issuer

    def __enter__(self) -> HttpOidcClient:
        """返回客户端以支持上下文管理器写法。"""

        return self

    def __exit__(self, *_exception: object) -> None:
        """关闭由本实例创建的 HTTP 客户端。"""

        self.close()

    def close(self) -> None:
        """关闭默认创建的 HTTP 客户端；外部注入的客户端仍由调用方管理。"""

        if self._owns_http_client:
            self._http_client.close()

    def build_authorization_url(
        self,
        *,
        state: str,
        nonce: str,
        code_verifier: str,
    ) -> str:
        """构造固定回调地址并带 PKCE S256 参数的 IdP 授权 URL。

        Args:
            state: 宿主生成并保存的随机 state。
            nonce: 宿主生成并保存的随机 nonce。
            code_verifier: 宿主保存在一次性事务中的 PKCE verifier。

        Returns:
            从已验证 discovery 元数据读取的授权端点 URL。

        Raises:
            OidcAuthenticationError: discovery 不可用或格式错误。
            ValueError: state、nonce 或 code verifier 格式错误。
        """

        if not state or not nonce:
            raise ValueError("OIDC state and nonce must not be empty.")
        discovery = self._fetch_discovery()
        authorization_endpoint = discovery.get("authorization_endpoint")
        if not isinstance(authorization_endpoint, str) or not authorization_endpoint:
            raise OidcAuthenticationError(
                "OIDC discovery is missing the authorization endpoint.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            )
        authorization_parameters = {
            "response_type": "code",
            "client_id": self._client_id,
            "redirect_uri": self._callback_uri,
            "scope": self._scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": build_pkce_s256_challenge(code_verifier),
            "code_challenge_method": "S256",
        }
        return f"{authorization_endpoint}?{urlencode(authorization_parameters)}"

    def exchange_and_verify_authorization_code(
        self,
        *,
        code: str,
        code_verifier: str,
        nonce: str,
    ) -> VerifiedOidcIdentity:
        """兑换授权码并校验响应中的 ID Token。

        Args:
            code: 宿主回调收到的授权码。
            code_verifier: 与本次事务一同保存的 verifier。
            nonce: 与本次事务一同保存的预期 nonce。

        Returns:
            已通过协议校验的 ID Token 身份声明。

        Raises:
            OidcAuthenticationError: IdP、授权码兑换、签名或声明校验失败。
            ValueError: PKCE verifier 格式错误。
        """

        if not code or not nonce:
            raise ValueError("Authorization code and nonce must not be empty.")
        build_pkce_s256_challenge(code_verifier)
        discovery = self._fetch_discovery()
        token_endpoint = discovery.get("token_endpoint")
        if not isinstance(token_endpoint, str) or not token_endpoint:
            raise OidcAuthenticationError(
                "OIDC discovery is missing the token endpoint.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            )
        try:
            token_response = self._http_client.post(
                token_endpoint,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self._callback_uri,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code_verifier": code_verifier,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError:
            raise OidcAuthenticationError(
                "OIDC token endpoint is unreachable.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            ) from None
        token_payload = self._safe_json(token_response)
        if token_response.status_code != 200 or not isinstance(token_payload, dict):
            raise OidcAuthenticationError(
                "Authorization code exchange failed.",
                reason=OidcFailureReason.TOKEN_EXCHANGE_FAILED,
            )
        id_token = token_payload.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise OidcAuthenticationError(
                "Authorization code exchange failed.",
                reason=OidcFailureReason.TOKEN_EXCHANGE_FAILED,
            )
        claims = self._verify_id_token(id_token)
        if claims.get("nonce") != nonce:
            raise OidcAuthenticationError(
                "ID Token nonce validation failed.",
                reason=OidcFailureReason.TOKEN_VALIDATION,
            )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject.strip():
            raise OidcAuthenticationError(
                "ID Token subject is missing.",
                reason=OidcFailureReason.TOKEN_VALIDATION,
            )
        email_claim = claims.get("email")
        name_claim = claims.get("name")
        return VerifiedOidcIdentity(
            issuer=self._issuer,
            subject=subject,
            email=email_claim if isinstance(email_claim, str) else "",
            email_verified=claims.get("email_verified") is True,
            name=name_claim if isinstance(name_claim, str) else "",
        )

    def _verify_id_token(self, id_token: str) -> dict[str, Any]:
        """校验 RS256 签名及必需 OIDC 声明。"""

        key_set = self._fetch_jwks()
        try:
            decoded_token = jwt.decode(
                id_token,
                key_set,
                algorithms=list(_SUPPORTED_ALGORITHMS),
            )
        except (JoseError, TypeError, ValueError):
            raise OidcAuthenticationError(
                "ID Token signature validation failed.",
                reason=OidcFailureReason.TOKEN_VALIDATION,
            ) from None
        registry = JWTClaimsRegistry(
            leeway=_CLAIMS_LEEWAY_SECONDS,
            iss={"essential": True, "values": [self._issuer]},
            aud={"essential": True, "values": [self._client_id]},
            exp={"essential": True},
            iat={"essential": True},
            sub={"essential": True},
        )
        try:
            registry.validate(decoded_token.claims)
        except JoseError:
            raise OidcAuthenticationError(
                "ID Token claims validation failed.",
                reason=OidcFailureReason.TOKEN_VALIDATION,
            ) from None
        claims: dict[str, Any] = dict(decoded_token.claims)
        audience = claims.get("aud")
        authorized_party = claims.get("azp")
        if isinstance(audience, list) and len(audience) > 1 and authorized_party != self._client_id:
            raise OidcAuthenticationError(
                "ID Token authorized party validation failed.",
                reason=OidcFailureReason.TOKEN_VALIDATION,
            )
        if authorized_party is not None and authorized_party != self._client_id:
            raise OidcAuthenticationError(
                "ID Token authorized party validation failed.",
                reason=OidcFailureReason.TOKEN_VALIDATION,
            )
        return claims

    def _fetch_discovery(self) -> dict[str, Any]:
        """读取并缓存 discovery 元数据，同时核对其 issuer。"""

        now = time.monotonic()
        with self._cache_lock:
            if (
                self._discovery_cache is not None
                and now - self._discovery_cached_at < _DISCOVERY_CACHE_TTL_SECONDS
            ):
                return dict(self._discovery_cache)
        try:
            response = self._http_client.get(f"{self._issuer}{_DISCOVERY_SUFFIX}")
        except httpx.HTTPError:
            raise OidcAuthenticationError(
                "OIDC discovery document is unreachable.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            ) from None
        document = self._safe_json(response)
        if response.status_code != 200 or not isinstance(document, dict):
            raise OidcAuthenticationError(
                "OIDC discovery document is invalid.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            )
        discovered_issuer = document.get("issuer")
        if not isinstance(discovered_issuer, str) or discovered_issuer.rstrip("/") != self._issuer:
            raise OidcAuthenticationError(
                "OIDC discovery issuer does not match configuration.",
                reason=OidcFailureReason.CONFIGURATION_INCOMPLETE,
            )
        with self._cache_lock:
            self._discovery_cache = dict(document)
            self._discovery_cached_at = now
        return dict(document)

    def _fetch_jwks(self) -> KeySet:
        """读取并缓存 discovery 声明的 RSA 签名公钥。"""

        now = time.monotonic()
        with self._cache_lock:
            if (
                self._jwks_cache is not None
                and now - self._jwks_cached_at < _JWKS_CACHE_TTL_SECONDS
            ):
                return self._jwks_cache
        discovery = self._fetch_discovery()
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise OidcAuthenticationError(
                "OIDC discovery is missing the JWKS URI.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            )
        try:
            response = self._http_client.get(jwks_uri)
        except httpx.HTTPError:
            raise OidcAuthenticationError(
                "OIDC JWKS endpoint is unreachable.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            ) from None
        document = self._safe_json(response)
        keys = document.get("keys") if isinstance(document, dict) else None
        if response.status_code != 200 or not isinstance(keys, list) or not keys:
            raise OidcAuthenticationError(
                "OIDC JWKS document is invalid.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            )
        rsa_keys: list[RSAKey] = []
        for key_data in keys:
            if not isinstance(key_data, dict) or key_data.get("kty") != "RSA":
                continue
            if key_data.get("use") not in (None, "sig"):
                continue
            if key_data.get("alg") not in (None, "RS256"):
                continue
            key_operations = key_data.get("key_ops")
            if key_operations is not None and (
                not isinstance(key_operations, list) or "verify" not in key_operations
            ):
                continue
            try:
                rsa_keys.append(RSAKey.import_key(key_data))
            except (JoseError, TypeError, ValueError):
                continue
        if not rsa_keys:
            raise OidcAuthenticationError(
                "OIDC JWKS has no usable RSA signing key.",
                reason=OidcFailureReason.PROVIDER_UNAVAILABLE,
            )
        key_set = KeySet(rsa_keys)
        with self._cache_lock:
            self._jwks_cache = key_set
            self._jwks_cached_at = now
        return key_set

    @staticmethod
    def _safe_json(response: httpx.Response) -> object:
        """解析 JSON，并避免错误信息暴露 IdP 响应正文。"""

        try:
            return response.json()
        except ValueError:
            return None


__all__ = ["HttpOidcClient", "OidcClientSettings"]
