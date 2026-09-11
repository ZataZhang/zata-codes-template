"""守护 Alembic 迁移命名约定的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

本文件只守护 ``alembic.ini`` 的 ``file_template`` 契约（项目自有配置）；
schema convention hook（``hooks/shared/check_schema_conventions.py``，随
sync 分发）的行为守卫位于 ``tests/guards/shared/test_check_schema_conventions.py``。

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
