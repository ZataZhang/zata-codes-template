"""注册策略真实 HTTP、身份流程与持久化失败测试。"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.database import SessionLocal, engine
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from backend.infrastructure.persistence.models.system_setting import SystemSettingModel
from tests.backend.oidc_test_support import ControlledOidcIssuer
from tests.backend.public_oidc_api_helpers import (
    close_public_oidc_issuer,
    configure_public_oidc,
    finish_public_oidc_login,
    install_public_oidc_issuer,
    start_public_oidc_login,
)
from tests.realdb_test_support import TrackedEntityRegistry

pytestmark = pytest.mark.realdb
_REGISTRATION_POLICY_KEY = "registration_policy"
_HIDDEN_SETTING_TABLE = "system_settings_prd_unavailable"


@pytest.fixture
def preserve_registration_policy() -> Iterator[None]:
    """保存并恢复隔离数据库已有注册策略，避免测试间共享状态。"""
    with SessionLocal() as session:
        existing_setting = session.get(SystemSettingModel, _REGISTRATION_POLICY_KEY)
        original_value: str | None = existing_setting.value if existing_setting else None

    yield

    with SessionLocal.begin() as session:
        current_setting = session.get(SystemSettingModel, _REGISTRATION_POLICY_KEY)
        if original_value is None:
            if current_setting is not None:
                session.delete(current_setting)
        elif current_setting is None:
            session.add(
                SystemSettingModel(
                    key=_REGISTRATION_POLICY_KEY,
                    value=original_value,
                )
            )
        else:
            current_setting.value = original_value


def _disable_public_oidc(monkeypatch: pytest.MonkeyPatch) -> None:
    """显式关闭 OIDC，确保密码渠道测试不依赖开发机配置。"""
    monkeypatch.setattr(config.user_oidc, "enabled", False)


def _disable_rate_limit_for_policy_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """隔离策略组合矩阵与 API 限流计数，测试只比较注册策略决策。"""
    monkeypatch.setattr(config.security, "rate_limit_enabled", False)


def _sign_in_platform_admin(
    api_client: TestClient,
    seed_admin: Callable[[str, str], str],
) -> str:
    """通过真实密码 API 创建并登录平台管理员。"""
    username = f"policy-admin-{uuid.uuid4().hex[:10]}"
    admin_id = seed_admin(username, "adminpass1")
    login_response = api_client.post(
        "/admin/auth/login",
        json={"identifier": username, "password": "adminpass1"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["role"] == "platform"
    return admin_id


def _save_policy(
    api_client: TestClient,
    registration_mode: str,
    allowed_email_domains: list[str],
) -> dict[str, object]:
    """经平台管理员 HTTP API 保存注册策略。"""
    update_response = api_client.put(
        "/admin/settings/registration-policy",
        json={
            "registration_mode": registration_mode,
            "allowed_email_domains": allowed_email_domains,
        },
    )
    assert update_response.status_code == 200
    return update_response.json()


def _rename_registration_policy_table(*, unavailable: bool) -> None:
    """在隔离数据库中短暂模拟真实系统设置表不可读。"""
    source_table = "system_settings" if unavailable else _HIDDEN_SETTING_TABLE
    target_table = _HIDDEN_SETTING_TABLE if unavailable else "system_settings"
    with engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {source_table} RENAME TO {target_table}"))


def test_registration_policy_admin_auth_and_public_status_contract(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
    preserve_registration_policy: None,
) -> None:
    """策略写入需平台会话，公开状态只暴露模式而不返回白名单。"""
    _disable_public_oidc(monkeypatch)
    _disable_rate_limit_for_policy_tests(monkeypatch)
    api_client = build_client()
    assert api_client.get("/admin/settings/registration-policy").status_code == 401
    assert (
        api_client.put(
            "/admin/settings/registration-policy",
            json={"registration_mode": "both", "allowed_email_domains": []},
        ).status_code
        == 401
    )

    _sign_in_platform_admin(api_client, seed_admin)
    saved_policy = _save_policy(api_client, "oidc_only", ["private.example.test"])
    public_status = api_client.get("/auth/registration-status")

    assert public_status.status_code == 200
    assert public_status.json() == {"registration_mode": "oidc_only"}
    assert "allowed_email_domains" not in public_status.json()
    assert saved_policy == {
        "registration_mode": "oidc_only",
        "allowed_email_domains": ["private.example.test"],
    }


def test_missing_registration_policy_record_uses_real_http_default(
    build_client: Callable[[], TestClient],
    monkeypatch: pytest.MonkeyPatch,
    unique_email: Callable[[], str],
    entity_registry: TrackedEntityRegistry,
    preserve_registration_policy: None,
) -> None:
    """缺少设置键时公开状态与密码注册按 both、无限域名兼容默认运行。"""
    _disable_public_oidc(monkeypatch)
    _disable_rate_limit_for_policy_tests(monkeypatch)
    with SessionLocal.begin() as session:
        setting_record = session.get(SystemSettingModel, _REGISTRATION_POLICY_KEY)
        if setting_record is not None:
            session.delete(setting_record)
    api_client = build_client()

    public_status = api_client.get("/auth/registration-status")
    email = unique_email().replace("@example.com", "@anywhere.example.test")
    registration_response = api_client.post(
        "/auth/register",
        json={"display_name": "Open Registration", "email": email, "password": "password123"},
    )
    with SessionLocal() as session:
        persisted_user = session.query(PublicUserModel).filter_by(email=email).one_or_none()
        persisted_user_id = persisted_user.id if persisted_user else None
    if persisted_user_id:
        entity_registry.public_user_ids.append(persisted_user_id)

    assert public_status.status_code == 200
    assert public_status.json() == {"registration_mode": "both"}
    assert registration_response.status_code == 201
    assert persisted_user_id == registration_response.json()["user_id"]


@pytest.mark.parametrize(
    ("registration_mode", "channel", "domain_allowed", "expected_allowed", "expected_error"),
    [
        ("both", "password", True, True, None),
        ("both", "password", False, False, "email_domain_not_allowed"),
        ("both", "oidc", True, True, None),
        ("both", "oidc", False, False, "registration_not_allowed"),
        ("oidc_only", "password", True, False, "registration_not_allowed"),
        ("oidc_only", "password", False, False, "registration_not_allowed"),
        ("oidc_only", "oidc", True, True, None),
        ("oidc_only", "oidc", False, False, "registration_not_allowed"),
        ("closed", "password", True, False, "registration_not_allowed"),
        ("closed", "password", False, False, "registration_not_allowed"),
        ("closed", "oidc", True, False, "registration_not_allowed"),
        ("closed", "oidc", False, False, "registration_not_allowed"),
    ],
)
def test_registration_policy_http_matrix_controls_both_channels(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: TrackedEntityRegistry,
    preserve_registration_policy: None,
    registration_mode: str,
    channel: str,
    domain_allowed: bool,
    expected_allowed: bool,
    expected_error: str | None,
) -> None:
    """管理 API 写入的模式与域名白名单即时控制真实密码及 OIDC 请求。"""
    if channel == "oidc":
        configure_public_oidc(monkeypatch)
    else:
        _disable_public_oidc(monkeypatch)
    _disable_rate_limit_for_policy_tests(monkeypatch)
    api_client = build_client()
    _sign_in_platform_admin(api_client, seed_admin)
    _save_policy(api_client, registration_mode, ["example.test"])
    email_domain = "example.test" if domain_allowed else "outside.test"
    target_email = f"policy-{uuid.uuid4().hex[:12]}@{email_domain}"

    public_status = api_client.get("/auth/registration-status")
    assert public_status.status_code == 200
    assert set(public_status.json()) == {"registration_mode"}
    assert public_status.json()["registration_mode"] == registration_mode

    if channel == "password":
        registration_response = api_client.post(
            "/auth/register",
            json={
                "display_name": "Policy Matrix User",
                "email": target_email,
                "password": "password123",
            },
        )
        if expected_allowed:
            assert registration_response.status_code == 201
            assert api_client.get("/auth/me").status_code == 200
            api_client.post("/auth/logout")
        else:
            assert registration_response.status_code == 400
            assert registration_response.json()["detail"] == expected_error
            assert not api_client.cookies.get("session_id")
        return

    issuer = ControlledOidcIssuer()
    gateway, http_client = install_public_oidc_issuer(api_client, issuer)
    try:
        authorization_query = start_public_oidc_login(api_client)
        callback_response = finish_public_oidc_login(
            api_client,
            issuer,
            authorization_query,
            email=target_email,
        )
        if expected_allowed:
            assert callback_response.status_code == 302
            assert callback_response.headers["location"] == "/app/dashboard"
            session_response = api_client.get("/auth/me")
            assert session_response.status_code == 200
            assert session_response.json()["email"] == target_email
            entity_registry.public_user_ids.append(session_response.json()["user_id"])
            api_client.post("/auth/logout")
        else:
            assert callback_response.status_code == 302
            assert callback_response.headers["location"] == "/login?sso_error=1"
            assert not api_client.cookies.get("session_id")
            with SessionLocal() as session:
                created_user_count = (
                    session.query(PublicUserModel).filter_by(email=target_email).count()
                )
            assert created_user_count == 0
    finally:
        close_public_oidc_issuer(api_client, gateway, http_client)


def test_invalid_domain_request_returns_stable_422_detail(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
    preserve_registration_policy: None,
) -> None:
    """非法白名单域名经真实管理 API 返回稳定 code 与原始条目列表。"""
    _disable_public_oidc(monkeypatch)
    _disable_rate_limit_for_policy_tests(monkeypatch)
    api_client = build_client()
    _sign_in_platform_admin(api_client, seed_admin)

    response = api_client.put(
        "/admin/settings/registration-policy",
        json={
            "registration_mode": "both",
            "allowed_email_domains": ["example.test", "bad_domain.test"],
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "code": "invalid_email_domains",
        "invalid_domains": ["bad_domain.test"],
    }


@pytest.mark.parametrize("failure_mode", ["invalid_json", "storage_error"])
def test_registration_policy_failures_block_password_and_oidc_creation(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    failure_mode: str,
    preserve_registration_policy: None,
) -> None:
    """真实 SQL 读取异常或损坏 JSON 时密码注册与 OIDC 建号均 fail closed。"""
    configure_public_oidc(monkeypatch)
    _disable_rate_limit_for_policy_tests(monkeypatch)
    api_client = build_client()
    _sign_in_platform_admin(api_client, seed_admin)
    _save_policy(api_client, "closed", ["example.test"])
    password_email = f"policy-failure-password-{uuid.uuid4().hex[:10]}@example.test"
    oidc_email = f"policy-failure-oidc-{uuid.uuid4().hex[:10]}@example.test"
    if failure_mode == "invalid_json":
        with SessionLocal.begin() as session:
            setting_record = session.get(SystemSettingModel, _REGISTRATION_POLICY_KEY)
            assert setting_record is not None
            setting_record.value = "{"
    else:
        with engine.connect() as connection:
            assert not engine.dialect.has_table(connection, _HIDDEN_SETTING_TABLE)
        _rename_registration_policy_table(unavailable=True)

    issuer = ControlledOidcIssuer()
    gateway, http_client = install_public_oidc_issuer(api_client, issuer)
    try:
        status_response = api_client.get("/auth/registration-status")
        password_response = api_client.post(
            "/auth/register",
            json={
                "display_name": "Policy Failure Password",
                "email": password_email,
                "password": "password123",
            },
        )
        authorization_query = start_public_oidc_login(api_client)
        oidc_callback_response = finish_public_oidc_login(
            api_client,
            issuer,
            authorization_query,
            email=oidc_email,
        )

        with SessionLocal() as session:
            password_user_count = (
                session.query(PublicUserModel).filter_by(email=password_email).count()
            )
            oidc_user_count = session.query(PublicUserModel).filter_by(email=oidc_email).count()
    finally:
        close_public_oidc_issuer(api_client, gateway, http_client)
        if failure_mode == "storage_error":
            _rename_registration_policy_table(unavailable=False)

    assert status_response.status_code == 503
    assert status_response.json()["detail"] == "registration_policy_unavailable"
    assert password_response.status_code == 503
    assert password_response.json()["detail"] == "registration_policy_unavailable"
    assert oidc_callback_response.status_code == 302
    assert oidc_callback_response.headers["location"] == "/login?sso_error=1"
    assert not api_client.cookies.get("session_id")
    assert password_user_count == 0
    assert oidc_user_count == 0
    assert any(
        "reason=registration_policy_unavailable" in record.getMessage()
        for record in caplog.records
        if record.name.startswith("backend.")
    )

    recovered_policy = _save_policy(api_client, "closed", ["example.test"])
    assert recovered_policy["registration_mode"] == "closed"
    assert api_client.get("/auth/registration-status").json() == {"registration_mode": "closed"}
