#!/usr/bin/env python3
"""Check deliverable PRD checklists and validation-evidence oracle integrity."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ACTIVE_PRD_PATH_RE = re.compile(r"^tasks/([^/]+-prd-[^/]+|P[0-3]-[A-Z]+-\d{8}-\d{6}-[^/]+)\.md$")
ARCHIVED_PRD_PATH_RE = re.compile(
    r"^tasks/archive/([^/]+-prd-[^/]+|P[0-3]-[A-Z]+-\d{8}-\d{6}-[^/]+)\.md$"
)
ACCEPTANCE_CHECKLIST_HEADING_RE = re.compile(
    r"^##\s+(?:\d+\.\s+)?(?:Acceptance Checklist\b.*|验收清单.*)\s*$"
)
TOP_LEVEL_HEADING_RE = re.compile(r"^##\s+")
CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[(?P<mark>[ xX])\]\s*(?P<label>.*)$")
CODE_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
REALISTIC_VALIDATION_HEADING_RE = re.compile(r"^###\s+(?:7\.6\s+)?Realistic Validation Plan\b")
THIRD_LEVEL_HEADING_RE = re.compile(r"^###\s+")
YAML_FENCE_START_RE = re.compile(r"^\s*```ya?ml\s*$", re.IGNORECASE)
YAML_FENCE_END_RE = re.compile(r"^\s*```\s*$")
ORACLE_ENTRY_RE = re.compile(r"^\s*-\s+id:\s*(?P<value>.*)$")
ORACLE_FIELD_RE = re.compile(r"^\s+(?P<key>[a-z_]+):\s*(?P<value>.*)$")
PART_A_HEADING_RE = re.compile(r"^#\s+Part A\b")
PART_B_HEADING_RE = re.compile(r"^#\s+Part B\b")
PART_A_EXECUTOR_METADATA_RE = re.compile(
    r"\brv-\d+\b|critical_value_source:|must_cross:|forbidden_bypasses:|"
    r"fresh_state_probe:|final_tree_evidence:"
)
FUNCTIONAL_REQUIREMENT_HEADING_RE = re.compile(r"^##\s+(?:10\.\s+)?Functional Requirements\b")
FUNCTIONAL_REQUIREMENT_RE = re.compile(r"^\s*[-*+]\s+(?:\*\*)?FR-(?P<number>\d+)(?:\*\*)?\s*[:：]")
FINAL_RECONCILIATION_HEADING_RE = re.compile(r"^###\s+Final Reconciliation\b")
RECONCILIATION_FIELD_RE = re.compile(
    r"^\s*[-*+]\s+(?P<key>Interpretation|Public behavior and contracts|"
    r"Related PRD status|Requirements and risks):\s*(?P<value>.*)$"
)
NO_EXECUTABLE_BEHAVIOR_MARKER = (
    "No executable behavior changes; realistic validation is limited to "
    "documentation/build checks."
)
INTERPRETATION_HEADING_RE = re.compile(r"^###\s+Interpretation\b")
MARKDOWN_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
MARKDOWN_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
INTERPRETATION_REQUIRED_BLOCKS = ("我默默定了这些", "我理解为不做")
MINIMUM_BEHAVIOR_EXAMPLE_ROWS = 3
BASE_ORACLE_FIELDS = (
    "behavior",
    "real_entry",
    "expected",
    "mock_boundary",
    "tier",
    "test_layer",
    "required_for_acceptance",
)
# Evidence-chain provenance is only worth its authoring and collection cost where
# failure has real blast radius. R0/R1 entries need a discriminating assertion,
# not a five-field provenance chain.
DEEP_CHAIN_ORACLE_FIELDS = (
    "critical_value_source",
    "must_cross",
    "forbidden_bypasses",
    "fresh_state_probe",
    "final_tree_evidence",
)
NEGATIVE_CONTROL_ORACLE_FIELDS = ("negative_control", "expected_fail")
VALID_ORACLE_TIERS = ("R0", "R1", "R2", "R3")
DEEP_CHAIN_TIERS = frozenset({"R2", "R3"})
NEGATIVE_CONTROL_TIERS = frozenset({"R3"})
# An oracle that omits its tier is treated as R3, so an unclassified entry keeps
# the full burden and the reduction has to be earned by declaring low risk.
DEFAULT_ORACLE_TIER = "R3"
NEGATIVE_CONTROL_NOT_FEASIBLE_PREFIX = "not feasible"
REQUIRED_RECONCILIATION_FIELDS = (
    "Interpretation",
    "Public behavior and contracts",
    "Related PRD status",
    "Requirements and risks",
)
REQUIRED_SECTION_PATTERNS = (
    ("Introduction & Goals", re.compile(r"^##\s+(?:1\.\s+)?Introduction & Goals\s*$")),
    ("Human Review Map", re.compile(r"^##\s+(?:2\.\s+)?Human Review Map\b")),
    (
        "Usage And Impact After Implementation",
        re.compile(r"^##\s+(?:3\.\s+)?Usage And Impact After Implementation\s*$"),
    ),
    ("Requirement Shape", re.compile(r"^##\s+(?:4\.\s+)?Requirement Shape\s*$")),
    (
        "Repository Context And Architecture Fit",
        re.compile(r"^##\s+(?:5\.\s+)?Repository Context And Architecture Fit\s*$"),
    ),
    ("Recommendation", re.compile(r"^##\s+(?:6\.\s+)?Recommendation\s*$")),
    (
        "Implementation Guide",
        re.compile(r"^##\s+(?:7\.\s+)?Implementation Guide\s*$"),
    ),
    (
        "Delivery Dependencies",
        re.compile(r"^##\s+(?:8\.\s+)?Delivery Dependencies\s*$"),
    ),
    ("Acceptance Checklist", ACCEPTANCE_CHECKLIST_HEADING_RE),
    (
        "Functional Requirements",
        re.compile(r"^##\s+(?:10\.\s+)?Functional Requirements\s*$"),
    ),
    ("Non-Goals", re.compile(r"^##\s+(?:11\.\s+)?Non-Goals\s*$")),
    (
        "Risks And Follow-Ups",
        re.compile(r"^##\s+(?:12\.\s+)?Risks And Follow-Ups\s*$"),
    ),
    ("Decision Log", re.compile(r"^##\s+(?:13\.\s+)?Decision Log\s*$")),
)


def _repo_root(start_path: Path | None = None) -> Path:
    """Return the repository root inferred from cwd or a provided path."""

    start_path = Path.cwd() if start_path is None else start_path
    git_process = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if git_process.returncode == 0:
        return Path(git_process.stdout.strip()).resolve()
    return start_path.resolve()


def _relative_path(path: Path, repo_root: Path) -> Path | None:
    """Return a repository-relative path when the file is inside the repo."""

    try:
        return path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None


def _is_active_prd_path(path: Path, repo_root: Path) -> bool:
    """Return whether a path is an active root-level PRD markdown file."""

    relative_path = _relative_path(path, repo_root)
    if relative_path is None:
        return False

    if relative_path.parent != Path("tasks"):
        return False
    return bool(ACTIVE_PRD_PATH_RE.match(relative_path.as_posix()))


def _is_archived_prd_path(path: Path, repo_root: Path) -> bool:
    """Return whether a path is an archived PRD markdown file."""

    relative_path = _relative_path(path, repo_root)
    if relative_path is None:
        return False

    return bool(ARCHIVED_PRD_PATH_RE.match(relative_path.as_posix()))


def _staged_archive_prd_paths(repo_root: Path) -> set[Path]:
    """Return PRDs newly added, copied, or renamed into the archive in git index."""

    git_diff_process = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--name-status",
            "--diff-filter=ACR",
            "--",
            "tasks/archive",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if git_diff_process.returncode != 0:
        return set()

    staged_archive_paths: set[Path] = set()
    for raw_status_line in git_diff_process.stdout.splitlines():
        status_parts = raw_status_line.split("\t")
        if not status_parts:
            continue

        staged_relative_path_text = status_parts[-1].strip()
        if not staged_relative_path_text:
            continue

        staged_relative_path = Path(staged_relative_path_text)
        if ARCHIVED_PRD_PATH_RE.match(staged_relative_path.as_posix()):
            staged_archive_paths.add(staged_relative_path)

    return staged_archive_paths


def _candidate_prd_paths(
    repo_root: Path,
    provided_paths: Iterable[Path],
    staged_archive_prd_paths: set[Path] | None = None,
) -> list[Path]:
    """Return deliverable PRD paths selected by the lifecycle filter."""

    staged_archive_prd_paths = (
        _staged_archive_prd_paths(repo_root)
        if staged_archive_prd_paths is None
        else staged_archive_prd_paths
    )
    provided_paths_list = list(provided_paths)
    if provided_paths_list:
        candidate_paths: list[Path] = []
        for path in provided_paths_list:
            absolute_path = path if path.is_absolute() else repo_root / path
            relative_path = _relative_path(absolute_path, repo_root)
            if relative_path is None:
                continue
            if _is_active_prd_path(absolute_path, repo_root):
                candidate_paths.append(absolute_path)
                continue
            if (
                _is_archived_prd_path(absolute_path, repo_root)
                and relative_path in staged_archive_prd_paths
            ):
                candidate_paths.append(absolute_path)
        return candidate_paths

    tasks_dir = repo_root / "tasks"
    if not tasks_dir.exists():
        return []

    discovered_paths: list[Path] = []
    for prd_path in sorted(tasks_dir.glob("*.md")):
        if _is_active_prd_path(prd_path, repo_root):
            discovered_paths.append(prd_path)
    for archived_prd_path in sorted(staged_archive_prd_paths):
        discovered_paths.append(repo_root / archived_prd_path)
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


def _required_section_issues(file_content: str) -> list[tuple[int, str]]:
    """Return missing or out-of-order required PRD section issues."""

    lines = file_content.splitlines()
    section_positions: list[tuple[str, int]] = []
    issues: list[tuple[int, str]] = []

    for section_name, section_pattern in REQUIRED_SECTION_PATTERNS:
        matching_indexes = [
            line_index for line_index, line in enumerate(lines) if section_pattern.match(line)
        ]
        if not matching_indexes:
            issues.append((-1, f"Missing required PRD section: {section_name}"))
            continue
        section_positions.append((section_name, matching_indexes[0]))

    for previous_section, current_section in zip(
        section_positions, section_positions[1:], strict=False
    ):
        previous_name, previous_index = previous_section
        current_name, current_index = current_section
        if current_index < previous_index:
            issues.append(
                (
                    current_index + 1,
                    f"Section {current_name!r} must appear after {previous_name!r}",
                )
            )

    return issues


def _part_a_metadata_issues(file_content: str) -> list[tuple[int, str]]:
    """Return executor-only metadata found inside the human review layer."""

    lines = file_content.splitlines()
    part_a_index = next(
        (line_index for line_index, line in enumerate(lines) if PART_A_HEADING_RE.match(line)),
        None,
    )
    part_b_index = next(
        (line_index for line_index, line in enumerate(lines) if PART_B_HEADING_RE.match(line)),
        None,
    )
    if part_a_index is None:
        return [(-1, "Missing Part A review-layer heading")]
    if part_b_index is None:
        return [(-1, "Missing Part B build-layer heading")]
    if part_b_index <= part_a_index:
        return [(part_b_index + 1, "Part B must appear after Part A")]

    issues: list[tuple[int, str]] = []
    for line_index in range(part_a_index + 1, part_b_index):
        metadata_match = PART_A_EXECUTOR_METADATA_RE.search(lines[line_index])
        if metadata_match:
            issues.append(
                (
                    line_index + 1,
                    f"Part A contains executor-only metadata: {metadata_match.group(0)!r}",
                )
            )
    return issues


def _functional_requirement_issues(file_content: str) -> list[tuple[int, str]]:
    """Return missing, duplicate, skipped, or out-of-order FR identifiers."""

    lines = file_content.splitlines()
    heading_index = next(
        (
            line_index
            for line_index, line in enumerate(lines)
            if FUNCTIONAL_REQUIREMENT_HEADING_RE.match(line)
        ),
        None,
    )
    if heading_index is None:
        return [(-1, "Missing Functional Requirements section")]

    end_index = next(
        (
            line_index
            for line_index in range(heading_index + 1, len(lines))
            if TOP_LEVEL_HEADING_RE.match(lines[line_index])
        ),
        len(lines),
    )
    requirement_entries = [
        (line_index + 1, int(requirement_match.group("number")))
        for line_index in range(heading_index + 1, end_index)
        if (requirement_match := FUNCTIONAL_REQUIREMENT_RE.match(lines[line_index]))
    ]
    if not requirement_entries:
        return [(heading_index + 1, "Functional Requirements must contain FR-1, FR-2, … items")]

    actual_numbers = [requirement_number for _, requirement_number in requirement_entries]
    expected_numbers = list(range(1, len(actual_numbers) + 1))
    if actual_numbers == expected_numbers:
        return []
    return [
        (
            requirement_entries[0][0],
            "Functional Requirement IDs must be unique, sequential, and ordered from FR-1; "
            f"found {actual_numbers}",
        )
    ]


def _archive_reconciliation_issues(file_content: str) -> list[tuple[int, str]]:
    """Return missing or incomplete final narrative reconciliation issues."""

    lines = file_content.splitlines()
    heading_index = next(
        (
            line_index
            for line_index, line in enumerate(lines)
            if FINAL_RECONCILIATION_HEADING_RE.match(line)
        ),
        None,
    )
    if heading_index is None:
        return [(-1, "Missing Final Reconciliation section required for archive readiness")]

    end_index = next(
        (
            line_index
            for line_index in range(heading_index + 1, len(lines))
            if THIRD_LEVEL_HEADING_RE.match(lines[line_index])
        ),
        len(lines),
    )
    reconciliation_fields: dict[str, tuple[int, str]] = {}
    for line_index in range(heading_index + 1, end_index):
        field_match = RECONCILIATION_FIELD_RE.match(lines[line_index])
        if field_match:
            reconciliation_fields[field_match.group("key")] = (
                line_index + 1,
                field_match.group("value").strip(),
            )

    issues: list[tuple[int, str]] = []
    for field_name in REQUIRED_RECONCILIATION_FIELDS:
        field_entry = reconciliation_fields.get(field_name)
        if field_entry is None:
            issues.append((heading_index + 1, f"Final Reconciliation missing field: {field_name}"))
            continue
        line_number, field_value = field_entry
        normalized_value = field_value.lower().replace(" ", "")
        if (
            not field_value
            or ("[" in field_value and "]" in field_value)
            or normalized_value in {"confirmed/corrected", "confirmed/corrected—summary"}
        ):
            issues.append((line_number, f"Final Reconciliation field {field_name!r} is incomplete"))
    return issues


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


def _interpretation_echo_issues(file_content: str) -> list[tuple[int, str]]:
    """Return a correctable-interpretation issue list for the Section 1 echo.

    The interpretation echo is the only gate that can catch a wrong reading of
    the request: the oracles and the implementation are both derived from that
    reading, so when it is wrong they agree with each other and every downstream
    check passes on the wrong behavior. Prose is not correctable by a skimming
    reviewer, so the echo must carry a concrete behavior-example table plus the
    silently-resolved decisions and the scope read as excluded.
    """

    lines = file_content.splitlines()
    heading_index = next(
        (
            line_index
            for line_index, line in enumerate(lines)
            if INTERPRETATION_HEADING_RE.match(line)
        ),
        None,
    )
    if heading_index is None:
        return [(-1, "Missing Section 1 'Interpretation (解读回显)' subsection")]

    end_index = next(
        (
            line_index
            for line_index in range(heading_index + 1, len(lines))
            if THIRD_LEVEL_HEADING_RE.match(lines[line_index])
            or TOP_LEVEL_HEADING_RE.match(lines[line_index])
        ),
        len(lines),
    )
    section_lines = lines[heading_index + 1 : end_index]

    example_row_count = 0
    for offset, line in enumerate(section_lines):
        if not MARKDOWN_TABLE_SEPARATOR_RE.match(line):
            continue
        row_count = 0
        for row_line in section_lines[offset + 1 :]:
            if not MARKDOWN_TABLE_ROW_RE.match(row_line):
                break
            row_count += 1
        example_row_count = max(example_row_count, row_count)

    issues: list[tuple[int, str]] = []
    if example_row_count < MINIMUM_BEHAVIOR_EXAMPLE_ROWS:
        issues.append(
            (
                heading_index + 1,
                "Interpretation echo needs a behavior-example table with at least "
                f"{MINIMUM_BEHAVIOR_EXAMPLE_ROWS} rows; found {example_row_count}",
            )
        )

    section_text = "\n".join(section_lines)
    issues.extend(
        (heading_index + 1, f"Interpretation echo missing block: {block_marker}")
        for block_marker in INTERPRETATION_REQUIRED_BLOCKS
        if block_marker not in section_text
    )
    return issues


def _meaningful_yaml_value(raw_value: str) -> str:
    """Return a scalar YAML value with simple comments and quotes removed."""

    value_without_comment = raw_value.partition("#")[0].strip()
    return value_without_comment.strip("\"'").strip()


def _oracle_schema_issues(file_content: str) -> list[tuple[int, str]]:
    """Return missing or incomplete validation-oracle schema issues."""

    lines = file_content.splitlines()
    validation_heading_indexes = [
        line_index
        for line_index, line in enumerate(lines)
        if REALISTIC_VALIDATION_HEADING_RE.match(line)
    ]
    if not validation_heading_indexes:
        return [(-1, "Missing Realistic Validation Plan section")]

    start_index = validation_heading_indexes[0] + 1
    end_index = next(
        (
            line_index
            for line_index in range(start_index, len(lines))
            if THIRD_LEVEL_HEADING_RE.match(lines[line_index])
        ),
        len(lines),
    )
    section_lines = lines[start_index:end_index]
    if any(NO_EXECUTABLE_BEHAVIOR_MARKER in line for line in section_lines):
        return []

    oracle_entries: list[tuple[str, int, dict[str, str]]] = []
    current_oracle_id = ""
    current_oracle_line_number = -1
    current_oracle_fields: dict[str, str] = {}
    in_yaml_block = False

    for section_offset, line in enumerate(section_lines):
        absolute_line_number = start_index + section_offset + 1
        if not in_yaml_block and YAML_FENCE_START_RE.match(line):
            in_yaml_block = True
            continue
        if in_yaml_block and YAML_FENCE_END_RE.match(line):
            if current_oracle_id:
                oracle_entries.append(
                    (current_oracle_id, current_oracle_line_number, current_oracle_fields)
                )
            current_oracle_id = ""
            current_oracle_fields = {}
            in_yaml_block = False
            continue
        if not in_yaml_block:
            continue

        entry_match = ORACLE_ENTRY_RE.match(line)
        if entry_match:
            if current_oracle_id:
                oracle_entries.append(
                    (current_oracle_id, current_oracle_line_number, current_oracle_fields)
                )
            current_oracle_id = _meaningful_yaml_value(entry_match.group("value"))
            current_oracle_line_number = absolute_line_number
            current_oracle_fields = {}
            continue

        field_match = ORACLE_FIELD_RE.match(line)
        if field_match and current_oracle_id:
            current_oracle_fields[field_match.group("key")] = _meaningful_yaml_value(
                field_match.group("value")
            )

    if current_oracle_id:
        oracle_entries.append(
            (current_oracle_id, current_oracle_line_number, current_oracle_fields)
        )

    if not oracle_entries:
        return [
            (
                start_index,
                "Realistic Validation Plan must contain a structured YAML oracle block",
            )
        ]

    schema_issues: list[tuple[int, str]] = []
    for oracle_id, oracle_line_number, oracle_fields in oracle_entries:
        declared_tier = oracle_fields.get("tier", "").upper()
        if declared_tier and declared_tier not in VALID_ORACLE_TIERS:
            schema_issues.append(
                (
                    oracle_line_number,
                    f"Oracle {oracle_id!r} has invalid tier {declared_tier!r}; "
                    f"expected one of {', '.join(VALID_ORACLE_TIERS)}",
                )
            )
            continue

        effective_tier = declared_tier or DEFAULT_ORACLE_TIER
        required_fields = list(BASE_ORACLE_FIELDS)
        if effective_tier in DEEP_CHAIN_TIERS:
            required_fields += DEEP_CHAIN_ORACLE_FIELDS
        if effective_tier in NEGATIVE_CONTROL_TIERS:
            required_fields += NEGATIVE_CONTROL_ORACLE_FIELDS

        # A documented "not feasible" negative control is an accepted outcome and
        # makes expected_fail meaningless; requiring it would push authors toward
        # inventing a failure mode instead of recording the real limitation.
        negative_control_value = oracle_fields.get("negative_control", "").lower()
        if negative_control_value.startswith(NEGATIVE_CONTROL_NOT_FEASIBLE_PREFIX):
            required_fields = [name for name in required_fields if name != "expected_fail"]

        missing_fields = [
            field_name
            for field_name in dict.fromkeys(required_fields)
            if not oracle_fields.get(field_name)
        ]
        if missing_fields:
            tier_note = "" if declared_tier else f" (untiered, treated as {DEFAULT_ORACLE_TIER})"
            schema_issues.append(
                (
                    oracle_line_number,
                    f"Oracle {oracle_id!r}{tier_note} missing non-empty field(s): "
                    + ", ".join(missing_fields),
                )
            )

    return schema_issues


def _validate_file(
    path: Path, *, require_archive_reconciliation: bool = False
) -> list[tuple[int, str]]:
    """Read a PRD file and return checklist or oracle-integrity issues."""

    file_content = path.read_text(encoding="utf-8")
    issues = (
        _required_section_issues(file_content)
        + _part_a_metadata_issues(file_content)
        + _interpretation_echo_issues(file_content)
        + _functional_requirement_issues(file_content)
        + _unchecked_items_in_acceptance_section(file_content)
        + _oracle_schema_issues(file_content)
    )
    if require_archive_reconciliation:
        issues += _archive_reconciliation_issues(file_content)
    return issues


def _build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""

    parser = argparse.ArgumentParser(
        description=(
            "Check deliverable PRD structure, Acceptance Checklist completion, "
            "validation-evidence oracles, and archive reconciliation."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root to validate. Defaults to git root from cwd.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Discover active task PRDs instead of relying only on provided paths.",
    )
    parser.add_argument(
        "--check-provided",
        action="store_true",
        help=(
            "Validate explicitly provided paths even if they are pending PRDs "
            "or otherwise outside the default deliverable lifecycle filter."
        ),
    )
    parser.add_argument(
        "--archive-ready",
        action="store_true",
        help=(
            "Require Final Reconciliation for explicitly provided PRDs that are "
            "being prepared for archive. Requires --check-provided."
        ),
    )
    parser.add_argument("paths", nargs="*", type=Path, help="PRD files to validate.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the acceptance checklist validation."""

    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = _repo_root(args.repo_root)
    if args.archive_ready and not args.check_provided:
        parser.error("--archive-ready requires --check-provided")
    if args.check_provided:
        if not args.paths:
            parser.error("--check-provided requires at least one PRD path")
        candidate_paths = [path if path.is_absolute() else repo_root / path for path in args.paths]
        missing_paths = [path for path in candidate_paths if not path.exists()]
        if missing_paths:
            print("Missing PRD path(s):")
            for missing_path in missing_paths:
                print(f"   - {missing_path}")
            return 1
    else:
        provided_paths = [] if args.all else args.paths
        candidate_paths = _candidate_prd_paths(repo_root, provided_paths)

    if not candidate_paths:
        return 0

    has_errors = False
    print("Checking PRD acceptance checklists and validation oracles...\n")

    for prd_path in candidate_paths:
        relative_path = prd_path.resolve().relative_to(repo_root.resolve())
        issues = _validate_file(
            prd_path,
            require_archive_reconciliation=(
                args.archive_ready or _is_archived_prd_path(prd_path, repo_root)
            ),
        )
        if not issues:
            print(f"PASS {relative_path.as_posix()}")
            continue

        has_errors = True
        print(f"FAIL {relative_path.as_posix()}")
        for line_number, issue_text in issues:
            if line_number < 0:
                print(f"   - {issue_text}")
            else:
                print(f"   - L{line_number}: {issue_text}")
        print()

    if has_errors:
        print("One or more deliverable PRDs have structural or delivery-readiness issues.")
        return 1

    print("\nAll deliverable PRD acceptance checklists and validation oracles are complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
