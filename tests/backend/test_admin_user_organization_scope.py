"""验证组织管理员的用户状态更新在数据库写入时仍受组织范围约束。"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from backend.api.admin.admin_user_router import router as admin_user_router
from backend.api.dependencies import get_current_admin_user, get_public_user_directory
from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthDomain, AuthenticatedPrincipal
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.organization import OrganizationModel
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from backend.infrastructure.persistence.repos.organization_repo import (
    SqlAlchemyOrganizationRepository,
)
from backend.infrastructure.persistence.repos.user_account_repo import (
    SqlAlchemyUserAccountRepository,
    UserAccountRepositoryMapping,
)
from tests.realdb_test_support import TrackedEntityRegistry

pytestmark = pytest.mark.realdb


class _TransferAfterReadRepository:
    """在读取后模拟另一请求完成合法用户转组的代理。"""

    def __init__(
        self,
        repository: SqlAlchemyUserAccountRepository,
        session_factory: sessionmaker[Session],
        destination_organization_id: str,
    ) -> None:
        """保存真实仓库及测试转组目标。"""
        self._repository = repository
        self._session_factory = session_factory
        self._destination_organization_id = destination_organization_id

    def get_by_id(self, account_id: str) -> Any:
        """返回写入前的账户读取结果。"""
        return self._repository.get_by_id(account_id)

    def set_active(
        self,
        account_id: str,
        is_active: bool,
        *,
        organization_id: str | None = None,
    ) -> Any:
        """先提交转组，再将原组织范围原样传给真实条件更新。"""
        with self._session_factory.begin() as session:
            user_account = session.get(PublicUserModel, account_id)
            assert user_account is not None
            user_account.organization_id = self._destination_organization_id
        return self._repository.set_active(
            account_id,
            is_active,
            organization_id=organization_id,
        )


def test_org_admin_cannot_toggle_user_transferred_after_scope_read(
    entity_registry: TrackedEntityRegistry,
) -> None:
    """账户在范围读取后转出时，真实路由返回 404 且状态保持不变。"""
    user_id: str = uuid.uuid4().hex
    email: str = f"scope-{uuid.uuid4().hex}@example.test"
    destination_organization_id: str = uuid.uuid4().hex
    with SessionLocal.begin() as session:
        session.add_all(
            [
                OrganizationModel(
                    id=destination_organization_id,
                    name=f"Transferred {destination_organization_id}",
                    is_active=True,
                ),
                PublicUserModel(
                    id=user_id,
                    email=email,
                    display_name="Person",
                    password_hash="encoded-hash",
                    is_active=True,
                    organization_id="default",
                ),
            ]
        )
    entity_registry.public_user_ids.append(user_id)

    public_repository = SqlAlchemyUserAccountRepository(
        session_factory=SessionLocal,
        mapping=UserAccountRepositoryMapping(
            model_class=PublicUserModel,
            identifier_attr="email",
            email_attr="email",
            organization_attr="organization_id",
        ),
    )
    transfer_repository = _TransferAfterReadRepository(
        public_repository,
        SessionLocal,
        destination_organization_id=destination_organization_id,
    )
    organization_repository = SqlAlchemyOrganizationRepository(session_factory=SessionLocal)
    directory = PublicUserDirectory(
        public_repository=transfer_repository,
        organization_repository=organization_repository,
    )
    app = FastAPI()
    app.include_router(admin_user_router)
    app.dependency_overrides[get_current_admin_user] = lambda: AuthenticatedPrincipal(
        user_id="org-admin",
        display_name="Organization Admin",
        identifier="org-admin",
        domain=AuthDomain.ADMIN,
        role="org",
        organization_id="default",
    )
    app.dependency_overrides[get_public_user_directory] = lambda: directory

    try:
        response = TestClient(app).post(f"/admin/users/{user_id}/disable")

        assert response.status_code == 404
        with SessionLocal() as session:
            persisted_user = session.get(PublicUserModel, user_id)
            assert persisted_user is not None
            assert persisted_user.organization_id == destination_organization_id
            assert persisted_user.is_active is True
    finally:
        with SessionLocal.begin() as session:
            session.execute(delete(PublicUserModel).where(PublicUserModel.id == user_id))
            session.execute(
                delete(OrganizationModel).where(OrganizationModel.id == destination_organization_id)
            )
