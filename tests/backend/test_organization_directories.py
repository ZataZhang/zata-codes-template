"""组织与管理员目录用例及持久化仓库测试。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from logging import INFO
from types import SimpleNamespace
from typing import Sequence
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.auth.admin_directory import AdminCreateCommand, AdminDirectory
from backend.core.auth.organization_directory import OrganizationDirectory
from backend.core.shared.models.organization import (
    DEFAULT_ORGANIZATION_ID,
    Organization,
)
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.organization import OrganizationModel
from backend.infrastructure.persistence.repos.organization_repo import (
    SqlAlchemyOrganizationRepository,
)


@dataclass(frozen=True)
class _AdminAccount:
    """测试用管理员账户投影。"""

    id: str
    identifier: str
    display_name: str
    password_hash: str
    is_active: bool
    email: str | None = None
    oidc_issuer: str | None = None
    oidc_subject: str | None = None
    role: str = "platform"
    organization_id: str | None = None
    organization_name: str | None = None
    created_at: datetime | None = None


class _MemoryOrganizationRepository:
    """组织目录用例的内存仓库替身。"""

    def __init__(self) -> None:
        self.organizations: dict[str, Organization] = {
            DEFAULT_ORGANIZATION_ID: Organization(
                id=DEFAULT_ORGANIZATION_ID,
                name="默认组织",
                is_active=True,
            )
        }

    def list_organizations(self) -> Sequence[Organization]:
        return tuple(self.organizations.values())

    def create(self, name: str) -> Organization:
        if self.find_by_name(name) is not None:
            raise ValueError("organization_name_conflict")
        organization = Organization(
            id=uuid.uuid4().hex,
            name=name,
            is_active=True,
        )
        self.organizations[organization.id] = organization
        return organization

    def set_active(self, organization_id: str, *, is_active: bool) -> Organization | None:
        organization = self.organizations.get(organization_id)
        if organization is None:
            return None
        updated_organization = Organization(
            id=organization.id,
            name=organization.name,
            is_active=is_active,
            created_at=organization.created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self.organizations[organization_id] = updated_organization
        return updated_organization

    def get_by_id(self, organization_id: str) -> Organization | None:
        return self.organizations.get(organization_id)

    def find_by_name(self, name: str) -> Organization | None:
        return next(
            (
                organization
                for organization in self.organizations.values()
                if organization.name.casefold() == name.casefold()
            ),
            None,
        )


def _make_admin_repository(accounts: Sequence[_AdminAccount] = ()) -> Mock:
    """创建仅配置本用例所需方法的管理员仓库替身。"""
    account_by_id: dict[str, _AdminAccount] = {account.id: account for account in accounts}
    admin_repository = Mock()
    admin_repository.guard_error = None
    admin_repository.unbind_calls = []
    admin_repository.list_accounts.side_effect = lambda *, offset, limit, **_: (
        list(account_by_id.values())[offset : offset + limit],
        len(account_by_id),
    )
    admin_repository.find_by_identifier.side_effect = lambda identifier: next(
        (account for account in account_by_id.values() if account.identifier == identifier), None
    )
    admin_repository.find_by_email.side_effect = lambda email: next(
        (account for account in account_by_id.values() if account.email == email), None
    )
    admin_repository.get_by_id.side_effect = account_by_id.get

    def create_unique(account: _AdminAccount) -> _AdminAccount:
        account_by_id[account.id] = account
        return account

    def set_active_with_guard(account_id: str, is_active: bool) -> _AdminAccount | None:
        if admin_repository.guard_error is not None:
            raise ValueError(admin_repository.guard_error)
        account = account_by_id.get(account_id)
        if account is None:
            return None
        updated_account = replace(account, is_active=is_active)
        account_by_id[account_id] = updated_account
        return updated_account

    def unbind_oidc_identity(account_id: str) -> _AdminAccount | None:
        admin_repository.unbind_calls.append(account_id)
        account = account_by_id.get(account_id)
        if account is None:
            return None
        updated_account = replace(account, oidc_issuer=None, oidc_subject=None)
        account_by_id[account_id] = updated_account
        return updated_account

    admin_repository.create_unique.side_effect = create_unique
    admin_repository.set_active_with_platform_guard.side_effect = set_active_with_guard
    admin_repository.unbind_oidc_identity.side_effect = unbind_oidc_identity
    return admin_repository


class _MemoryPasswordHasher:
    """记录测试密码哈希输入的替身。"""

    def __init__(self) -> None:
        self.hashed_passwords: list[str] = []

    def hash(self, plain_password: str) -> str:
        self.hashed_passwords.append(plain_password)
        return "encoded-hash"


class _RouterAdminDirectory:
    """管理端路由 DTO 与审计测试替身。"""

    def __init__(self, account: _AdminAccount) -> None:
        self.account = account

    def list_admins(self) -> Sequence[_AdminAccount]:
        return [self.account]

    def create_admin(self, _command: AdminCreateCommand) -> _AdminAccount:
        return self.account


def _build_platform_test_client(
    *,
    organization_directory: OrganizationDirectory | None = None,
    admin_directory: _RouterAdminDirectory | None = None,
) -> TestClient:
    """创建使用测试目录与平台管理员主体的路由客户端。"""
    from backend.api.admin.admin_directory_router import admin_directory_router
    from backend.api.admin.organization_router import organization_router
    from backend.api.dependencies import (
        get_admin_directory,
        get_current_platform_admin,
        get_organization_directory,
    )

    app = FastAPI()
    app.include_router(organization_router)
    app.include_router(admin_directory_router)
    app.dependency_overrides[get_current_platform_admin] = lambda: SimpleNamespace(
        user_id="platform-actor"
    )
    if organization_directory is not None:
        app.dependency_overrides[get_organization_directory] = lambda: organization_directory
    if admin_directory is not None:
        app.dependency_overrides[get_admin_directory] = lambda: admin_directory
    return TestClient(app)


def test_organization_repository_persists_and_filters_organization() -> None:
    """组织仓库可创建组织并通过 ID / 名称读取。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[OrganizationModel.__table__])
    repository = SqlAlchemyOrganizationRepository(
        session_factory=sessionmaker(bind=engine, autoflush=False, autocommit=False)
    )

    organization = repository.create("Example Team")

    assert organization.name == "Example Team"
    organization_by_id = repository.get_by_id(organization.id)
    organization_by_name = repository.find_by_name("Example Team")
    assert organization_by_id is not None
    assert organization_by_name is not None
    assert organization_by_id.id == organization.id
    assert organization_by_name.id == organization.id
    assert [entry.id for entry in repository.list_organizations()] == [organization.id]
    with pytest.raises(ValueError, match="organization_name_conflict"):
        repository.create("Example Team")
    disabled_organization = repository.set_active(organization.id, is_active=False)
    assert disabled_organization is not None
    assert disabled_organization.is_active is False
    assert repository.set_active("missing-organization", is_active=False) is None


