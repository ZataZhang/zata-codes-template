"""守护真实数据库测试必须打 ``realdb`` 标记的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着有测试经 ``build_client`` /
``seed_admin`` 写入真实数据库却没打 ``realdb`` 标记，会绕过残留哨兵并在
xdist 并行下污染其他 worker 的快照。正确做法是给该测试打
``@pytest.mark.realdb`` 并确保它清理自己创建的数据（经 ``build_client`` /
``seed_admin`` 自动登记），而不是修改本文件让测试通过；仅当约定本身需要变更时
才改本文件，并同步更新相关约定文档。详见 ``docs/ai-standards/testing.md`` 的
Guard Tests 小节。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_TEST_DIR = REPO_ROOT / "tests" / "backend"

# 请求这两个 fixture 之一的测试会经 ``TestClient(create_app())`` 或
# ``SessionLocal`` 写入真实数据库。
WRITE_FIXTURES = ("build_client", "seed_admin")
# 命中即视为"已有自动登记清理"的特征；这样的文件由残留哨兵兜底。
CLEANUP_SIGNALS = (
    "entity_registry",
    "delete_tracked_entities",
    "TrackedTestClient",
    "has_realdb_marker",
)


def _test_files() -> list[Path]:
    """列出 backend 包下的测试文件（排除本守卫文件）。"""
    self_path = Path(__file__).resolve()
    return [
        test_file
        for test_file in sorted(BACKEND_TEST_DIR.glob("test_*.py"))
        if test_file.resolve() != self_path
    ]


def _has_realdb_marker(source_text: str) -> bool:
    """判断源码是否带 ``realdb`` 标记（模块级 ``pytestmark``）。"""
    return bool(re.search(r"pytestmark\s*=\s*pytest\.mark\.realdb", source_text))


def _requests_write_fixture(source_text: str) -> bool:
    """判断源码是否请求了会写真实数据库的 fixture。"""
    return any(f"{fixture}" in source_text for fixture in WRITE_FIXTURES)


def _has_cleanup(source_text: str) -> bool:
    """判断源码是否含自动登记清理逻辑。"""
    return any(signal in source_text for signal in CLEANUP_SIGNALS)


def test_realdb_tests_must_be_marked() -> None:
    """写真实数据库的测试必须打 realdb 标记，否则无法被残留哨兵保护。"""
    unmarked_files: list[str] = []
    for test_file in _test_files():
        source_text = test_file.read_text(encoding="utf-8")
        if not _requests_write_fixture(source_text):
            continue
        if _has_realdb_marker(source_text):
            continue
        unmarked_files.append(str(test_file.relative_to(REPO_ROOT)))
    assert not unmarked_files, (
        "以下测试会写真实数据库但未打 realdb 标记，将被残留哨兵漏检并在并行下"
        "互相污染快照，请为其添加标记并确保清理自己创建的数据：\n  - "
        + "\n  - ".join(unmarked_files)
    )
