#!/usr/bin/env python3
"""Render and evaluate planning workspace files.

This helper keeps the initialization and archive checks aligned so the
planning workspace can be created with contextual defaults and empty sessions
do not get archived repeatedly.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path


PLANNING_FILE_NAMES: tuple[str, str, str] = (
    "task_plan.md",
    "findings.md",
    "progress.md",
)
DEFAULT_BASELINE_DATE = "2000-01-01"
DEFAULT_BASELINE_TIMESTAMP = "2000-01-01 00:00:00"
PHASE_ONE_TITLE = "Requirements & Discovery"
PHASE_TWO_TITLE = "Planning & Structure"


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser for this helper.
    """
    parser = argparse.ArgumentParser(
        description="Render or evaluate planning workspace files."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init",
        help="Render an initialized planning workspace into an output directory.",
    )
    init_parser.add_argument(
        "--template-dir",
        type=Path,
        required=True,
        help="Directory containing task_plan.md, findings.md, and progress.md templates.",
    )
    init_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where the initialized planning files should be written.",
    )
    init_parser.add_argument(
        "--project-name",
        required=True,
        help="Project or task name used to contextualize the templates.",
    )
    init_parser.add_argument(
        "--current-date",
        default=None,
        help="Optional YYYY-MM-DD override used when rendering progress.md.",
    )
    init_parser.add_argument(
        "--current-timestamp",
        default=None,
        help="Optional YYYY-MM-DD HH:MM:SS override used when rendering timestamps.",
    )

    archive_parser = subparsers.add_parser(
        "should-archive",
        help="Exit 0 when the current workspace contains meaningful changes.",
    )
    archive_parser.add_argument(
        "--template-dir",
        type=Path,
        required=True,
        help="Directory containing the planning templates.",
    )
    archive_parser.add_argument(
        "--current-dir",
        type=Path,
        required=True,
        help="Directory containing the active planning workspace.",
    )
    archive_parser.add_argument(
        "--archive-dir",
        type=Path,
        required=True,
        help="Directory containing archived planning sessions.",
    )
    archive_parser.add_argument(
        "--project-name",
        required=True,
        help="Project or task name used to contextualize the templates.",
    )

    archive_name_parser = subparsers.add_parser(
        "archive-name",
        help="Print the preferred archive label derived from the active task plan title.",
    )
    archive_name_parser.add_argument(
        "--current-dir",
        type=Path,
        required=True,
        help="Directory containing the active planning workspace.",
    )
    archive_name_parser.add_argument(
        "--project-name",
        required=True,
        help="Fallback project or task name when no meaningful plan title exists.",
    )

    return parser


def build_goal_statement(project_name: str) -> str:
    """Build the default goal statement.

    Args:
        project_name: Project or task name.

    Returns:
        str: A concise default goal statement for the task plan.
    """
    return f"Define and deliver the current task for {project_name}."


def load_template_text(template_dir_path: Path, file_name: str) -> str:
    """Load a planning template as UTF-8 text.

    Args:
        template_dir_path: Directory containing planning templates.
        file_name: Template file name to read.

    Returns:
        str: Template contents.
    """
    template_file_path = template_dir_path / file_name
    return template_file_path.read_text(encoding="utf-8")


def apply_replacements(
    template_text: str, replacement_items: list[tuple[str, str]]
) -> str:
    """Apply literal string replacements in order.

    Args:
        template_text: Original template text.
        replacement_items: Ordered pairs of old and new text.

    Returns:
        str: Updated template text.
    """
    rendered_text = template_text
    for source_text, target_text in replacement_items:
        rendered_text = rendered_text.replace(source_text, target_text)
    return rendered_text


