"""配置文件 - 使用 pydantic-settings 集中管理所有配置。

支持三层配置源（优先级从高到低）：
1. 环境变量 / .env / .env.local
2. config.toml（非敏感配置）
3. 代码中的默认值
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, MutableMapping
from urllib.parse import quote_plus

from pydantic import Field, SecretStr

if TYPE_CHECKING:
    from langchain_core.language_models import BaseLanguageModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

_SETTINGS_FILE_PATH: Path = Path(__file__).resolve()
_CONFIG_DIR_PATH: Path = _SETTINGS_FILE_PATH.parent
_INFRASTRUCTURE_DIR_PATH: Path = _CONFIG_DIR_PATH.parent
_BACKEND_DIR_PATH: Path = _INFRASTRUCTURE_DIR_PATH.parent
_SOURCE_DIR_PATH: Path = _BACKEND_DIR_PATH.parent
_PROJECT_ROOT_PATH: Path = _SOURCE_DIR_PATH.parent
_TOML_CONFIG_FILE_PATH: Path = _PROJECT_ROOT_PATH / "config.toml"


def _load_toml_section_data(section_name: str) -> dict[str, Any]:
    """从 config.toml 加载指定 section 的配置。

    Args:
        section_name: TOML section 名称。

    Returns:
        section 内容字典，文件不存在或 section 不存在时返回空 dict。
    """
    if not _TOML_CONFIG_FILE_PATH.is_file():
        return {}
    try:
        with open(_TOML_CONFIG_FILE_PATH, "rb") as toml_file:
            toml_data: dict[str, Any] = tomllib.load(toml_file)
        return toml_data.get(section_name, {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


class _TomlSectionSource(PydanticBaseSettingsSource):
    """从 config.toml 指定 section 读取配置的自定义源。"""

    def __init__(self, settings_cls: type[BaseSettings], section_name: str) -> None:
        super().__init__(settings_cls)
        self._section_data: dict[str, Any] = _load_toml_section_data(section_name)

    def get_field_value(
        self,
        field: Any,  # noqa: ARG002
        field_name: str,
    ) -> tuple[Any, str, bool]:
        field_value: Any = self._section_data.get(field_name)
        return field_value, field_name, False

    def __call__(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field_name in self.settings_cls.model_fields:
            field_value: Any = self._section_data.get(field_name)
            if field_value is not None:
                result[field_name] = field_value
        return result


class DatabaseSettings(BaseSettings):
    """数据库连接配置（非敏感部分）。"""

    model_config = SettingsConfigDict(env_prefix="DB_")

    backend: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    name: str = "app_database"
    driver: str = "psycopg2"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "database")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class ObservabilitySettings(BaseSettings):
    """可观测性配置 - 支持独立开关和平台无关的服务标识。"""

    model_config = SettingsConfigDict(
        env_prefix="OBSERVABILITY_",
        extra="ignore",
    )

    enabled: bool = Field(default=True)
    metrics_enabled: bool = Field(default=True)
    request_id_enabled: bool = Field(default=True)
    log_format: str = Field(default="text")
    service_name: str = Field(default="zata-codes-template-backend")
    service_version: str = Field(default="0.1.0")
    deployment_environment: str = Field(default="development")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_source: _TomlSectionSource = _TomlSectionSource(
            settings_cls, "observability"
        )
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class AppSettings(BaseSettings):
    """应用主配置 - 聚合所有子配置。"""

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT_PATH / ".env", _PROJECT_ROOT_PATH / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="app", validation_alias="NAME")
    log_level: str = Field(default="INFO")

    postgres_user: str = ""
    postgres_password: SecretStr = SecretStr("")
    database_url: str = ""
    db_migration_mode: str = Field(default="auto")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)

    base_dir: Path = _PROJECT_ROOT_PATH
    log_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT_PATH / "logs")
    log_file: Path = Field(
        default_factory=lambda: _PROJECT_ROOT_PATH / "logs" / "app.log"
    )

    @property
    def resolved_database_url(self) -> str:
        """解析最终 DATABASE_URL：env var > TOML + credentials > default。"""
        if self.database_url and self.database_url.strip():
            return self.database_url.strip()

        db_config: DatabaseSettings = self.database
        encoded_user: str = quote_plus(self.postgres_user) if self.postgres_user else ""
        raw_password: str = self.postgres_password.get_secret_value()
        encoded_password: str = quote_plus(raw_password) if raw_password else ""

        credentials_part: str = ""
        if encoded_user or encoded_password:
            credentials_part = f"{encoded_user}:{encoded_password}"

        netloc: str = (
            f"{credentials_part}@{db_config.host}"
            if credentials_part
            else db_config.host
        )

        resolved_url: str = f"{db_config.backend}+{db_config.driver}://{netloc}:{db_config.port}/{db_config.name}"
        return resolved_url

    def ensure_log_directory(self) -> None:
        """确保日志目录存在。"""
        self.log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "app")
        return (
            env_settings,
            dotenv_settings,
            toml_source,
            init_settings,
        )


class ModelConfigError(RuntimeError):
    """当 provider 配置或调用前置条件不满足时抛出的异常。

    例如：模型名格式错（缺少 provider 前缀）、provider 未在 ``[providers]`` 中
    声明、缺少 ``base_url``，或对应的 API key 环境变量缺失。
    """


@dataclass(frozen=True)
class ProviderEndpoint:
    """单个 provider 对应的 OpenAI 协议端点描述。

    Attributes:
        provider_name (str): provider 标识（与配置文件中的键一致）。
        base_url (str): OpenAI 协议端点的基础 URL。
        api_key (str): 已经解析好的 API 密钥。
        extra (Mapping[str, Any]): 透传给 ``ChatOpenAI`` 的额外关键字参数。
    """

    provider_name: str
    base_url: str
    api_key: str
    extra: Mapping[str, Any]


@lru_cache(maxsize=4)
def load_providers_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """加载 ``config.toml`` 中的 ``[providers]`` section。

    每个子表（``[providers.<provider-name>]``）描述一个 OpenAI 协议端点：
    ``base_url``、``api_key_env``，以及可选的 ``extra`` 子表。

    Args:
        config_path (str | Path | None): 可选的 TOML 文件路径覆盖；缺省为仓库根
            的 ``config.toml``。

    Returns:
        dict[str, Any]: 形如 ``{"openai": {"base_url": ..., "api_key_env": ...}}``
        的 provider 条目映射；若 section 缺失则返回空 dict。

    Raises:
        FileNotFoundError: 当显式传入的 ``config_path`` 不存在时抛出。
    """

    resolved_toml_path: Path = (
        Path(config_path) if config_path else _TOML_CONFIG_FILE_PATH
    )
    if not resolved_toml_path.is_file():
        if config_path is not None:
            raise FileNotFoundError(
                f"Providers config file not found: {resolved_toml_path}"
            )
        return {}

    with open(resolved_toml_path, "rb") as toml_file_handle:
        raw_toml_data: dict[str, Any] = tomllib.load(toml_file_handle)

    providers_section: Any = raw_toml_data.get("providers", {})
    if not isinstance(providers_section, dict):
        return {}
    return providers_section


def _lookup_provider(
    provider_name: str,
    providers_config: Mapping[str, Any],
) -> Mapping[str, Any]:
    """根据 provider 名在配置中查找条目（大小写不敏感、忽略首尾空白）。

    Args:
        provider_name (str): provider 标识符。
        providers_config (Mapping[str, Any]): 已加载的 provider 配置。

    Returns:
        Mapping[str, Any]: 对应的 provider 条目。

    Raises:
        ModelConfigError: 如果 provider 名未在配置中声明。
    """

    normalized_provider_name: str = provider_name.strip().lower()
    for declared_provider_name, provider_entry in providers_config.items():
        if (
            declared_provider_name.strip().lower() == normalized_provider_name
            and isinstance(provider_entry, Mapping)
        ):
            return provider_entry
    raise ModelConfigError(
        f"Provider '{provider_name}' is not declared in providers config."
    )


def list_providers(
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """返回配置中所有可用 provider 的元数据列表。

    Args:
        config_path (str | Path | None): 配置文件路径的覆盖。

    Returns:
        list[dict[str, Any]]: 形如 ``{"name": ..., "base_url": ..., ...}`` 的
        条目列表。
    """

    raw_providers_config: dict[str, Any] = load_providers_config(config_path)
    listed_providers: list[dict[str, Any]] = []
    for provider_name, provider_entry in raw_providers_config.items():
        if not isinstance(provider_entry, Mapping):
            continue
        listed_providers.append({"name": provider_name, **dict(provider_entry)})
    return listed_providers


def resolve_provider_endpoint(
    provider_name: str,
    *,
    config_path: str | Path | None = None,
) -> ProviderEndpoint:
    """解析 provider 对应的 OpenAI 协议端点。

    解析顺序：

    1. 在 ``[providers]`` 中按 provider 名查表（大小写不敏感）
    2. 读取 ``base_url``（必填）
    3. 读取 ``api_key_env``（必填）指向的环境变量
    4. 读取可选 ``extra`` 字段，透传给 ``ChatOpenAI``

    Args:
        provider_name (str): provider 名称。
        config_path (str | Path | None): 可选的配置文件路径覆盖。

    Returns:
        ProviderEndpoint: 已解析好的端点描述。

    Raises:
        ModelConfigError: 当 provider 未声明、缺少 ``base_url`` 或 API 密钥无法
            解析时抛出。
    """

    providers_config: dict[str, Any] = load_providers_config(config_path)
    provider_entry: Mapping[str, Any] = _lookup_provider(
        provider_name, providers_config
    )

    base_url_value: Any = provider_entry.get("base_url")
    if not isinstance(base_url_value, str) or not base_url_value:
        raise ModelConfigError(
            f"Provider '{provider_name}' is missing a string 'base_url' in providers config."
        )

    api_key_env_name: Any = provider_entry.get("api_key_env")
    if not isinstance(api_key_env_name, str) or not api_key_env_name:
        raise ModelConfigError(
            f"Provider '{provider_name}' is missing 'api_key_env' in providers config."
        )
    env_api_key_value: str | None = os.getenv(api_key_env_name)
    if not env_api_key_value:
        raise ModelConfigError(
            f"Environment variable '{api_key_env_name}' for provider '{provider_name}' is empty or unset."
        )

    extra_value: Any = provider_entry.get("extra", {})
    if not isinstance(extra_value, Mapping):
        raise ModelConfigError(
            f"Provider '{provider_name}' field 'extra' must be a mapping if provided."
        )

    return ProviderEndpoint(
        provider_name=provider_name,
        base_url=base_url_value,
        api_key=env_api_key_value,
        extra=dict(extra_value),
    )


def create_chat_model(
    model_name: str,
    *,
    temperature: float = 0.0,
    config_path: str | Path | None = None,
    client_kwargs: Mapping[str, Any] | None = None,
) -> BaseLanguageModel:
    """根据 ``provider/model_id`` 形式的模型名实例化 OpenAI 协议聊天客户端。

    解析顺序：

    1. 按第一个 ``/`` 拆分 ``model_name`` → ``(provider_name, model_id)``
    2. 在 ``[providers]`` 中查找 ``provider_name`` 端点
    3. 读取 ``base_url`` 和对应的 API key（必填）
    4. 透传 provider 的 ``extra`` 表与 ``client_kwargs`` 给 ``ChatOpenAI``

    Args:
        model_name (str): ``provider/model_id`` 形式的模型名（例
            ``"openai/gpt-4o"``、``"dashscope/qwen3-max"``）。
        temperature (float): 传递给底层客户端的温度值。
        config_path (str | Path | None): 可选的配置路径覆盖。
        client_kwargs (Mapping[str, Any] | None): 额外的 ``ChatOpenAI`` 关键字参数；
            优先级高于配置文件 ``extra``。

    Returns:
        BaseLanguageModel: 已配置好的 ``ChatOpenAI`` 实例。

    Raises:
        ModelConfigError: 当 ``model_name`` 格式错、provider 未声明、缺少
            ``base_url`` 或 API key 无法解析时抛出。
        FileNotFoundError: 当配置路径不存在时抛出。
    """

    if not isinstance(model_name, str) or "/" not in model_name:
        raise ModelConfigError(
            f"Model name '{model_name}' must be in 'provider/model_id' form."
        )

    provider_name, model_id = model_name.split("/", 1)
    if not provider_name.strip() or not model_id.strip():
        raise ModelConfigError(
            f"Model name '{model_name}' must be in 'provider/model_id' form."
        )

    resolved_endpoint: ProviderEndpoint = resolve_provider_endpoint(
        provider_name,
        config_path=config_path,
    )

    chat_model_kwargs: MutableMapping[str, Any] = {
        "model": model_id,
        "temperature": temperature,
        "base_url": resolved_endpoint.base_url,
        "api_key": resolved_endpoint.api_key,
    }
    chat_model_kwargs.update(resolved_endpoint.extra)
    if client_kwargs:
        chat_model_kwargs.update(client_kwargs)

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(**chat_model_kwargs)


def _ensure_no_proxy_for_local_services() -> None:
    """确保本地服务（localhost/127.0.0.1）不经过系统 HTTP 代理。"""
    existing_no_proxy: str = os.getenv("NO_PROXY", "")
    local_hosts: set[str] = {"localhost", "127.0.0.1", "::1"}
    current_entries: set[str] = {
        entry.strip() for entry in existing_no_proxy.split(",") if entry.strip()
    }
    missing_entries: set[str] = local_hosts - current_entries

    if missing_entries:
        updated_no_proxy: str = ",".join(current_entries | local_hosts)
        os.environ["NO_PROXY"] = updated_no_proxy
        os.environ["no_proxy"] = updated_no_proxy


config: AppSettings = AppSettings()
config.ensure_log_directory()
_ensure_no_proxy_for_local_services()

__all__ = [
    "AppSettings",
    "DatabaseSettings",
    "ModelConfigError",
    "ObservabilitySettings",
    "ProviderEndpoint",
    "config",
    "create_chat_model",
    "list_providers",
    "load_providers_config",
    "resolve_provider_endpoint",
]
