"""系统设置键值数据访问抽象端口。"""

from __future__ import annotations

from typing import Protocol


class SystemSettingRepository(Protocol):
    """为后端系统级 JSON 设置提供最小读写契约。"""

    def get(self, key: str) -> str | None:
        """按键读取 JSON 文本；只有键不存在时返回 None。

        Args:
            key (str): 系统设置键。

        Returns:
            str | None: 持久化的 JSON 文本；键不存在返回 None。
        """
        ...

    def put(self, key: str, value_json: str) -> None:
        """写入或更新 JSON 文本。

        Args:
            key (str): 系统设置键。
            value_json (str): 已序列化的 JSON 文本。
        """
        ...


__all__ = ["SystemSettingRepository"]
