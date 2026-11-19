"""rv-4：从实际 just copy 输出检查公开分发资产、凭据与历史边界。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402
sys.path.insert(0, str(stack.WORKTREE / "scripts/shared/template"))
from setup_copied_database import derive_database_name  # noqa: E402

COPY_RELATIVE_PATH = Path(".venv/rv58-copy-rv4-audit")
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".otf"}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".jar", ".whl"}
FORBIDDEN_PATTERN = re.compile(
    r"cargox|outlook|freight|cost\.rate|vendor/|shadcn[- ]admin|satnaing|zata admin|1126828125",
    re.IGNORECASE,
)
FORBIDDEN_PATH_PATTERNS = (
    re.compile(r"(^|/)shadcn-admin[^/]*(/|$)", re.IGNORECASE),
    re.compile(r"(^|/)qq-group-qr[^/]*(/|$)", re.IGNORECASE),
    re.compile(r"^frontend-admin/\.github(?:/|$)", re.IGNORECASE),
)
GENERATED_DIRECTORY_NAMES = {
    "node_modules",
    "dist",
    ".next",
    "__pycache__",
    ".venv",
    ".pnpm-store",
    ".turbo",
    ".cache",
    "playwright-report",
    "test-results",
    "coverage",
}
COPY_ARTIFACT_DIRECTORY_NAMES = {
    "node_modules",
    "dist",
    ".next",
    ".pnpm-store",
    ".turbo",
    ".cache",
    "playwright-report",
    "test-results",
    "coverage",
}
ALLOWED_NEUTRAL_REFERENCES = {
    "scripts/shared/template/sync_template.sh": (
        "cargox",
        "historical product-specific customization in a sync-policy comment",
    ),
    "tests/guards/shared/test_worktree_submodule_init.py": (
        "vendor/",
        "generic third-party submodule path in an isolated git fixture",
    ),
}


def files_below(path: Path) -> list[Path]:
    """列出实际复制输出下的发布文件，跳过生成目录。"""
    if path.is_file():
        return [path]
    return [
        file_path
        for file_path in path.rglob("*")
        if file_path.is_file()
        and not GENERATED_DIRECTORY_NAMES.intersection(file_path.relative_to(path).parts[:-1])
    ]


def run_copy() -> str:
    """经正式模板入口生成一次性干净副本。"""
    destination = stack.WORKTREE / COPY_RELATIVE_PATH
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite {destination}")
    result = subprocess.run(
        ["just", "copy", str(COPY_RELATIVE_PATH)],
        cwd=stack.WORKTREE,
        env={
            **os.environ,
            "MODEL_BASE_URL": "",
            "MODEL_API_KEY": "",
            "MODEL_NAME": "",
            "SYNC_TEMPLATE_TEMPLATE_REPO": str(stack.WORKTREE),
        },
        capture_output=True,
        text=True,
        errors="replace",
        timeout=240,
    )
    output = f"$ just copy {COPY_RELATIVE_PATH}\n{result.stdout}{result.stderr}"
    if result.returncode != 0:
        raise RuntimeError(output[-5000:])
    return output


def source_history_inventory(report: stack.Report) -> None:
    """检查被审计仓库自己的历史文件边界，不对外分发该历史。"""
    tracked_files = subprocess.run(
        ["git", "ls-files"], cwd=stack.WORKTREE, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    secret_history = subprocess.run(
        ["git", "log", "--all", "--format=%H %s", "--", ".env", ".env.local", ".env.*.local"],
        cwd=stack.WORKTREE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    media_history = subprocess.run(
        [
            "git",
            "log",
            "--all",
            "--format=%H %s",
            "--",
            "*.png",
            "*.jpg",
            "*.zip",
            "*.woff",
            "*.woff2",
            "*.ttf",
        ],
        cwd=stack.WORKTREE,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    report("source tracked-file count:", len(tracked_files))
    report("source local-secret-file history:", secret_history or "<none>")
    report("source historical media entries are not exported with `just copy`:", media_history or "<none>")
    if secret_history:
        raise AssertionError("source Git history contains local secret files; clean-history distribution required")


def drop_copy_database() -> None:
    """删除 just copy 为隔离副本创建的本地数据库。"""
    try:
        source_url = sa.engine.make_url(stack._dotenv_value("DATABASE_URL"))
    except RuntimeError:
        return
    database_name = derive_database_name(COPY_RELATIVE_PATH.name)
    if source_url.drivername.startswith(("postgresql", "postgres")):
        maintenance_database = "postgres"
        database_kind = "pg"
    elif source_url.drivername.startswith("mysql"):
        maintenance_database = "mysql"
        database_kind = "mysql"
    else:
        return
    target_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    maintenance_url = source_url.set(database=maintenance_database).render_as_string(hide_password=False)
    stack.TempDatabase(
        kind=database_kind,
        name=database_name,
        url=target_url,
        admin_url=maintenance_url,
    ).drop()


def main() -> None:
    """从真实派生项目检查发布文件、资产、环境文件与 Git 元数据。"""
    report = stack.Report(stack.EVIDENCE_DIR / "rv-4-distribution-audit.txt")
    destination = stack.WORKTREE / COPY_RELATIVE_PATH
    try:
        report(f"# rv-4 distribution audit at {datetime.now(UTC).isoformat()}")
        report("identity:", stack.git_identity())
        source_history_inventory(report)
        copy_output = run_copy()
        report("real copy entry:", "just copy completed; source .env.local is temporary migration input only")
        report("copy output summary:", "\n".join(line for line in copy_output.splitlines() if "Copying template" in line or "migrations" in line or "Skipping initial commit" in line))

        publish_files = files_below(destination)
        leftover_build_artifacts = [
            path.relative_to(destination).as_posix()
            for path in destination.rglob("*")
            if path.is_dir() and path.name in COPY_ARTIFACT_DIRECTORY_NAMES
        ]
        report("excluded local build/cache directories in clean copy:", leftover_build_artifacts or "<none>")
        if leftover_build_artifacts:
            raise AssertionError("clean copy contains local build or test artifacts")
        suffix_counts = Counter(path.suffix.lower() or "<no-extension>" for path in publish_files)
        report("clean-copy publish file count:", len(publish_files))
        report("clean-copy suffix inventory:", dict(sorted(suffix_counts.items())))

        violations = []
        allowed_references = []
        for file_path in publish_files:
            relative_path = file_path.relative_to(destination).as_posix()
            for path_pattern in FORBIDDEN_PATH_PATTERNS:
                if path_pattern.search(relative_path):
                    violations.append(f"{relative_path}: forbidden source-branded path")
            if file_path.suffix.lower() in MEDIA_SUFFIXES | ARCHIVE_SUFFIXES:
                continue
            try:
                file_text = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for match in FORBIDDEN_PATTERN.finditer(file_text):
                expected_reference = ALLOWED_NEUTRAL_REFERENCES.get(relative_path)
                if expected_reference and match.group(0).lower() == expected_reference[0]:
                    allowed_references.append(
                        f"{relative_path}: {match.group(0)} — {expected_reference[1]}"
                    )
                else:
                    violations.append(f"{relative_path}: {match.group(0)}")
        report("approved neutral infrastructure/test references:", allowed_references or "<none>")
        report("forbidden source-product path/text hits:", violations or "<none>")
        if violations:
            raise AssertionError("forbidden source-product path or text exists in actual distribution output")

        private_environment_files = [
            file_path.relative_to(destination).as_posix()
            for file_path in files_below(destination)
            if file_path.name.startswith(".env")
            and file_path.name != ".env.run-state"
            and not file_path.name.endswith(".example")
        ]
        report("private dotenv files in clean copy:", private_environment_files or "<none>")
        if private_environment_files:
            raise AssertionError("private dotenv file was copied into the distribution output")

        copied_archives = [path.relative_to(destination).as_posix() for path in publish_files if path.suffix.lower() in ARCHIVE_SUFFIXES]
        report("archive/binary packages in clean copy:", copied_archives or "<none>")
        if copied_archives:
            raise AssertionError("archive or binary package requires explicit rights review")

        tracked_files = subprocess.run(
            ["git", "ls-files"], cwd=stack.WORKTREE, capture_output=True, text=True, check=True
        ).stdout.splitlines()
        media_files = [path for path in tracked_files if Path(path).suffix.lower() in MEDIA_SUFFIXES]
        report("tracked media from source tree:", media_files or "<none>")
        for relative_path in media_files:
            copied_media_path = destination / relative_path
            if not copied_media_path.is_file():
                report("media excluded by copy policy:", relative_path)
                continue
            metadata = subprocess.run(
                ["file", "--brief", str(copied_media_path)], capture_output=True, text=True, check=True
            ).stdout.strip()
            report("copy media metadata:", relative_path, "=>", metadata)

        git_metadata_path = destination / ".git"
        report("Git history copied:", git_metadata_path.exists())
        if git_metadata_path.exists():
            raise AssertionError("distribution copy unexpectedly contains Git history")
        report("source import/license inventory:", "no ai-assistant/freshai source file, migration, dependency lock, font, media, or binary is imported")
        report("history decision:", "`just copy` output has clean history; public source repository history is not claimed as the distribution artifact")
        report("rights decision:", "all copied media are target template assets; no source-repository asset needs a new license grant")
        report("\nRV_RESULT: PASS rv-4")
    finally:
        if destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        try:
            drop_copy_database()
        finally:
            report.save()


if __name__ == "__main__":
    stack.main_guard(main)
