"""Backend 测试共享 fixture。

统一管理后端测试的数据库建表与 Redis 替身：
- 用真实测试数据库（由 ``DATABASE_URL`` 指向）建表，会话级、幂等、不删表以兼容并行；
- 用进程内 fakeredis 替换装配中的 Redis 客户端，使认证 / 会话测试无需真实 Redis。

数据残留防护
-------------

``_realdb_residue_sentinel`` 是写真实数据库的测试的统一防线：快照哨兵覆盖表
的主键集合，任何净新增/净删除直接 fail 并列出泄漏行；``build_client`` /
``seed_admin`` 配合 ``entity_registry`` 自动登记并清理测试创建的实体。任何
测试只要经 ``TestClient(create_app())`` 或 ``SessionLocal`` 写入真实数据库，
**必须打 ``@pytest.mark.realdb``**（在哨兵中且以真实库测试同组串行执行），
否则并行 worker 间的写入会被误判为残留。
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
from tests.realdb_test_support import (
    TrackedEntityRegistry,
    TrackedTestClient,
    has_realdb_marker,
)

_REGISTRY_CLEANUP_FAILURE_KEY = pytest.StashKey[str]()


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
def entity_registry(
    request: pytest.FixtureRequest,
) -> Iterator[TrackedEntityRegistry]:
    """提供实体登记注册表，teardown 按精确 ID 删除。

    写真实数据库的测试（打 ``realdb`` 标记）经 ``build_client`` /
    ``seed_admin`` 自动登记创建实体的 ID，teardown 由本 fixture 精确清理。
    未打 ``realdb`` 标记的测试不登记、也不清理。
    """
    registry = TrackedEntityRegistry()
    yield registry
    try:
        registry.delete_tracked_entities()
    except Exception as cleanup_exception:
        if has_realdb_marker(request):
            request.node.stash[_REGISTRY_CLEANUP_FAILURE_KEY] = str(cleanup_exception)
        else:
            raise


@pytest.fixture
def build_client(
    request: pytest.FixtureRequest, entity_registry: TrackedEntityRegistry
) -> Callable[[], TrackedTestClient]:
    """返回构造全新 ``TrackedTestClient``（含独立 Cookie jar）的工厂。

    工厂包装 ``TestClient(create_app())``：对打 ``realdb`` 标记的测试自动登记
    ``/auth/register`` 创建的用户 ID，测试结束由 ``entity_registry`` 精确清理。
    仅用于写真实数据库的测试（须打 ``realdb`` 标记）。
    """

    def _factory() -> TrackedTestClient:
        from backend.main import create_app

        client = TestClient(create_app())
        if has_realdb_marker(request):
            return TrackedTestClient(client, entity_registry)
        return client

    return _factory


@pytest.fixture
def unique_email() -> Callable[[], str]:
    """返回生成唯一邮箱的工厂，避免并行 / 跨用例数据冲突。"""

    def _factory() -> str:
        return f"user-{uuid.uuid4().hex[:12]}@example.com"

    return _factory


@pytest.fixture
def seed_admin(
    entity_registry: TrackedEntityRegistry,
) -> Callable[[str, str], str]:
    """返回向 admin_user 表种入管理员并返回其主键的工厂。

    种入的管理员 ID 自动登记，teardown 精确删除，测试无需手写清理。
    """
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
        entity_registry.admin_user_ids.append(account_id)
        return account_id

    return _factory
