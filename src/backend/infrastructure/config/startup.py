"""在应用依赖初始化前读取并合并 Nacos 启动配置。"""

from __future__ import annotations

import asyncio
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings import ConfigProviderSettings


def build_startup_environment(
    config_snapshot: dict[str, object], *, credential_names: tuple[str, str]
) -> dict[str, str]:
    """校验启动文档，并将 JSON 值转换成环境变量字符串。

    Args:
        config_snapshot: Nacos JSON 对象，使用大写环境变量名作为键。
        credential_names: 仅允许在本地声明的 Nacos 账号与密码变量名。

    Returns:
        尚未写入进程环境的配置值；字符串保持原文，其他值使用 JSON 编码。

    Raises:
        ValueError: 键名、保留参数或值类型不符合启动配置契约。
    """
    startup_environment: dict[str, str] = {}
    for config_key, config_value in config_snapshot.items():
        if config_key == "runtime_config":
            if not isinstance(config_value, dict):
                raise ValueError("Nacos runtime_config 必须是 JSON 对象。")
            continue
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", config_key):
            raise ValueError("Nacos 启动配置键必须使用大写环境变量名。")
        if config_key.startswith("NACOS_") or config_key in {
            "PROVIDER",
            "CONFIG_PROVIDER",
            *credential_names,
        }:
            raise ValueError("Nacos 连接参数只能由本地环境或 TOML 提供。")
        if config_value is None:
            raise ValueError("Nacos 启动配置不接受 null；省略该键可使用默认值。")
        try:
            startup_environment[config_key] = (
                config_value
                if isinstance(config_value, str)
                else json.dumps(config_value, ensure_ascii=False, allow_nan=False)
            )
        except (ValueError, TypeError):
            raise ValueError("Nacos 启动配置包含无法编码的 JSON 值。") from None
    return startup_environment


def load_startup_configuration(
    settings: ConfigProviderSettings, *, config_file_path: Path
) -> dict[str, object]:
    """在创建 Settings 前同步读取 Nacos，保留已有环境变量的优先级。

    Args:
        settings: 已由本地环境及 TOML 解析的 Nacos 连接配置。
        config_file_path: 项目的 TOML 默认配置路径。

    Returns:
        供应用读取的 runtime_config 子对象；未启用 Nacos 时为空对象。

    Raises:
        ConfigProviderError: Nacos 连接、认证或读取失败。
        ValueError: 启动文档格式无效。
    """
    if settings.provider == "local" and not settings.nacos_server_addr.strip():
        return {}

    # 延迟导入避免 settings 定义与 provider 工厂之间的循环依赖。
    from .providers.factory import build_config_provider

    async def read_startup_document() -> dict[str, object]:
        config_provider = build_config_provider(settings, config_file_path=config_file_path)
        try:
            return dict(await config_provider.load())
        finally:
            await config_provider.close()

    # 模块也可能在已有事件循环的 worker 中导入，独立线程负责本次网络请求。
    with ThreadPoolExecutor(max_workers=1) as startup_executor:
        config_snapshot = startup_executor.submit(
            lambda: asyncio.run(read_startup_document())
        ).result()
    startup_environment = build_startup_environment(
        config_snapshot,
        credential_names=(settings.nacos_username_env, settings.nacos_password_env),
    )
    for config_key, config_value in startup_environment.items():
        os.environ.setdefault(config_key, config_value)
    runtime_snapshot = config_snapshot.get("runtime_config", {})
    assert isinstance(runtime_snapshot, dict)
    return runtime_snapshot
