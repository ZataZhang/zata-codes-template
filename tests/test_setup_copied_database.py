"""验证 Worktree 专用数据库名称与连接配置。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT_PATH = Path("scripts/shared/template/setup_copied_database.py")
_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "setup_copied_database",
    _SCRIPT_PATH,
)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
_SCRIPT_MODULE = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(_SCRIPT_MODULE)


def test_derive_database_name_preserves_digest_for_long_identifier() -> None:
    """超长且前缀相同的标识仍派生不同的合法数据库名。"""
    shared_prefix = "feature-" + "x" * 70
    first_database_name = _SCRIPT_MODULE.derive_database_name(f"{shared_prefix}-one")
    second_database_name = _SCRIPT_MODULE.derive_database_name(f"{shared_prefix}-two")

    assert len(first_database_name) <= 63
    assert len(second_database_name) <= 63
    assert first_database_name != second_database_name


def test_derive_database_name_prefixes_leading_digit() -> None:
    """派生名称始终可作为未引用的 PostgreSQL 标识符使用。"""
    assert _SCRIPT_MODULE.derive_database_name("2026-feature") == "app_2026_feature"


def test_update_database_url_rewrites_only_postgres_database_name(tmp_path: Path) -> None:
    """更新 Worktree 配置时保留连接凭据和其他环境变量。"""
    env_local_path = tmp_path / ".env.local"
    env_local_path.write_text(
        "LOG_LEVEL=INFO\n" "DATABASE_URL=postgresql+psycopg2://app:secret@localhost:5432/main_db\n",
        encoding="utf-8",
    )

    updated_database_url, derived_database_name = _SCRIPT_MODULE.update_database_url(
        env_local_path,
        "template-wt-feature-login-a1b2c3d4",
    )

    assert derived_database_name == "template_wt_feature_login_a1b2c3d4"
    assert updated_database_url is not None
    assert updated_database_url.endswith(f"/{derived_database_name}")
    assert env_local_path.read_text(encoding="utf-8") == (
        "LOG_LEVEL=INFO\nDATABASE_URL="
        f"postgresql+psycopg2://app:secret@localhost:5432/{derived_database_name}\n"
    )


def test_strict_mode_rejects_missing_postgres_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Worktree 严格模式不会静默回退到共享数据库。"""
    monkeypatch.setattr(
        _SCRIPT_MODULE.sys,
        "argv",
        ["setup_copied_database.py", "worktree-db", str(tmp_path), "--strict"],
    )

    assert _SCRIPT_MODULE.main() == 1


def test_database_setup_does_not_print_connection_secret(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """自动建库日志只输出数据库名，不输出连接凭据。"""
    secret_database_url = "postgresql://app:top-secret@localhost:5432/worktree_db"
    monkeypatch.setattr(
        _SCRIPT_MODULE.sys,
        "argv",
        ["setup_copied_database.py", "worktree-db", str(tmp_path), "--strict"],
    )
    monkeypatch.setattr(
        _SCRIPT_MODULE,
        "update_database_url",
        lambda *_: (secret_database_url, "worktree_db"),
    )
    monkeypatch.setattr(_SCRIPT_MODULE, "create_postgres_database", lambda _: True)

    assert _SCRIPT_MODULE.main() == 0

    captured_output = capsys.readouterr().out
    assert "worktree_db" in captured_output
    assert "top-secret" not in captured_output