def extract_task_plan_title(task_plan_text: str, fallback_project_name: str) -> str:
    """Extract a meaningful title from task_plan.md.

    Args:
        task_plan_text: Task plan markdown content.
        fallback_project_name: Fallback label when the heading is still generic.

    Returns:
        str: Extracted task title or the fallback project name.
    """
    task_plan_heading_match = re.search(
        r"^#\s+(?:Task Plan:\s*)?(.+?)\s*$",
        task_plan_text,
        re.MULTILINE,
    )
    if not task_plan_heading_match:
        return fallback_project_name

    extracted_title_text = task_plan_heading_match.group(1).strip()
    if not extracted_title_text or extracted_title_text == "[Brief Description]":
        return fallback_project_name

    return extracted_title_text


def render_task_plan_text(
    task_plan_template_text: str,
    project_name: str,
    current_timestamp: str,
) -> str:
    """Render the initialized task plan file.

    Args:
        task_plan_template_text: Raw task plan template text.
        project_name: Project or task name.
        current_timestamp: Timestamp used for the Phase 1 Started field.

    Returns:
        str: Rendered task plan content.
    """
    goal_statement_text = build_goal_statement(project_name)
    contextualized_task_plan_text = apply_replacements(
        task_plan_template_text,
        [
            ("# Task Plan: [Brief Description]", f"# Task Plan: {project_name}"),
            ("[One sentence describing the end state]", goal_statement_text),
            (
                "1. [Question to answer]",
                f"1. What is the exact task to finish for {project_name}?",
            ),
            (
                "2. [Question to answer]",
                "2. Which files, constraints, and tests define done?",
            ),
        ],
    )
    initialized_phase_one_text = contextualized_task_plan_text.replace(
        "- **Status:** pending\n- **Started:**\n- **Completed:**",
        (
            "- **Status:** in_progress\n"
            f"- **Started:** {current_timestamp}\n"
            "- **Completed:**"
        ),
        1,
    )
    return initialized_phase_one_text


def render_progress_text(
    progress_template_text: str,
    project_name: str,
    current_date: str,
    current_timestamp: str,
) -> str:
    """Render the initialized progress log file.

    Args:
        progress_template_text: Raw progress template text.
        project_name: Project or task name.
        current_date: Session date for the log header.
        current_timestamp: Timestamp used for the Phase 1 Started field.

    Returns:
        str: Rendered progress file content.
    """
    goal_statement_text = build_goal_statement(project_name)
    return apply_replacements(
        progress_template_text,
        [
            ("[DATE]", current_date),
            ("[timestamp]", current_timestamp),
            ("### Phase 1: [Title]", f"### Phase 1: {PHASE_ONE_TITLE}"),
            ("### Phase 2: [Title]", f"### Phase 2: {PHASE_TWO_TITLE}"),
            ("[goal statement]", goal_statement_text),
        ],
    )


def render_initialized_workspace(
    template_dir_path: Path,
    project_name: str,
    current_date: str,
    current_timestamp: str,
) -> dict[str, str]:
    """Render all initialized planning workspace files.

    Args:
        template_dir_path: Directory containing planning templates.
        project_name: Project or task name.
        current_date: Session date for progress.md.
        current_timestamp: Timestamp for initial Started fields.

    Returns:
        dict[str, str]: Mapping from planning file name to rendered content.
    """
    task_plan_template_text = load_template_text(template_dir_path, "task_plan.md")
    findings_template_text = load_template_text(template_dir_path, "findings.md")
    progress_template_text = load_template_text(template_dir_path, "progress.md")

    rendered_task_plan_text = render_task_plan_text(
        task_plan_template_text=task_plan_template_text,
        project_name=project_name,
        current_timestamp=current_timestamp,
    )
    rendered_progress_text = render_progress_text(
        progress_template_text=progress_template_text,
        project_name=project_name,
        current_date=current_date,
        current_timestamp=current_timestamp,
    )

    return {
        "task_plan.md": rendered_task_plan_text,
        "findings.md": findings_template_text,
        "progress.md": rendered_progress_text,
    }


