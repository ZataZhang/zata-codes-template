"""运行时配置来源适配器。"""

from .factory import build_config_provider
from .protocol import (
    ConfigProvider,
    ConfigProviderError,
    RuntimeConfigListener,
    RuntimeConfigSnapshot,
)

__all__ = [
    "ConfigProvider",
    "ConfigProviderError",
    "RuntimeConfigListener",
    "RuntimeConfigSnapshot",
    "build_config_provider",
]
