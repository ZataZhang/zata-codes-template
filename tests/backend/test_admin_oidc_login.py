"""管理端 OIDC 登录的真实 API 与数据库集成测试。"""

from __future__ import annotations

import uuid
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient
from joserfc.jwk import RSAKey
from pydantic import SecretStr

from backend.api.dependencies import get_admin_oidc_gateway
from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.admin_user import AdminUserModel
from tests.backend.oidc_test_support import (
    TEST_OIDC_CALLBACK_URI,
    TEST_OIDC_CLIENT_SECRET,
    TEST_OIDC_ISSUER,
    ControlledOidcIssuer,
    parse_authorization_query,
)

pytestmark = pytest.mark.realdb
_OIDC_TRANSACTION_COOKIE = "admin_oidc_txn"


def _seed_admin_email(admin_id: str, email: str) -> None:
    """给测试种子管理员写入首绑邮箱。"""

    with SessionLocal.begin() as session:
        admin_record = session.get(AdminUserModel, admin_id)
        assert admin_record is not None
        admin_record.email = email


def _install_oidc_gateway(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
) -> tuple[Any, Any]:
    """只替换身份中心传输，应用路由与 OIDC 账号解析保持真实。"""

    gateway, http_client = issuer.build_gateway()
    api_client.app.dependency_overrides[get_admin_oidc_gateway] = lambda: gateway
    return gateway, http_client


def _start_login(api_client: TestClient) -> dict[str, str]:
    """调用真实 start API 并解析其 302 参数。"""

    start_response = api_client.get("/admin/auth/oidc/start", follow_redirects=False)
    assert start_response.status_code == 302
    return parse_authorization_query(start_response.headers["location"])


def _application_log_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """筛选应用自身日志，排除 TestClient 对请求 URL 的访问日志。"""
    return [
        record.getMessage()
        for record in caplog.records
        if record.name == config.app_name or record.name.startswith("backend.")
    ]


def _set_claims_for_start(
    issuer: ControlledOidcIssuer,
    start_query: dict[str, str],
    **claim_overrides: Any,
) -> None:
    """使用 start 响应中的 nonce 签发本次 callback token。"""

    token_claims = issuer.standard_claims(nonce=start_query["nonce"])
    token_claims.update(claim_overrides)
    issuer.token_claims = token_claims


def test_oidc_status_is_disabled_without_configuration_and_password_login_works(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配 OIDC 时不显示入口，密码登录保持可用。"""

    monkeypatch.setattr(config.admin_oidc, "enabled", True)
    monkeypatch.setattr(config.admin_oidc, "issuer", "")
    monkeypatch.setattr(config.admin_oidc, "client_id", "")
    monkeypatch.setattr(config.admin_oidc, "callback_uri", "")
    username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(username, "adminpass1")
    api_client = build_client()

    status_response = api_client.get("/admin/auth/oidc/status")
    start_response = api_client.get("/admin/auth/oidc/start", follow_redirects=False)
    password_response = api_client.post(
        "/admin/auth/login",
        json={"identifier": username, "password": "adminpass1"},
    )

    assert status_response.status_code == 200
    assert status_response.json() == {"enabled": False}
    assert start_response.status_code == 503
    assert password_response.status_code == 200


def test_explicit_oidc_disable_keeps_password_login_available(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置齐全但显式关闭 OIDC 时只隐藏企业入口，不影响密码登录。"""
    monkeypatch.setattr(config.admin_oidc, "enabled", False)
    monkeypatch.setattr(config.admin_oidc, "issuer", TEST_OIDC_ISSUER)
    monkeypatch.setattr(config.admin_oidc, "client_id", "configured-client")
    monkeypatch.setattr(config.admin_oidc, "client_secret", SecretStr("configured-secret"))
    monkeypatch.setattr(config.admin_oidc, "callback_uri", TEST_OIDC_CALLBACK_URI)
    username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(username, "adminpass1")
    api_client = build_client()

    assert api_client.get("/admin/auth/oidc/status").json() == {"enabled": False}
    assert api_client.get("/admin/auth/oidc/start", follow_redirects=False).status_code == 503
    assert (
        api_client.post(
            "/admin/auth/login",
            json={"identifier": username, "password": "adminpass1"},
        ).status_code
        == 200
    )


def test_start_sets_one_time_transaction_cookie_and_pkce_parameters(
    build_client: Callable[[], TestClient],
) -> None:
    """start 经过真实路由写入短时 HttpOnly cookie 并设置 S256。"""

    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    try:
        start_query = _start_login(api_client)
        raw_cookie = api_client.get("/admin/auth/oidc/start", follow_redirects=False).headers[
            "set-cookie"
        ]
    finally:
        gateway.close()
        http_client.close()

    assert start_query["endpoint"] == (f"{TEST_OIDC_ISSUER}/protocol/openid-connect/auth")
    assert start_query["response_type"] == "code"
    assert start_query["code_challenge_method"] == "S256"
    assert start_query["code_challenge"] and len(start_query["code_challenge"]) == 43
    assert start_query["state"] and start_query["nonce"]
    assert api_client.cookies.get(_OIDC_TRANSACTION_COOKIE)
    assert "HttpOnly" in raw_cookie
    assert "samesite=lax" in raw_cookie.lower()
    assert "max-age=600" in raw_cookie.lower()


def test_verified_email_first_binding_creates_admin_session_and_redacts_secrets(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """唯一已验证邮箱命中已有管理员后完成原子首绑并签发 admin 会话。"""

    username = f"admin-{uuid.uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    _seed_admin_email(admin_id, "ops@example.test")
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    caplog.set_level("INFO")
    try:
        start_query = _start_login(api_client)
        _set_claims_for_start(issuer, start_query, email="OPS@example.test")
        callback_response = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "test-authorization-code", "state": start_query["state"]},
            follow_redirects=False,
        )
        me_response = api_client.get("/admin/auth/me")
        with SessionLocal() as session:
            bound_admin = session.get(AdminUserModel, admin_id)
            assert bound_admin is not None
            bound_identity = (bound_admin.oidc_issuer, bound_admin.oidc_subject)
    finally:
        gateway.close()
        http_client.close()

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "/"
    assert api_client.cookies.get("admin_session_id")
    assert not api_client.cookies.get(_OIDC_TRANSACTION_COOKIE)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == username
    assert bound_identity == (TEST_OIDC_ISSUER, "test-subject-1")
    application_logs = _application_log_messages(caplog)
    assert not any(
        TEST_OIDC_CLIENT_SECRET in message or "test-authorization-code" in message
        for message in application_logs
    )


