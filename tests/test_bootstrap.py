"""验证应用 bootstrap 的并发种子行为。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.composition import bootstrap


def test_seed_tools_accepts_complete_concurrent_seed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """另一并发启动实例完整写入内置工具时，当前实例应安全结束。"""
    database_session = MagicMock()
    database_session.query.return_value.first.return_value = None
    database_session.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))
    database_session.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(id="web_search"),
        SimpleNamespace(id="code_runner"),
    ]
    monkeypatch.setattr(bootstrap, "SessionLocal", lambda: database_session)

    bootstrap.seed_tools()

    database_session.rollback.assert_called_once()
    database_session.close.assert_called_once()


def test_seed_tools_reraises_unexpected_integrity_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """内置工具未完整存在时，不能吞掉非并发种子导致的完整性错误。"""
    database_session = MagicMock()
    database_session.query.return_value.first.return_value = None
    database_session.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))
    database_session.query.return_value.filter.return_value.all.return_value = [
        SimpleNamespace(id="web_search"),
    ]
    monkeypatch.setattr(bootstrap, "SessionLocal", lambda: database_session)

    with pytest.raises(IntegrityError):
        bootstrap.seed_tools()

    database_session.rollback.assert_called_once()
    database_session.close.assert_called_once()
