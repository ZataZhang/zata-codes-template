"""守护「in-process alembic 迁移不得摧毁宿主进程 logging 配置」的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

为什么值得一条守卫：``logging.config.fileConfig`` 是"清场式"配置调用。它会
无条件清空 root logger 的 handler 列表、把 root level 重置成 ``alembic.ini``
里的 ``WARNING``，并且 ``disable_existing_loggers`` 默认为 ``True``——所有已存在
且不属于 ``alembic.ini`` logger 层级的 logger 会被永久标记 ``disabled = True``。

迁移并不总是独占一个进程：``database.py`` 的 ``create_tables()`` /
``init_database()`` 会在进程内调用 ``command.upgrade(...)``，测试 fixture 也常
在进程内跑 ``alembic upgrade head``。在 pytest 进程里这个破坏是静默且严重的：
``caplog`` 依赖挂在 root logger 上的 handler，它会被摘掉；迁移之前 import 过的
``backend.*`` logger 会永久 ``disabled``。此后所有基于日志的断言都退化成
"records 恒为空"——通过或失败都与被测行为无关。

因此 ``alembic/env.py`` 必须在 pytest 进程内完全跳过 ``fileConfig``，并在 CLI /
in-process 应用路径上传 ``disable_existing_loggers=False``。
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from alembic import command
from alembic.config import Config as AlembicConfig

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[2]


def _alembic_config() -> AlembicConfig:
    """返回指向本项目迁移脚本的 Alembic 配置。

    Returns:
        AlembicConfig: 已绑定 ``alembic.ini`` 与 ``script_location`` 的配置对象。
    """
    alembic_cfg = AlembicConfig(str(_PROJECT_ROOT_PATH / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(_PROJECT_ROOT_PATH / "alembic"))
    return alembic_cfg


def _run_in_process_upgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """在临时 SQLite 库上真实执行一次进程内 ``alembic upgrade head``。

    这里刻意不 mock ``command.upgrade``：被守护的副作用发生在 ``env.py`` 被
    alembic 执行的那一刻，任何替身都会把要抓的 bug 一起替掉。

    Args:
        tmp_path: pytest 临时目录。
        monkeypatch: 用于把 ``DATABASE_URL`` 指向临时库，避免碰到真实数据库。
    """
    sqlite_database_path = tmp_path / "alembic-logging-guard.sqlite3"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{sqlite_database_path}")
    command.upgrade(_alembic_config(), "head")


@pytest.fixture(autouse=True)
def restore_process_logging_state() -> Iterator[None]:
    """快照并恢复进程级 logging 状态。

    本文件的断言必须在迁移**真的**破坏日志配置时变红，因此不能阻止破坏发生。
    但破坏一旦逸出本文件，同一个 xdist worker 里后续用例的日志断言就会跟着
    静默失效。这里在用例结束时把 root handler、root level 和所有已存在 logger
    的 ``disabled`` 标记复原，把爆炸半径关在本文件内。

    Yields:
        None: 用例执行期间不需要向外暴露对象。
    """
    root_logger = logging.getLogger()
    saved_root_handlers = list(root_logger.handlers)
    saved_root_level = root_logger.level
    saved_manager_disable = logging.root.manager.disable
    saved_disabled_flags = {
        logger_name: existing_logger.disabled
        for logger_name, existing_logger in logging.root.manager.loggerDict.items()
        if isinstance(existing_logger, logging.Logger)
    }
    try:
        yield
    finally:
        root_logger.handlers[:] = saved_root_handlers
        root_logger.setLevel(saved_root_level)
        logging.root.manager.disable = saved_manager_disable
        for logger_name, was_disabled in saved_disabled_flags.items():
            restored_logger = logging.root.manager.loggerDict.get(logger_name)
            if isinstance(restored_logger, logging.Logger):
                restored_logger.disabled = was_disabled


def test_in_process_migration_does_not_disable_existing_loggers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """迁移前已创建的业务 logger，迁移后不得被标记 ``disabled``。"""
    pre_existing_logger = logging.getLogger("backend.guards.alembic_logging_isolation.disabled")
    assert not pre_existing_logger.disabled, "前置条件不成立：logger 在迁移前就已被禁用"

    _run_in_process_upgrade(tmp_path, monkeypatch)

    assert not pre_existing_logger.disabled, (
        "进程内 alembic 迁移把已存在的 backend.* logger 永久禁用了："
        "alembic/env.py 的 fileConfig 使用了默认的 disable_existing_loggers=True。"
        "此后该 logger 不再产出任何记录，基于日志的断言会静默退化成恒为空。"
    )


def test_in_process_migration_keeps_root_handlers_attached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """迁移前挂在 root logger 上的 handler，迁移后必须仍然在位。"""
    root_logger = logging.getLogger()
    probe_handler = logging.NullHandler()
    root_logger.addHandler(probe_handler)

    _run_in_process_upgrade(tmp_path, monkeypatch)

    assert probe_handler in root_logger.handlers, (
        "进程内 alembic 迁移清空了 root logger 的 handler 列表："
        "fileConfig 是清场式配置，会无条件替换 root handlers。"
        "宿主进程（pytest caplog、应用自身的 JSON/文件 handler）由此静默失去日志输出。"
    )


def test_caplog_still_captures_records_after_in_process_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """迁移之后，``caplog`` 仍须能捕获到业务 logger 的记录。"""
    captured_logger_name = "backend.guards.alembic_logging_isolation.caplog"
    expected_message = "guard probe after in-process migration"

    _run_in_process_upgrade(tmp_path, monkeypatch)

    with caplog.at_level(logging.INFO, logger=captured_logger_name):
        logging.getLogger(captured_logger_name).info(expected_message)

    assert any(record.getMessage() == expected_message for record in caplog.records), (
        "迁移之后 caplog 抓不到任何记录：caplog 依赖挂在 root logger 上的 handler，"
        "被 alembic/env.py 的 fileConfig 摘掉了。所有 caplog 断言都会退化成"
        "'records 恒为空'，通过与失败都与被测行为无关。"
    )
