"""OIDC 协议客户端行为测试；只替换网络传输，签名与 claims 校验走真实代码。"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from joserfc import jwt
from joserfc.jwk import OctKey, RSAKey
from zata_oidc import (
    HttpOidcClient,
    OidcAuthenticationError,
    OidcClientSettings,
    OidcFailureReason,
)

ISSUER = "https://id.example.test/realms/main"
CLIENT_ID = "app-client"
CLIENT_SECRET = "test-client-secret"
CALLBACK_URI = "https://app.example.test/oidc/callback"
AUTHORIZATION_ENDPOINT = f"{ISSUER}/protocol/openid-connect/auth"
TOKEN_ENDPOINT = f"{ISSUER}/protocol/openid-connect/token"
JWKS_ENDPOINT = f"{ISSUER}/protocol/openid-connect/certs"


class ControlledOidcIssuer:
    """受控 issuer 使用真实 RSA 签名，避免替换包内验证逻辑。"""

    def __init__(self, *, discovery_issuer: str | None = None) -> None:
        """初始化使用固定密钥的本地身份中心替身。"""

        self.signing_key = RSAKey.generate_key()
        private_key: dict[str, Any] = self.signing_key.as_dict(private=True)
        private_key["kid"] = "issuer-key"
        self.signing_key = RSAKey.import_key(private_key)
        self.public_key: dict[str, Any] = self.signing_key.as_dict(private=False)
        self.public_key["kid"] = "issuer-key"
        self.discovery_issuer = discovery_issuer or ISSUER
        self.claims: dict[str, Any] = {}
        self.token_override: str | None = None
        self.authorization_requests: list[str] = []
        self.token_requests: list[dict[str, str]] = []

    def mint_token(self, claims: dict[str, Any], *, signing_key: RSAKey | None = None) -> str:
        """用 issuer 的私钥或负控密钥签署 ID Token。"""

        active_key = signing_key or self.signing_key
        return jwt.encode({"alg": "RS256", "kid": "issuer-key"}, claims, active_key)

    def build_http_client(self) -> httpx.Client:
        """返回只替换网络 I/O 的客户端。"""

        def handle(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(
                    200,
                    json={
                        "issuer": self.discovery_issuer,
                        "authorization_endpoint": AUTHORIZATION_ENDPOINT,
                        "token_endpoint": TOKEN_ENDPOINT,
                        "jwks_uri": JWKS_ENDPOINT,
                    },
                )
            if str(request.url) == JWKS_ENDPOINT:
                return httpx.Response(200, json={"keys": [self.public_key]})
            if str(request.url) == AUTHORIZATION_ENDPOINT:
                self.authorization_requests.append(str(request.url))
                return httpx.Response(200, json={"ok": True})
            if str(request.url) == TOKEN_ENDPOINT:
                token_form = parse_qs(request.content.decode("utf-8"))
                self.token_requests.append({key: values[0] for key, values in token_form.items()})
                return httpx.Response(
                    200,
                    json={
                        "id_token": self.token_override or self.mint_token(self.claims),
                    },
                )
            return httpx.Response(404, json={"error": "not_found"})

        return httpx.Client(transport=httpx.MockTransport(handle))

    def valid_claims(self, *, nonce: str, **overrides: Any) -> dict[str, Any]:
        """构造最小的有效 OIDC ID Token claims。"""

        current_time = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "sub": "subject-1",
            "iat": current_time,
            "exp": current_time + 300,
            "nonce": nonce,
            "email": "person@example.com",
            "email_verified": True,
            "name": "Person Example",
        }
        claims.update(overrides)
        return claims


def build_client(issuer: ControlledOidcIssuer) -> tuple[HttpOidcClient, httpx.Client]:
    """装配协议客户端与由测试拥有的 HTTP 资源。"""

    http_client = issuer.build_http_client()
    client = HttpOidcClient(
        OidcClientSettings(
            issuer=ISSUER,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            callback_uri=CALLBACK_URI,
        ),
        http_client=http_client,
    )
    return client, http_client


def test_authorization_url_uses_fixed_callback_and_pkce_s256() -> None:
    """授权地址含固定 callback、state、nonce 与 S256 challenge。"""

    issuer = ControlledOidcIssuer()
    client, http_client = build_client(issuer)
    verifier = "v" * 43

    try:
        authorization_url = client.build_authorization_url(
            state="state-value",
            nonce="nonce-value",
            code_verifier=verifier,
        )
    finally:
        client.close()
        http_client.close()

    query = parse_qs(urlparse(authorization_url).query)
    assert urlparse(authorization_url).scheme == "https"
    assert query["client_id"] == [CLIENT_ID]
    assert query["redirect_uri"] == [CALLBACK_URI]
    assert query["state"] == ["state-value"]
    assert query["nonce"] == ["nonce-value"]
    assert query["code_challenge_method"] == ["S256"]
    assert len(query["code_challenge"][0]) == 43


def test_token_exchange_verifies_signed_identity_and_pkce() -> None:
    """成功路径交换 code、核对 confidential client 参数并返回已验证身份。"""

    issuer = ControlledOidcIssuer()
    client, http_client = build_client(issuer)
    issuer.claims = issuer.valid_claims(nonce="nonce-value")

    try:
        identity = client.exchange_and_verify_authorization_code(
            code="authorization-code",
            code_verifier="v" * 43,
            nonce="nonce-value",
        )
    finally:
        client.close()
        http_client.close()

    token_request = issuer.token_requests[0]
    assert token_request["grant_type"] == "authorization_code"
    assert token_request["code"] == "authorization-code"
    assert token_request["client_id"] == CLIENT_ID
    assert token_request["client_secret"] == CLIENT_SECRET
    assert token_request["redirect_uri"] == CALLBACK_URI
    assert token_request["code_verifier"] == "v" * 43
    assert identity.issuer == ISSUER
    assert identity.subject == "subject-1"
    assert identity.email == "person@example.com"
    assert identity.email_verified is True
    assert identity.name == "Person Example"


@pytest.mark.parametrize(
    ("claim_overrides", "expected_reason"),
    [
        ({"iss": "https://evil.example.test"}, OidcFailureReason.TOKEN_VALIDATION),
        ({"aud": "other-client"}, OidcFailureReason.TOKEN_VALIDATION),
        ({"exp": 1}, OidcFailureReason.TOKEN_VALIDATION),
        ({"nonce": "wrong"}, OidcFailureReason.TOKEN_VALIDATION),
        ({"sub": ""}, OidcFailureReason.TOKEN_VALIDATION),
    ],
)
def test_invalid_claims_are_rejected(
    claim_overrides: dict[str, Any], expected_reason: OidcFailureReason
) -> None:
    """issuer、audience、过期时间、nonce 与 subject 错误均被拒绝。"""

    issuer = ControlledOidcIssuer()
    client, http_client = build_client(issuer)
    invalid_claims = issuer.valid_claims(nonce="nonce-value")
    invalid_claims.update(claim_overrides)
    issuer.claims = invalid_claims

    try:
        with pytest.raises(OidcAuthenticationError) as error_info:
            client.exchange_and_verify_authorization_code(
                code="authorization-code",
                code_verifier="v" * 43,
                nonce="nonce-value",
            )
    finally:
        client.close()
        http_client.close()

    assert error_info.value.reason is expected_reason
    assert "authorization-code" not in str(error_info.value)
    assert CLIENT_SECRET not in str(error_info.value)


def test_token_signed_by_untrusted_key_is_rejected() -> None:
    """信任列表以外的 RSA 私钥签发 token 不得通过验证。"""

    issuer = ControlledOidcIssuer()
    client, http_client = build_client(issuer)
    attacker_key = RSAKey.generate_key()
    attacker_private = attacker_key.as_dict(private=True)
    attacker_private["kid"] = "issuer-key"
    attacker_key = RSAKey.import_key(attacker_private)
    issuer.claims = issuer.valid_claims(nonce="nonce-value")
    forged_token = issuer.mint_token(issuer.claims, signing_key=attacker_key)

    def handle_forged_token(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": AUTHORIZATION_ENDPOINT,
                    "token_endpoint": TOKEN_ENDPOINT,
                    "jwks_uri": JWKS_ENDPOINT,
                },
            )
        if str(request.url) == JWKS_ENDPOINT:
            return httpx.Response(200, json={"keys": [issuer.public_key]})
        if str(request.url) == TOKEN_ENDPOINT:
            return httpx.Response(200, json={"id_token": forged_token})
        return httpx.Response(404)

    forged_http_client = httpx.Client(transport=httpx.MockTransport(handle_forged_token))
    forged_client = HttpOidcClient(
        OidcClientSettings(
            issuer=ISSUER,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            callback_uri=CALLBACK_URI,
        ),
        http_client=forged_http_client,
    )
    client.close()
    http_client.close()

    try:
        with pytest.raises(OidcAuthenticationError) as error_info:
            forged_client.exchange_and_verify_authorization_code(
                code="forged-code",
                code_verifier="v" * 43,
                nonce="nonce-value",
            )
    finally:
        forged_client.close()
        forged_http_client.close()

    assert error_info.value.reason is OidcFailureReason.TOKEN_VALIDATION


def test_non_rs256_algorithm_is_rejected() -> None:
    """即使 token 使用可验证密钥，客户端也只接受 RS256。"""

    issuer = ControlledOidcIssuer()
    client, http_client = build_client(issuer)
    issuer.claims = issuer.valid_claims(nonce="nonce-value")
    issuer.token_override = jwt.encode(
        {"alg": "HS256", "kid": "issuer-key"},
        issuer.claims,
        OctKey.import_key("test-hmac-secret"),
    )

    try:
        with pytest.raises(OidcAuthenticationError) as error_info:
            client.exchange_and_verify_authorization_code(
                code="wrong-algorithm-code",
                code_verifier="v" * 43,
                nonce="nonce-value",
            )
    finally:
        client.close()
        http_client.close()

    assert error_info.value.reason is OidcFailureReason.TOKEN_VALIDATION


def test_discovery_rejects_a_different_issuer() -> None:
    """Discovery 中的 issuer 必须与显式配置完全匹配。"""

    issuer = ControlledOidcIssuer(discovery_issuer="https://evil.example.test")
    client, http_client = build_client(issuer)

    try:
        with pytest.raises(OidcAuthenticationError) as error_info:
            client.build_authorization_url(
                state="state-value",
                nonce="nonce-value",
                code_verifier="v" * 43,
            )
    finally:
        client.close()
        http_client.close()

    assert error_info.value.reason is OidcFailureReason.CONFIGURATION_INCOMPLETE