def normalize_planning_text(planning_markdown_text: str) -> str:
    """Normalize dynamic timestamps so planning files can be compared safely.

    Args:
        planning_markdown_text: Raw markdown text from a planning file.

    Returns:
        str: Normalized markdown text.
    """
    normalized_timestamp_text = re.sub(
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",
        "<TIMESTAMP>",
        planning_markdown_text,
    )
    normalized_date_text = re.sub(
        r"\d{4}-\d{2}-\d{2}",
        "<DATE>",
        normalized_timestamp_text,
    )
    stripped_line_list = [
        stripped_line.rstrip()
        for stripped_line in normalized_date_text.strip().splitlines()
    ]
    return "\n".join(stripped_line_list) + "\n"


def read_workspace_contents(workspace_dir_path: Path) -> dict[str, str]:
    """Read the planning files from a workspace directory.

    Args:
        workspace_dir_path: Directory that should contain the planning files.

    Returns:
        dict[str, str]: Mapping from planning file name to file contents.

    Raises:
        FileNotFoundError: Raised when a required planning file is missing.
    """
    workspace_content_map: dict[str, str] = {}
    for planning_file_name in PLANNING_FILE_NAMES:
        planning_file_path = workspace_dir_path / planning_file_name
        if not planning_file_path.exists():
            raise FileNotFoundError(f"Missing planning file: {planning_file_path}")
        workspace_content_map[planning_file_name] = planning_file_path.read_text(
            encoding="utf-8"
        )
    return workspace_content_map


def resolve_archive_label(current_dir_path: Path, project_name: str) -> str:
    """Resolve the preferred archive label from the active task plan title.

    Args:
        current_dir_path: Current planning workspace directory.
        project_name: Fallback project or task name.

    Returns:
        str: Human-readable archive label.
    """
    task_plan_file_path = current_dir_path / "task_plan.md"
    if not task_plan_file_path.exists():
        return project_name

    task_plan_text = task_plan_file_path.read_text(encoding="utf-8")
    return extract_task_plan_title(
        task_plan_text=task_plan_text,
        fallback_project_name=project_name,
    )


def normalize_workspace_contents(
    workspace_content_map: dict[str, str],
) -> dict[str, str]:
    """Normalize a workspace content map for comparison.

    Args:
        workspace_content_map: Raw planning contents keyed by file name.

    Returns:
        dict[str, str]: Normalized planning contents keyed by file name.
    """
    normalized_content_map: dict[str, str] = {}
    for planning_file_name, planning_file_text in workspace_content_map.items():
        normalized_content_map[planning_file_name] = normalize_planning_text(
            planning_file_text
        )
    return normalized_content_map


def write_workspace_contents(
    output_dir_path: Path, rendered_workspace_map: dict[str, str]
) -> None:
    """Write the rendered planning workspace to disk.

    Args:
        output_dir_path: Directory where planning files should be written.
        rendered_workspace_map: Rendered planning contents keyed by file name.
    """
    output_dir_path.mkdir(parents=True, exist_ok=True)
    for planning_file_name, planning_file_text in rendered_workspace_map.items():
        output_file_path = output_dir_path / planning_file_name
        output_file_path.write_text(planning_file_text, encoding="utf-8")


def find_latest_archive_dir(archive_dir_path: Path) -> Path | None:
    """Return the latest archive directory that contains planning files.

    Args:
        archive_dir_path: Parent directory for archived sessions.

    Returns:
        Path | None: Latest archived session directory or None when unavailable.
    """
    if not archive_dir_path.exists():
        return None

    archive_candidate_list = [
        archive_candidate_path
        for archive_candidate_path in archive_dir_path.iterdir()
        if archive_candidate_path.is_dir()
        and all(
            (archive_candidate_path / planning_file_name).exists()
            for planning_file_name in PLANNING_FILE_NAMES
        )
    ]
    if not archive_candidate_list:
        return None

    return max(
        archive_candidate_list,
        key=lambda archive_candidate_path: archive_candidate_path.stat().st_mtime,
    )


