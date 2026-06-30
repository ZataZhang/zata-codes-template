"""Tests for the OpenAI-protocol provider registry in settings.

These tests cover provider configuration parsing, endpoint resolution, and
``ChatOpenAI`` instantiation. They never make outbound network calls.

Test fixtures write minimal ``config.toml`` files with only the ``[providers]``
section because that is the only section the loader consumes.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest

from backend.infrastructure.config import settings as settings_module
from backend.infrastructure.config.settings import (
    ModelConfigError,
    create_chat_model,
    list_providers,
    load_providers_config,
)


@pytest.fixture(autouse=True)
def _clear_providers_config_cache() -> None:
    """Each test starts with a fresh providers config cache.

    ``load_providers_config`` is wrapped in ``lru_cache`` at module scope.
    Without clearing between tests, a custom config path read once would leak
    into the next test that uses the default path.
    """

    load_providers_config.cache_clear()


@pytest.fixture()
def custom_config_toml(tmp_path: Path) -> Path:
    """写入一个最小化的 config.toml，仅包含 [providers] section。"""

    config_payload: str = dedent(
        """
        [providers.test-provider]
        base_url = "https://api.example.com/v1"
        api_key_env = "TEST_API_KEY"
        description = "Test provider"

        [providers.test-provider.extra]
        organization = "org-test"

        [providers.no-extra-provider]
        base_url = "https://api.example.com/v1"
        api_key_env = "TEST_API_KEY"
        """
    ).strip()
    config_file_path: Path = tmp_path / "config.toml"
    config_file_path.write_text(config_payload, encoding="utf-8")
    return config_file_path


class TestLoadProvidersConfig:
    """Tests for ``load_providers_config``."""

    def test_load_default_providers_config(self) -> None:
        """默认仓库 config.toml 中应至少声明 openai provider。"""

        loaded_default_config: dict[str, Any] = load_providers_config()

        assert isinstance(loaded_default_config, dict)
        assert "openai" in loaded_default_config
        assert loaded_default_config["openai"]["base_url"].startswith("https://")

    def test_load_providers_config_cached(self) -> None:
        """相同入参的加载结果应来自缓存。"""

        first_load_result: dict[str, Any] = load_providers_config()
        second_load_result: dict[str, Any] = load_providers_config()

        assert first_load_result is second_load_result

    def test_load_custom_providers_config(self, custom_config_toml: Path) -> None:
        """自定义路径应能加载并保留 TOML 子表键。"""

        loaded_custom_config: dict[str, Any] = load_providers_config(custom_config_toml)

        assert "test-provider" in loaded_custom_config
        assert loaded_custom_config["test-provider"]["api_key_env"] == "TEST_API_KEY"

    def test_load_nonexistent_path_raises(self, tmp_path: Path) -> None:
        """显式传入不存在的路径应抛出 FileNotFoundError。"""

        nonexistent_path: Path = tmp_path / "nope.toml"

        with pytest.raises(FileNotFoundError):
            load_providers_config(nonexistent_path)

    def test_load_missing_default_returns_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """默认 config.toml 缺失时应返回空 dict，而不是抛错。"""

        monkeypatch.setattr(settings_module, "_TOML_CONFIG_FILE_PATH", tmp_path / "missing.toml")

        assert load_providers_config() == {}


class TestListProviders:
    """Tests for ``list_providers``."""

    def test_list_default_providers(self) -> None:
        """默认配置应至少返回 openai provider，且包含名称字段。"""

        listed_default_providers: list[dict[str, Any]] = list_providers()

        assert any(entry["name"] == "openai" for entry in listed_default_providers)

    def test_list_custom_providers(self, custom_config_toml: Path) -> None:
        """自定义配置中的所有 provider 都应被列出。"""

        listed_custom_providers: list[dict[str, Any]] = list_providers(
            config_path=custom_config_toml
        )
        listed_provider_names: list[str] = [entry["name"] for entry in listed_custom_providers]

        assert listed_provider_names == ["test-provider", "no-extra-provider"]


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
            "test-provider/test-model",
            config_path=custom_config_toml,
        )

        assert chat_model_instance.model_name == "test-model"
        assert str(chat_model_instance.openai_api_base) == "https://api.example.com/v1"
        assert chat_model_instance.openai_api_key.get_secret_value() == "env-key-value"

    def test_create_chat_model_default_provider(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """自定义配置中的另一个 provider 也应能被解析。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        chat_model_instance: Any = create_chat_model(
            "no-extra-provider/some-model",
            config_path=custom_config_toml,
        )

        assert chat_model_instance.model_name == "some-model"

    def test_create_chat_model_provider_name_is_case_insensitive(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """provider 名称应大小写不敏感。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        chat_model_instance: Any = create_chat_model(
            "Test-Provider/test-model",
            config_path=custom_config_toml,
        )

        assert chat_model_instance.model_name == "test-model"

    def test_create_chat_model_client_kwargs_override_extra(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """client_kwargs 应能覆盖配置中的 extra 字段。"""

        monkeypatch.setenv("TEST_API_KEY", "env-key-value")

        chat_model_instance: Any = create_chat_model(
            "test-provider/test-model",
            config_path=custom_config_toml,
            client_kwargs={"max_retries": 5},
        )

        assert chat_model_instance.max_retries == 5

    def test_create_chat_model_unknown_provider_raises(self, custom_config_toml: Path) -> None:
        """未声明的 provider 应抛出 ModelConfigError。"""

        with pytest.raises(ModelConfigError, match="not declared"):
            create_chat_model(
                "no-such-provider/gpt-4o",
                config_path=custom_config_toml,
            )

    def test_create_chat_model_missing_slash_raises(self, custom_config_toml: Path) -> None:
        """缺少 ``/`` 分隔符的 model_name 应抛出 ModelConfigError。"""

        with pytest.raises(ModelConfigError, match="provider/model_id"):
            create_chat_model("gpt-4o", config_path=custom_config_toml)

    def test_create_chat_model_empty_segments_raises(self, custom_config_toml: Path) -> None:
        """空 provider 或空 model_id 应抛出 ModelConfigError。"""

        with pytest.raises(ModelConfigError, match="provider/model_id"):
            create_chat_model("/gpt-4o", config_path=custom_config_toml)

        with pytest.raises(ModelConfigError, match="provider/model_id"):
            create_chat_model("test-provider/", config_path=custom_config_toml)

    def test_create_chat_model_missing_base_url_raises(self, tmp_path: Path) -> None:
        """缺失 base_url 的 provider 条目应抛出 ModelConfigError。"""

        broken_config_payload: str = dedent(
            """
            [providers.broken-provider]
            api_key_env = "TEST_API_KEY"
            """
        ).strip()
        broken_config_file: Path = tmp_path / "broken.toml"
        broken_config_file.write_text(broken_config_payload, encoding="utf-8")

        with pytest.raises(ModelConfigError, match="base_url"):
            create_chat_model(
                "broken-provider/gpt-4o",
                config_path=broken_config_file,
            )

    def test_create_chat_model_missing_api_key_env_raises(self, tmp_path: Path) -> None:
        """缺失 api_key_env 字段的 provider 条目应抛出 ModelConfigError。"""

        broken_config_payload: str = dedent(
            """
            [providers.broken-provider]
            base_url = "https://api.example.com/v1"
            """
        ).strip()
        broken_config_file: Path = tmp_path / "broken.toml"
        broken_config_file.write_text(broken_config_payload, encoding="utf-8")

        with pytest.raises(ModelConfigError, match="api_key_env"):
            create_chat_model(
                "broken-provider/gpt-4o",
                config_path=broken_config_file,
            )

    def test_create_chat_model_unset_api_key_env_raises(
        self,
        custom_config_toml: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """api_key_env 指向的环境变量未设置时应抛出 ModelConfigError。"""

        monkeypatch.delenv("TEST_API_KEY", raising=False)

        with pytest.raises(ModelConfigError, match="TEST_API_KEY"):
            create_chat_model(
                "test-provider/test-model",
                config_path=custom_config_toml,
            )
