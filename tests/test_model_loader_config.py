"""Tests for the OpenAI-protocol model loader.

These tests cover configuration parsing, endpoint resolution, and chat-model
instantiation. They never make outbound network calls.

Test fixtures write minimal ``config.toml`` files with only the ``[models]``
section because that is the only section the loader consumes.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from backend.infrastructure.config import settings as settings_module
from backend.infrastructure.models import (
    ModelConfigError,
    ModelEndpoint,
    create_chat_model,
    list_models,
    load_models_config,
    resolve_model_endpoint,
)


@pytest.fixture(autouse=True)
def _clear_models_config_cache() -> None:
    """Each test starts with a fresh models config cache.

    ``load_models_config`` is wrapped in ``lru_cache`` at module scope. Without
    clearing between tests, a custom config path read once would leak into the
    next test that uses the default path.
    """

    load_models_config.cache_clear()


@pytest.fixture()
def custom_config_toml(tmp_path: Path) -> Path:
    """写入一个最小化的 config.toml，仅包含 [models] section。"""

    config_payload: str = dedent(
        """
        [models."test-model"]
        base_url = "https://api.example.com/v1"
        api_key_env = "TEST_API_KEY"
        description = "Test model"

        [models."test-model".extra]
        organization = "org-test"

        [models."no-extra-model"]
        base_url = "https://api.example.com/v1"
        api_key_env = "TEST_API_KEY"
        """
    ).strip()
    config_file_path: Path = tmp_path / "config.toml"
    config_file_path.write_text(config_payload, encoding="utf-8")
    return config_file_path


class TestLoadModelsConfig:
    """Tests for ``load_models_config``."""

    def test_load_default_models_config(self) -> None:
        """默认仓库 config.toml 中应至少声明 gpt-4。"""

        loaded_default_config: dict[str, Any] = load_models_config()

        assert isinstance(loaded_default_config, dict)
        assert "gpt-4" in loaded_default_config
        assert loaded_default_config["gpt-4"]["base_url"].startswith("https://")

    def test_load_models_config_cached(self) -> None:
        """相同入参的加载结果应来自缓存。"""

        first_load_result: dict[str, Any] = load_models_config()
        second_load_result: dict[str, Any] = load_models_config()

        assert first_load_result is second_load_result

    def test_load_custom_models_config(self, custom_config_toml: Path) -> None:
        """自定义路径应能加载并保留 TOML 子表键。"""

        loaded_custom_config: dict[str, Any] = load_models_config(custom_config_toml)

        assert "test-model" in loaded_custom_config
        assert loaded_custom_config["test-model"]["api_key_env"] == "TEST_API_KEY"

    def test_load_nonexistent_path_raises(self, tmp_path: Path) -> None:
        """显式传入不存在的路径应抛出 FileNotFoundError。"""

        nonexistent_path: Path = tmp_path / "nope.toml"

        with pytest.raises(FileNotFoundError):
            load_models_config(nonexistent_path)

    def test_load_missing_default_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """默认 config.toml 缺失时应返回空 dict，而不是抛错。"""

        monkeypatch.setattr(
            settings_module, "_TOML_CONFIG_FILE_PATH", tmp_path / "missing.toml"
        )

        assert load_models_config() == {}


class TestListModels:
    """Tests for ``list_models``."""

    def test_list_default_models(self) -> None:
        """默认配置应至少返回一条模型条目，且包含名称字段。"""

        listed_default_models: list[dict[str, Any]] = list_models()

        assert any(entry["name"] == "gpt-4" for entry in listed_default_models)

    def test_list_custom_models(self, custom_config_toml: Path) -> None:
        """自定义配置中的所有模型都应被列出。"""

        listed_custom_models: list[dict[str, Any]] = list_models(
            config_path=custom_config_toml
        )
        listed_model_names: list[str] = [
            entry["name"] for entry in listed_custom_models
        ]

        assert listed_model_names == ["test-model", "no-extra-model"]


class TestResolveModelEndpoint:
    """Tests for ``resolve_model_endpoint``."""

    def test_resolve_endpoint_from_env(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """配置里的 api_key_env 指向的环境变量应被读取。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        resolved_endpoint: ModelEndpoint = resolve_model_endpoint(
            "test-model", config_path=custom_config_toml
        )

        assert resolved_endpoint.model_name == "test-model"
        assert resolved_endpoint.base_url == "https://api.example.com/v1"
        assert resolved_endpoint.api_key == "env-key-value"
        assert resolved_endpoint.extra == {"organization": "org-test"}

    def test_resolve_endpoint_with_explicit_api_key(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """显式传入的 api_key 优先于环境变量。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        resolved_endpoint: ModelEndpoint = resolve_model_endpoint(
            "test-model",
            config_path=custom_config_toml,
            api_key="explicit-key-value",
        )

        assert resolved_endpoint.api_key == "explicit-key-value"

    def test_resolve_endpoint_without_extra(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """未声明 extra 时应返回空字典。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        resolved_endpoint: ModelEndpoint = resolve_model_endpoint(
            "no-extra-model", config_path=custom_config_toml
        )

        assert resolved_endpoint.extra == {}

    def test_resolve_endpoint_unknown_model_raises(
        self, custom_config_toml: Path
    ) -> None:
        """未声明的模型名应抛出 ModelConfigError。"""

        with pytest.raises(ModelConfigError, match="not declared"):
            resolve_model_endpoint("no-such-model", config_path=custom_config_toml)

    def test_resolve_endpoint_missing_env_raises(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """环境变量未设置时应抛出明确的 ModelConfigError。"""

        monkeypatch.delenv("TEST_API_KEY", raising=False)

        with pytest.raises(ModelConfigError, match="TEST_API_KEY"):
            resolve_model_endpoint("test-model", config_path=custom_config_toml)

    def test_resolve_endpoint_missing_base_url_raises(self, tmp_path: Path) -> None:
        """缺失 base_url 的条目应抛出 ModelConfigError。"""

        broken_config_payload: str = dedent(
            """
            [models."broken-model"]
            api_key_env = "TEST_API_KEY"
            """
        ).strip()
        broken_config_file: Path = tmp_path / "broken.toml"
        broken_config_file.write_text(broken_config_payload, encoding="utf-8")

        with pytest.raises(ModelConfigError, match="base_url"):
            resolve_model_endpoint("broken-model", config_path=broken_config_file)


class TestCreateChatModel:
    """Tests for ``create_chat_model``."""

    def test_create_chat_model_uses_resolved_endpoint(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """生成的客户端应携带配置中的 base_url 与解析后的 api_key。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        chat_model_instance: Any = create_chat_model(
            "test-model",
            config_path=custom_config_toml,
        )

        assert chat_model_instance.model_name == "test-model"
        assert str(chat_model_instance.openai_api_base) == "https://api.example.com/v1"
        assert chat_model_instance.openai_api_key.get_secret_value() == "env-key-value"

    def test_create_chat_model_client_kwargs_override_extra(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """client_kwargs 应能覆盖配置中的 extra 字段。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        chat_model_instance: Any = create_chat_model(
            "test-model",
            config_path=custom_config_toml,
            client_kwargs={"max_retries": 5},
        )

        assert chat_model_instance.max_retries == 5