def test_organization_directory_trims_names_and_protects_default_organization() -> None:
    """组织目录会清理名称，且不能停用默认组织。"""
    repository = _MemoryOrganizationRepository()
    directory = OrganizationDirectory(repository)

    created_organization = directory.create_organization("  Example Team  ")

    assert created_organization.name == "Example Team"
    with pytest.raises(ValueError, match="default_organization_cannot_be_disabled"):
        directory.set_organization_active(DEFAULT_ORGANIZATION_ID, is_active=False)
    assert repository.get_by_id(DEFAULT_ORGANIZATION_ID).is_active is True


def test_organization_directory_rejects_duplicate_and_blank_names() -> None:
    """重复或空白组织名称返回可映射的领域错误。"""
    directory = OrganizationDirectory(_MemoryOrganizationRepository())
    directory.create_organization("Example Team")

    with pytest.raises(ValueError, match="organization_name_conflict"):
        directory.create_organization("Example Team")
    with pytest.raises(ValueError, match="organization_name_required"):
        directory.create_organization("   ")


def test_admin_directory_creates_normalized_org_admin_with_random_password_hash() -> None:
    """不提供初始密码时仅在 OIDC 可用前提下创建随机不可登录口令哈希。"""
    organization = Organization(
        id="org-1",
        name="Example Team",
        is_active=True,
    )
    organizations = _MemoryOrganizationRepository()
    organizations.organizations[organization.id] = organization
    accounts = _make_admin_repository()
    password_hasher = _MemoryPasswordHasher()
    directory = AdminDirectory(
        admin_repository=accounts,
        organization_repository=organizations,
        password_hasher=password_hasher,
        oidc_enabled=True,
    )

    created_account = directory.create_admin(
        AdminCreateCommand(
            username="  OPS.USER  ",
            email="  OPS@EXAMPLE.COM ",
            display_name=None,
            role="org",
            organization_id="org-1",
            password=None,
        )
    )

    assert created_account.identifier == "ops.user"
    assert created_account.email == "ops@example.com"
    assert created_account.display_name == "ops.user"
    assert created_account.role == "org"
    assert created_account.organization_id == "org-1"
    assert len(password_hasher.hashed_passwords) == 1
    assert len(password_hasher.hashed_passwords[0]) >= 32
    assert created_account.password_hash == "encoded-hash"


