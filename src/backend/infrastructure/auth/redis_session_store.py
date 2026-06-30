"""基于 Redis 的会话存储实现（按 key 前缀隔离认证域命名空间）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from redis import Redis

from backend.core.shared.interfaces.session_store import (
    ISessionStore,
    SessionRecord,
)

_SECONDS_PER_DAY: int = 60 * 60 * 24


def _now_utc() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class RedisSessionStore(ISessionStore):
    """Redis 会话存储，支持滑动窗口续期与命名空间前缀隔离。

    同一份实现可被实例化多次，通过不同的 ``key_prefix`` 把 public 与 admin
    的会话隔离到互不重叠的 key 空间；一个域的会话 token 永远查不到另一个
    域的会话记录。过期由 Redis TTL 兜底，绝对上限由记录内创建时间约束。
    """

    def __init__(
        self,
        *,
        redis_client: Redis,
        key_prefix: str,
        sliding_window_days: int = 15,
        absolute_max_days: int = 60,
    ) -> None:
        """初始化 Redis 会话存储。

        Args:
            redis_client (Redis): 同步 Redis 客户端（需 ``decode_responses=True``）。
            key_prefix (str): 会话 key 前缀，用于隔离认证域命名空间。
            sliding_window_days (int): 滑动窗口天数，每次活跃续期。
            absolute_max_days (int): 自创建起的绝对存活上限天数。
        """
        self._redis = redis_client
        self._key_prefix = key_prefix
        self._sliding_window_days = sliding_window_days
        self._absolute_max_days = absolute_max_days

    def create(self, user_id: str) -> str:
        """创建新会话，初始有效期为滑动窗口天数。"""
        token: str = uuid.uuid4().hex
        now: datetime = _now_utc()
        expires_at: datetime = now + timedelta(days=self._sliding_window_days)
        record = SessionRecord(
            token=token,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
        )
        self._persist(record, ttl_seconds=self._sliding_window_days * _SECONDS_PER_DAY)
        return token

    def get(self, token: str) -> SessionRecord | None:
        """读取会话记录，不触发续期。"""
        return self._read(token)

    def delete(self, token: str) -> None:
        """删除会话。"""
        self._redis.delete(self._build_key(token))

    def slide_expiration(self, token: str) -> SessionRecord | None:
        """读取会话并在滑动窗口规则下刷新过期时间。

        规则与内存实现一致：滑动窗口续期，但不超过创建起的绝对上限；
        超过任一界限即删除并视为失效。
        """
        record: SessionRecord | None = self._read(token)
        if record is None:
            return None

        now: datetime = _now_utc()
        absolute_deadline: datetime = record.created_at + timedelta(days=self._absolute_max_days)
        if now >= record.expires_at or now >= absolute_deadline:
            self._redis.delete(self._build_key(token))
            return None

        potential_expires: datetime = now + timedelta(days=self._sliding_window_days)
        new_expires: datetime = (
            potential_expires if potential_expires < absolute_deadline else absolute_deadline
        )
        updated_record = SessionRecord(
            token=record.token,
            user_id=record.user_id,
            created_at=record.created_at,
            expires_at=new_expires,
        )
        ttl_seconds: int = max(1, int((new_expires - now).total_seconds()))
        self._persist(updated_record, ttl_seconds=ttl_seconds)
        return updated_record

    def _build_key(self, token: str) -> str:
        """拼接带命名空间前缀的 Redis key。"""
        return f"{self._key_prefix}{token}"

    def _persist(self, record: SessionRecord, ttl_seconds: int) -> None:
        """把会话记录写入 Redis 并设置 TTL。"""
        payload: str = json.dumps(
            {
                "user_id": record.user_id,
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
            }
        )
        self._redis.set(self._build_key(record.token), payload, ex=ttl_seconds)

    def _read(self, token: str) -> SessionRecord | None:
        """从 Redis 读取并反序列化会话记录。"""
        raw_payload = self._redis.get(self._build_key(token))
        if raw_payload is None:
            return None
        data: dict[str, str] = json.loads(raw_payload)
        return SessionRecord(
            token=token,
            user_id=data["user_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )
