"""配置文件 - 使用 pydantic-settings 集中管理所有配置。

支持三层配置源（优先级从高到低）：
1. 环境变量 / .env / .env.local
2. config.toml（非敏感配置）
3. 代码中的默认值

需要调用大模型的派生项目，用 ``.env`` 的 ``MODEL_BASE_URL`` / ``MODEL_API_KEY`` /
``MODEL_NAME`` 三件套声明端点，经 :func:`load_primary_model_settings` 读取。模板
只做这层解析，不内置 LLM 客户端，也不维护 provider 目录。

新增配置项约定：
- 非敏感默认值放到 ``config.toml`` 对应 section。
- 密钥 / Token / 密码等敏感值本身不得在 ``config.toml`` 中写死；应只在
  ``config.toml`` 中保留「给密钥类的配置变量」。
- 新增给密钥类的配置变量时，同步在 ``.env.example`` 中保留未注释的空值并说明
  用途。非密钥类变量应以 ``# KEY=默认值`` 的注释形式作为示例；可能携带凭据的
  连接字符串（如 ``DATABASE_URL``、``REDIS_URL``）按密钥类处理，同样保留未注释
  的空值。
- 默认未填写 env 时，配置系统仍需能正常加载；若该密钥不可或缺，应在首次
  使用时抛出清晰错误，而不是在模块导入阶段失败。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from dotenv import dotenv_values
from pydantic import Field, SecretStr
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

# Pydantic 会把 .env/.env.local 加载到设置字段，但部分配置解析阶段会通过
# os.getenv 读取任意的环境变量。因此需要先把同一份环境文件写入
# os.environ，使这些变量可见；Shell 环境变量仍保持最高优先级。
_dotenv_loaded_values: dict[str, str | None] = {}
_dotenv_loaded_values.update(dotenv_values(_PROJECT_ROOT_PATH / ".env"))
_dotenv_loaded_values.update(dotenv_values(_PROJECT_ROOT_PATH / ".env.local"))
for _dotenv_key, _dotenv_value in _dotenv_loaded_values.items():
    if _dotenv_value is not None and not os.environ.get(_dotenv_key):
        os.environ[_dotenv_key] = _dotenv_value


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
        """自定义 database 设置的 pydantic 配置源优先级。"""
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
    service_name: str = Field(default="app-backend")
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
        """自定义 observability 设置的 pydantic 配置源优先级。"""
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "observability")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class RedisSettings(BaseSettings):
    """Redis 连接配置（用于会话存储）。"""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=(_PROJECT_ROOT_PATH / ".env", _PROJECT_ROOT_PATH / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "redis://localhost:6379/0"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """自定义 Redis 设置的 pydantic 配置源优先级。"""
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "redis")
        return (
            env_settings,
            dotenv_settings,
            toml_source,
            init_settings,
        )


class AuthSettings(BaseSettings):
    """认证与会话配置：会话窗口与初始管理员种子（Cookie 名为接入层常量）。"""

    model_config = SettingsConfigDict(
        env_prefix="AUTH_",
        env_file=(_PROJECT_ROOT_PATH / ".env", _PROJECT_ROOT_PATH / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    admin_bootstrap_username: str = ""
    admin_bootstrap_password: SecretStr = SecretStr("")
    session_sliding_days: int = 15
    session_absolute_days: int = 60

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """自定义 auth 设置的 pydantic 配置源优先级。"""
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "auth")
        return (
            env_settings,
            dotenv_settings,
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

    app_name: str = Field(default="app")
    log_level: str = Field(default="INFO")

    postgres_user: str = ""
    postgres_password: SecretStr = SecretStr("")
    database_url: str = ""
    db_migration_mode: str = Field(default="auto")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)

    base_dir: Path = _PROJECT_ROOT_PATH
    log_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT_PATH / "logs")
    log_file: Path = Field(default_factory=lambda: _PROJECT_ROOT_PATH / "logs" / "app.log")

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

        netloc: str = f"{credentials_part}@{db_config.host}" if credentials_part else db_config.host

        resolved_url: str = (
            f"{db_config.backend}+{db_config.driver}://{netloc}:{db_config.port}/{db_config.name}"
        )
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
        """自定义 app 设置的 pydantic 配置源优先级。"""
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "app")
        return (
            env_settings,
            dotenv_settings,
            toml_source,
            init_settings,
        )


# ---------------------------------------------------------------------------
# 主模型配置（厂商无关）
# ---------------------------------------------------------------------------
# 模板只负责把 `.env` 里的端点三件套读出来，不内置任何 LLM 客户端，也不维护
# provider 目录——那属于派生项目的业务选择。

PRIMARY_MODEL_BASE_URL_ENV: str = "MODEL_BASE_URL"
PRIMARY_MODEL_API_KEY_ENV: str = "MODEL_API_KEY"
PRIMARY_MODEL_NAME_ENV: str = "MODEL_NAME"


class PrimaryModelConfigError(RuntimeError):
    """主模型环境变量只声明了一部分时抛出。

    三件套要么齐全、要么全空；缺一半通常意味着复制 ``.env.example`` 时漏填，
    静默回退会让调用方在真正发请求时才收到含义不明的 401 或 404。
    """


@dataclass(frozen=True)
class PrimaryModelSettings:
    """``.env`` 声明的主模型端点。

    Attributes:
        base_url (str): OpenAI 协议端点的基础 URL，通常以 ``/v1`` 结尾。
        api_key (SecretStr): 端点密钥；包成 ``SecretStr`` 避免误打进日志。
        model_name (str): 模型 id，原样发送给端点，允许自带斜杠。
    """

    base_url: str
    api_key: SecretStr
    model_name: str


def load_primary_model_settings() -> PrimaryModelSettings | None:
    """读取 ``.env`` 的主模型三件套。

    模板不假设派生项目用哪个 SDK：拿到这三个值后，接 ``langchain_openai``
    的 ``ChatOpenAI``、官方 ``openai.OpenAI`` 或任意 OpenAI 协议兼容客户端都可以。
    需要同时接多个端点的项目，在此基础上自建 provider 注册表。

    Returns:
        PrimaryModelSettings | None: 三件套齐全时返回端点配置；三者都未设置时
        返回 ``None``，表示本项目不使用模型。

    Raises:
        PrimaryModelConfigError: 三件套只设置了一部分时抛出，错误体列出缺失的
            变量名。
    """
    configured_base_url: str = os.getenv(PRIMARY_MODEL_BASE_URL_ENV, "").strip()
    configured_api_key: str = os.getenv(PRIMARY_MODEL_API_KEY_ENV, "").strip()
    configured_model_name: str = os.getenv(PRIMARY_MODEL_NAME_ENV, "").strip()

    missing_env_names: list[str] = [
        env_name
        for env_name, env_value in (
            (PRIMARY_MODEL_BASE_URL_ENV, configured_base_url),
            (PRIMARY_MODEL_API_KEY_ENV, configured_api_key),
            (PRIMARY_MODEL_NAME_ENV, configured_model_name),
        )
        if not env_value
    ]
    if len(missing_env_names) == 3:
        return None
    if missing_env_names:
        raise PrimaryModelConfigError(
            f"主模型环境变量不完整，缺少：{'、'.join(missing_env_names)}。请同时设置 "
            f"{PRIMARY_MODEL_BASE_URL_ENV} / {PRIMARY_MODEL_API_KEY_ENV} / "
            f"{PRIMARY_MODEL_NAME_ENV}，或三者都留空表示本项目不使用模型。"
        )

    return PrimaryModelSettings(
        base_url=configured_base_url,
        api_key=SecretStr(configured_api_key),
        model_name=configured_model_name,
    )


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
    "PRIMARY_MODEL_API_KEY_ENV",
    "PRIMARY_MODEL_BASE_URL_ENV",
    "PRIMARY_MODEL_NAME_ENV",
    "AppSettings",
    "AuthSettings",
    "DatabaseSettings",
    "ObservabilitySettings",
    "PrimaryModelConfigError",
    "PrimaryModelSettings",
    "RedisSettings",
    "config",
    "load_primary_model_settings",
]
