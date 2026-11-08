"""Nacos 配置中心适配器。"""

import logging
from typing import Any

from backend.infrastructure.config.settings import ConfigProviderSettings

from .nacos_helpers import parse_nacos_config_document
from .protocol import ConfigProviderError, RuntimeConfigListener, RuntimeConfigSnapshot

_LOGGER: logging.Logger = logging.getLogger(__name__)


class NacosConfigProvider:
    """通过 Nacos Python SDK 读取并监听 JSON 配置文档。"""

    def __init__(self, settings: ConfigProviderSettings) -> None:
        """初始化 Nacos provider，但延迟创建网络客户端。

        Args:
            settings: Nacos 地址、Namespace、文档名称和凭据环境变量别名。
        """
        self._settings = settings
        self._config_client: Any | None = None
        self._config_param_type: Any | None = None

    async def load(self) -> RuntimeConfigSnapshot:
        """读取当前 Nacos 配置，并要求文档根节点为 JSON 对象。"""
        config_client, config_param_type = await self._get_config_client()
        try:
            config_content: str | None = await config_client.get_config(
                config_param_type(
                    data_id=self._settings.nacos_data_id,
                    group=self._settings.nacos_group,
                )
            )
        except Exception as config_error:  # noqa: BLE001
            raise ConfigProviderError(
                "读取 Nacos 配置失败；请确认应用账号有权读取指定 Namespace、Group 和 Data ID。"
            ) from config_error
        return self._parse_config_document(config_content)

    async def subscribe(self, listener: RuntimeConfigListener) -> None:
        """订阅 Nacos 文档更新；无效更新会被忽略并保留当前快照。"""
        config_client, _ = await self._get_config_client()

        async def on_config_changed(
            _namespace_id: str,
            group: str,
            data_id: str,
            config_content: str | None,
        ) -> None:
            try:
                config_snapshot: RuntimeConfigSnapshot = self._parse_config_document(config_content)
            except ConfigProviderError as config_error:
                _LOGGER.warning(
                    "忽略无效的 Nacos 配置更新 data_id=%s group=%s: %s",
                    data_id,
                    group,
                    config_error,
                )
                return
            await listener(config_snapshot)

        try:
            await config_client.add_listener(
                self._settings.nacos_data_id,
                self._settings.nacos_group,
                on_config_changed,
            )
        except Exception as listener_error:  # noqa: BLE001
            raise ConfigProviderError("订阅 Nacos 配置变更失败。") from listener_error

    async def close(self) -> None:
        """关闭 Nacos SDK 客户端。"""
        if self._config_client is None:
            return
        await self._config_client.shutdown()
        self._config_client = None
        self._config_param_type = None

    async def _get_config_client(self) -> tuple[Any, Any]:
        if self._config_client is not None and self._config_param_type is not None:
            return self._config_client, self._config_param_type

        try:
            from v2.nacos import ClientConfigBuilder, ConfigParam, NacosConfigService
        except ImportError as import_error:
            raise ConfigProviderError(
                "启用 Nacos provider 需要安装依赖 nacos-sdk-python。"
            ) from import_error

        client_config = (
            ClientConfigBuilder()
            .server_address(self._settings.nacos_server_addr.strip())
            .namespace_id(self._settings.nacos_namespace_id.strip())
            .username(self._settings.nacos_username)
            .password(self._settings.nacos_password.get_secret_value())
            .build()
        )
        try:
            self._config_client = await NacosConfigService.create_config_service(client_config)
        except Exception as client_error:  # noqa: BLE001
            raise ConfigProviderError(
                "初始化 Nacos 客户端失败；请确认地址及 8848 HTTP、9848 gRPC 端口可达。"
            ) from client_error
        self._config_param_type = ConfigParam
        return self._config_client, self._config_param_type

    @staticmethod
    def _parse_config_document(config_content: str | None) -> RuntimeConfigSnapshot:
        return parse_nacos_config_document(config_content)