def test_bound_identity_remains_authoritative_after_email_changes(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """绑定后只按 issuer + subject 登录，不依赖身份中心邮箱保持不变。"""

    username = f"admin-{uuid.uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    _seed_admin_email(admin_id, "ops@example.test")
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    try:
        first_start = _start_login(api_client)
        _set_claims_for_start(issuer, first_start, email="ops@example.test")
        first_callback = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "first-code", "state": first_start["state"]},
            follow_redirects=False,
        )
        assert first_callback.status_code == 302
        api_client.post("/admin/auth/logout")

        second_start = _start_login(api_client)
        _set_claims_for_start(
            issuer,
            second_start,
            email="renamed@example.test",
            email_verified=False,
        )
        second_callback = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "second-code", "state": second_start["state"]},
            follow_redirects=False,
        )
    finally:
        gateway.close()
        http_client.close()

    assert second_callback.status_code == 302
    assert second_callback.headers["location"] == "/"
    assert api_client.get("/admin/auth/me").json()["username"] == username


@pytest.mark.parametrize("second_subject", ["userA", "UserA "])
def test_oidc_subject_comparison_preserves_case_and_trailing_characters(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    second_subject: str,
) -> None:
    """MySQL 等大小写不敏感数据库也不得混淆不同 subject。"""
    username = f"admin-{uuid.uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    _seed_admin_email(admin_id, "ops@example.test")
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    try:
        first_start = _start_login(api_client)
        _set_claims_for_start(issuer, first_start, email="ops@example.test", sub="UserA")
        first_callback = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "first-subject-code", "state": first_start["state"]},
            follow_redirects=False,
        )
        assert first_callback.headers["location"] == "/"
        api_client.post("/admin/auth/logout")

        second_start = _start_login(api_client)
        _set_claims_for_start(
            issuer,
            second_start,
            email="ops@example.test",
            sub=second_subject,
        )
        second_callback = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "second-subject-code", "state": second_start["state"]},
            follow_redirects=False,
        )
        with SessionLocal() as session:
            bound_admin = session.get(AdminUserModel, admin_id)
            assert bound_admin is not None
            stored_subject = bound_admin.oidc_subject
    finally:
        gateway.close()
        http_client.close()

    assert second_callback.status_code == 302
    assert second_callback.headers["location"] == "/sign-in?sso_error=1"
    assert not api_client.cookies.get("admin_session_id")
    assert stored_subject == "UserA"


