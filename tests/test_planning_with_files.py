"""Regression tests for the planning-with-files skill scripts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = REPO_ROOT / "skills" / "planning-with-files" / "scripts"
INIT_SESSION_SCRIPT_PATH = SCRIPT_DIR / "init-session.sh"
ARCHIVE_SESSION_SCRIPT_PATH = SCRIPT_DIR / "archive-session.sh"
UPDATE_PHASE_SCRIPT_PATH = SCRIPT_DIR / "update_phase_status.py"
CHECK_COMPLETE_SCRIPT_PATH = SCRIPT_DIR / "check-complete.sh"
CURRENT_PLAN_FILE_PATH = Path(".claude/planning/current/task_plan.md")


def run_command(
    command_parts: list[str], cwd_path: Path
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess command in a temporary workspace.

    Args:
        command_parts: Command and arguments to execute.
        cwd_path: Working directory for the command.

    Returns:
        Completed subprocess result with captured UTF-8 output.
    """
    return subprocess.run(
        command_parts,
        cwd=cwd_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def test_init_session_writes_to_ignored_current_directory(tmp_path: Path) -> None:
    """The init script should create the active workspace under .claude/planning/current."""
    completed_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )

    assert completed_process.returncode == 0
    assert (tmp_path / CURRENT_PLAN_FILE_PATH).exists()
    assert not (tmp_path / "task_plan.md").exists()
    assert ".claude/planning/current/task_plan.md" in completed_process.stdout


def test_init_session_contextualizes_title_and_progress_sections(
    tmp_path: Path,
) -> None:
    """The initialized workspace should replace placeholder titles with useful defaults."""
    completed_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "TransMaster"],
        cwd_path=tmp_path,
    )

    assert completed_process.returncode == 0

    task_plan_text = (tmp_path / CURRENT_PLAN_FILE_PATH).read_text(encoding="utf-8")
    progress_text = (tmp_path / ".claude/planning/current/progress.md").read_text(
        encoding="utf-8"
    )

    assert "# Task Plan: TransMaster" in task_plan_text
    assert "[Brief Description]" not in task_plan_text
    assert "[One sentence describing the end state]" not in task_plan_text
    assert "### Phase 1: Requirements & Discovery" in progress_text
    assert "### Phase 2: Planning & Structure" in progress_text
    assert "[Title]" not in progress_text


def test_init_session_safe_mode_keeps_existing_current_workspace(
    tmp_path: Path,
) -> None:
    """Running init twice without --force should keep the current workspace unchanged."""
    first_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH)], cwd_path=tmp_path
    )
    assert first_process.returncode == 0

    current_plan_path = tmp_path / CURRENT_PLAN_FILE_PATH
    original_plan_content = current_plan_path.read_text(encoding="utf-8")
    current_plan_path.write_text(
        original_plan_content + "\n<!-- preserved marker -->\n",
        encoding="utf-8",
    )

    second_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH)], cwd_path=tmp_path
    )

    assert second_process.returncode == 0
    assert "Detected active planning session" in second_process.stdout
    assert "preserved marker" in current_plan_path.read_text(encoding="utf-8")


def test_force_reset_archives_previous_current_workspace(tmp_path: Path) -> None:
    """Force reset should archive the existing current workspace before recreating it."""
    initial_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH)], cwd_path=tmp_path
    )
    assert initial_process.returncode == 0

    current_plan_path = tmp_path / CURRENT_PLAN_FILE_PATH
    original_plan_content = current_plan_path.read_text(encoding="utf-8")
    current_plan_path.write_text(
        original_plan_content + "\n<!-- archived marker -->\n",
        encoding="utf-8",
    )

    reset_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "--force", "demo-project"],
        cwd_path=tmp_path,
    )

    assert reset_process.returncode == 0
    assert "Archived previous planning session" in reset_process.stdout
    assert "archived marker" not in current_plan_path.read_text(encoding="utf-8")

    archived_plan_path_list = list(
        (tmp_path / ".claude/planning/sessions").glob("*/task_plan.md")
    )
    assert archived_plan_path_list
    assert "archived marker" in archived_plan_path_list[0].read_text(encoding="utf-8")
    expected_archive_suffix = "-" + tmp_path.name.replace("_", "-").lower()
    assert archived_plan_path_list[0].parent.name.endswith(expected_archive_suffix)


