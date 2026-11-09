"""Nacos 配置内容解析工具。"""

import json
import re
from collections.abc import Mapping
from io import StringIO

from dotenv import dotenv_values
from dotenv.parser import parse_stream

from .protocol import ConfigProviderError, RuntimeConfigSnapshot


def parse_nacos_config_document(config_content: str | None) -> RuntimeConfigSnapshot:
    """解析 Nacos JSON 对象或 text/dotenv 文档，保留变量的字面值。

    Args:
        config_content: Nacos 返回的配置正文。

    Returns:
        已解析的运行时配置快照。

    Raises:
        ConfigProviderError: 配置缺失、语法无效、键重复或 JSON 根节点不是对象。
    """
    if not config_content:
        raise ConfigProviderError("Nacos 配置为空或不存在。")
    if "\x00" in config_content:
        raise ConfigProviderError("Nacos 配置包含非法字符。")
    try:
        parsed_config: object = json.loads(config_content)
    except json.JSONDecodeError:
        # 损坏的 JSON 不回退到 dotenv，以免误把配置正文当成变量名。
        if config_content.lstrip().startswith(("{", "[")):
            raise ConfigProviderError("Nacos JSON 配置无效。") from None
        declared_keys: set[str] = set()
        for binding in parse_stream(StringIO(config_content)):
            if binding.error:
                raise ConfigProviderError("Nacos dotenv 语法无效。")
            if binding.key is None:
                continue
            if (
                binding.key in declared_keys
                or binding.value is None
                or not re.fullmatch(r"[A-Z][A-Z0-9_]*|runtime_config", binding.key)
            ):
                raise ConfigProviderError("Nacos dotenv 变量名、赋值或重复键无效。")
            declared_keys.add(binding.key)
        if not declared_keys:
            raise ConfigProviderError("Nacos 配置为空或不存在。")
        parsed_config = dict(dotenv_values(stream=StringIO(config_content), interpolate=False))
        if "runtime_config" in parsed_config:
            try:
                parsed_config["runtime_config"] = json.loads(parsed_config["runtime_config"])
            except (json.JSONDecodeError, TypeError):
                raise ConfigProviderError("Nacos runtime_config 必须是 JSON 对象。") from None
            if not isinstance(parsed_config["runtime_config"], Mapping):
                raise ConfigProviderError("Nacos runtime_config 必须是 JSON 对象。")
    if not isinstance(parsed_config, Mapping):
        raise ConfigProviderError("Nacos 配置的 JSON 根节点必须是对象。")
    return dict(parsed_config)