@pytest.mark.parametrize(
    ("claim_overrides", "expected_reason"),
    [
        ({"email_verified": False}, "email_unverified"),
        ({"email": "unknown@example.test"}, "identity_not_mapped"),
        ({"iss": "https://evil.test/realm"}, "token_validation"),
        ({"aud": "other-client"}, "token_validation"),
        ({"exp": 1}, "token_validation"),
        ({"nonce": "different-nonce"}, "token_validation"),
    ],
)
def test_callback_rejects_untrusted_identity_and_invalid_claims(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    claim_overrides: dict[str, Any],
    expected_reason: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """身份邮箱或 OIDC 标准 claims 不满足时不建会话、不修改账号。"""

    username = f"admin-{uuid.uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    _seed_admin_email(admin_id, "ops@example.test")
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    caplog.set_level("INFO")
    try:
        start_query = _start_login(api_client)
        _set_claims_for_start(issuer, start_query, **claim_overrides)
        callback_response = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "rejected-code", "state": start_query["state"]},
            follow_redirects=False,
        )
        with SessionLocal() as session:
            admin_record = session.get(AdminUserModel, admin_id)
            assert admin_record is not None
            stored_identity = (admin_record.oidc_issuer, admin_record.oidc_subject)
    finally:
        gateway.close()
        http_client.close()

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "/sign-in?sso_error=1"
    assert not api_client.cookies.get("admin_session_id")
    assert stored_identity == (None, None)
    application_logs = _application_log_messages(caplog)
    assert any(f"reason={expected_reason}" in message for message in application_logs)
    assert not any("rejected-code" in message for message in application_logs)
    assert not any(TEST_OIDC_CLIENT_SECRET in message for message in application_logs)


def test_callback_rejects_replayed_state_and_missing_transaction_cookie(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """事务 Cookie 缺失、state 不匹配与回调重放均无法签发会话。"""

    username = f"admin-{uuid.uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    _seed_admin_email(admin_id, "ops@example.test")
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    try:
        no_cookie_start = _start_login(api_client)
        api_client.cookies.delete(_OIDC_TRANSACTION_COOKIE)
        no_cookie_response = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "no-cookie-code", "state": no_cookie_start["state"]},
            follow_redirects=False,
        )
        assert no_cookie_response.headers["location"] == "/sign-in?sso_error=1"

        _start_login(api_client)
        mismatch_response = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "mismatch-code", "state": "wrong-state"},
            follow_redirects=False,
        )
        assert mismatch_response.headers["location"] == "/sign-in?sso_error=1"

        replay_start = _start_login(api_client)
        _set_claims_for_start(issuer, replay_start, email="ops@example.test")
        callback_url = "/admin/auth/oidc/callback"
        callback_params = {"code": "replay-code", "state": replay_start["state"]}
        first_callback = api_client.get(
            callback_url,
            params=callback_params,
            follow_redirects=False,
        )
        api_client.post("/admin/auth/logout")
        replay_response = api_client.get(
            callback_url,
            params=callback_params,
            follow_redirects=False,
        )
    finally:
        gateway.close()
        http_client.close()

    assert first_callback.headers["location"] == "/"
    assert replay_response.headers["location"] == "/sign-in?sso_error=1"
    assert not api_client.cookies.get("admin_session_id")


def test_callback_rejects_untrusted_signature(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """JWKS 未信任的 RSA 私钥签名不能完成管理员首绑。"""

    username = f"admin-{uuid.uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    _seed_admin_email(admin_id, "ops@example.test")
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = _install_oidc_gateway(api_client, issuer)
    try:
        start_query = _start_login(api_client)
        forged_claims = issuer.standard_claims(
            nonce=start_query["nonce"],
            email="ops@example.test",
        )
        attacker_key: RSAKey = RSAKey.generate_key()
        attacker_jwk: dict[str, Any] = attacker_key.as_dict(private=True)
        attacker_jwk["kid"] = "controlled-issuer-key"
        attacker_key = RSAKey.import_key(attacker_jwk)
        issuer.token_override = issuer.mint_id_token(forged_claims, signing_key=attacker_key)
        callback_response = api_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "forged-code", "state": start_query["state"]},
            follow_redirects=False,
        )
        with SessionLocal() as session:
            admin_record = session.get(AdminUserModel, admin_id)
            assert admin_record is not None
            stored_identity = (admin_record.oidc_issuer, admin_record.oidc_subject)
    finally:
        gateway.close()
        http_client.close()

    assert callback_response.headers["location"] == "/sign-in?sso_error=1"
    assert not api_client.cookies.get("admin_session_id")
    assert stored_identity == (None, None)
