"""组织停用、两级管理员边界与组织角色约束的真实数据库测试。"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from pydantic import SecretStr
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.api.dependencies import get_admin_oidc_gateway, get_public_oidc_gateway
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.admin_user import AdminUserModel
from backend.infrastructure.persistence.models.organization import OrganizationModel
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from tests.backend.oidc_test_support import (
    TEST_OIDC_CLIENT_ID,
    TEST_PUBLIC_OIDC_CALLBACK_URI,
    TEST_PUBLIC_OIDC_CLIENT_ID,
    ControlledOidcIssuer,
    parse_authorization_query,
)
from tests.backend.public_oidc_api_helpers import (
    finish_public_oidc_login,
    start_public_oidc_login,
)
from tests.realdb_test_support import TrackedEntityRegistry

pytestmark = pytest.mark.realdb


@pytest.fixture(autouse=True)
def _isolate_auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """避免本机认证设置或限流状态影响真实 API 验收。"""
    monkeypatch.setattr(config.auth, "cookie_secure", False)
    monkeypatch.setattr(config.auth, "admin_bootstrap_username", "")
    monkeypatch.setattr(config.auth, "admin_bootstrap_password", SecretStr(""))
    monkeypatch.setattr(config.auth, "admin_bootstrap_email", "")
    monkeypatch.setattr(config.security, "rate_limit_enabled", False)
    monkeypatch.setattr(config.admin_oidc, "enabled", False)
    monkeypatch.setattr(config.admin_oidc, "issuer", "")
    monkeypatch.setattr(config.admin_oidc, "client_id", "")
    monkeypatch.setattr(config.admin_oidc, "client_secret", SecretStr(""))
    monkeypatch.setattr(config.admin_oidc, "callback_uri", "")
    monkeypatch.setattr(config.user_oidc, "enabled", False)
    monkeypatch.setattr(config.user_oidc, "issuer", "")
    monkeypatch.setattr(config.user_oidc, "client_id", "")
    monkeypatch.setattr(config.user_oidc, "client_secret", SecretStr(""))
    monkeypatch.setattr(config.user_oidc, "callback_uri", "")


@pytest.fixture
def created_organization_ids(
    entity_registry: TrackedEntityRegistry,
) -> Iterator[list[str]]:
    """在账号清理后删除本测试经 API 创建的组织。"""
    organization_ids: list[str] = []
    yield organization_ids
    entity_registry.delete_tracked_entities()
    if organization_ids:
        with SessionLocal.begin() as database_session:
            database_session.execute(
                delete(OrganizationModel).where(OrganizationModel.id.in_(organization_ids))
            )


@pytest.fixture
def oidc_transports() -> Iterator[list[tuple[object, object]]]:
    """在测试结束时关闭由 ControlledOidcIssuer 创建的 HTTP 客户端。"""
    owned_transports: list[tuple[object, object]] = []
    yield owned_transports
    for oidc_gateway, http_client in owned_transports:
        oidc_gateway.close()
        http_client.close()


def _login_platform_admin(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> TestClient:
    """种入并登录平台管理员，返回真实 admin 会话客户端。"""
    admin_username = f"platform-{uuid.uuid4().hex[:12]}"
    seed_admin(admin_username, "Platform-password123")
    admin_client = build_client()
    login_response = admin_client.post(
        "/admin/auth/login",
        json={"identifier": admin_username, "password": "Platform-password123"},
    )
    assert login_response.status_code == 200
    assert login_response.json()["role"] == "platform"
    return admin_client


def _create_organization(
    admin_client: TestClient,
    created_organization_ids: list[str],
    organization_name: str,
) -> str:
    """通过平台 API 创建组织并记录精确清理 ID。"""
    create_response = admin_client.post(
        "/admin/organizations",
        json={"name": organization_name},
    )
    assert create_response.status_code == 200
    organization_id: str = create_response.json()["id"]
    created_organization_ids.append(organization_id)
    return organization_id


def _create_organization_admin(
    admin_client: TestClient,
    entity_registry: TrackedEntityRegistry,
    organization_id: str,
    *,
    username: str,
    email: str,
    password: str,
) -> str:
    """通过平台 API 创建组织管理员并登记账号清理 ID。"""
    create_response = admin_client.post(
        "/admin/admins",
        json={
            "username": username,
            "email": email,
            "display_name": "Organization Admin",
            "role": "org",
            "organization_id": organization_id,
            "password": password,
        },
    )
    assert create_response.status_code == 200
    admin_id: str = create_response.json()["id"]
    entity_registry.admin_user_ids.append(admin_id)
    return admin_id


def _register_password_user(
    user_client: TestClient,
    email: str,
) -> str:
    """通过真实 public 注册接口创建密码用户。"""
    register_response = user_client.post(
        "/auth/register",
        json={
            "display_name": "Organization Member",
            "email": email,
            "password": "User-password123",
        },
    )
    assert register_response.status_code == 201
    return register_response.json()["user_id"]


def _move_user_to_organization(
    platform_client: TestClient,
    user_id: str,
    organization_id: str,
) -> None:
    """通过平台管理接口调整用户归属。"""
    move_response = platform_client.patch(
        f"/admin/users/{user_id}/organization",
        json={"organization_id": organization_id},
    )
    assert move_response.status_code == 200
    assert move_response.json()["organization_id"] == organization_id


def _install_admin_oidc_transport(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
) -> tuple[object, object]:
    """将真实 admin OIDC 客户端的 HTTP 传输替换为受控 issuer。"""
    oidc_gateway, http_client = issuer.build_gateway()
    api_client.app.dependency_overrides[get_admin_oidc_gateway] = lambda: oidc_gateway
    return oidc_gateway, http_client


def _install_public_oidc_transport(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
) -> tuple[object, object]:
    """将真实 public OIDC 客户端的 HTTP 传输替换为受控 issuer。"""
    oidc_gateway, http_client = issuer.build_gateway(
        client_id=TEST_PUBLIC_OIDC_CLIENT_ID,
        callback_uri=TEST_PUBLIC_OIDC_CALLBACK_URI,
    )
    api_client.app.dependency_overrides[get_public_oidc_gateway] = lambda: oidc_gateway
    return oidc_gateway, http_client


def _complete_admin_oidc_login(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
    *,
    email: str,
    subject: str,
) -> Response:
    """经真实 start/callback 路由完成一次管理员 OIDC 登录。"""
    start_response = api_client.get("/admin/auth/oidc/start", follow_redirects=False)
    assert start_response.status_code == 302
    authorization_query = parse_authorization_query(start_response.headers["location"])
    issuer.token_claims = issuer.standard_claims(
        nonce=authorization_query["nonce"],
        subject=subject,
        email=email,
        audience=TEST_OIDC_CLIENT_ID,
    )
    callback_response = api_client.get(
        "/admin/auth/oidc/callback",
        params={
            "code": f"org-security-{uuid.uuid4().hex}",
            "state": authorization_query["state"],
        },
        follow_redirects=False,
    )
    assert callback_response.status_code == 302
    return callback_response


def _complete_public_oidc_login(
    api_client: TestClient,
    issuer: ControlledOidcIssuer,
    *,
    email: str,
    subject: str,
) -> tuple[Response, str | None]:
    """经真实 public start/callback 路由完成一次 OIDC 登录。"""
    authorization_query = start_public_oidc_login(api_client)
    callback_response = finish_public_oidc_login(
        api_client,
        issuer,
        authorization_query,
        email=email,
        subject=subject,
    )
    if callback_response.headers["location"] != "/app/dashboard":
        return callback_response, None
    return callback_response, api_client.get("/auth/me").json()["user_id"]


def test_org_admin_is_forbidden_from_platform_apis_and_cross_org_user_scope_is_hidden(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
    entity_registry: TrackedEntityRegistry,
    created_organization_ids: list[str],
) -> None:
    """真实组织管理员会话不能访问平台 API 或发现其他组织用户。"""
    platform_client = _login_platform_admin(build_client, seed_admin)
    organization_a_id = _create_organization(
        platform_client,
        created_organization_ids,
        f"Org A {uuid.uuid4().hex[:8]}",
    )
    organization_b_id = _create_organization(
        platform_client,
        created_organization_ids,
        f"Org B {uuid.uuid4().hex[:8]}",
    )
    organization_admin_username = f"org-admin-{uuid.uuid4().hex[:10]}"
    organization_admin_email = unique_email()
    _create_organization_admin(
        platform_client,
        entity_registry,
        organization_a_id,
        username=organization_admin_username,
        email=organization_admin_email,
        password="Org-admin-password123",
    )
    organization_admin_client = build_client()
    organization_admin_login = organization_admin_client.post(
        "/admin/auth/login",
        json={"identifier": organization_admin_username, "password": "Org-admin-password123"},
    )
    assert organization_admin_login.status_code == 200
    assert organization_admin_login.json()["role"] == "org"
    assert organization_admin_login.json()["organization_id"] == organization_a_id

    valid_admin_body = {
        "username": f"denied-admin-{uuid.uuid4().hex[:8]}",
        "email": unique_email(),
        "role": "org",
        "organization_id": organization_a_id,
        "password": "Rejected-password123",
    }
    platform_only_requests: tuple[tuple[str, str, dict[str, object] | None], ...] = (
        ("GET", "/admin/organizations", None),
        ("POST", "/admin/organizations", {"name": f"Denied {uuid.uuid4().hex[:8]}"}),
        ("POST", f"/admin/organizations/{organization_b_id}/disable", None),
        ("GET", "/admin/admins", None),
        ("POST", "/admin/admins", valid_admin_body),
        ("POST", f"/admin/admins/{uuid.uuid4().hex}/disable", None),
        ("GET", "/admin/settings/registration-policy", None),
        (
            "PUT",
            "/admin/settings/registration-policy",
            {"registration_mode": "both", "allowed_email_domains": []},
        ),
        ("GET", "/admin/run-traces", None),
    )
    for method, path, request_body in platform_only_requests:
        response = organization_admin_client.request(method, path, json=request_body)
        if method == "POST" and path == "/admin/organizations" and response.status_code == 200:
            created_organization_ids.append(response.json()["id"])
        if method == "POST" and path == "/admin/admins" and response.status_code == 200:
            entity_registry.admin_user_ids.append(response.json()["id"])
        assert response.status_code == 403, (method, path, response.text)
        assert response.json()["detail"] == "platform_admin_required"

    target_user_client = build_client()
    target_user_email = unique_email()
    target_user_id = _register_password_user(target_user_client, target_user_email)
    _move_user_to_organization(platform_client, target_user_id, organization_b_id)
    with SessionLocal() as database_session:
        target_before = database_session.get(PublicUserModel, target_user_id)
        assert target_before is not None
        assert target_before.organization_id == organization_b_id
        assert target_before.is_active is True

    missing_user_id = f"missing-{uuid.uuid4().hex}"
    hidden_responses = (
        organization_admin_client.get(f"/admin/users/{target_user_id}"),
        organization_admin_client.get(f"/admin/users/{missing_user_id}"),
        organization_admin_client.post(f"/admin/users/{target_user_id}/enable"),
        organization_admin_client.post(f"/admin/users/{missing_user_id}/enable"),
        organization_admin_client.post(f"/admin/users/{target_user_id}/disable"),
        organization_admin_client.post(f"/admin/users/{missing_user_id}/disable"),
    )
    for visible_response, missing_response in zip(hidden_responses[::2], hidden_responses[1::2]):
        assert visible_response.status_code == missing_response.status_code == 404
        assert visible_response.json() == missing_response.json()
    with SessionLocal() as database_session:
        target_after = database_session.get(PublicUserModel, target_user_id)
        assert target_after is not None
        assert target_after.organization_id == organization_b_id
        assert target_after.is_active is True

    default_disable_response = platform_client.post("/admin/organizations/default/disable")
    assert default_disable_response.status_code == 400
    assert default_disable_response.json()["detail"] == "default_organization_cannot_be_disabled"
    with SessionLocal() as database_session:
        default_organization = database_session.get(OrganizationModel, "default")
        assert default_organization is not None
        assert default_organization.is_active is True

    passwordless_admin_response = platform_client.post(
        "/admin/admins",
        json={
            "username": f"passwordless-{uuid.uuid4().hex[:8]}",
            "email": unique_email(),
            "role": "org",
            "organization_id": organization_a_id,
        },
    )
    assert passwordless_admin_response.status_code == 400
    assert passwordless_admin_response.json()["detail"] == "oidc_unavailable_password_required"


def test_disabling_organization_blocks_member_and_admin_sessions_and_logins_until_enabled(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
    entity_registry: TrackedEntityRegistry,
    created_organization_ids: list[str],
    oidc_transports: list[tuple[object, object]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """组织停用拒绝成员/管理员密码与 OIDC 登录，并使旧会话即时不可用。"""
    caplog.set_level("INFO")
    platform_client = _login_platform_admin(build_client, seed_admin)
    organization_id = _create_organization(
        platform_client,
        created_organization_ids,
        f"Disable flow {uuid.uuid4().hex[:8]}",
    )
    admin_username = f"inactive-org-admin-{uuid.uuid4().hex[:10]}"
    admin_email = unique_email()
    admin_password = "Org-admin-password123"
    _create_organization_admin(
        platform_client,
        entity_registry,
        organization_id,
        username=admin_username,
        email=admin_email,
        password=admin_password,
    )

    password_user_email = unique_email()
    password_user_client = build_client()
    password_user_id = _register_password_user(password_user_client, password_user_email)
    password_user_client.post("/auth/logout")
    password_login = password_user_client.post(
        "/auth/login",
        json={"identifier": password_user_email, "password": "User-password123"},
    )
    assert password_login.status_code == 200
    _move_user_to_organization(platform_client, password_user_id, organization_id)

    organization_admin_password_client = build_client()
    admin_password_login = organization_admin_password_client.post(
        "/admin/auth/login",
        json={"identifier": admin_username, "password": admin_password},
    )
    assert admin_password_login.status_code == 200

    public_oidc_email = unique_email()
    public_oidc_subject = f"public-org-{uuid.uuid4().hex}"
    public_oidc_session_client = build_client()
    public_issuer = ControlledOidcIssuer()
    public_gateway, public_http_client = _install_public_oidc_transport(
        public_oidc_session_client,
        public_issuer,
    )
    oidc_transports.append((public_gateway, public_http_client))
    public_oidc_callback, public_oidc_user_id = _complete_public_oidc_login(
        public_oidc_session_client,
        public_issuer,
        email=public_oidc_email,
        subject=public_oidc_subject,
    )
    assert public_oidc_callback.headers["location"] == "/app/dashboard"
    assert public_oidc_user_id is not None
    entity_registry.public_user_ids.append(public_oidc_user_id)
    _move_user_to_organization(platform_client, public_oidc_user_id, organization_id)

    admin_oidc_subject = f"admin-org-{uuid.uuid4().hex}"
    admin_oidc_session_client = build_client()
    admin_issuer = ControlledOidcIssuer()
    admin_gateway, admin_http_client = _install_admin_oidc_transport(
        admin_oidc_session_client,
        admin_issuer,
    )
    oidc_transports.append((admin_gateway, admin_http_client))
    admin_oidc_callback = _complete_admin_oidc_login(
        admin_oidc_session_client,
        admin_issuer,
        email=admin_email,
        subject=admin_oidc_subject,
    )
    assert admin_oidc_callback.headers["location"] == "/"

    assert password_user_client.get("/auth/me").status_code == 200
    assert public_oidc_session_client.get("/auth/me").status_code == 200
    assert organization_admin_password_client.get("/admin/auth/me").status_code == 200
    assert admin_oidc_session_client.get("/admin/auth/me").status_code == 200

    disable_response = platform_client.post(f"/admin/organizations/{organization_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["is_active"] is False
    assert password_user_client.get("/auth/me").status_code == 401
    assert public_oidc_session_client.get("/auth/me").status_code == 401
    assert organization_admin_password_client.get("/admin/auth/me").status_code == 401
    assert admin_oidc_session_client.get("/admin/auth/me").status_code == 401

    disabled_password_user_client = build_client()
    disabled_public_password_login = disabled_password_user_client.post(
        "/auth/login",
        json={"identifier": password_user_email, "password": "User-password123"},
    )
    assert disabled_public_password_login.status_code == 401
    assert "组织已停用" in disabled_public_password_login.json()["detail"]

    disabled_admin_password_client = build_client()
    disabled_admin_password_login = disabled_admin_password_client.post(
        "/admin/auth/login",
        json={"identifier": admin_username, "password": admin_password},
    )
    assert disabled_admin_password_login.status_code == 401
    assert "组织已停用" in disabled_admin_password_login.json()["detail"]

    disabled_public_oidc_client = build_client()
    disabled_public_issuer = ControlledOidcIssuer()
    disabled_public_gateway, disabled_public_http_client = _install_public_oidc_transport(
        disabled_public_oidc_client,
        disabled_public_issuer,
    )
    oidc_transports.append((disabled_public_gateway, disabled_public_http_client))
    failed_public_oidc_callback, failed_public_oidc_user_id = _complete_public_oidc_login(
        disabled_public_oidc_client,
        disabled_public_issuer,
        email=public_oidc_email,
        subject=public_oidc_subject,
    )
    assert failed_public_oidc_callback.headers["location"] == "/login?sso_error=1"
    assert failed_public_oidc_user_id is None
    assert disabled_public_oidc_client.get("/auth/me").status_code == 401

    disabled_admin_oidc_client = build_client()
    disabled_admin_issuer = ControlledOidcIssuer()
    disabled_admin_gateway, disabled_admin_http_client = _install_admin_oidc_transport(
        disabled_admin_oidc_client,
        disabled_admin_issuer,
    )
    oidc_transports.append((disabled_admin_gateway, disabled_admin_http_client))
    failed_admin_oidc_login = _complete_admin_oidc_login(
        disabled_admin_oidc_client,
        disabled_admin_issuer,
        email=admin_email,
        subject=admin_oidc_subject,
    )
    assert failed_admin_oidc_login.headers["location"] == "/sign-in?sso_error=1"
    assert disabled_admin_oidc_client.get("/admin/auth/me").status_code == 401
    inactive_oidc_failures = [
        record.getMessage()
        for record in caplog.records
        if record.name.startswith("backend.")
        and "reason=organization_inactive" in record.getMessage()
    ]
    assert len(inactive_oidc_failures) >= 2

    assert platform_client.get("/admin/auth/me").status_code == 200
    assert platform_client.get("/admin/organizations").status_code == 200

    enable_response = platform_client.post(f"/admin/organizations/{organization_id}/enable")
    assert enable_response.status_code == 200
    assert enable_response.json()["is_active"] is True

    assert (
        disabled_password_user_client.post(
            "/auth/login",
            json={"identifier": password_user_email, "password": "User-password123"},
        ).status_code
        == 200
    )
    assert (
        disabled_admin_password_client.post(
            "/admin/auth/login",
            json={"identifier": admin_username, "password": admin_password},
        ).status_code
        == 200
    )
    recovered_public_oidc_callback, recovered_public_oidc_user_id = _complete_public_oidc_login(
        disabled_public_oidc_client,
        disabled_public_issuer,
        email=public_oidc_email,
        subject=public_oidc_subject,
    )
    assert recovered_public_oidc_callback.headers["location"] == "/app/dashboard"
    assert recovered_public_oidc_user_id == public_oidc_user_id
    recovered_admin_oidc_callback = _complete_admin_oidc_login(
        disabled_admin_oidc_client,
        disabled_admin_issuer,
        email=admin_email,
        subject=admin_oidc_subject,
    )
    assert recovered_admin_oidc_callback.headers["location"] == "/"
    assert disabled_admin_oidc_client.get("/admin/auth/me").status_code == 200


@pytest.mark.parametrize(
    ("admin_role", "organization_id"),
    [("org", None), ("platform", "default")],
)
def test_admin_role_organization_check_constraint_rejects_invalid_combinations(
    admin_role: str,
    organization_id: str | None,
) -> None:
    """真实迁移创建的数据库 CHECK 约束拒绝不一致的角色与组织归属。"""
    admin_id = uuid.uuid4().hex
    admin_username = f"constraint-{uuid.uuid4().hex[:12]}"
    with pytest.raises((IntegrityError, OperationalError)) as raised_database_error:
        with SessionLocal.begin() as database_session:
            database_session.add(
                AdminUserModel(
                    id=admin_id,
                    username=admin_username,
                    display_name="Constraint Check",
                    password_hash="test-only-hash",
                    role=admin_role,
                    organization_id=organization_id,
                    is_active=True,
                )
            )

    if isinstance(raised_database_error.value, IntegrityError):
        constraint_name = raised_database_error.value.orig.diag.constraint_name
    else:
        mysql_error = raised_database_error.value.orig
        assert mysql_error.args[0] == 3819
        assert "ck_admin_user_role_organization" in str(mysql_error)
        constraint_name = "ck_admin_user_role_organization"
    assert constraint_name == "ck_admin_user_role_organization"

    with SessionLocal() as database_session:
        persisted_admin = database_session.get(AdminUserModel, admin_id)
        assert persisted_admin is None


def test_bootstrap_seed_restores_disabled_org_admin_to_configured_platform_account(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    unique_email: Callable[[], str],
    entity_registry: TrackedEntityRegistry,
    created_organization_ids: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """启动种子恢复禁用组织管理员、同步密码和邮箱，并清除组织归属。"""
    platform_client = _login_platform_admin(build_client, seed_admin)
    organization_id = _create_organization(
        platform_client,
        created_organization_ids,
        f"Seed recovery {uuid.uuid4().hex[:8]}",
    )
    bootstrap_username = f"recover-{uuid.uuid4().hex[:10]}"
    existing_email = unique_email()
    updated_email = unique_email()
    old_password = "Org-old-password123"
    new_password = "Bootstrap-new-password123"
    bootstrap_admin_id = _create_organization_admin(
        platform_client,
        entity_registry,
        organization_id,
        username=bootstrap_username,
        email=existing_email,
        password=old_password,
    )
    disable_response = platform_client.post(f"/admin/admins/{bootstrap_admin_id}/disable")
    assert disable_response.status_code == 200
    assert disable_response.json()["status"] == "disabled"

    monkeypatch.setattr(config.auth, "admin_bootstrap_username", bootstrap_username.upper())
    monkeypatch.setattr(config.auth, "admin_bootstrap_password", SecretStr(new_password))
    monkeypatch.setattr(config.auth, "admin_bootstrap_email", updated_email.upper())

    from backend.main import create_app

    create_app()

    with SessionLocal() as database_session:
        recovered_admin = database_session.get(AdminUserModel, bootstrap_admin_id)
        assert recovered_admin is not None
        assert recovered_admin.is_active is True
        assert recovered_admin.role == "platform"
        assert recovered_admin.organization_id is None
        assert recovered_admin.email == updated_email
        assert BcryptPasswordHasher().verify(new_password, recovered_admin.password_hash)
        assert not BcryptPasswordHasher().verify(old_password, recovered_admin.password_hash)

    recovery_client = build_client()
    recovery_login = recovery_client.post(
        "/admin/auth/login",
        json={"identifier": bootstrap_username, "password": new_password},
    )
    assert recovery_login.status_code == 200
    assert recovery_login.json()["role"] == "platform"
    assert recovery_login.json()["organization_id"] is None
