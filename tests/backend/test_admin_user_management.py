"""Admin 管理 public 用户 API 测试。"""

from __future__ import annotations

import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.api.dependencies import get_admin_oidc_gateway
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.service import AuthService
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.admin_user import AdminUserModel
from tests.backend.oidc_test_support import (
    TEST_OIDC_CLIENT_ID,
    TEST_OIDC_ISSUER,
    ControlledOidcIssuer,
    parse_authorization_query,
)
from tests.realdb_test_support import TrackedEntityRegistry

pytestmark = pytest.mark.realdb


def _login_admin(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> TestClient:
    """种入并登录一个管理员，返回持 admin 会话的客户端。"""
    username = f"admin-{uuid.uuid4().hex[:8]}"
    seed_admin(username, "adminpass1")
    client = build_client()
    login_response = client.post(
        "/admin/auth/login", json={"identifier": username, "password": "adminpass1"}
    )
    assert login_response.status_code == 200
    return client


def test_admin_lists_and_toggles_public_user(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
) -> None:
    """admin 可按关键字列出 public 用户并启用 / 禁用。"""
    admin_client = _login_admin(build_client, seed_admin)

    public_client = build_client()
    email = unique_email()
    register_response = public_client.post(
        "/auth/register",
        json={"display_name": "Managed", "email": email, "password": "secret123"},
    )
    user_id = register_response.json()["user_id"]

    list_response = admin_client.get("/admin/users", params={"keyword": email})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] >= 1
    assert any(item["id"] == user_id for item in list_body["items"])

    disable_response = admin_client.post(f"/admin/users/{user_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["status"] == "disabled"

    get_response = admin_client.get(f"/admin/users/{user_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "disabled"

    enable_response = admin_client.post(f"/admin/users/{user_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["status"] == "active"


def test_admin_get_unknown_user_returns_404(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> None:
    """查询不存在的 public 用户返回 404。"""
    admin_client = _login_admin(build_client, seed_admin)
    assert admin_client.get("/admin/users/does-not-exist").status_code == 404


def test_admin_user_management_requires_admin_session(
    build_client: Callable[[], TestClient],
) -> None:
    """无 admin 会话访问管理端点返回 401。"""
    client = build_client()
    assert client.get("/admin/users").status_code == 401
    assert client.post("/admin/users/whatever/disable").status_code == 401


def test_status_filter_disabled(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
) -> None:
    """status=disabled 过滤仅返回被禁用用户。"""
    admin_client = _login_admin(build_client, seed_admin)

    public_client = build_client()
    email = unique_email()
    register_response = public_client.post(
        "/auth/register",
        json={"display_name": "Filterable", "email": email, "password": "secret123"},
    )
    user_id = register_response.json()["user_id"]
    admin_client.post(f"/admin/users/{user_id}/disable")

    filtered_response = admin_client.get(
        "/admin/users", params={"keyword": email, "status": "disabled"}
    )
    assert filtered_response.status_code == 200
    items = filtered_response.json()["items"]
    assert any(item["id"] == user_id for item in items)
    assert all(item["status"] == "disabled" for item in items)


def test_disabling_org_admin_invalidates_password_and_oidc_sessions(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    entity_registry: TrackedEntityRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """平台停用组织管理员后，两类既有会话与新登录都立即失效。"""
    platform_client = _login_admin(build_client, seed_admin)
    target_username = f"org-admin-{uuid.uuid4().hex[:10]}"
    target_email = f"org-admin-{uuid.uuid4().hex[:10]}@example.test"
    create_response = platform_client.post(
        "/admin/admins",
        json={
            "username": target_username,
            "email": target_email,
            "display_name": "Organization Admin",
            "role": "org",
            "organization_id": "default",
            "password": "Org-admin-password123",
        },
    )
    assert create_response.status_code == 200
    target_admin_id = create_response.json()["id"]
    entity_registry.admin_user_ids.append(target_admin_id)

    password_client = build_client()
    password_login = password_client.post(
        "/admin/auth/login",
        json={"identifier": target_username, "password": "Org-admin-password123"},
    )
    assert password_login.status_code == 200

    oidc_client = build_client()
    issuer = ControlledOidcIssuer()
    oidc_gateway, http_client = issuer.build_gateway()
    oidc_client.app.dependency_overrides[get_admin_oidc_gateway] = lambda: oidc_gateway
    try:
        start_response = oidc_client.get("/admin/auth/oidc/start", follow_redirects=False)
        assert start_response.status_code == 302
        authorization_query = parse_authorization_query(start_response.headers["location"])
        issuer.token_claims = issuer.standard_claims(
            nonce=authorization_query["nonce"],
            email=target_email,
            audience=TEST_OIDC_CLIENT_ID,
        )
        oidc_callback = oidc_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "admin-disable-flow-code", "state": authorization_query["state"]},
            follow_redirects=False,
        )
        assert oidc_callback.status_code == 302
        assert oidc_callback.headers["location"] == "/"
        assert password_client.get("/admin/auth/me").status_code == 200
        assert oidc_client.get("/admin/auth/me").status_code == 200

        disable_response = platform_client.post(f"/admin/admins/{target_admin_id}/disable")

        assert disable_response.status_code == 200
        assert disable_response.json()["status"] == "disabled"
        assert password_client.get("/admin/auth/me").status_code == 401
        assert oidc_client.get("/admin/auth/me").status_code == 401

        retry_password_client = build_client()
        retry_password = retry_password_client.post(
            "/admin/auth/login",
            json={"identifier": target_username, "password": "Org-admin-password123"},
        )
        assert retry_password.status_code == 401

        oidc_client.cookies.delete("admin_session_id")
        retry_start_response = oidc_client.get("/admin/auth/oidc/start", follow_redirects=False)
        retry_query = parse_authorization_query(retry_start_response.headers["location"])
        issuer.token_claims = issuer.standard_claims(
            nonce=retry_query["nonce"],
            email=target_email,
            audience=TEST_OIDC_CLIENT_ID,
        )
        retry_callback = oidc_client.get(
            "/admin/auth/oidc/callback",
            params={"code": "disabled-admin-retry-code", "state": retry_query["state"]},
            follow_redirects=False,
        )
        assert retry_callback.status_code == 302
        assert retry_callback.headers["location"] == "/sign-in?sso_error=1"
        assert not oidc_client.cookies.get("admin_session_id")
        assert any(
            "reason=admin_inactive" in record.getMessage()
            for record in caplog.records
            if record.name.startswith("backend.")
        )
        with SessionLocal() as session:
            disabled_admin = session.get(AdminUserModel, target_admin_id)
            assert disabled_admin is not None
            assert disabled_admin.is_active is False
            assert disabled_admin.oidc_issuer == TEST_OIDC_ISSUER
            assert disabled_admin.oidc_subject == "test-subject-1"
    finally:
        oidc_gateway.close()
        http_client.close()


def test_admin_api_rejects_disabling_the_last_enabled_platform_admin(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实平台账号并发互禁时事务只允许保留一名启用管理员。"""
    first_admin_username = f"platform-first-{uuid.uuid4().hex[:10]}"
    second_admin_username = f"platform-second-{uuid.uuid4().hex[:10]}"
    first_admin_id = seed_admin(first_admin_username, "adminpass1")
    second_admin_id = seed_admin(second_admin_username, "adminpass1")
    first_admin_client = build_client()
    second_admin_client = build_client()

    first_login_response = first_admin_client.post(
        "/admin/auth/login",
        json={"identifier": first_admin_username, "password": "adminpass1"},
    )
    second_login_response = second_admin_client.post(
        "/admin/auth/login",
        json={"identifier": second_admin_username, "password": "adminpass1"},
    )
    assert first_login_response.status_code == 200
    assert second_login_response.status_code == 200

    authenticated_admin_barrier = Barrier(2)
    resolved_admin_ids: set[str] = set()
    resolved_admin_ids_lock = Lock()
    original_resolve_session = AuthService.resolve_session

    def resolve_after_both_admins_authenticate(
        auth_service: AuthService, session_token: str
    ) -> AuthenticatedPrincipal | None:
        principal = original_resolve_session(auth_service, session_token)
        if principal is not None:
            with resolved_admin_ids_lock:
                resolved_admin_ids.add(principal.user_id)
            authenticated_admin_barrier.wait(timeout=15)
        return principal

    monkeypatch.setattr(AuthService, "resolve_session", resolve_after_both_admins_authenticate)

    with ThreadPoolExecutor(max_workers=2) as request_executor:
        first_disable_future = request_executor.submit(
            first_admin_client.post, f"/admin/admins/{second_admin_id}/disable"
        )
        second_disable_future = request_executor.submit(
            second_admin_client.post, f"/admin/admins/{first_admin_id}/disable"
        )
        first_disable_response = first_disable_future.result(timeout=20)
        second_disable_response = second_disable_future.result(timeout=20)

    assert resolved_admin_ids == {first_admin_id, second_admin_id}
    assert sorted((first_disable_response.status_code, second_disable_response.status_code)) == [
        200,
        400,
    ]
    rejected_disable_response = next(
        response
        for response in (first_disable_response, second_disable_response)
        if response.status_code == 400
    )
    assert rejected_disable_response.json()["detail"] == "last_platform_admin"

    with SessionLocal() as session:
        active_platform_admins = session.scalars(
            select(AdminUserModel).where(
                AdminUserModel.role == "platform",
                AdminUserModel.is_active.is_(True),
            )
        ).all()
        assert len(active_platform_admins) == 1
        assert active_platform_admins[0].id in {first_admin_id, second_admin_id}
