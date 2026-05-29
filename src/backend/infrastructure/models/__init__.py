"""Model loading and client factories.

该包是 OpenAI 协议模型配置解析和客户端实例化的入口。
模型配置本身存在 ``config.toml`` 的 ``[models]`` section 中。
"""

from backend.infrastructure.config.settings import load_models_config

from .model_loader import (
    ModelConfigError,
    ModelEndpoint,
    create_chat_model,
    list_models,
    resolve_model_endpoint,
)

__all__ = [
    "ModelConfigError",
    "ModelEndpoint",
    "create_chat_model",
    "list_models",
    "load_models_config",
    "resolve_model_endpoint",
]
