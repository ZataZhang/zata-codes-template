"""运行时配置 provider 的平台无关契约。"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol, TypeAlias

RuntimeConfigSnapshot: TypeAlias = Mapping[str, object]
RuntimeConfigListener: TypeAlias = Callable[[RuntimeConfigSnapshot], Awaitable[None]]


class ConfigProviderError(RuntimeError):
    """运行时配置 provider 初始化、读取或解析失败。"""


class ConfigProvider(Protocol):
    """提供配置快照和后续变更通知。"""

    async def load(self) -> RuntimeConfigSnapshot:
        """读取当前完整配置快照。"""

    async def subscribe(self, listener: RuntimeConfigListener) -> None:
        """订阅完整配置快照变更。"""

    async def close(self) -> None:
        """释放 provider 持有的客户端资源。"""
