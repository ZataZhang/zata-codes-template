"""Tests for application configuration loading."""

from __future__ import annotations

from pathlib import Path

from backend.infrastructure.config import settings as settings_module


def test_settings_reads_repository_root_config_toml() -> None:
    """Settings should locate the config.toml in the repository root."""
    repository_root_path = Path(__file__).resolve().parents[1]

    assert settings_module._PROJECT_ROOT_PATH == repository_root_path
    assert (
        settings_module._TOML_CONFIG_FILE_PATH == repository_root_path / "config.toml"
    )
    assert settings_module._load_toml_section_data("app")["name"] == "my-app"
    assert settings_module.config.database.name == "app_database"
