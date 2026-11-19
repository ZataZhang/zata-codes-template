"""清理本次 RV-5 同步断言调试用副本及其临时数据库。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402
sys.path.insert(0, str(stack.WORKTREE / "scripts/shared/template"))
from setup_copied_database import derive_database_name  # noqa: E402


def main() -> None:
    """删除唯一命名的临时副本和数据库，不显示连接凭据。"""
    relative_copy = Path(".venv/rv58-copy-sync-debug")
    copy_directory = stack.WORKTREE / relative_copy
    database_name = derive_database_name(relative_copy.name)
    source_url = sa.engine.make_url(stack._dotenv_value("DATABASE_URL"))
    if source_url.drivername.startswith(("postgresql", "postgres")):
        database_kind, maintenance_name = "pg", "postgres"
    elif source_url.drivername.startswith("mysql"):
        database_kind, maintenance_name = "mysql", "mysql"
    else:
        raise RuntimeError("debug copy database uses an unsupported local driver")
    target_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    maintenance_url = source_url.set(database=maintenance_name).render_as_string(hide_password=False)
    stack.TempDatabase(
        kind=database_kind,
        name=database_name,
        url=target_url,
        admin_url=maintenance_url,
    ).drop()
    if copy_directory.exists():
        shutil.rmtree(copy_directory)
    generated_videos = stack.EVIDENCE_DIR / "videos"
    if generated_videos.exists():
        shutil.rmtree(generated_videos)
    obsolete_screenshot_video = stack.EVIDENCE_DIR / "rv-2-agent-run.webm"
    obsolete_screenshot_video.unlink(missing_ok=True)
    print("RV5 debug copy, isolated database, and disposable Playwright videos cleaned")


if __name__ == "__main__":
    stack.main_guard(main)
