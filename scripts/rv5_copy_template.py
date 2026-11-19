"""rv-5：真实 just copy、干净配置、模板同步与派生底座启动。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402
sys.path.insert(0, str(stack.WORKTREE / "scripts/shared/template"))
from setup_copied_database import derive_database_name  # noqa: E402

COPY_RELATIVE_PATH = Path(".venv/rv58-copy-issue58")
COPY_DIRECTORY = stack.WORKTREE / COPY_RELATIVE_PATH


def copy_database_url() -> tuple[str, str]:
    """返回副本隔离数据库的连接串与数据库名，不将其写入证据。"""
    source_url = sa.engine.make_url(stack._dotenv_value("DATABASE_URL"))
    database_name = derive_database_name(COPY_RELATIVE_PATH.name)
    target_url = source_url.set(database=database_name).render_as_string(hide_password=False)
    return target_url, database_name


def run_command(arguments: list[str], cwd: Path, timeout: int = 240) -> subprocess.CompletedProcess[str]:
    """以副本隔离数据库运行维护命令，捕获输出但不打印凭据。"""
    target_database_url, _database_name = copy_database_url()
    return subprocess.run(
        arguments,
        cwd=cwd,
        env={
            **os.environ,
            "DATABASE_URL": target_database_url,
            "MODEL_BASE_URL": "",
            "MODEL_API_KEY": "",
            "MODEL_NAME": "",
            "SYNC_TEMPLATE_TEMPLATE_REPO": str(stack.WORKTREE),
        },
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
    )


def public_output_summary(output_text: str) -> str:
    """保留副本命令关键行，并过滤可能包含配置内容的文本。"""
    approved_markers = (
        "Copying template",
        "Picked random ports",
        "Created bilingual README",
        "Running database migrations",
        "Skipping initial commit",
        "Everything is up to date",
        "No files need to be updated",
        "Found ",
        "CHANGED",
        "NEW",
        "ERROR:",
        "ModuleNotFoundError",
    )
    return "\n".join(
        output_line
        for output_line in output_text.splitlines()
        if any(marker in output_line for marker in approved_markers)
    )


def drop_copy_database() -> None:
    """删除本次 just copy 派生项目创建的测试数据库。"""
    target_database_url, database_name = copy_database_url()
    parsed_url = sa.engine.make_url(target_database_url)
    if parsed_url.drivername.startswith(("postgresql", "postgres")):
        database_kind, maintenance_name = "pg", "postgres"
    elif parsed_url.drivername.startswith("mysql"):
        database_kind, maintenance_name = "mysql", "mysql"
    else:
        return
    maintenance_url = parsed_url.set(database=maintenance_name).render_as_string(hide_password=False)
    stack.TempDatabase(
        kind=database_kind,
        name=database_name,
        url=target_database_url,
        admin_url=maintenance_url,
    ).drop()


def private_environment_files(copy_root: Path) -> list[str]:
    """列出副本中的私有 dotenv 文件名，不读取或输出其内容。"""
    return [
        file_path.relative_to(copy_root).as_posix()
        for file_path in copy_root.rglob("*")
        if file_path.is_file()
        and not {".venv", "node_modules", "dist", ".next"}.intersection(
            file_path.relative_to(copy_root).parts[:-1]
        )
        and file_path.name.startswith(".env")
        and file_path.name != ".env.run-state"
        and not file_path.name.endswith(".example")
    ]


def start_backend_and_check_health(report: stack.Report, *, negative_control: bool) -> None:
    """启动复制项目的真实后端，或在入口故障注入后要求启动断言失败。"""
    run_state_lines = (COPY_DIRECTORY / ".env.run-state").read_text(encoding="utf-8").splitlines()
    backend_port = next(
        line.split("=", 1)[1] for line in run_state_lines if line.startswith("BACKEND_PORT=")
    )
    health_url = f"http://127.0.0.1:{backend_port}/health"
    if negative_control:
        backend_entry_path = COPY_DIRECTORY / "src/backend/main.py"
        quarantined_entry_path = backend_entry_path.with_suffix(".rv5-negative-control")
        backend_entry_path.rename(quarantined_entry_path)
        try:
            broken_start = run_command(["just", "run", "backend"], COPY_DIRECTORY, timeout=30)
            health_response = None
            try:
                health_response = httpx.get(health_url, timeout=2)
            except httpx.HTTPError:
                pass
            if broken_start.returncode == 0 or health_response is not None:
                raise AssertionError("missing copied backend entry point unexpectedly started successfully")
            report("fault injection:", "removed copied src/backend/main.py in isolated destination")
            report("backend startup result:", public_output_summary(broken_start.stdout + broken_start.stderr))
            report("expected_fail:", "the copied project cannot expose /health after its backend entry point is removed")
            report("\nEXPECTED_FAIL: rv-5 startup assertion detected the missing copied entry point")
            report("RV_RESULT: NEGATIVE CONTROL DETECTED rv-5")
        finally:
            quarantined_entry_path.rename(backend_entry_path)
        return

    backend_process = subprocess.Popen(
        ["just", "run", "backend"],
        cwd=COPY_DIRECTORY,
        env={
            **os.environ,
            "DATABASE_URL": copy_database_url()[0],
            "MODEL_BASE_URL": "",
            "MODEL_API_KEY": "",
            "MODEL_NAME": "",
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    try:
        health_response = None
        deadline = time.time() + 90
        while time.time() < deadline:
            try:
                health_response = httpx.get(health_url, timeout=2)
                if health_response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if backend_process.poll() is not None:
                break
            time.sleep(0.5)
        if health_response is None or health_response.status_code != 200:
            raise AssertionError("copied backend did not expose /health")
        report("copied backend /health:", health_response.status_code, health_response.json())
        report("startup uses a separately configured DATABASE_URL; copied local credentials are absent")
    finally:
        run_command(["just", "down"], COPY_DIRECTORY, timeout=60)
        backend_process.wait(timeout=30)


def main() -> None:
    """经真实 just copy 入口检查干净副本、同步和运行能力。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    arguments = parser.parse_args()
    report_path = stack.EVIDENCE_DIR / (
        "rv-5-negative-control.txt" if arguments.negative_control else "rv-5-template-copy.txt"
    )
    report = stack.Report(report_path)
    try:
        report(f"# rv-5 template copy at {datetime.now(UTC).isoformat()}")
        report("identity:", json.dumps(stack.git_identity()))
        if COPY_DIRECTORY.exists():
            raise RuntimeError(f"refusing to overwrite {COPY_DIRECTORY}")
        copy_command = ["just", "copy", str(COPY_RELATIVE_PATH)]
        copy_result = run_command(copy_command, stack.WORKTREE)
        if copy_result.returncode != 0:
            raise RuntimeError(public_output_summary(copy_result.stdout + copy_result.stderr))
        report("copy command:", "just copy", COPY_RELATIVE_PATH)
        report("local dotenv files in clean copy:", private_environment_files(COPY_DIRECTORY) or "<none>")
        if private_environment_files(COPY_DIRECTORY):
            raise AssertionError("clean copy contains a private dotenv file")
        report("runner/viewer state excluded:", not (COPY_DIRECTORY / ".agent-runner").exists(), not (COPY_DIRECTORY / ".env.view-state").exists())
        report(public_output_summary(copy_result.stdout + copy_result.stderr))

        if arguments.negative_control:
            start_backend_and_check_health(report, negative_control=True)
            return

        sync_result = run_command(["just", "sync-template", "--list"], COPY_DIRECTORY)
        if sync_result.returncode != 0:
            raise RuntimeError(public_output_summary(sync_result.stdout + sync_result.stderr))
        sync_output = sync_result.stdout + sync_result.stderr
        has_sync_listing = "Found " in sync_output and any(
            marker in sync_output for marker in ("CHANGED", "NEW", "justfile.shared")
        )
        if not has_sync_listing and "Everything is up to date" not in sync_output:
            raise AssertionError("copied template sync entry point did not enumerate shared files")
        report("real clone/compare sync-list completed; shared-file candidates are visible")
        report(public_output_summary(sync_output))
        start_backend_and_check_health(report, negative_control=False)
        report("copy migration and app configuration are current; model is intentionally unconfigured")
        report("\nRV_RESULT: PASS rv-5")
    finally:
        if COPY_DIRECTORY.exists():
            subprocess.run(
                ["just", "down"], cwd=COPY_DIRECTORY, capture_output=True, timeout=60, check=False
            )
            shutil.rmtree(COPY_DIRECTORY, ignore_errors=True)
        try:
            drop_copy_database()
        finally:
            report.save()


if __name__ == "__main__":
    stack.main_guard(main)
