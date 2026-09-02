"""Tests for application configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.infrastructure.config import settings as settings_module
from backend.infrastructure.config.settings import (
    PRIMARY_MODEL_API_KEY_ENV,
    PRIMARY_MODEL_BASE_URL_ENV,
    PRIMARY_MODEL_NAME_ENV,
    PrimaryModelConfigError,
    load_primary_model_settings,
)

_PRIMARY_MODEL_ENV_NAMES: tuple[str, str, str] = (
    PRIMARY_MODEL_BASE_URL_ENV,
    PRIMARY_MODEL_API_KEY_ENV,
    PRIMARY_MODEL_NAME_ENV,
)


def test_settings_reads_repository_root_config_toml() -> None:
    """Settings should locate the config.toml in the repository root."""
    repository_root_path = Path(__file__).resolve().parents[1]

    assert settings_module._PROJECT_ROOT_PATH == repository_root_path
    assert settings_module._TOML_CONFIG_FILE_PATH == repository_root_path / "config.toml"
    assert settings_module._load_toml_section_data("app")["app_name"] == "my-app"
    assert settings_module.config.database.name == "app_database"


class TestPrimaryModelSettings:
    """Tests for the ``MODEL_*`` endpoint trio."""

    @pytest.fixture(autouse=True)
    def _cleared_primary_model_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """每个用例都从未声明主模型的环境开始。

        settings 模块导入时会把开发者本地的 ``.env`` / ``.env.local`` 写入
        ``os.environ``，不清掉断言就会依赖本机状态。
        """
        for primary_model_env_name in _PRIMARY_MODEL_ENV_NAMES:
            monkeypatch.delenv(primary_model_env_name, raising=False)

    def test_returns_none_when_all_unset(self) -> None:
        """三件套都没配时返回 None，代表本项目不使用模型。"""
        assert load_primary_model_settings() is None

    def test_reads_all_three_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """三件套齐全时返回端点配置，密钥包在 SecretStr 里。"""
        monkeypatch.setenv(PRIMARY_MODEL_BASE_URL_ENV, "https://api.example.com/v1")
        monkeypatch.setenv(PRIMARY_MODEL_API_KEY_ENV, "key-value")
        monkeypatch.setenv(PRIMARY_MODEL_NAME_ENV, "example-model")

        primary_model_settings = load_primary_model_settings()

        assert primary_model_settings is not None
        assert primary_model_settings.base_url == "https://api.example.com/v1"
        assert primary_model_settings.api_key.get_secret_value() == "key-value"
        assert primary_model_settings.model_name == "example-model"

    def test_keeps_slashes_in_model_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """MODEL_NAME 自带斜杠时原样保留，供 OpenRouter 这类端点使用。"""
        monkeypatch.setenv(PRIMARY_MODEL_BASE_URL_ENV, "https://api.example.com/v1")
        monkeypatch.setenv(PRIMARY_MODEL_API_KEY_ENV, "key-value")
        monkeypatch.setenv(PRIMARY_MODEL_NAME_ENV, "anthropic/claude-3.5-sonnet")

        primary_model_settings = load_primary_model_settings()

        assert primary_model_settings is not None
        assert primary_model_settings.model_name == "anthropic/claude-3.5-sonnet"

    def test_partial_declaration_raises_with_missing_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """只配一部分时 fail-fast，并在错误体中列出缺失的变量名。"""
        monkeypatch.setenv(PRIMARY_MODEL_BASE_URL_ENV, "https://api.example.com/v1")

        with pytest.raises(PrimaryModelConfigError) as raised_config_error:
            load_primary_model_settings()

        assert PRIMARY_MODEL_API_KEY_ENV in str(raised_config_error.value)
        assert PRIMARY_MODEL_NAME_ENV in str(raised_config_error.value)

    def test_blank_values_count_as_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """.env.example 里留空的三行等同于未声明，不应触发报错。"""
        for primary_model_env_name in _PRIMARY_MODEL_ENV_NAMES:
            monkeypatch.setenv(primary_model_env_name, "   ")

        assert load_primary_model_settings() is None
