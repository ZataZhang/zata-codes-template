"""配置文件 - 使用 pydantic-settings 集中管理所有配置。

支持三层配置源（优先级从高到低）：
1. 环境变量 / .env / .env.local
2. config.toml（非敏感配置）
3. 代码中的默认值
"""

import os
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from pydantic import Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

# ==========================================
# 路径常量定义
# ==========================================

_SETTINGS_FILE_PATH: Path = Path(__file__).resolve()
_UTILS_DIR_PATH: Path = _SETTINGS_FILE_PATH.parent
_PROJECT_ROOT_PATH: Path = _UTILS_DIR_PATH.parent
_TOML_CONFIG_FILE_PATH: Path = _PROJECT_ROOT_PATH / "config.toml"


# ==========================================
# TOML 配置源实现
# ==========================================


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
    except Exception:
        return {}


class _TomlSectionSource(PydanticBaseSettingsSource):
    """从 config.toml 指定 section 读取配置的自定义源。

    Attributes:
        _section_data: TOML section 数据字典。
    """

    def __init__(self, settings_cls: type[BaseSettings], section_name: str) -> None:
        """初始化 TOML section 源。

        Args:
            settings_cls: Pydantic Settings 类。
            section_name: TOML 文件中的 section 名称。
        """
        super().__init__(settings_cls)
        self._section_data: dict[str, Any] = _load_toml_section_data(section_name)

    def get_field_value(
        self,
        field: Any,  # noqa: ARG002
        field_name: str,
    ) -> tuple[Any, str, bool]:
        """获取指定字段的值。

        Args:
            field: Pydantic 字段信息（未使用）。
            field_name: 字段名称。

        Returns:
            三元组: (字段值, 字段名, 是否为复杂类型)。
        """
        field_value: Any = self._section_data.get(field_name)
        return field_value, field_name, False

    def __call__(self) -> dict[str, Any]:
        """返回 section 中与模型字段匹配的配置。

        Returns:
            匹配的配置键值对字典。
        """
        result: dict[str, Any] = {}
        for field_name in self.settings_cls.model_fields:
            field_value: Any = self._section_data.get(field_name)
            if field_value is not None:
                result[field_name] = field_value
        return result


# ==========================================
# 子配置类定义
# ==========================================


class DatabaseSettings(BaseSettings):
    """数据库连接配置（非敏感部分）。

    Attributes:
        backend: 数据库后端类型，如 postgresql, mysql。
        host: 数据库主机地址。
        port: 数据库端口。
        name: 数据库名称。
        driver: 数据库驱动，如 psycopg2, pymysql。
    """

    model_config = SettingsConfigDict(env_prefix="DB_")

    backend: str = "postgresql"
    host: str = "localhost"
    port: int = 5432
    name: str = "chameleon_meta"
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
        """配置源优先级：env vars > TOML [database] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "database")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class ChatModelSettings(BaseSettings):
    """默认聊天模型配置。

    Attributes:
        name: 模型名称，如 qwen-flash, gpt-4。
        provider: 模型提供商，如 dashscope, openai。
        temperature: 采样温度，0.0-2.0 之间。
    """

    model_config = SettingsConfigDict(env_prefix="CHAT_MODEL_")

    name: str = "qwen-flash"
    provider: str = "dashscope"
    temperature: float = 0.2

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """配置源优先级：env vars > TOML [chat_model] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "chat_model")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class MinioSettings(BaseSettings):
    """MinIO 对象存储配置（非敏感部分）。

    Attributes:
        endpoint: MinIO 服务端点，如 localhost:9000。
        secure: 是否使用 HTTPS。
        bucket_raw_documents: 原始文档存储桶名称。
    """

    model_config = SettingsConfigDict(env_prefix="MINIO_")

    endpoint: str = "localhost:9000"
    secure: bool = False
    bucket_raw_documents: str = "raw-documents"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """配置源优先级：env vars > TOML [minio] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "minio")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class QdrantSettings(BaseSettings):
    """Qdrant 向量数据库配置。

    Attributes:
        host: Qdrant 服务主机。
        port: Qdrant 服务端口。
        collection_name: 向量集合名称。
    """

    model_config = SettingsConfigDict(env_prefix="QDRANT_")

    host: str = "localhost"
    port: int = 6333
    collection_name: str = "document_vectors"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """配置源优先级：env vars > TOML [qdrant] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "qdrant")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class EmbeddingSettings(BaseSettings):
    """Embedding 模型配置。

    Attributes:
        model: 模型名称，如 sentence-transformers/all-MiniLM-L6-v2。
        dim: 向量维度。
        offline_mode: 是否使用离线模式。
        model_dir: 项目本地模型存储目录，相对于项目根目录。
    """

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_")

    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    dim: int = 384
    offline_mode: bool = True
    model_dir: str = "resources/models"

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """配置源优先级：env vars > TOML [embedding] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "embedding")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class ChunkingSettings(BaseSettings):
    """文档分块配置。

    Attributes:
        size: 分块大小（字符数）。
        overlap: 分块重叠（字符数）。
    """

    model_config = SettingsConfigDict(env_prefix="CHUNK_")

    size: int = 512
    overlap: int = 50

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """配置源优先级：env vars > TOML [chunking] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "chunking")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


