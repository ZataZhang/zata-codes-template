"""Pytest 全局配置：本地导入路径、跨目录共享夹具与真实库残留哨兵。

``_realdb_residue_sentinel`` 对所有测试生效：前后对比哨兵覆盖表的主键集合，
任何测试泄漏或误删真实数据库数据都会当场 fail 并列出泄漏的表与 ID。写真实
数据库的测试（打 ``@pytest.mark.realdb``）会被 xdist 串行调度，避免并行
worker 互相污染快照。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Iterator

import pytest


def _ensure_project_root_on_path() -> None:
    """Ensure project root is on sys.path for local package imports."""
    project_root_path = Path(__file__).resolve().parents[1]
    if str(project_root_path) not in sys.path:
        sys.path.insert(0, str(project_root_path))


# backend 包的导入依赖上面这行先把项目根放进 sys.path，因此不能提到文件顶部。
_ensure_project_root_on_path()

from tests.realdb_test_support import has_realdb_marker  # noqa: E402

_REALDB_SCOPE: str = "realdb"

# 写真实数据库的测试文件（整个文件打 ``pytestmark = pytest.mark.realdb``）。
# controller 端 xdist 调度器只有 nodeid、拿不到 item，无法按 marker 判断；
# 而文件是 realdb 测试的天然串行单元（整文件同标记），故按文件路径分组，
# 让同文件的 realdb 测试在同一 worker 串行，哨兵快照不被其他 worker 干扰。
_REALDB_TEST_FILES: frozenset[str] = frozenset(
    {
        "tests/backend/test_admin_user_management.py",
        "tests/backend/test_auth_domains.py",
    }
)


class _RealDbLoadScopeScheduling:
    """把 ``_REALDB_TEST_FILES`` 里的测试固定进同一 scope 的 loadgroup 调度器。

    xdist 自带的 ``LoadGroupScheduling`` 只按 nodeid 里的 ``@<组名>`` 后缀
    分组。realdb 测试写入由 ``DATABASE_URL`` 指向的真实数据库，哨兵依赖前后
    主键快照，若 realdb 测试跨 worker 并行，快照会把其他 worker 的写入误判为
    残留。因此把 realdb 文件收进单一 scope（同 worker 串行），其余测试回退到
    xdist 默认的文件级 loadgroup 分组，保住并行度。
    """

    def __new__(cls, config, log=None):
        """惰性继承 xdist 的 LoadScopeScheduling，避免无 xdist 时导入失败。"""
        from xdist.scheduler.loadscope import LoadScopeScheduling

        class _Scheduling(LoadScopeScheduling):
            def _split_scope(self_inner, nodeid: str) -> str:  # noqa: N805
                scope_name = nodeid.split("::")[0]
                if scope_name in _REALDB_TEST_FILES:
                    return _REALDB_SCOPE
                if nodeid.rfind("@") > nodeid.rfind("]"):
                    return nodeid.split("@")[-1]
                return nodeid

        return _Scheduling(config, log)


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_make_scheduler(config, log) -> "_RealDbLoadScopeScheduling | None":
    """把 ``--dist=loadgroup`` 替换为按 realdb 文件分组的调度器。"""
    if config.getoption("dist") != "loadgroup":
        return None
    return _RealDbLoadScopeScheduling(config, log)


@pytest.fixture(autouse=True)
def _realdb_residue_sentinel(request: pytest.FixtureRequest) -> Iterator[None]:
    """真实数据库测试的前后主键快照对比，净变化即 fail。

    只对带 ``realdb`` 标记的测试生效。realdb 文件已由
    ``pytest_xdist_make_scheduler`` 定制的调度器收进同一 scope，
    ``--dist=loadgroup`` 下整组在同一 worker 串行执行，快照不被其他
    worker 的写入干扰。哨兵覆盖表见
    ``tests.realdb_test_support.residue_table_models``。快照前先预建一次
    应用，确保 ``create_app()`` 装配期种子的净新增不会误报。
    """
    if not has_realdb_marker(request):
        yield
        return
    from backend.main import create_app

    create_app()
    from tests.realdb_test_support import (  # noqa: PLC0415
        diff_residue_tables,
        snapshot_residue_tables,
    )

    snapshot_before = snapshot_residue_tables()
    yield
    residue_diff = diff_residue_tables(snapshot_before, snapshot_residue_tables())
    assert not residue_diff, "真实数据库测试泄漏或误删数据：" + ", ".join(
        f"{table_name} {direction}={sorted(primary_keys)[:5]}"
        for table_name, directions in residue_diff.items()
        for direction, primary_keys in directions.items()
        if primary_keys
    )
