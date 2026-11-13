"""后端 OIDC 集成测试共用的 RS256 身份中心替身。"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from joserfc import jwt
from joserfc.jwk import RSAKey
from zata_oidc import HttpOidcClient, OidcClientSettings

TEST_OIDC_ISSUER = "https://issuer.test/realms/template"
TEST_OIDC_CLIENT_ID = "template-admin"
TEST_PUBLIC_OIDC_CLIENT_ID = "template-public"
TEST_OIDC_CLIENT_SECRET = "test-client-secret"
TEST_OIDC_CALLBACK_URI = "https://app.test/api/admin/auth/oidc/callback"
TEST_PUBLIC_OIDC_CALLBACK_URI = "https://app.test/api/auth/oidc/callback"
TEST_OIDC_AUTHORIZATION_ENDPOINT = f"{TEST_OIDC_ISSUER}/protocol/openid-connect/auth"
TEST_OIDC_TOKEN_ENDPOINT = f"{TEST_OIDC_ISSUER}/protocol/openid-connect/token"
TEST_OIDC_JWKS_ENDPOINT = f"{TEST_OIDC_ISSUER}/protocol/openid-connect/certs"


class ControlledOidcIssuer:
    """受控 issuer 使用真实 RS256 签名，只替换 HTTP 传输。"""

    def __init__(self, *, discovery_issuer: str | None = None) -> None:
        """初始化 issuer 密钥与请求记录。"""

        raw_private_key: RSAKey = RSAKey.generate_key()
        private_jwk: dict[str, Any] = raw_private_key.as_dict(private=True)
        private_jwk["kid"] = "controlled-issuer-key"
        self.signing_key: RSAKey = RSAKey.import_key(private_jwk)
        self.public_jwk: dict[str, Any] = self.signing_key.as_dict(private=False)
        self.public_jwk["kid"] = "controlled-issuer-key"
        self.discovery_issuer = discovery_issuer or TEST_OIDC_ISSUER
        self.token_claims: dict[str, Any] = {}
        self.token_override: str | None = None
        self.authorization_requests: list[str] = []
        self.token_requests: list[dict[str, str]] = []

    def mint_id_token(self, claims: dict[str, Any], *, signing_key: RSAKey | None = None) -> str:
        """使用身份中心私钥或指定负控密钥签署 ID Token。"""

        active_key: RSAKey = signing_key or self.signing_key
        return jwt.encode(
            {"alg": "RS256", "kid": "controlled-issuer-key"},
            claims,
            active_key,
        )

    def build_http_client(self) -> httpx.Client:
        """返回通过 MockTransport 提供 discovery、JWKS 与 token 的客户端。"""

        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(
                    200,
                    json={
                        "issuer": self.discovery_issuer,
                        "authorization_endpoint": TEST_OIDC_AUTHORIZATION_ENDPOINT,
                        "token_endpoint": TEST_OIDC_TOKEN_ENDPOINT,
                        "jwks_uri": TEST_OIDC_JWKS_ENDPOINT,
                        "response_types_supported": ["code"],
                        "id_token_signing_alg_values_supported": ["RS256"],
                    },
                )
            if str(request.url) == TEST_OIDC_JWKS_ENDPOINT:
                return httpx.Response(200, json={"keys": [self.public_jwk]})
            if str(request.url) == TEST_OIDC_AUTHORIZATION_ENDPOINT:
                self.authorization_requests.append(str(request.url))
                return httpx.Response(200, json={"ok": True})
            if str(request.url) == TEST_OIDC_TOKEN_ENDPOINT:
                form_values = parse_qs(request.content.decode("utf-8"))
                self.token_requests.append(
                    {form_key: values[0] for form_key, values in form_values.items()}
                )
                id_token = self.token_override or self.mint_id_token(self.token_claims)
                return httpx.Response(200, json={"id_token": id_token})
            return httpx.Response(404, json={"error": "not_found"})

        return httpx.Client(transport=httpx.MockTransport(handle))

    def build_gateway(
        self,
        *,
        client_id: str = TEST_OIDC_CLIENT_ID,
        callback_uri: str = TEST_OIDC_CALLBACK_URI,
    ) -> tuple[HttpOidcClient, httpx.Client]:
        """为测试提供真实协议客户端与其测试所有的 HTTP 客户端。"""

        http_client = self.build_http_client()
        gateway = HttpOidcClient(
            OidcClientSettings(
                issuer=TEST_OIDC_ISSUER,
                client_id=client_id,
                client_secret=TEST_OIDC_CLIENT_SECRET,
                callback_uri=callback_uri,
            ),
            http_client=http_client,
        )
        return gateway, http_client

    def standard_claims(
        self,
        *,
        nonce: str,
        subject: str = "test-subject-1",
        email: str = "admin@example.test",
        email_verified: bool = True,
        issuer: str | None = None,
        audience: str | list[str] | None = None,
        expires_in_seconds: int = 300,
    ) -> dict[str, Any]:
        """构造有效 ID Token claims，可覆盖字段制造拒绝场景。"""

        now_unix: int = int(time.time())
        return {
            "iss": issuer or TEST_OIDC_ISSUER,
            "sub": subject,
            "aud": audience or TEST_OIDC_CLIENT_ID,
            "iat": now_unix,
            "exp": now_unix + expires_in_seconds,
            "nonce": nonce,
            "email": email,
            "email_verified": email_verified,
            "name": "Test Admin",
        }


def parse_authorization_query(location: str) -> dict[str, str]:
    """读取授权重定向中的协议参数。"""

    parsed_url = urlparse(location)
    query = {name: values[0] for name, values in parse_qs(parsed_url.query).items()}
    query["endpoint"] = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
    return query


__all__ = [
    "ControlledOidcIssuer",
    "TEST_OIDC_AUTHORIZATION_ENDPOINT",
    "TEST_OIDC_CALLBACK_URI",
    "TEST_OIDC_CLIENT_ID",
    "TEST_OIDC_CLIENT_SECRET",
    "TEST_OIDC_ISSUER",
    "TEST_OIDC_JWKS_ENDPOINT",
    "TEST_OIDC_TOKEN_ENDPOINT",
    "TEST_PUBLIC_OIDC_CALLBACK_URI",
    "TEST_PUBLIC_OIDC_CLIENT_ID",
    "parse_authorization_query",
]
