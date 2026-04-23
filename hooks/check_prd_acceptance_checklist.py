#!/usr/bin/env python3
"""Check that active PRD acceptance checklists are fully completed."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable


ACTIVE_PRD_PATH_RE = re.compile(r"^tasks/[^/]+-prd-[^/]+\.md$")
ACCEPTANCE_CHECKLIST_HEADING_RE = re.compile(
    r"^##\s+(?:\d+\.\s+)?Acceptance Checklist\s*$"
)
TOP_LEVEL_HEADING_RE = re.compile(r"^##\s+")
CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[(?P<mark>[ xX])\]\s*(?P<label>.*)$")
CODE_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")


def _repo_root() -> Path:
    """Return the repository root inferred from this file location."""

    return Path(__file__).resolve().parents[1]


def _is_active_prd_path(path: Path, repo_root: Path) -> bool:
    """Return whether a path is an active root-level PRD markdown file."""

    try:
        relative_path = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False

    if relative_path.parent != Path("tasks"):
        return False
    if relative_path.parts[:2] == ("tasks", "archive"):
        return False
    if relative_path.parts[:2] == ("tasks", "pending"):
        return False
    return bool(ACTIVE_PRD_PATH_RE.match(relative_path.as_posix()))


def _candidate_prd_paths(repo_root: Path, provided_paths: Iterable[Path]) -> list[Path]:
    """Return active PRD paths to validate."""

    provided_paths_list = list(provided_paths)
    if provided_paths_list:
        return [
            path for path in provided_paths_list if _is_active_prd_path(path, repo_root)
        ]

    tasks_dir = repo_root / "tasks"
    if not tasks_dir.exists():
        return []

    discovered_paths: list[Path] = []
    for prd_path in sorted(tasks_dir.glob("*-prd-*.md")):
        if _is_active_prd_path(prd_path, repo_root):
            discovered_paths.append(prd_path)
    return discovered_paths


def _section_bounds(lines: list[str]) -> tuple[int, int] | None:
    """Return the line bounds for the Acceptance Checklist section."""

    start_index: int | None = None
    for line_index, line in enumerate(lines):
        if ACCEPTANCE_CHECKLIST_HEADING_RE.match(line):
            start_index = line_index
            break

    if start_index is None:
        return None

    end_index = len(lines)
    for line_index in range(start_index + 1, len(lines)):
        if TOP_LEVEL_HEADING_RE.match(lines[line_index]):
            end_index = line_index
            break

    return start_index + 1, end_index


def _unchecked_items_in_acceptance_section(file_content: str) -> list[tuple[int, str]]:
    """Return unchecked checklist items found in the acceptance section."""

    lines = file_content.splitlines()
    section_bounds = _section_bounds(lines)
    if section_bounds is None:
        return [(-1, "Missing Acceptance Checklist section")]

    start_index, end_index = section_bounds
    unchecked_items: list[tuple[int, str]] = []
    in_code_block = False

    for line_index in range(start_index, end_index):
        line = lines[line_index]
        if CODE_FENCE_RE.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        checkbox_match = CHECKBOX_RE.match(line)
        if checkbox_match and checkbox_match.group("mark") == " ":
            unchecked_items.append((line_index + 1, line.rstrip()))

    return unchecked_items


def _validate_file(path: Path) -> list[tuple[int, str]]:
    """Read a PRD file and return any checklist issues."""

    file_content = path.read_text(encoding="utf-8")
    return _unchecked_items_in_acceptance_section(file_content)


def main() -> int:
    """Run the acceptance checklist validation."""

    repo_root = _repo_root()
    provided_paths = [repo_root / Path(argument) for argument in sys.argv[1:]]
    candidate_paths = _candidate_prd_paths(repo_root, provided_paths)

    if not candidate_paths:
        return 0

    has_errors = False
    print("🔍 Checking PRD acceptance checklists...\n")

    for prd_path in candidate_paths:
        relative_path = prd_path.resolve().relative_to(repo_root.resolve())
        issues = _validate_file(prd_path)
        if not issues:
            print(f"✅ {relative_path.as_posix()}")
            continue

        has_errors = True
        print(f"❌ {relative_path.as_posix()}")
        for line_number, issue_text in issues:
            if line_number < 0:
                print(f"   - {issue_text}")
            else:
                print(f"   - L{line_number}: {issue_text}")
        print()

    if has_errors:
        print(
            "⚠️  One or more active PRD acceptance checklists still contain unchecked items."
        )
        return 1

    print("\n🎉 All active PRD acceptance checklists are complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