def test_force_reset_skips_archiving_template_only_workspace(tmp_path: Path) -> None:
    """Force reset should recreate current/ without archiving untouched template content."""
    initial_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )
    assert initial_process.returncode == 0

    reset_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "--force", "demo-project"],
        cwd_path=tmp_path,
    )

    assert reset_process.returncode == 0
    assert "matches the initialized template" in reset_process.stdout
    assert (
        "Skipped archiving previous planning session before reset."
        in reset_process.stdout
    )
    archived_session_dir_list = list((tmp_path / ".claude/planning/sessions").glob("*"))
    assert archived_session_dir_list == []


def test_archive_session_skips_fresh_initialized_workspace(tmp_path: Path) -> None:
    """Fresh template-only workspaces should not create archived session directories."""
    init_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )
    assert init_process.returncode == 0

    archive_process = run_command(
        ["bash", str(ARCHIVE_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )

    assert archive_process.returncode == 0
    assert "matches the initialized template" in archive_process.stdout
    archived_session_dir_list = list((tmp_path / ".claude/planning/sessions").glob("*"))
    assert archived_session_dir_list == []


def test_archive_session_skips_duplicate_snapshot(tmp_path: Path) -> None:
    """Re-archiving unchanged content should not create duplicate snapshots."""
    init_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )
    assert init_process.returncode == 0

    current_plan_path = tmp_path / CURRENT_PLAN_FILE_PATH
    updated_plan_text = current_plan_path.read_text(encoding="utf-8").replace(
        "## Decisions Made",
        "| Decide archive policy | Skip untouched or duplicate sessions |\n\n## Decisions Made",
        1,
    )
    current_plan_path.write_text(updated_plan_text, encoding="utf-8")

    first_archive_process = run_command(
        ["bash", str(ARCHIVE_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )
    assert first_archive_process.returncode == 0
    assert "Archive required" in first_archive_process.stdout

    archived_session_dir_list = list((tmp_path / ".claude/planning/sessions").glob("*"))
    assert len(archived_session_dir_list) == 1

    second_archive_process = run_command(
        ["bash", str(ARCHIVE_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )
    assert second_archive_process.returncode == 0
    assert "matches latest snapshot" in second_archive_process.stdout
    archived_session_dir_list = list((tmp_path / ".claude/planning/sessions").glob("*"))
    assert len(archived_session_dir_list) == 1


def test_archive_session_uses_task_plan_title_for_directory_name(
    tmp_path: Path,
) -> None:
    """Archive directories should be named from the current task plan title."""
    init_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )
    assert init_process.returncode == 0

    current_plan_path = tmp_path / CURRENT_PLAN_FILE_PATH
    current_plan_text = current_plan_path.read_text(encoding="utf-8")
    current_plan_path.write_text(
        current_plan_text.replace(
            "# Task Plan: demo-project",
            "# Task Plan: Release Plan / v2",
            1,
        )
        + "\n<!-- archive by title -->\n",
        encoding="utf-8",
    )

    archive_process = run_command(
        ["bash", str(ARCHIVE_SESSION_SCRIPT_PATH), "demo-project"],
        cwd_path=tmp_path,
    )

    assert archive_process.returncode == 0
    archived_session_dir_list = list((tmp_path / ".claude/planning/sessions").glob("*"))
    assert len(archived_session_dir_list) == 1
    assert archived_session_dir_list[0].name.endswith("-release-plan-v2")


def test_update_phase_status_defaults_to_current_workspace(tmp_path: Path) -> None:
    """Status updates should target the active planning workspace by default."""
    init_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH)], cwd_path=tmp_path
    )
    assert init_process.returncode == 0

    update_process = run_command(
        [
            sys.executable,
            str(UPDATE_PHASE_SCRIPT_PATH),
            "--phase",
            "Phase 1",
            "--status",
            "complete",
        ],
        cwd_path=tmp_path,
    )

    assert update_process.returncode == 0
    updated_plan_content = (tmp_path / CURRENT_PLAN_FILE_PATH).read_text(
        encoding="utf-8"
    )
    assert "**Status:** complete" in updated_plan_content


def test_check_complete_uses_current_workspace_by_default(tmp_path: Path) -> None:
    """Completion checks should read the active plan path without extra arguments."""
    init_process = run_command(
        ["bash", str(INIT_SESSION_SCRIPT_PATH)], cwd_path=tmp_path
    )
    assert init_process.returncode == 0

    check_process = run_command(
        ["bash", str(CHECK_COMPLETE_SCRIPT_PATH)], cwd_path=tmp_path
    )

    assert check_process.returncode == 1
    assert (
        "Plan file:        .claude/planning/current/task_plan.md"
        in check_process.stdout
    )
