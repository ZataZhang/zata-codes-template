"""守护「与 dev server 共用真实数据库」外部写者守卫的守卫测试（guard test）。

本文件位于 ``tests/guards/``，守护的是 ``tests/conftest.py`` 里的
``_guard_shared_database_external_writer``：它只在「run-state 记录的端口有监听者，
且 run-state 记录的库名与本次测试写的库相同（或旧格式没有库名）」时拦截。
失败意味着守卫退回「只看端口」（误拦 worktree 与主仓的端口撞车），或把旧格式 / 同库
放行（漏拦真正的共库）——两种都不会让别的测试变红，所以必须用真实本地监听钉住。
正确做法是修复守卫逻辑，而不是修改本文件让守卫通过；仅当判据本身需要变更时才改本文件，
并同步更新 ``docs/ai-standards/testing.md`` 的「与 dev server 共用数据库」小节。
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from tests import conftest as project_conftest
from tests import realdb_test_support

_CURRENT_DATABASE_NAME = "guard_current_db"
_OTHER_DATABASE_NAME = "guard_other_db"
_ACTIVE_RUN_HOOK_NAME = "find_live_nonterminal_runs"


@pytest.fixture
def dev_server_listener() -> Iterator[int]:
    """起一个真实的本地监听 socket，充当 ``just run`` 的后端端口。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener_socket:
        listener_socket.bind(("127.0.0.1", 0))
        listener_socket.listen(1)
        yield listener_socket.getsockname()[1]


@pytest.fixture
def guard_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """把守卫的 run-state 路径、本次库名与 pytest config 换成可控的真实边界。

    run-state 文件与监听 socket 都是真实的，只有「本次测试写哪个库」用 monkeypatch 固定，
    避免守卫测试依赖开发机的 ``DATABASE_URL``。
    """
    run_state_path = tmp_path / ".env.run-state"
    monkeypatch.setattr(project_conftest, "_RUN_STATE_FILE_PATH", run_state_path)
    monkeypatch.setattr(project_conftest, "_current_database_name", lambda: _CURRENT_DATABASE_NAME)
    monkeypatch.delenv("ALLOW_SHARED_DATABASE", raising=False)
    # 项目没有定义探测钩子时的默认形态；个别用例再显式装上钩子。
    monkeypatch.delattr(realdb_test_support, _ACTIVE_RUN_HOOK_NAME, raising=False)
    # 不带目标路径、不带 -m 表达式：守卫按「默认全量会选中 realdb 测试」处理。
    pytest_config = SimpleNamespace(
        getoption=lambda option_name, default=None: default,
        args=[],
        rootpath=tmp_path,
    )
    return SimpleNamespace(run_state_path=run_state_path, pytest_config=pytest_config)


def _write_run_state(run_state_path: Path, *, backend_port: int, database_name: str | None) -> None:
    """按 ``just run`` 的格式写 run-state；``database_name=None`` 模拟旧格式（无库名）。"""
    run_state_lines = [f"BACKEND_PORT={backend_port}", "FRONTEND_ADMIN_PORT=5173"]
    if database_name is not None:
        run_state_lines.append(f"DATABASE_NAME={database_name}")
    run_state_path.write_text("\n".join(run_state_lines) + "\n", encoding="utf-8")


def _blocking_message(pytest_config: SimpleNamespace) -> str | None:
    """触达守卫；被拦截时返回 ``pytest.exit`` 的提示文案，放行时返回 ``None``。

    不让 ``pytest.exit`` 直接冒出测试：它会终止整个 pytest 会话，守卫被改坏时就只剩
    「no tests ran」而没有可读的失败用例。
    """
    try:
        project_conftest._guard_shared_database_external_writer(pytest_config)
    except pytest.exit.Exception as blocked:
        return str(blocked)
    return None


