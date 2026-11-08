"""根据启动配置构造运行时配置 provider。"""

from pathlib import Path
from urllib.parse import SplitResult, urlsplit

from backend.infrastructure.config.settings import ConfigProviderSettings

from .local_provider import LocalConfigProvider
from .nacos_http_provider import NacosHttpConfigProvider
from .nacos_provider import NacosConfigProvider
from .protocol import ConfigProvider, ConfigProviderError


def build_config_provider(
    settings: ConfigProviderSettings,
    *,
    config_file_path: Path,
) -> ConfigProvider:
    """按本地配置及 Nacos 地址自动选择运行时配置 provider。

    Args:
        settings: provider 选择及连接参数。
        config_file_path: 本地配置文件路径，供 ``local`` provider 使用。

    Returns:
        已配置但尚未连接的运行时配置 provider。

    Raises:
        ConfigProviderError: Nacos 必需参数缺失或 provider 名称不支持。
    """
    if settings.provider == "local" and not settings.nacos_server_addr.strip():
        return LocalConfigProvider(config_file_path)

    missing_nacos_values: list[str] = [
        env_name
        for env_name, env_value in (
            ("NACOS_SERVER_ADDR", settings.nacos_server_addr.strip()),
            (settings.nacos_username_env, settings.nacos_username),
            (settings.nacos_password_env, settings.nacos_password.get_secret_value()),
        )
        if not env_value
    ]
    if missing_nacos_values:
        raise ConfigProviderError(
            "启用 Nacos provider 时必须填写：" + ", ".join(missing_nacos_values)
        )
    server_address: str = settings.nacos_server_addr.strip()
    if "://" not in server_address:
        if server_address.lower().startswith(("http:", "https:")):
            raise ConfigProviderError("NACOS_SERVER_ADDR 的 HTTP(S) URL 格式无效。")
        return NacosConfigProvider(settings)
    try:
        server_address_parts: SplitResult = urlsplit(server_address)
    except ValueError as address_error:
        raise ConfigProviderError("NACOS_SERVER_ADDR 格式无效。") from address_error
    if server_address_parts.scheme in {"http", "https"}:
        if not server_address_parts.netloc:
            raise ConfigProviderError("NACOS_SERVER_ADDR 必须包含有效的 HTTP 主机名。")
        if (
            server_address_parts.path not in {"", "/"}
            or server_address_parts.query
            or server_address_parts.fragment
        ):
            raise ConfigProviderError(
                "NACOS_SERVER_ADDR 仅填写 HTTP(S) 基础地址，不要附加路径或查询参数。"
            )
        return NacosHttpConfigProvider(settings)
    raise ConfigProviderError("NACOS_SERVER_ADDR 仅支持 http(s) URL 或 host:port 格式。")
