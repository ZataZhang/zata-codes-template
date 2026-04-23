"""Regression tests for the PRD acceptance checklist hook."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[1]
PRD_ACCEPTANCE_CHECKLIST_SCRIPT_PATH = (
    REPO_ROOT / "hooks" / "check_prd_acceptance_checklist.py"
)


def load_prd_acceptance_checklist_module() -> ModuleType:
    """Load the PRD acceptance checklist hook module directly from disk."""

    module_spec = importlib.util.spec_from_file_location(
        "prd_acceptance_checklist_hook", PRD_ACCEPTANCE_CHECKLIST_SCRIPT_PATH
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    prd_acceptance_checklist_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(prd_acceptance_checklist_module)
    return prd_acceptance_checklist_module


def test_is_active_prd_path_only_accepts_root_level_active_prds(tmp_path: Path) -> None:
    """Only root-level active PRDs should be treated as hook candidates."""

    prd_acceptance_checklist_module = load_prd_acceptance_checklist_module()

    tasks_dir = tmp_path / "tasks"
    archive_dir = tasks_dir / "archive"
    pending_dir = tasks_dir / "pending"
    nested_dir = tasks_dir / "review"
    archive_dir.mkdir(parents=True, exist_ok=True)
    pending_dir.mkdir(parents=True, exist_ok=True)
    nested_dir.mkdir(parents=True, exist_ok=True)

    active_prd_path = tasks_dir / "20260423-100000-prd-active.md"
    pending_prd_path = pending_dir / "20260423-100001-prd-pending.md"
    archived_prd_path = archive_dir / "20260423-100002-prd-archived.md"
    nested_prd_path = nested_dir / "20260423-100003-prd-nested.md"

    assert prd_acceptance_checklist_module._is_active_prd_path(  # noqa: SLF001
        active_prd_path, tmp_path
    )
    assert not prd_acceptance_checklist_module._is_active_prd_path(  # noqa: SLF001
        pending_prd_path, tmp_path
    )
    assert not prd_acceptance_checklist_module._is_active_prd_path(  # noqa: SLF001
        archived_prd_path, tmp_path
    )
    assert not prd_acceptance_checklist_module._is_active_prd_path(  # noqa: SLF001
        nested_prd_path, tmp_path
    )


def test_unchecked_items_outside_acceptance_section_are_ignored(tmp_path: Path) -> None:
    """Unchecked boxes outside the acceptance section should not fail validation."""

    prd_acceptance_checklist_module = load_prd_acceptance_checklist_module()

    prd_path = tmp_path / "tasks" / "20260423-110000-prd-example.md"
    prd_path.parent.mkdir(parents=True, exist_ok=True)
    prd_path.write_text(
        """# PRD: Example

## 1. Introduction & Goals

- [ ] this checklist item is outside the acceptance section

## 7. Acceptance Checklist

### Architecture Acceptance

- [x] checked item

### Validation Acceptance

- [x] another checked item

## 8. User Stories

- [ ] this item is also outside the acceptance section
""",
        encoding="utf-8",
    )

    issues = prd_acceptance_checklist_module._validate_file(prd_path)  # noqa: SLF001

    assert issues == []


def test_missing_or_unchecked_acceptance_items_are_reported(tmp_path: Path) -> None:
    """Missing sections and unchecked boxes in the acceptance section should fail."""

    prd_acceptance_checklist_module = load_prd_acceptance_checklist_module()

    missing_section_path = tmp_path / "tasks" / "20260423-120000-prd-missing.md"
    missing_section_path.parent.mkdir(parents=True, exist_ok=True)
    missing_section_path.write_text("# PRD: Missing Checklist\n", encoding="utf-8")

    unchecked_path = tmp_path / "tasks" / "20260423-120001-prd-unchecked.md"
    unchecked_path.write_text(
        """# PRD: Unchecked

## 7. Acceptance Checklist

### Validation Acceptance

- [x] checked item
- [ ] still needs work
""",
        encoding="utf-8",
    )

    missing_section_issues = prd_acceptance_checklist_module._validate_file(  # noqa: SLF001
        missing_section_path
    )
    unchecked_issues = prd_acceptance_checklist_module._validate_file(  # noqa: SLF001
        unchecked_path
    )

    assert missing_section_issues == [(-1, "Missing Acceptance Checklist section")]
    assert unchecked_issues == [(8, "- [ ] still needs work")]
