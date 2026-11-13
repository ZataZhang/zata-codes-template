"""注册策略值对象与持久化服务测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.auth.registration_policy import (
    InvalidEmailDomains,
    RegistrationPolicy,
    normalize_email_domain,
)
from backend.core.auth.registration_policy_service import (
    RegistrationPolicyService,
    RegistrationPolicyUnavailable,
)
from backend.infrastructure.persistence.database import Base
from backend.infrastructure.persistence.models.system_setting import SystemSettingModel
from backend.infrastructure.persistence.repos.system_setting_repo import (
    SqlAlchemySystemSettingRepository,
)


class _MemorySystemSettingRepository:
    """系统设置端口的内存替身。"""

    def __init__(self, value_json: str | None = None) -> None:
        self.values: dict[str, str] = {}
        if value_json is not None:
            self.values["registration_policy"] = value_json
        self.read_error: Exception | None = None
        self.write_error: Exception | None = None
        self.put_calls: list[tuple[str, str]] = []

    def get(self, key: str) -> str | None:
        if self.read_error is not None:
            raise self.read_error
        return self.values.get(key)

    def put(self, key: str, value_json: str) -> None:
        if self.write_error is not None:
            raise self.write_error
        self.put_calls.append((key, value_json))
        self.values[key] = value_json


def _build_registration_policy_client(service: RegistrationPolicyService) -> TestClient:
    """创建使用平台管理员替身与指定注册策略服务的 HTTP 客户端。"""
    from backend.api.admin.registration_policy_router import registration_policy_router
    from backend.api.dependencies import (
        get_current_platform_admin,
        get_registration_policy_service,
    )

    app = FastAPI()
    app.include_router(registration_policy_router)
    app.dependency_overrides[get_current_platform_admin] = lambda: SimpleNamespace(
        user_id="platform-admin"
    )
    app.dependency_overrides[get_registration_policy_service] = lambda: service
    return TestClient(app)


def test_system_setting_repository_reads_and_updates_one_setting_key() -> None:
    """SQLAlchemy 设置仓库支持缺项读取和通用键值更新。"""
    sqlite_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(sqlite_engine, tables=[SystemSettingModel.__table__])
    setting_repository = SqlAlchemySystemSettingRepository(
        session_factory=sessionmaker(
            bind=sqlite_engine,
            autoflush=False,
            autocommit=False,
            class_=Session,
        )
    )

    assert setting_repository.get("registration_policy") is None
    setting_repository.put("registration_policy", '{"registration_mode":"both"}')
    setting_repository.put("registration_policy", '{"registration_mode":"closed"}')

    assert setting_repository.get("registration_policy") == '{"registration_mode":"closed"}'


def test_domain_normalization_uses_idna_and_rejects_invalid_hostnames() -> None:
    """邮箱域名去空白、转小写并支持 IDNA ASCII 表示。"""
    assert normalize_email_domain("  EXAMPLE.COM ") == "example.com"
    assert normalize_email_domain("例子.测试") == "xn--fsqu00a.xn--0zwm56d"
    with pytest.raises(ValueError):
        normalize_email_domain("bad_domain.example")
    with pytest.raises(ValueError):
        normalize_email_domain("https://example.com")


@pytest.mark.parametrize(
    ("registration_mode", "channel", "email", "expected"),
    [
        ("both", "password", "person@example.com", True),
        ("both", "oidc", "person@example.com", True),
        ("both", "password", "person@outside.com", False),
        ("both", "password", "person@sub.example.com", False),
        ("oidc_only", "password", "person@example.com", False),
        ("oidc_only", "oidc", "person@example.com", True),
        ("closed", "oidc", "person@example.com", False),
    ],
)
def test_registration_policy_allows_channel_and_exact_email_domain(
    registration_mode: str,
    channel: str,
    email: str,
    expected: bool,
) -> None:
    """策略按注册模式与邮箱的精确域名控制渠道。"""
    policy = RegistrationPolicy(
        registration_mode=registration_mode,
        allowed_email_domains=("example.com",),
    )

    assert policy.allows(channel, email) is expected


def test_missing_policy_record_uses_open_compatibility_default() -> None:
    """只有确认键不存在时使用兼容现状的开放策略。"""
    service = RegistrationPolicyService(_MemorySystemSettingRepository())

    policy = service.get_registration_policy()

    assert policy.registration_mode == "both"
    assert policy.allowed_email_domains == ()
    assert policy.allows("password", "person@any-domain.test") is True


def test_update_normalizes_deduplicates_and_is_immediately_readable() -> None:
    """写入时域名归一化去重，下一次读取立即返回最新策略。"""
    repository = _MemorySystemSettingRepository()
    service = RegistrationPolicyService(repository)

    updated_policy = service.update_registration_policy(
        "oidc_only",
        [" EXAMPLE.COM ", "example.com", "例子.测试"],
    )

    assert updated_policy.registration_mode == "oidc_only"
    assert updated_policy.allowed_email_domains == (
        "example.com",
        "xn--fsqu00a.xn--0zwm56d",
    )
    assert service.get_registration_policy() == updated_policy
    saved_key, saved_json = repository.put_calls[0]
    assert saved_key == "registration_policy"
    assert json.loads(saved_json) == {
        "registration_mode": "oidc_only",
        "allowed_email_domains": ["example.com", "xn--fsqu00a.xn--0zwm56d"],
    }


@pytest.mark.parametrize(
    "stored_json",
    [
        "{",
        "null",
        "true",
        "[]",
        '{"registration_mode":true,"allowed_email_domains":[]}',
        '{"registration_mode":"open","allowed_email_domains":[]}',
        '{"registration_mode":"both","allowed_email_domains":true}',
        '{"registration_mode":"both","allowed_email_domains":[7]}',
        '{"registration_mode":"both","allowed_email_domains":["bad_domain"]}',
    ],
)
def test_invalid_stored_policy_fails_closed_without_open_default(
    stored_json: str,
) -> None:
    """JSON 损坏或字段类型 / 内容错误时不回落到默认开放策略。"""
    service = RegistrationPolicyService(_MemorySystemSettingRepository(stored_json))

    with pytest.raises(RegistrationPolicyUnavailable):
        service.get_registration_policy()


def test_storage_read_and_write_failures_are_reported_as_unavailable() -> None:
    """存储异常在服务边界统一转为策略不可用。"""
    read_repository = _MemorySystemSettingRepository()
    read_repository.read_error = RuntimeError("database unavailable")
    write_repository = _MemorySystemSettingRepository()
    write_repository.write_error = RuntimeError("database unavailable")

    with pytest.raises(RegistrationPolicyUnavailable):
        RegistrationPolicyService(read_repository).get_registration_policy()
    with pytest.raises(RegistrationPolicyUnavailable):
        RegistrationPolicyService(write_repository).update_registration_policy("both", [])


def test_invalid_domains_keep_original_values_and_do_not_write() -> None:
    """拒绝无效域名时保留输入项以供 422 指明错误位置。"""
    repository = _MemorySystemSettingRepository()
    service = RegistrationPolicyService(repository)
    invalid_domain_values = ["example.com", " bad..domain ", "bad_domain.com"]

    with pytest.raises(InvalidEmailDomains) as error_info:
        service.update_registration_policy("both", invalid_domain_values)

    assert error_info.value.invalid_domains == [" bad..domain ", "bad_domain.com"]
    assert repository.put_calls == []


def test_invalid_mode_does_not_write_policy() -> None:
    """未知注册模式不会持久化。"""
    repository = _MemorySystemSettingRepository()

    with pytest.raises(ValueError, match="invalid_registration_mode"):
        RegistrationPolicyService(repository).update_registration_policy("unexpected", [])

    assert repository.put_calls == []


def test_registration_policy_router_reads_saves_and_returns_invalid_domains() -> None:
    """管理路由能读写策略，并以稳定 422 字段返回非法域名。"""
    setting_repository = _MemorySystemSettingRepository()
    client = _build_registration_policy_client(RegistrationPolicyService(setting_repository))

    initial_response = client.get("/admin/settings/registration-policy")
    assert initial_response.status_code == 200
    assert initial_response.json() == {
        "registration_mode": "both",
        "allowed_email_domains": [],
    }

    invalid_response = client.put(
        "/admin/settings/registration-policy",
        json={
            "registration_mode": "both",
            "allowed_email_domains": ["example.com", "bad_domain.com"],
        },
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json()["detail"] == {
        "code": "invalid_email_domains",
        "invalid_domains": ["bad_domain.com"],
    }

    update_response = client.put(
        "/admin/settings/registration-policy",
        json={
            "registration_mode": "oidc_only",
            "allowed_email_domains": [" EXAMPLE.COM ", "example.com"],
        },
    )
    assert update_response.status_code == 200
    assert update_response.json() == {
        "registration_mode": "oidc_only",
        "allowed_email_domains": ["example.com"],
    }
    assert setting_repository.put_calls[0][0] == "registration_policy"


def test_registration_policy_router_requires_platform_role() -> None:
    """组织管理员不能读取注册策略管理端点。"""
    from backend.api.admin.registration_policy_router import registration_policy_router
    from backend.api.dependencies import get_current_admin_user

    app = FastAPI()
    app.include_router(registration_policy_router)
    app.dependency_overrides[get_current_admin_user] = lambda: SimpleNamespace(
        user_id="org-admin",
        role="org",
    )

    response = TestClient(app).get("/admin/settings/registration-policy")

    assert response.status_code == 403


def test_registration_policy_router_returns_503_when_storage_is_unavailable() -> None:
    """设置存储异常不会伪装成开放的默认策略。"""
    setting_repository = _MemorySystemSettingRepository()
    setting_repository.read_error = RuntimeError("database unavailable")
    client = _build_registration_policy_client(RegistrationPolicyService(setting_repository))

    response = client.get("/admin/settings/registration-policy")

    assert response.status_code == 503
    assert response.json()["detail"] == "registration_policy_unavailable"