class TimeoutSettings(BaseSettings):
    """超时配置（秒）。

    Attributes:
        embedding_model_load_seconds: 模型加载超时。
        ingestion_document_seconds: 单文档处理超时。
        ingestion_job_seconds: 整体任务超时。
        minio_seconds: MinIO 读取超时。
    """

    model_config = SettingsConfigDict(env_prefix="TIMEOUT_")

    embedding_model_load_seconds: int = 300
    ingestion_document_seconds: int = 600
    ingestion_job_seconds: int = 7200
    minio_seconds: int = 60

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,  # noqa: ARG003
        file_secret_settings: PydanticBaseSettingsSource,  # noqa: ARG003
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """配置源优先级：env vars > TOML [timeouts] > defaults。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源（未使用）。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "timeouts")
        return (
            env_settings,
            toml_source,
            init_settings,
        )


# ==========================================
# 主配置类
# ==========================================


class AppSettings(BaseSettings):
    """应用主配置 - 聚合所有子配置。

    Attributes:
        app_name: 应用名称。
        log_level: 日志级别。
        postgres_user: PostgreSQL 用户名。
        postgres_password: PostgreSQL 密码。
        database_url: 完整数据库 URL 覆盖。
        minio_access_key: MinIO 访问密钥。
        minio_secret_key: MinIO 密钥。
        minio_root_user: Docker MinIO root 用户。
        minio_root_password: Docker MinIO root 密码。
        database: 数据库子配置。
        chat_model: 聊天模型子配置。
        minio: MinIO 子配置。
        qdrant: Qdrant 子配置。
        embedding: Embedding 子配置。
        chunking: 分块子配置。
        timeouts: 超时子配置。
        base_dir: 项目根目录。
        log_dir: 日志目录。
        log_file: 日志文件路径。
    """

    model_config = SettingsConfigDict(
        env_file=(_PROJECT_ROOT_PATH / ".env", _PROJECT_ROOT_PATH / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 顶层配置
    app_name: str = Field(default="app", validation_alias="NAME")
    log_level: str = Field(default="INFO")

    # 密钥（仅从 env vars / .env 读取）
    postgres_user: str = ""
    postgres_password: SecretStr = SecretStr("")
    database_url: str = ""
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: SecretStr = SecretStr("minioadmin")
    minio_root_user: str = ""
    minio_root_password: SecretStr = SecretStr("")

    # 嵌套配置（各子模型自行读取 config.toml 对应 section + env vars）
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    chat_model: ChatModelSettings = Field(default_factory=ChatModelSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    timeouts: TimeoutSettings = Field(default_factory=TimeoutSettings)

    # 派生路径
    base_dir: Path = _PROJECT_ROOT_PATH
    log_dir: Path = Field(default_factory=lambda: _PROJECT_ROOT_PATH / "logs")
    log_file: Path = Field(
        default_factory=lambda: _PROJECT_ROOT_PATH / "logs" / "app.log"
    )

    @property
    def resolved_database_url(self) -> str:
        """解析最终 DATABASE_URL：env var > TOML + credentials > default。

        优先级：
        1. DATABASE_URL 环境变量（完整 URL）
        2. 从组件构建（DB_HOST, DB_PORT, POSTGRES_USER 等）

        Returns:
            最终的数据库连接 URL。

        Raises:
            ValueError: 当无法构建完整 URL 时抛出。
        """
        # 优先级 1：直接指定的 DATABASE_URL
        if self.database_url and self.database_url.strip():
            return self.database_url.strip()

        # 优先级 2：从组件构建
        db_config: DatabaseSettings = self.database

        # URL 编码用户名和密码
        encoded_user: str = quote_plus(self.postgres_user) if self.postgres_user else ""
        raw_password: str = self.postgres_password.get_secret_value()
        encoded_password: str = quote_plus(raw_password) if raw_password else ""

        # 构建认证部分
        credentials_part: str = ""
        if encoded_user or encoded_password:
            credentials_part = f"{encoded_user}:{encoded_password}"

        # 构建网络位置部分
        netloc: str = (
            f"{credentials_part}@{db_config.host}"
            if credentials_part
            else db_config.host
        )

        # 构建完整 URL
        resolved_url: str = f"{db_config.backend}+{db_config.driver}://{netloc}:{db_config.port}/{db_config.name}"

        return resolved_url

    @property
    def resolved_minio_access_key(self) -> str:
        """解析 MinIO access key。

        优先级：MINIO_ACCESS_KEY > MINIO_ROOT_USER > default

        Returns:
            解析后的 MinIO access key。
        """
        if self.minio_access_key != "minioadmin":
            return self.minio_access_key
        return self.minio_root_user or "minioadmin"

    @property
    def resolved_minio_secret_key(self) -> str:
        """解析 MinIO secret key。

        优先级：MINIO_SECRET_KEY > MINIO_ROOT_PASSWORD > default

        Returns:
            解析后的 MinIO secret key。
        """
        secret_value: str = self.minio_secret_key.get_secret_value()
        if secret_value != "minioadmin":
            return secret_value
        root_password: str = self.minio_root_password.get_secret_value()
        return root_password or "minioadmin"

    def ensure_log_directory(self) -> None:
        """确保日志目录存在。

        Raises:
            OSError: 当无法创建目录时抛出。
        """
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
        """配置源优先级：env vars > .env > TOML [app] > defaults。

        嵌套子模型各自读取 config.toml 对应 section。

        Args:
            settings_cls: Settings 类。
            init_settings: 初始化设置源。
            env_settings: 环境变量设置源。
            dotenv_settings: dotenv 设置源。
            file_secret_settings: 文件密钥设置源（未使用）。

        Returns:
            按优先级排序的配置源元组。
        """
        toml_source: _TomlSectionSource = _TomlSectionSource(settings_cls, "app")
        return (
            env_settings,
            dotenv_settings,
            toml_source,
            init_settings,
        )


# ==========================================
# 全局配置实例与初始化
# ==========================================


def _ensure_no_proxy_for_local_services() -> None:
    """确保本地服务（localhost/127.0.0.1）不经过系统 HTTP 代理。

    macOS 系统代理会被 httpx 等库自动检测并使用，导致对 localhost 的请求
    被转发到代理服务器（如 Clash），代理无法正确处理本地请求而返回 502。
    通过设置 NO_PROXY 环境变量来绕过此问题。
    """
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


# 全局配置实例
config: AppSettings = AppSettings()
config.ensure_log_directory()

# 确保本地服务不经过系统代理
_ensure_no_proxy_for_local_services()
