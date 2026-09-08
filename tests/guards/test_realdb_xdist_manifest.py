"""守护 xdist 分组调度器的 realdb 文件清单与实际标记一致的守卫测试（guard test）。

``tests/conftest.py`` 的 ``_REALDB_TEST_FILES`` 是静态声明的"哪些测试文件写真实
数据库"。xdist 的 controller 端调度器只有 nodeid、拿不到 item，无法按 marker
判断，只能依赖这份清单把 realdb 文件收进同一 worker 串行。若新测试文件打了
``realdb`` 标记却未加入清单，xdist 并行下哨兵会把其他 worker 的写入误判为残留；
若清单里的文件实际已不标 realdb，则白白损失并行度。

本文件位于 ``tests/guards/``，失败意味着清单与实际标记漂移，应更新
``tests/conftest.py`` 的 ``_REALDB_TEST_FILES``，而不是修改本文件让测试通过；
仅当约定本身需要变更时才改本文件，并同步更新对应约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_TEST_DIR = REPO_ROOT / "tests" / "backend"
CONFTEST_PATH = REPO_ROOT / "tests" / "conftest.py"

_MODULE_PYTESTMARK_REALDB = re.compile(r"^pytestmark\s*=\s*pytest\.mark\.realdb", re.MULTILINE)


def _declared_realdb_files() -> set[str]:
    """从根 conftest 解析出静态声明的 realdb 文件清单。"""
    source = CONFTEST_PATH.read_text(encoding="utf-8")
    match = re.search(r"_REALDB_TEST_FILES[^=]*=\s*frozenset\(\s*\{(.*?)\}\s*\)", source, re.DOTALL)
    assert match, "未在 tests/conftest.py 找到 _REALDB_TEST_FILES 集合"
    return set(re.findall(r'"([^"]+)"', match.group(1)))


def _actual_realdb_files() -> set[str]:
    """扫描出实际打了模块级 ``pytestmark = pytest.mark.realdb`` 的测试文件。"""
    actual: set[str] = set()
    for test_file in sorted(BACKEND_TEST_DIR.glob("test_*.py")):
        source = test_file.read_text(encoding="utf-8")
        if _MODULE_PYTESTMARK_REALDB.search(source):
            actual.add(str(test_file.relative_to(REPO_ROOT)))
    return actual


def test_realdb_file_manifest_matches_actual_marks() -> None:
    """静态声明的 realdb 文件清单必须与实际的模块级 realdb 标记一致。"""
    declared = _declared_realdb_files()
    actual = _actual_realdb_files()
    missing_in_manifest = actual - declared
    stale_in_manifest = declared - actual
    assert not missing_in_manifest, (
        "以下测试文件打了模块级 pytest.mark.realdb，但未加入 "
        "tests/conftest.py 的 _REALDB_TEST_FILES，xdist 并行下哨兵会误判残留：\n  - "
        + "\n  - ".join(sorted(missing_in_manifest))
    )
    assert not stale_in_manifest, (
        "tests/conftest.py 的 _REALDB_TEST_FILES 声明了以下文件，但它们并未打 "
        "模块级 pytest.mark.realdb（白白损失并行度）：\n  - "
        + "\n  - ".join(sorted(stale_in_manifest))
    )
