"""内存 Session 存储实现（线程安全，适用于单进程开发）。"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone

from backend.core.shared.interfaces.session_store import ISessionStore, SessionRecord

_SLIDING_WINDOW_DAYS: int = 15
_ABSOLUTE_MAX_DAYS: int = 60


def _now_utc() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class InMemorySessionStore(ISessionStore):
    """线程安全的内存 Session 存储，支持滑动窗口续期。"""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock: threading.Lock = threading.Lock()

    def create(self, user_id: str) -> str:
        """创建新 Session，初始有效期 15 天。"""
        token: str = uuid.uuid4().hex
        now: datetime = _now_utc()
        expires_at: datetime = now + timedelta(days=_SLIDING_WINDOW_DAYS)
        record = SessionRecord(
            token=token,
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
        )
        with self._lock:
            self._sessions[token] = record
        return token

    def get(self, token: str) -> SessionRecord | None:
        """获取 Session 记录，不触发续期。"""
        with self._lock:
            return self._sessions.get(token)

    def delete(self, token: str) -> None:
        """删除 Session。"""
        with self._lock:
            self._sessions.pop(token, None)

    def slide_expiration(self, token: str) -> SessionRecord | None:
        """获取 Session 并在滑动窗口规则下刷新过期时间。

        规则：
        - 15 天滑动窗口：每次活跃操作续期 15 天
        - 60 天绝对上限：从创建起最多存活 60 天
        """
        with self._lock:
            record = self._sessions.get(token)
            if record is None:
                return None

            now: datetime = _now_utc()

            # 检查是否已过当前过期时间
            if now >= record.expires_at:
                self._sessions.pop(token, None)
                return None

            # 检查是否超过绝对上限
            absolute_deadline: datetime = record.created_at + timedelta(
                days=_ABSOLUTE_MAX_DAYS
            )
            if now >= absolute_deadline:
                self._sessions.pop(token, None)
                return None

            # 计算新的过期时间：min(now + 15天, created_at + 60天)
            potential_expires: datetime = now + timedelta(days=_SLIDING_WINDOW_DAYS)
            new_expires: datetime = (
                potential_expires
                if potential_expires < absolute_deadline
                else absolute_deadline
            )

            updated_record = SessionRecord(
                token=record.token,
                user_id=record.user_id,
                created_at=record.created_at,
                expires_at=new_expires,
            )
            self._sessions[token] = updated_record
            return updated_record
