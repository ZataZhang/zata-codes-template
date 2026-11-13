"""Public OIDC 路由的真实数据库与身份中心协议集成测试。"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient

from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from tests.backend.oidc_test_support import (
    TEST_OIDC_CLIENT_SECRET,
    TEST_OIDC_ISSUER,
    ControlledOidcIssuer,
)
from tests.backend.public_oidc_api_helpers import (
    close_public_oidc_issuer,
    configure_public_oidc,
    finish_public_oidc_login,
    install_public_oidc_issuer,
    start_public_oidc_login,
)
from tests.realdb_test_support import TrackedEntityRegistry

pytestmark = pytest.mark.realdb
_PUBLIC_OIDC_TRANSACTION_COOKIE = "public_oidc_txn"


def test_verified_oidc_identity_creates_user_and_public_session(
    build_client: Callable[[], TestClient],
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: TrackedEntityRegistry,
) -> None:
    """真实 callback 按验证邮箱建号并建立可由 /auth/me 解析的会话。"""
    configure_public_oidc(monkeypatch)
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = install_public_oidc_issuer(api_client, issuer)
    email = f"oidc-new-{uuid.uuid4().hex[:12]}@example.test"
    try:
        assert api_client.get("/auth/oidc/status").json() == {"enabled": True}
        authorization_query = start_public_oidc_login(api_client)
        callback_response = finish_public_oidc_login(
            api_client,
            issuer,
            authorization_query,
            email=email,
        )
        me_response = api_client.get("/auth/me")
        with SessionLocal() as session:
            public_user = (
                session.query(PublicUserModel).filter(PublicUserModel.email == email).one()
            )
            stored_user = (
                public_user.id,
                public_user.oidc_issuer,
                public_user.oidc_subject,
                public_user.organization_id,
                public_user.password_hash,
            )
        entity_registry.public_user_ids.append(stored_user[0])
    finally:
        close_public_oidc_issuer(api_client, gateway, http_client)

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "/app/dashboard"
    assert api_client.cookies.get("session_id")
    assert not api_client.cookies.get(_PUBLIC_OIDC_TRANSACTION_COOKIE)
    assert me_response.status_code == 200
    assert me_response.json()["email"] == email
    assert stored_user[:4] == (
        me_response.json()["user_id"],
        TEST_OIDC_ISSUER,
        "public-subject-1",
        "default",
    )
    assert stored_user[4] and stored_user[4] != TEST_OIDC_CLIENT_SECRET


def test_bound_identity_logs_in_after_email_changes_and_verification_expires(
    build_client: Callable[[], TestClient],
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: TrackedEntityRegistry,
) -> None:
    """已绑定账户按 issuer + subject 登录，不再依赖当前邮箱 claim。"""
    configure_public_oidc(monkeypatch)
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = install_public_oidc_issuer(api_client, issuer)
    email = f"oidc-bound-{uuid.uuid4().hex[:12]}@example.test"
    try:
        first_query = start_public_oidc_login(api_client)
        first_callback = finish_public_oidc_login(api_client, issuer, first_query, email=email)
        assert first_callback.headers["location"] == "/app/dashboard"
        first_user_id = api_client.get("/auth/me").json()["user_id"]
        api_client.post("/auth/logout")

        second_query = start_public_oidc_login(api_client)
        second_callback = finish_public_oidc_login(
            api_client,
            issuer,
            second_query,
            email=f"renamed-{uuid.uuid4().hex[:8]}@example.test",
            email_verified=False,
        )
        me_response = api_client.get("/auth/me")
        with SessionLocal() as session:
            identity_match_count = (
                session.query(PublicUserModel)
                .filter(
                    PublicUserModel.oidc_issuer == TEST_OIDC_ISSUER,
                    PublicUserModel.oidc_subject == "public-subject-1",
                )
                .count()
            )
        entity_registry.public_user_ids.append(first_user_id)
    finally:
        close_public_oidc_issuer(api_client, gateway, http_client)

    assert second_callback.status_code == 302
    assert second_callback.headers["location"] == "/app/dashboard"
    assert me_response.status_code == 200
    assert me_response.json()["user_id"] == first_user_id
    assert me_response.json()["email"] == email
    assert identity_match_count == 1


def test_same_email_password_account_is_not_linked_or_modified(
    build_client: Callable[[], TestClient],
    monkeypatch: pytest.MonkeyPatch,
    unique_email: Callable[[], str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """拒绝将已注册密码账户关联到同邮箱 IdP 身份，并保留原凭据。"""
    configure_public_oidc(monkeypatch)
    api_client = build_client()
    email = unique_email()
    password_register = api_client.post(
        "/auth/register",
        json={"display_name": "Password User", "email": email, "password": "password123"},
    )
    assert password_register.status_code == 201
    user_id = password_register.json()["user_id"]
    api_client.post("/auth/logout")
    with SessionLocal() as session:
        original_password_hash = session.get(PublicUserModel, user_id).password_hash

    issuer = ControlledOidcIssuer()
    gateway, http_client = install_public_oidc_issuer(api_client, issuer)
    caplog.set_level("INFO")
    try:
        authorization_query = start_public_oidc_login(api_client)
        callback_response = finish_public_oidc_login(
            api_client,
            issuer,
            authorization_query,
            email=email,
        )
        with SessionLocal() as session:
            unchanged_user = session.get(PublicUserModel, user_id)
            assert unchanged_user is not None
            stored_identity = (unchanged_user.oidc_issuer, unchanged_user.oidc_subject)
            stored_password_hash = unchanged_user.password_hash
    finally:
        close_public_oidc_issuer(api_client, gateway, http_client)

    assert callback_response.status_code == 302
    assert callback_response.headers["location"] == "/login?sso_error=account_exists"
    assert not api_client.cookies.get("session_id")
    assert stored_identity == (None, None)
    assert stored_password_hash == original_password_hash
    assert any(
        "reason=user_account_conflict" in record.getMessage()
        for record in caplog.records
        if record.name.startswith("backend.")
    )

    password_login = api_client.post(
        "/auth/login",
        json={"identifier": email, "password": "password123"},
    )
    assert password_login.status_code == 200
    assert api_client.get("/auth/me").json()["user_id"] == user_id


def test_disabled_bound_user_loses_session_and_cannot_log_in_with_oidc(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: TrackedEntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """平台停用已绑定普通用户后使现有会话和后续 OIDC 登录失效。"""
    configure_public_oidc(monkeypatch)
    api_client = build_client()
    issuer = ControlledOidcIssuer()
    gateway, http_client = install_public_oidc_issuer(api_client, issuer)
    email = f"oidc-disabled-{uuid.uuid4().hex[:12]}@example.test"
    caplog.set_level("INFO")
    try:
        first_query = start_public_oidc_login(api_client)
        first_callback = finish_public_oidc_login(
            api_client,
            issuer,
            first_query,
            email=email,
        )
        assert first_callback.headers["location"] == "/app/dashboard"
        account_session = api_client.get("/auth/me")
        user_id = account_session.json()["user_id"]
        entity_registry.public_user_ids.append(user_id)

        admin_username = f"user-admin-{uuid.uuid4().hex[:10]}"
        seed_admin(admin_username, "adminpass1")
        admin_login = api_client.post(
            "/admin/auth/login",
            json={"identifier": admin_username, "password": "adminpass1"},
        )
        assert admin_login.status_code == 200
        disable_response = api_client.post(f"/admin/users/{user_id}/disable")
        assert disable_response.status_code == 200
        assert api_client.get("/auth/me").status_code == 401

        api_client.cookies.delete("session_id")
        retry_query = start_public_oidc_login(api_client)
        retry_callback = finish_public_oidc_login(
            api_client,
            issuer,
            retry_query,
            email=email,
        )
        with SessionLocal() as session:
            disabled_account = session.get(PublicUserModel, user_id)
            assert disabled_account is not None
            stored_identity = (disabled_account.oidc_issuer, disabled_account.oidc_subject)
            stored_is_active = disabled_account.is_active
    finally:
        close_public_oidc_issuer(api_client, gateway, http_client)

    assert retry_callback.status_code == 302
    assert retry_callback.headers["location"] == "/login?sso_error=1"
    assert not api_client.cookies.get("session_id")
    assert stored_identity == (TEST_OIDC_ISSUER, "public-subject-1")
    assert stored_is_active is False
    assert any(
        "reason=user_inactive" in record.getMessage()
        for record in caplog.records
        if record.name.startswith("backend.")
    )