def test_listener_on_a_different_database_does_not_block(
    guard_environment: SimpleNamespace, dev_server_listener: int
) -> None:
    """端口有监听者但 run-state 记录的是另一个库：别处进程占了同名端口，不拦。"""
    _write_run_state(
        guard_environment.run_state_path,
        backend_port=dev_server_listener,
        database_name=_OTHER_DATABASE_NAME,
    )

    assert _blocking_message(guard_environment.pytest_config) is None


def test_listener_on_the_same_database_blocks_and_names_the_database(
    guard_environment: SimpleNamespace, dev_server_listener: int
) -> None:
    """端口有监听者且 run-state 指向本库：真共库，拦截并在提示里带出库名。"""
    _write_run_state(
        guard_environment.run_state_path,
        backend_port=dev_server_listener,
        database_name=_CURRENT_DATABASE_NAME,
    )

    blocking_message = _blocking_message(guard_environment.pytest_config)

    assert blocking_message is not None
    assert _CURRENT_DATABASE_NAME in blocking_message
    assert "ALLOW_SHARED_DATABASE" in blocking_message


def test_legacy_run_state_without_database_name_blocks_conservatively(
    guard_environment: SimpleNamespace, dev_server_listener: int
) -> None:
    """旧格式 run-state 没有库名，无法证明不是同库：保守拦截，不因缺字段而放松。"""
    _write_run_state(
        guard_environment.run_state_path, backend_port=dev_server_listener, database_name=None
    )

    assert _blocking_message(guard_environment.pytest_config) is not None


def test_same_database_without_a_listener_does_not_block(
    guard_environment: SimpleNamespace,
) -> None:
    """run-state 指向本库但端口上没有任何监听者：dev server 已停，不拦。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as closed_port_socket:
        closed_port_socket.bind(("127.0.0.1", 0))
        closed_port = closed_port_socket.getsockname()[1]
    _write_run_state(
        guard_environment.run_state_path,
        backend_port=closed_port,
        database_name=_CURRENT_DATABASE_NAME,
    )

    assert _blocking_message(guard_environment.pytest_config) is None


def test_allow_shared_database_environment_variable_skips_the_guard(
    guard_environment: SimpleNamespace, dev_server_listener: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """显式设 ``ALLOW_SHARED_DATABASE=1`` 是文档化的逃生口，同库也放行。"""
    _write_run_state(
        guard_environment.run_state_path,
        backend_port=dev_server_listener,
        database_name=_CURRENT_DATABASE_NAME,
    )
    monkeypatch.setenv("ALLOW_SHARED_DATABASE", "1")

    assert _blocking_message(guard_environment.pytest_config) is None


def test_missing_active_run_hook_leaves_the_port_and_name_signal_working(
    guard_environment: SimpleNamespace,
) -> None:
    """项目没提供「库内活跃运行」探测时，该信号关闭：既不崩溃，也不静默放行端口信号。"""
    assert not hasattr(realdb_test_support, _ACTIVE_RUN_HOOK_NAME)

    assert project_conftest._find_project_active_runs() == []
    assert _blocking_message(guard_environment.pytest_config) is None


def test_project_active_run_hook_adds_its_own_blocking_signal(
    guard_environment: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """项目提供了探测钩子且报告有活跃运行：即使端口上没有监听者也拦截。"""
    monkeypatch.setattr(
        realdb_test_support,
        _ACTIVE_RUN_HOOK_NAME,
        lambda: [("run-1", "running")],
        raising=False,
    )

    blocking_message = _blocking_message(guard_environment.pytest_config)

    assert blocking_message is not None
    assert "run-1(running)" in blocking_message


def test_project_active_run_hook_database_errors_do_not_block(
    guard_environment: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """探测钩子因库不可用 / 表未建立而抛 SQLAlchemy 错误：守卫不越权，交给测试自身暴露。"""

    def _raise_database_error() -> list[tuple[str, str]]:
        raise OperationalError("select 1", {}, Exception("database unavailable"))

    monkeypatch.setattr(
        realdb_test_support, _ACTIVE_RUN_HOOK_NAME, _raise_database_error, raising=False
    )

    assert _blocking_message(guard_environment.pytest_config) is None
