"""守护 Alembic 迁移命名约定的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

These tests guard the contract documented in ``docs/database/migrations.md``:

- ``alembic.ini`` defines ``file_template`` as
  ``YYYYMMDD-HHMMSS-<slug>.py``, deliberately dropping Alembic's default
  12-char hash segment.
- Slugs are normalized by Alembic via
  ``"_".join(re.findall(r"\\w+", message)).lower()`` (see
  ``alembic/script/base.py``), so the developer-facing ``-m`` message is
  a natural-language short phrase; the filename slug will be snake_case.

We do not invoke the ``alembic`` CLI here because doing so would require
either a working database or stubbing ``alembic/env.py``'s ``backend.*``
imports. The contract is fully determined by the ``file_template`` string
and the slug normalization above, so a unit test that mirrors them is
more reliable than a CLI smoke test.
"""

from __future__ import annotations

import configparser
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"
EXPECTED_FILE_TEMPLATE = "%(year)d%(month).2d%(day).2d-%(hour).2d%(minute).2d%(second).2d-%(slug)s"


def _read_alembic_file_template() -> str:
    """Return the configured ``file_template`` value from ``alembic.ini``."""
    parser = configparser.ConfigParser()
    parser.read(ALEMBIC_INI_PATH, encoding="utf-8")
    return parser["alembic"]["file_template"]


def _alembic_slug_from_message(message: str) -> str:
    """Mirror Alembic's slug normalization (alembic/script/base.py:771)."""
    return "_".join(re.findall(r"\w+", message or "")).lower()


def test_alembic_ini_file_template_matches_documented_format() -> None:
    """``alembic.ini`` must use ``YYYYMMDD-HHMMSS-<slug>.py`` and drop the default hash segment."""
    file_template = _read_alembic_file_template()
    assert file_template == EXPECTED_FILE_TEMPLATE
    assert "%(rev)s" not in file_template


@pytest.mark.parametrize(
    ("revision_message", "expected_slug"),
    [
        ("Add user email index", "add_user_email_index"),
        ("Create orders table", "create_orders_table"),
        ("Backfill user display name", "backfill_user_display_name"),
        ("Drop legacy column foo", "drop_legacy_column_foo"),
        ("add-user-email-index", "add_user_email_index"),
        ("AddUserEmailIndex", "adduseremailindex"),
        ("  Multiple   spaces  ", "multiple_spaces"),
    ],
)
def test_alembic_slug_normalization_matches_documented_behavior(
    revision_message: str, expected_slug: str
) -> None:
    """``-m`` message is normalized to snake_case per Alembic's regex.

    See ``alembic/script/base.py:771`` and the examples in
    ``docs/database/migrations.md``.
    """
    assert _alembic_slug_from_message(revision_message) == expected_slug


def test_empty_message_yields_empty_slug() -> None:
    """Empty ``-m`` message produces an empty slug — caller must pass one."""
    assert _alembic_slug_from_message("") == ""


# ==========================================
# Schema convention hook tests
# ==========================================


SCRIPT_PATH = REPO_ROOT / "hooks" / "shared" / "check_schema_conventions.py"


def _run_schema_convention_hook(
    *extra_args: str,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run the schema conventions hook as a subprocess.

    Args:
        *extra_args: Additional command-line arguments to pass to the hook.
        check: Whether to raise on non-zero exit status.

    Returns:
        The completed subprocess result.
    """
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def _migration_body(revision_id: str) -> str:
    """Return a minimal Alembic migration body with the given revision ID."""
    return textwrap.dedent(
        f"""\
        \"\"\"Test migration.

        Revision ID: {revision_id}
        \"\"\"
        from __future__ import annotations

        revision: str = "{revision_id}"

        def upgrade() -> None:
            pass

        def downgrade() -> None:
            pass
        """
    )


def test_schema_convention_hook_passes_for_existing_migrations() -> None:
    """The hook must accept the existing migrations in this template repo."""
    result = _run_schema_convention_hook()
    assert result.returncode == 0, result.stdout + result.stderr
    assert "✅ 无违规" in result.stdout


@pytest.mark.parametrize(
    ("filename", "revision_id", "extra_args", "expected_reason"),
    [
        (
            "20260701_000000_create_blog_tables.py",
            "20260701_000000",
            ["--filename-separator", "_", "--disallow-zero-time"],
            "时间部分为 '000000'",
        ),
        (
            "20260701-104204-bad-slug.py",
            "20260701-104204",
            [],
            "不符合迁移脚本命名约定",
        ),
        (
            "20260701_104205_mismatch.py",
            "20260701_104204",
            ["--filename-separator", "_", "--require-revision-equals-timestamp-prefix"],
            "时间戳前缀",
        ),
    ],
)
def test_schema_convention_hook_rejects_invalid_migration_files(
    tmp_path: Path,
    filename: str,
    revision_id: str,
    extra_args: list[str],
    expected_reason: str,
) -> None:
    """The hook must reject malformed migration filenames and revision mismatches."""
    versions_dir = tmp_path / "alembic" / "versions"
    versions_dir.mkdir(parents=True)
    migration_file = versions_dir / filename
    migration_file.write_text(_migration_body(revision_id), encoding="utf-8")

    result = _run_schema_convention_hook(
        "--alembic-versions-dir",
        str(versions_dir),
        *extra_args,
        str(migration_file),
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert expected_reason in result.stdout


def test_schema_convention_hook_accepts_underscore_separator_with_timestamp_revision(
    tmp_path: Path,
) -> None:
    """Derived projects using '_' and timestamp-prefix-as-revision must pass."""
    versions_dir = tmp_path / "alembic" / "versions"
    versions_dir.mkdir(parents=True)
    migration_file = versions_dir / "20260701_104202_create_blog_tables.py"
    migration_file.write_text(_migration_body("20260701_104202"), encoding="utf-8")

    result = _run_schema_convention_hook(
        "--alembic-versions-dir",
        str(versions_dir),
        "--filename-separator",
        "_",
        "--require-revision-equals-timestamp-prefix",
        str(migration_file),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "✅ 无违规" in result.stdout
