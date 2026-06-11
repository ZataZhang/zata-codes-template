"""Session 存储抽象接口。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class SessionRecord:
    """会话存储记录。"""

    token: str
    user_id: str
    created_at: datetime
    expires_at: datetime


class ISessionStore(Protocol):
    """Session 存储抽象接口，支持滑动窗口续期。"""

    def create(self, user_id: str) -> str:
        """为指定用户创建新 Session，返回随机 token。"""
        ...

    def get(self, token: str) -> SessionRecord | None:
        """根据 token 获取 Session 记录；不触发滑动续期。"""
        ...

    def delete(self, token: str) -> None:
        """删除指定 Session。"""
        ...

    def slide_expiration(self, token: str) -> SessionRecord | None:
        """获取 Session 并在滑动窗口规则下刷新过期时间。

        Returns:
            更新后的 SessionRecord；若已过期或不存在则返回 None。
        """
        ...
