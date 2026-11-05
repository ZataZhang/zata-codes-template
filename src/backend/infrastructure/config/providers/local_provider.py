"""读取 config.toml 中本地运行时配置的 provider。"""

import tomllib
from pathlib import Path

from .protocol import ConfigProviderError, RuntimeConfigListener, RuntimeConfigSnapshot


class LocalConfigProvider:
    """从 ``config.toml`` 的 ``[runtime_config]`` 表读取配置。"""

    def __init__(self, config_file_path: Path) -> None:
        """初始化本地配置 provider。

        Args:
            config_file_path: 项目级 TOML 配置文件路径。
        """
        self._config_file_path = config_file_path

    async def load(self) -> RuntimeConfigSnapshot:
        """返回本地配置快照；缺少该表时返回空配置。"""
        if not self._config_file_path.is_file():
            return {}
        try:
            with open(self._config_file_path, "rb") as config_file:
                toml_document: dict[str, object] = tomllib.load(config_file)
        except (OSError, tomllib.TOMLDecodeError) as config_error:
            raise ConfigProviderError(
                f"无法读取本地运行时配置文件：{self._config_file_path}"
            ) from config_error

        runtime_config: object = toml_document.get("runtime_config", {})
        if not isinstance(runtime_config, dict):
            raise ConfigProviderError("config.toml 的 [runtime_config] 必须是 TOML 表。")
        return runtime_config

    async def subscribe(self, listener: RuntimeConfigListener) -> None:  # noqa: ARG002
        """本地 TOML provider 不支持进程内热更新。"""

    async def close(self) -> None:
        """本地 TOML provider 不持有外部资源。"""
