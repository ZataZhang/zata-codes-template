"""服务端密钥引用解析端口。"""

from __future__ import annotations

from typing import Protocol


class SecretResolver(Protocol):
    """按部署方提供的密钥别名读取服务端密钥。"""

    def get_secret(self, alias: str) -> str | None:
        """按别名返回密钥值；未配置时返回 None。"""
        ...


__all__ = ["SecretResolver"]