def test_admin_directory_rejects_passwordless_admin_when_oidc_is_unavailable() -> None:
    """OIDC 不可用时必须设置管理员初始密码。"""
    directory = AdminDirectory(
        admin_repository=_make_admin_repository(),
        organization_repository=_MemoryOrganizationRepository(),
        password_hasher=_MemoryPasswordHasher(),
        oidc_enabled=False,
    )

    with pytest.raises(ValueError, match="oidc_unavailable_password_required"):
        directory.create_admin(
            AdminCreateCommand(
                username="new.admin",
                email="new@example.com",
                display_name=None,
                role="platform",
                organization_id=None,
                password=None,
            )
        )


def test_admin_directory_preserves_password_and_rejects_malformed_email() -> None:
    """管理员初始密码保留首尾空格，非法邮箱地址不会创建账户。"""
    accounts = _make_admin_repository()
    password_hasher = _MemoryPasswordHasher()
    directory = AdminDirectory(
        admin_repository=accounts,
        organization_repository=_MemoryOrganizationRepository(),
        password_hasher=password_hasher,
        oidc_enabled=False,
    )
    original_password: str = "  secret123  "

    created_account = directory.create_admin(
        AdminCreateCommand(
            username="space.password",
            email="user@example.com",
            display_name=None,
            role="platform",
            organization_id=None,
            password=original_password,
        )
    )

    assert password_hasher.hashed_passwords == [original_password]
    assert created_account.password_hash == "encoded-hash"
    with pytest.raises(ValueError, match="invalid_email"):
        directory.create_admin(
            AdminCreateCommand(
                username="invalid.email",
                email="not-an-email",
                display_name=None,
                role="platform",
                organization_id=None,
                password="long-enough",
            )
        )


def test_admin_directory_requires_existing_organization_and_valid_role() -> None:
    """组织管理员必须关联现存组织，平台管理员不能附带组织。"""
    directory = AdminDirectory(
        admin_repository=_make_admin_repository(),
        organization_repository=_MemoryOrganizationRepository(),
        password_hasher=_MemoryPasswordHasher(),
        oidc_enabled=True,
    )

    with pytest.raises(ValueError, match="organization_required"):
        directory.create_admin(
            AdminCreateCommand(
                username="missing.org",
                email="missing@example.com",
                display_name=None,
                role="org",
                organization_id=None,
                password="long-enough",
            )
        )
    with pytest.raises(ValueError, match="platform_admin_cannot_have_organization"):
        directory.create_admin(
            AdminCreateCommand(
                username="platform.admin",
                email="platform@example.com",
                display_name=None,
                role="platform",
                organization_id="unexpected",
                password="long-enough",
            )
        )


def test_admin_directory_protects_self_and_last_platform_admin() -> None:
    """不能禁用自己或仓库认定的最后一名启用平台管理员。"""
    accounts = _make_admin_repository(
        [
            _AdminAccount(
                id="actor-id",
                identifier="actor",
                display_name="Actor",
                password_hash="hash",
                is_active=True,
            )
        ]
    )
    directory = AdminDirectory(
        admin_repository=accounts,
        organization_repository=_MemoryOrganizationRepository(),
        password_hasher=_MemoryPasswordHasher(),
        oidc_enabled=True,
    )

    with pytest.raises(ValueError, match="self_disable"):
        directory.set_admin_active("actor-id", "actor-id", is_active=False)
    accounts.guard_error = "last_platform_admin"
    with pytest.raises(ValueError, match="last_platform_admin"):
        directory.set_admin_active("other-actor", "actor-id", is_active=False)
    assert accounts.get_by_id("actor-id").is_active is True


