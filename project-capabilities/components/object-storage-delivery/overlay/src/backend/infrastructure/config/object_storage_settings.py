"""可选对象存储配置加载。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ObjectStorageConfigError(RuntimeError):
    """对象存储被启用但配置缺失或非法时抛出。"""


@dataclass(frozen=True)
class ObjectStorageSettings:
    """阿里云 OSS adapter 所需的运行配置。"""

    endpoint: str
    region: str
    bucket: str
    access_key_id: str
    access_key_secret: str = field(repr=False)
    cdn_base_url: str | None


def load_object_storage_settings(
    config_path: str | Path = "config.toml",
) -> ObjectStorageSettings | None:
    """读取可选 ``[object_storage]`` 配置并从环境变量解析服务端密钥。

    Args:
        config_path (str | Path): 项目 TOML 配置路径。

    Returns:
        ObjectStorageSettings | None: 已启用的 OSS 设置；缺少配置段或显式关闭时为 ``None``。

    Raises:
        ObjectStorageConfigError: TOML 无法读取、配置字段非法或密钥环境变量为空。
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
    if provider_name != "aliyun-oss":
        raise ObjectStorageConfigError("[object_storage] provider 当前只支持 aliyun-oss")

    access_key_id_env_name = _required_string(storage_section, "access_key_id_env")
    access_key_secret_env_name = _required_string(storage_section, "access_key_secret_env")
    access_key_id_value = os.getenv(access_key_id_env_name, "").strip()
    access_key_secret_value = os.getenv(access_key_secret_env_name, "").strip()
    if not access_key_id_value or not access_key_secret_value:
        missing_environment_names = [
            name
            for name, value in (
                (access_key_id_env_name, access_key_id_value),
                (access_key_secret_env_name, access_key_secret_value),
            )
            if not value
        ]
        raise ObjectStorageConfigError(
            "对象存储已启用，但服务端环境变量未配置: " + ", ".join(missing_environment_names)
        )

    return ObjectStorageSettings(
        endpoint=_required_string(storage_section, "endpoint").rstrip("/"),
        region=_required_string(storage_section, "region"),
        bucket=_required_string(storage_section, "bucket"),
        access_key_id=access_key_id_value,
        access_key_secret=access_key_secret_value,
        cdn_base_url=_optional_string(storage_section.get("cdn_base_url")),
    )


def _required_string(section_dict: dict[str, Any], setting_name: str) -> str:
    """读取非空字符串设置。"""
    setting_value = section_dict.get(setting_name)
    if not isinstance(setting_value, str) or not setting_value.strip():
        raise ObjectStorageConfigError(f"[object_storage] 缺少 {setting_name}")
    return setting_value.strip()


def _optional_string(setting_value: Any) -> str | None:
    """将可选字符串规范化为空值或已去空白字符串。"""
    if not isinstance(setting_value, str) or not setting_value.strip():
        return None
    return setting_value.strip().rstrip("/")


__all__ = ["ObjectStorageConfigError", "ObjectStorageSettings", "load_object_storage_settings"]
