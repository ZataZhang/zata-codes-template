"""Public OIDC 真实 API 测试共用的客户端装配与回调流程。"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.api.dependencies import get_public_oidc_gateway
from backend.infrastructure.config.settings import config
from tests.backend.oidc_test_support import (
    TEST_OIDC_CLIENT_SECRET,
    TEST_OIDC_ISSUER,
    TEST_PUBLIC_OIDC_CALLBACK_URI,
    TEST_PUBLIC_OIDC_CLIENT_ID,
    ControlledOidcIssuer,
    parse_authorization_query,
)


def configure_public_oidc(monkeypatch: Any) -> None:
    """为测试应用显式设置完整 public OIDC 配置。"""
    monkeypatch.setattr(config.user_oidc, "enabled", True)
    monkeypatch.setattr(config.user_oidc, "issuer", TEST_OIDC_ISSUER)
    monkeypatch.setattr(config.user_oidc, "client_id", TEST_PUBLIC_OIDC_CLIENT_ID)
    monkeypatch.setattr(config.user_oidc, "client_secret", SecretStr(TEST_OIDC_CLIENT_SECRET))
    monkeypatch.setattr(config.user_oidc, "callback_uri", TEST_PUBLIC_OIDC_CALLBACK_URI)


def install_public_oidc_issuer(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
) -> tuple[Any, Any]:
    """仅替换 IdP 的 HTTP 传输，保留应用路由、仓库和会话流程。"""
    gateway, http_client = issuer.build_gateway(
        client_id=TEST_PUBLIC_OIDC_CLIENT_ID,
        callback_uri=TEST_PUBLIC_OIDC_CALLBACK_URI,
    )
    api_client.app.dependency_overrides[get_public_oidc_gateway] = lambda: gateway
    return gateway, http_client


def close_public_oidc_issuer(
    api_client: TestClient,
    gateway: Any,
    http_client: Any,
) -> None:
    """关闭测试 IdP 传输和应用装配的未使用客户端。"""
    configured_gateway = api_client.app.state.public_oidc_gateway
    if configured_gateway is not gateway and configured_gateway is not None:
        configured_gateway.close()
    gateway.close()
    http_client.close()


def start_public_oidc_login(api_client: TestClient) -> dict[str, str]:
    """调用真实授权起始路由并解析标准 OIDC 参数。"""
    start_response = api_client.get("/auth/oidc/start", follow_redirects=False)
    assert start_response.status_code == 302
    authorization_query = parse_authorization_query(start_response.headers["location"])
    assert authorization_query["client_id"] == TEST_PUBLIC_OIDC_CLIENT_ID
    return authorization_query


def set_public_identity_claims(
    issuer: ControlledOidcIssuer,
    authorization_query: dict[str, str],
    *,
    email: str,
    subject: str = "public-subject-1",
    email_verified: bool = True,
) -> None:
    """按授权事务 nonce 签发真实 RS256 测试身份令牌。"""
    issuer.token_claims = issuer.standard_claims(
        nonce=authorization_query["nonce"],
        subject=subject,
        email=email,
        email_verified=email_verified,
        audience=TEST_PUBLIC_OIDC_CLIENT_ID,
    )


def finish_public_oidc_login(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
    authorization_query: dict[str, str],
    *,
    email: str,
    subject: str = "public-subject-1",
    email_verified: bool = True,
) -> Any:
    """调用真实 callback 路由完成身份令牌交换。"""
    set_public_identity_claims(
        issuer,
        authorization_query,
        email=email,
        subject=subject,
        email_verified=email_verified,
    )
    return api_client.get(
        "/auth/oidc/callback",
        params={"code": "public-test-authorization-code", "state": authorization_query["state"]},
        follow_redirects=False,
    )


__all__ = [
    "close_public_oidc_issuer",
    "configure_public_oidc",
    "finish_public_oidc_login",
    "install_public_oidc_issuer",
    "set_public_identity_claims",
    "start_public_oidc_login",
]