def test_admin_directory_lists_more_than_one_page_of_accounts() -> None:
    """管理员列表跨页读取，不因页面大小而丢失后续账号。"""
    accounts = _make_admin_repository(
        [
            _AdminAccount(
                id=f"admin-{admin_index}",
                identifier=f"admin-{admin_index}",
                display_name=f"Admin {admin_index}",
                password_hash="hash",
                is_active=True,
            )
            for admin_index in range(450)
        ]
    )
    directory = AdminDirectory(
        admin_repository=accounts,
        organization_repository=_MemoryOrganizationRepository(),
        password_hasher=_MemoryPasswordHasher(),
        oidc_enabled=True,
    )

    assert len(directory.list_admins()) == 450


def test_admin_directory_unbinds_identity_without_disabling_account() -> None:
    """解绑仅清除本地身份映射并保留管理员及登录状态。"""
    accounts = _make_admin_repository(
        [
            _AdminAccount(
                id="bound-admin",
                identifier="bound",
                display_name="Bound Admin",
                password_hash="hash",
                is_active=True,
                email="bound@example.com",
                oidc_issuer="https://identity.example.com",
                oidc_subject="subject-1",
            )
        ]
    )
    directory = AdminDirectory(
        admin_repository=accounts,
        organization_repository=_MemoryOrganizationRepository(),
        password_hasher=_MemoryPasswordHasher(),
        oidc_enabled=True,
    )

    unbound_account = directory.unbind_admin_oidc_identity("bound-admin")

    assert unbound_account.oidc_issuer is None
    assert unbound_account.oidc_subject is None
    assert unbound_account.email == "bound@example.com"
    assert unbound_account.is_active is True
    assert accounts.unbind_calls == ["bound-admin"]
    with pytest.raises(ValueError, match="oidc_not_bound"):
        directory.unbind_admin_oidc_identity("bound-admin")


def test_organization_router_maps_conflicts_and_audits_mutations(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """组织路由返回标准 DTO、冲突状态并记录操作者与目标。"""
    caplog.set_level(INFO, logger="backend.api.admin.organization_router")
    organization_directory = OrganizationDirectory(_MemoryOrganizationRepository())
    client = _build_platform_test_client(organization_directory=organization_directory)

    initial_response = client.get("/admin/organizations")
    assert initial_response.status_code == 200
    assert initial_response.json()["items"][0]["id"] == DEFAULT_ORGANIZATION_ID

    create_response = client.post("/admin/organizations", json={"name": "Example Team"})
    assert create_response.status_code == 200
    organization_id = create_response.json()["id"]
    duplicate_response = client.post("/admin/organizations", json={"name": "Example Team"})
    assert duplicate_response.status_code == 409
    disable_default_response = client.post(
        f"/admin/organizations/{DEFAULT_ORGANIZATION_ID}/disable"
    )
    assert disable_default_response.status_code == 400

    assert "actor_id=platform-actor" in caplog.text
    assert f"target_id={organization_id}" in caplog.text
    assert "action=organization.create" in caplog.text


def test_admin_router_never_returns_or_logs_initial_password(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """创建管理员路由只返回公开字段，日志不包含初始密码。"""
    secret_password: str = "sensitive-initial-password"
    admin_account = _AdminAccount(
        id="admin-created",
        identifier="new.admin",
        display_name="New Admin",
        password_hash="hashed-password",
        is_active=True,
        email="admin@example.com",
        created_at=datetime.now(timezone.utc),
    )
    client = _build_platform_test_client(admin_directory=_RouterAdminDirectory(admin_account))
    caplog.set_level(INFO, logger="backend.api.admin.admin_directory_router")

    create_response = client.post(
        "/admin/admins",
        json={
            "username": "new.admin",
            "email": "admin@example.com",
            "role": "platform",
            "password": secret_password,
        },
    )

    assert create_response.status_code == 200
    assert create_response.json()["username"] == "new.admin"
    assert "password" not in create_response.json()
    assert secret_password not in caplog.text
    assert "action=admin.create" in caplog.text
    assert "target_id=admin-created" in caplog.text


def test_organization_router_rejects_org_admin_principal() -> None:
    """组织管理员不能绕过平台角色守卫调用组织管理路由。"""
    from backend.api.admin.organization_router import organization_router
    from backend.api.dependencies import get_current_admin_user

    app = FastAPI()
    app.include_router(organization_router)
    app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
        user_id="org-admin",
        role="org",
    )

    response = TestClient(app).get("/admin/organizations")

    assert response.status_code == 403