def should_archive_workspace(
    template_dir_path: Path,
    current_dir_path: Path,
    archive_dir_path: Path,
    project_name: str,
) -> tuple[bool, str]:
    """Decide whether the current workspace should be archived.

    Args:
        template_dir_path: Directory containing planning templates.
        current_dir_path: Current planning workspace directory.
        archive_dir_path: Archived session directory root.
        project_name: Project or task name.

    Returns:
        tuple[bool, str]: Archive decision and an explanatory message.
    """
    try:
        current_workspace_map = read_workspace_contents(current_dir_path)
    except FileNotFoundError as missing_file_error:
        return False, f"[planning] Skip archive: {missing_file_error}"

    rendered_baseline_map = render_initialized_workspace(
        template_dir_path=template_dir_path,
        project_name=project_name,
        current_date=DEFAULT_BASELINE_DATE,
        current_timestamp=DEFAULT_BASELINE_TIMESTAMP,
    )
    normalized_current_map = normalize_workspace_contents(current_workspace_map)
    normalized_baseline_map = normalize_workspace_contents(rendered_baseline_map)

    if normalized_current_map == normalized_baseline_map:
        return (
            False,
            "[planning] Skip archive: current workspace still matches the initialized template.",
        )

    latest_archive_dir_path = find_latest_archive_dir(archive_dir_path)
    if latest_archive_dir_path is None:
        return (
            True,
            "[planning] Archive required: current workspace has substantive changes.",
        )

    latest_archive_map = read_workspace_contents(latest_archive_dir_path)
    normalized_latest_archive_map = normalize_workspace_contents(latest_archive_map)

    if normalized_current_map == normalized_latest_archive_map:
        return (
            False,
            f"[planning] Skip archive: current workspace matches latest snapshot {latest_archive_dir_path.name}.",
        )

    return (
        True,
        "[planning] Archive required: current workspace changed since the latest snapshot.",
    )


def handle_init_command(parsed_args: argparse.Namespace) -> int:
    """Handle the init subcommand.

    Args:
        parsed_args: Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """
    now_datetime = datetime.now()
    current_date_text = parsed_args.current_date or now_datetime.strftime("%Y-%m-%d")
    current_timestamp_text = parsed_args.current_timestamp or now_datetime.strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    rendered_workspace_map = render_initialized_workspace(
        template_dir_path=parsed_args.template_dir,
        project_name=parsed_args.project_name,
        current_date=current_date_text,
        current_timestamp=current_timestamp_text,
    )
    write_workspace_contents(
        output_dir_path=parsed_args.output_dir,
        rendered_workspace_map=rendered_workspace_map,
    )
    return 0


def handle_should_archive_command(parsed_args: argparse.Namespace) -> int:
    """Handle the should-archive subcommand.

    Args:
        parsed_args: Parsed CLI arguments.

    Returns:
        int: Exit code. Zero means archive, ten means skip.
    """
    should_archive, archive_reason_text = should_archive_workspace(
        template_dir_path=parsed_args.template_dir,
        current_dir_path=parsed_args.current_dir,
        archive_dir_path=parsed_args.archive_dir,
        project_name=parsed_args.project_name,
    )
    print(archive_reason_text)
    return 0 if should_archive else 10


def handle_archive_name_command(parsed_args: argparse.Namespace) -> int:
    """Handle the archive-name subcommand.

    Args:
        parsed_args: Parsed CLI arguments.

    Returns:
        int: Process exit code.
    """
    archive_label_text = resolve_archive_label(
        current_dir_path=parsed_args.current_dir,
        project_name=parsed_args.project_name,
    )
    print(archive_label_text)
    return 0


def main() -> int:
    """Run the planning session helper CLI.

    Returns:
        int: Process exit code.
    """
    parser = build_parser()
    parsed_args = parser.parse_args()

    if parsed_args.command == "init":
        return handle_init_command(parsed_args)
    if parsed_args.command == "should-archive":
        return handle_should_archive_command(parsed_args)
    if parsed_args.command == "archive-name":
        return handle_archive_name_command(parsed_args)

    parser.error(f"Unsupported command: {parsed_args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
