"""Nacos 配置内容解析工具。"""

import json
from collections.abc import Mapping

from .protocol import ConfigProviderError, RuntimeConfigSnapshot


def parse_nacos_config_document(config_content: str | None) -> RuntimeConfigSnapshot:
    """解析 Nacos JSON 配置，并要求文档根节点为对象。

    Args:
        config_content: Nacos 返回的配置正文。

    Returns:
        已解析的运行时配置快照。

    Raises:
        ConfigProviderError: 配置缺失、JSON 无效或根节点不是对象。
    """
    if not config_content:
        raise ConfigProviderError("Nacos 配置为空或不存在。")
    try:
        parsed_config: object = json.loads(config_content)
    except json.JSONDecodeError as parse_error:
        raise ConfigProviderError("Nacos 配置必须是有效的 JSON 文档。") from parse_error
    if not isinstance(parsed_config, Mapping):
        raise ConfigProviderError("Nacos 配置的 JSON 根节点必须是对象。")
    return dict(parsed_config)
