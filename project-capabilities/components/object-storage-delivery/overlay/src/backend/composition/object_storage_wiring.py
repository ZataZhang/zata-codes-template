"""按消费项目配置创建可选对象存储实现。"""

from __future__ import annotations

from pathlib import Path

from backend.core.shared.interfaces.object_storage import ObjectStorage
from backend.infrastructure.config.object_storage_settings import load_object_storage_settings
from backend.infrastructure.storage.aliyun_oss import AliyunOssObjectStorage


def build_object_storage(
    config_path: str | Path = "config.toml",
) -> ObjectStorage | None:
    """按需装配 OSS adapter；未启用时不导入或初始化 OSS SDK。

    Args:
        config_path (str | Path): 消费项目配置文件路径。

    Returns:
        ObjectStorage | None: 配置启用时的 OSS adapter；未配置时为 ``None``。

    Raises:
        ObjectStorageConfigError: 能力启用但配置或服务端凭据非法。
        RuntimeError: 能力启用但消费项目没有安装 OSS SDK。
    """
    storage_settings = load_object_storage_settings(config_path)
    if storage_settings is None:
        return None
    return AliyunOssObjectStorage(storage_settings)


__all__ = ["build_object_storage"]
