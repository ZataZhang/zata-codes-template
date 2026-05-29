"""OpenAI-protocol chat model loader.

模型加载器只关心一件事：根据模型名查表，生成一个 ``ChatOpenAI`` 客户端。

模型配置存在 ``config.toml`` 的 ``[models]`` section 中：每个子表就是一个模型条目，
其值描述该模型对应的 OpenAI 协议端点。不再有 provider 分组、不再有多 base_url 回退、
不再有 provider 特定参数；多区域 / 多端点请配置成独立模型条目。

配置示例（``config.toml``）::

    [models."gpt-4"]
    base_url = "https://api.openai.com/v1"
    api_key_env = "OPENAI_API_KEY"
    description = "OpenAI GPT-4 model"

    # 可选：透传给 ChatOpenAI 的额外关键字参数
    [models."gpt-4".extra]
    organization = "org-..."

API 密钥本身始终通过 ``.env`` / 环境变量提供，配置文件只声明应读取哪个环境变量名。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, MutableMapping

from dotenv import load_dotenv
from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from backend.infrastructure.config.settings import load_models_config

PROJECT_ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT_DIR / ".env", override=False)


class ModelConfigError(RuntimeError):
    """当模型配置无法满足请求时抛出的异常。

    例如：模型名未在 ``[models]`` 中声明，或对应的 API key 环境变量缺失。
    """


@dataclass(frozen=True)
class ModelEndpoint:
    """单个模型对应的 OpenAI 协议端点描述。

    Attributes:
        model_name (str): 模型名称（与配置文件中的键一致）。
        base_url (str): OpenAI 协议端点的基础 URL。
        api_key (str): 已经解析好的 API 密钥。
        extra (Mapping[str, Any]): 透传给 ``ChatOpenAI`` 的额外关键字参数。
    """

    model_name: str
    base_url: str
    api_key: str
    extra: Mapping[str, Any]


def list_models(
    *,
    config_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """返回配置中所有可用模型的元数据列表。

    Args:
        config_path (str | Path | None): 配置文件路径的覆盖。

    Returns:
        list[dict[str, Any]]: 形如 ``{"name": ..., "base_url": ..., ...}`` 的条目列表。
    """

    raw_models_config: dict[str, Any] = load_models_config(config_path)
    listed_models: list[dict[str, Any]] = []
    for model_name, model_entry in raw_models_config.items():
        if not isinstance(model_entry, Mapping):
            continue
        listed_models.append({"name": model_name, **dict(model_entry)})
    return listed_models


def _lookup_model_entry(
    model_name: str,
    models_config: Mapping[str, Any],
) -> Mapping[str, Any]:
    """根据模型名在配置中查找条目（大小写不敏感、忽略首尾空白）。

    Args:
        model_name (str): 模型标识符。
        models_config (Mapping[str, Any]): 已加载的模型配置。

    Returns:
        Mapping[str, Any]: 对应的模型条目。

    Raises:
        ModelConfigError: 如果模型名未在配置中声明。
    """

    normalized_model_name: str = model_name.strip().lower()
    for declared_model_name, model_entry in models_config.items():
        if declared_model_name.strip().lower() == normalized_model_name and isinstance(
            model_entry, Mapping
        ):
            return model_entry
    raise ModelConfigError(f"Model '{model_name}' is not declared in models config.")


def resolve_model_endpoint(
    model_name: str,
    *,
    config_path: str | Path | None = None,
    api_key: str | None = None,
) -> ModelEndpoint:
    """解析模型对应的 OpenAI 协议端点。

    解析顺序：

    1. 在 ``[models]`` 中按模型名查表
    2. 读取 ``base_url``（必填）
    3. 读取 API key：显式入参 > 条目里 ``api_key_env`` 指向的环境变量
    4. 读取可选 ``extra`` 字段，透传给 ``ChatOpenAI``

    Args:
        model_name (str): 模型名称。
        config_path (str | Path | None): 可选的配置文件路径覆盖。
        api_key (str | None): 显式覆盖的 API 密钥；优先级最高。

    Returns:
        ModelEndpoint: 已解析好的端点描述。

    Raises:
        ModelConfigError: 当模型未声明、缺少 ``base_url`` 或 API 密钥无法解析时抛出。
    """

    models_config: dict[str, Any] = load_models_config(config_path)
    model_entry: Mapping[str, Any] = _lookup_model_entry(model_name, models_config)

    base_url_value: Any = model_entry.get("base_url")
    if not isinstance(base_url_value, str) or not base_url_value:
        raise ModelConfigError(
            f"Model '{model_name}' is missing a string 'base_url' in models config."
        )

    if api_key:
        resolved_api_key: str = api_key
    else:
        api_key_env_name: Any = model_entry.get("api_key_env")
        if not isinstance(api_key_env_name, str) or not api_key_env_name:
            raise ModelConfigError(
                f"Model '{model_name}' is missing 'api_key_env' and no explicit api_key was provided."
            )
        env_api_key_value: str | None = os.getenv(api_key_env_name)
        if not env_api_key_value:
            raise ModelConfigError(
                f"Environment variable '{api_key_env_name}' for model '{model_name}' is empty or unset."
            )
        resolved_api_key = env_api_key_value

    extra_value: Any = model_entry.get("extra", {})
    if not isinstance(extra_value, Mapping):
        raise ModelConfigError(
            f"Model '{model_name}' field 'extra' must be a mapping if provided."
        )

    return ModelEndpoint(
        model_name=model_name,
        base_url=base_url_value,
        api_key=resolved_api_key,
        extra=dict(extra_value),
    )


def create_chat_model(
    model_name: str,
    *,
    temperature: float = 0.0,
    config_path: str | Path | None = None,
    api_key: str | None = None,
    client_kwargs: Mapping[str, Any] | None = None,
) -> BaseLanguageModel:
    """根据模型配置实例化 OpenAI 协议聊天模型。

    Args:
        model_name (str): 要实例化的模型名称（必须在 ``[models]`` 中声明）。
        temperature (float): 传递给底层客户端的温度值。
        config_path (str | Path | None): 可选的配置路径覆盖。
        api_key (str | None): 显式覆盖的 API 密钥；优先级最高。
        client_kwargs (Mapping[str, Any] | None): 额外的 ``ChatOpenAI`` 关键字参数；
            优先级高于配置文件 ``extra``。

    Returns:
        BaseLanguageModel: 已配置好的 ``ChatOpenAI`` 实例。

    Raises:
        ModelConfigError: 当配置缺失、模型未声明或 API key 无法解析时抛出。
        FileNotFoundError: 当配置路径不存在时抛出。
    """

    resolved_endpoint: ModelEndpoint = resolve_model_endpoint(
        model_name,
        config_path=config_path,
        api_key=api_key,
    )

    chat_model_kwargs: MutableMapping[str, Any] = {
        "model": resolved_endpoint.model_name,
        "temperature": temperature,
        "base_url": resolved_endpoint.base_url,
        "api_key": resolved_endpoint.api_key,
    }
    chat_model_kwargs.update(resolved_endpoint.extra)
    if client_kwargs:
        chat_model_kwargs.update(client_kwargs)

    return ChatOpenAI(**chat_model_kwargs)
