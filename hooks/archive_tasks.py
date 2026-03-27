"""Archive task markdown files before commit.

Moves Markdown files from the tasks directory into tasks/archive and stages
the resulting changes for commit.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Sequence


def _repo_root() -> Path:
    """Return the repository root inferred from this file's location."""

    return Path(__file__).resolve().parents[1]


def _staged_task_paths(
    repo_root: Path, tasks_dir: Path, archive_dir: Path
) -> list[Path]:
    """Collect staged markdown files under tasks, excluding the archive directory.

    This inspects the git index rather than the working tree so that only
    already staged files are archived.

    Args:
        repo_root (Path): Repository root used as subprocess cwd.
        tasks_dir (Path): The tasks directory to constrain results.
        archive_dir (Path): The archive directory to exclude.

    Returns:
        list[Path]: Staged markdown file paths to be archived.
    """

    git_diff_process = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--cached",
            "--diff-filter=ACMR",
            "--",
            "tasks",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    staged_files: list[Path] = []
    for line in git_diff_process.stdout.splitlines():
        relative_path = line.strip()
        if not relative_path:
            continue
        relative_path_obj = Path(relative_path)
        if relative_path_obj.suffix.lower() != ".md":
            continue

        full_path = repo_root / relative_path_obj
        if not full_path.exists():
            # File might be deleted or renamed; skip to avoid filesystem errors.
            continue
        if not full_path.is_file():
            continue
        if archive_dir in full_path.parents:
            continue
        if tasks_dir not in full_path.parents and full_path != tasks_dir:
            # Constrain to paths under tasks_dir.
            continue

        staged_files.append(full_path)

    return staged_files


def _ensure_archive_dir(archive_dir: Path) -> None:
    """Ensure the archive directory exists.

    Args:
        archive_dir (Path): The archive directory path.
    """

    archive_dir.mkdir(parents=True, exist_ok=True)


def _move_files(files: Sequence[Path], archive_dir: Path) -> list[Path]:
    """Move files into the archive directory.

    Args:
        files (Sequence[Path]): Files to move.
        archive_dir (Path): Destination archive directory.

    Returns:
        list[Path]: Destination paths for moved files.
    """

    moved: list[Path] = []
    for source in files:
        destination = archive_dir / source.name
        moved.append(Path(shutil.move(str(source), str(destination))))
    return moved


def _stage_changes(paths: Iterable[Path], repo_root: Path) -> None:
    """Stage git changes for the provided paths.

    Args:
        paths (Iterable[Path]): Paths to stage.
        repo_root (Path): Repository root used as subprocess cwd.

    Raises:
        subprocess.CalledProcessError: When git add fails.
    """

    paths_list = list(paths)
    if not paths_list:
        return
    subprocess.run(
        ["git", "add", "-A", "tasks"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    """Run the archive process and stage results.

    Returns:
        int: Process exit code.
    """

    repo_root = _repo_root()
    tasks_dir = repo_root / "tasks"
    archive_dir = tasks_dir / "archive"

    if not tasks_dir.exists():
        return 0

    try:
        files = _staged_task_paths(repo_root, tasks_dir, archive_dir)
        if not files:
            return 0
        _ensure_archive_dir(archive_dir)
        _move_files(files, archive_dir)
        _stage_changes([tasks_dir], repo_root)
    except Exception as exc:  # noqa: BLE001 - exit non-zero on any failure
        print(f"Failed to archive tasks: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
