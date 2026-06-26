"""Backend 测试共享 fixture。

统一管理后端测试的数据库建表与 Redis 替身：
- 用真实测试数据库（由 ``DATABASE_URL`` 指向）建表，会话级、幂等、不删表以兼容并行；
- 用进程内 fakeredis 替换装配中的 Redis 客户端，使认证 / 会话测试无需真实 Redis。
"""

from __future__ import annotations

import uuid
from typing import Callable, Iterator

import fakeredis
import pytest
from fastapi.testclient import TestClient

import backend.infrastructure.persistence.models  # noqa: F401  注册模型到 Base.metadata
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.persistence.database import Base, SessionLocal, engine
from backend.infrastructure.persistence.models.admin_user import AdminUserModel


@pytest.fixture(scope="session", autouse=True)
def _setup_backend_database() -> Iterator[None]:
    """为后端测试建立数据库表（会话级、幂等、不删表）。"""
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture(autouse=True)
def _use_fake_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """把后端装配使用的 Redis 客户端替换为进程内 fakeredis。

    同一 fake 实例下，两域仍通过 key 前缀隔离，便于验证物理隔离。
    """
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("backend.main.create_redis_client", lambda _url: fake_client)


@pytest.fixture
def build_client() -> Callable[[], TestClient]:
    """返回构造全新 TestClient（含独立 Cookie jar）的工厂。"""

    def _factory() -> TestClient:
        from backend.main import create_app

        return TestClient(create_app())

    return _factory


@pytest.fixture
def unique_email() -> Callable[[], str]:
    """返回生成唯一邮箱的工厂，避免并行 / 跨用例数据冲突。"""

    def _factory() -> str:
        return f"user-{uuid.uuid4().hex[:12]}@example.com"

    return _factory


@pytest.fixture
def seed_admin() -> Callable[[str, str], str]:
    """返回向 admin_user 表种入管理员并返回其主键的工厂。"""
    password_hasher = BcryptPasswordHasher()

    def _factory(username: str, password: str) -> str:
        account_id: str = uuid.uuid4().hex
        with SessionLocal() as session:
            session.add(
                AdminUserModel(
                    id=account_id,
                    username=username,
                    display_name=username,
                    password_hash=password_hasher.hash(password),
                    is_active=True,
                )
            )
            session.commit()
        return account_id

    return _factory
