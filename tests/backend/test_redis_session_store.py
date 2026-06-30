"""Redis 会话存储测试（fakeredis 单元 + 可选真实 Redis）。"""

from __future__ import annotations

import os

import fakeredis
import pytest

from backend.infrastructure.auth.redis_session_store import RedisSessionStore


def _build_store(prefix: str = "test:session:") -> RedisSessionStore:
    """构造一个基于独立 fakeredis 的会话存储。"""
    return RedisSessionStore(
        redis_client=fakeredis.FakeRedis(decode_responses=True),
        key_prefix=prefix,
    )


def test_create_get_delete_roundtrip() -> None:
    """create / get / delete 基本往返。"""
    store = _build_store()
    token = store.create("user-1")
    record = store.get(token)
    assert record is not None
    assert record.user_id == "user-1"
    store.delete(token)
    assert store.get(token) is None


def test_slide_expiration_returns_record() -> None:
    """滑动续期返回有效记录。"""
    store = _build_store()
    token = store.create("user-1")
    slid_record = store.slide_expiration(token)
    assert slid_record is not None
    assert slid_record.user_id == "user-1"


def test_unknown_token_returns_none() -> None:
    """未知 token 的读取与续期均返回 None。"""
    store = _build_store()
    assert store.get("nonexistent") is None
    assert store.slide_expiration("nonexistent") is None


def test_prefix_isolation_between_domains() -> None:
    """同一 Redis 实例下，不同前缀命名空间互不可见。"""
    shared_client = fakeredis.FakeRedis(decode_responses=True)
    public_store = RedisSessionStore(redis_client=shared_client, key_prefix="public:session:")
    admin_store = RedisSessionStore(redis_client=shared_client, key_prefix="admin:session:")
    public_token = public_store.create("public-user")
    assert public_store.get(public_token) is not None
    # admin 命名空间查不到 public token —— 物理隔离
    assert admin_store.get(public_token) is None
    assert admin_store.slide_expiration(public_token) is None


@pytest.mark.redis
def test_real_redis_roundtrip() -> None:
    """opt-in：对真实 Redis 验证往返（需设置 REDIS_URL）。"""
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        pytest.skip("REDIS_URL 未设置，跳过真实 Redis 测试")

    from backend.infrastructure.auth.redis_client import create_redis_client

    store = RedisSessionStore(
        redis_client=create_redis_client(redis_url),
        key_prefix="test:session:",
    )
    token = store.create("user-real")
    record = store.get(token)
    assert record is not None
    assert record.user_id == "user-real"
    store.delete(token)
    assert store.get(token) is None
