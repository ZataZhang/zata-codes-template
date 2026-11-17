"""可选阿里云 OSS 配置加载。"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

DEFAULT_REGION = "cn-hangzhou"
SUPPORTED_PROVIDER = "aliyun_oss"


class ObjectStorageConfigError(RuntimeError):
    """对象存储被启用但配置缺失或非法时抛出。"""


@dataclass(frozen=True)
class ObjectStorageSettings:
    """阿里云 OSS adapter 所需的服务端配置。"""

    endpoint: str
    region: str
    bucket: str
    access_key_id: str = field(repr=False)
    access_key_secret: str = field(repr=False)
    cdn_base_url: str | None = None


def load_object_storage_settings(
    config_path: str | Path = "config.toml",
) -> ObjectStorageSettings | None:
    """读取可选 OSS 配置并从服务端环境变量解析凭据。

    Args:
        config_path (str | Path): 项目 TOML 配置路径。

    Returns:
        ObjectStorageSettings | None: 已启用的 OSS 设置；缺少配置段或显式关闭时为 None。

    Raises:
        ObjectStorageConfigError: TOML 无法读取、配置非法或密钥环境变量为空。
    """
    resolved_config_path = Path(config_path)
    if not resolved_config_path.is_file():
        return None

    try:
        with resolved_config_path.open("rb") as config_file_handle:
            raw_config_dict: dict[str, Any] = tomllib.load(config_file_handle)
    except (OSError, tomllib.TOMLDecodeError) as config_error:
        raise ObjectStorageConfigError(f"无法读取对象存储配置: {config_error}") from config_error

    storage_section = raw_config_dict.get("object_storage")
    if not isinstance(storage_section, dict):
        return None
    enabled_value = storage_section.get("enabled", False)
    if not isinstance(enabled_value, bool):
        raise ObjectStorageConfigError("[object_storage] enabled 必须是布尔值")
    if not enabled_value:
        return None

    provider_name = _required_string(storage_section, "provider")
    if provider_name != SUPPORTED_PROVIDER:
        raise ObjectStorageConfigError(
            f"[object_storage] provider 当前只支持 {SUPPORTED_PROVIDER}"
        )

    access_key_id_env_name = _required_string(storage_section, "access_key_id_env")
    access_key_secret_env_name = _required_string(storage_section, "access_key_secret_env")
    access_key_id_value = os.getenv(access_key_id_env_name, "").strip()
    access_key_secret_value = os.getenv(access_key_secret_env_name, "").strip()
    if not access_key_id_value or not access_key_secret_value:
        missing_environment_names = [
            environment_name
            for environment_name, environment_value in (
                (access_key_id_env_name, access_key_id_value),
                (access_key_secret_env_name, access_key_secret_value),
            )
            if not environment_value
        ]
        raise ObjectStorageConfigError(
            "对象存储已启用，但服务端环境变量未配置: "
            + ", ".join(missing_environment_names)
        )

    endpoint_value = _required_https_authority(
        _required_string(storage_section, "endpoint"),
        "endpoint",
    )
    cdn_base_url_value = _optional_https_url(storage_section.get("cdn_base_url"))
    region_setting = storage_section.get("region", DEFAULT_REGION)
    if not isinstance(region_setting, str) or not region_setting.strip():
        raise ObjectStorageConfigError("[object_storage] region 必须是非空字符串")
    region_value = region_setting.strip()
    if not re.fullmatch(r"[a-z0-9-]+", region_value):
        raise ObjectStorageConfigError("[object_storage] region 格式无效")

    return ObjectStorageSettings(
        endpoint=endpoint_value,
        region=region_value,
        bucket=_required_string(storage_section, "bucket"),
        access_key_id=access_key_id_value,
        access_key_secret=access_key_secret_value,
        cdn_base_url=cdn_base_url_value,
    )


def _required_string(section_dict: dict[str, Any], setting_name: str) -> str:
    """读取非空字符串设置。"""
    setting_value = section_dict.get(setting_name)
    if not isinstance(setting_value, str) or not setting_value.strip():
        raise ObjectStorageConfigError(f"[object_storage] 缺少 {setting_name}")
    return setting_value.strip()


def _required_https_authority(endpoint: str, setting_name: str) -> str:
    """校验 OSS endpoint 只有 HTTPS authority。"""
    endpoint_parts = urlsplit(endpoint)
    if (
        endpoint_parts.scheme != "https"
        or not endpoint_parts.hostname
        or endpoint_parts.username
        or endpoint_parts.password
        or endpoint_parts.path not in {"", "/"}
        or endpoint_parts.query
        or endpoint_parts.fragment
    ):
        raise ObjectStorageConfigError(
            f"[object_storage] {setting_name} 必须是无凭据、无路径的 HTTPS authority"
        )
    try:
        endpoint_parts.port
    except ValueError as endpoint_error:
        raise ObjectStorageConfigError(
            f"[object_storage] {setting_name} 端口无效"
        ) from endpoint_error
    return endpoint.rstrip("/")


def _optional_https_url(setting_value: Any) -> str | None:
    """校验可选 CDN HTTPS 地址并移除末尾斜线。"""
    if not isinstance(setting_value, str) or not setting_value.strip():
        return None
    cdn_url = setting_value.strip()
    cdn_parts = urlsplit(cdn_url)
    if (
        cdn_parts.scheme != "https"
        or not cdn_parts.hostname
        or cdn_parts.username
        or cdn_parts.password
        or cdn_parts.query
        or cdn_parts.fragment
    ):
        raise ObjectStorageConfigError(
            "[object_storage] cdn_base_url 必须是无凭据、无查询参数的 HTTPS 地址"
        )
    try:
        cdn_parts.port
    except ValueError as cdn_error:
        raise ObjectStorageConfigError("[object_storage] cdn_base_url 端口无效") from cdn_error
    return cdn_url.rstrip("/")


__all__ = [
    "DEFAULT_REGION",
    "ObjectStorageConfigError",
    "ObjectStorageSettings",
    "SUPPORTED_PROVIDER",
    "load_object_storage_settings",
]
