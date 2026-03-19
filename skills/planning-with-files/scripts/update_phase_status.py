#!/usr/bin/env python3
"""
Auto-update task_plan.md phase status based on file changes.

This script is designed to be called by the planning-with-files skill hooks.
It analyzes recent file changes and updates the corresponding phase status.

Usage:
    python update_phase_status.py [--plan-file PATH] [--phase PHASE_NAME] [--status STATUS]

Examples:
    # Mark a specific phase as complete
    python update_phase_status.py --phase "Phase 1" --status complete

    # Auto-detect and advance to next phase
    python update_phase_status.py --auto-advance

    # Show current status
    python update_phase_status.py --status-report
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

CURRENT_PLAN_PATH = Path(".claude/planning/current/task_plan.md")
LEGACY_PLAN_PATH = Path("task_plan.md")


def resolve_plan_path(explicit_plan_path: Path | None) -> Path:
    """Resolve the task plan path for the active planning session.

    Args:
        explicit_plan_path: Optional plan path passed on the command line.

    Returns:
        The resolved task plan path. Explicit paths win, then the ignored
        `.claude/planning/current/` workspace, then the legacy project-root file.
    """
    if explicit_plan_path is not None:
        return explicit_plan_path

    if CURRENT_PLAN_PATH.exists():
        return CURRENT_PLAN_PATH

    if LEGACY_PLAN_PATH.exists():
        return LEGACY_PLAN_PATH

    return CURRENT_PLAN_PATH


def parse_task_plan(plan_path: Path) -> dict:
    """Parse task_plan.md and extract phase information.

    Args:
        plan_path: Path to the task_plan.md file.

    Returns:
        Dictionary containing parsed phase information.
    """
    if not plan_path.exists():
        return {"error": f"Plan file not found: {plan_path}"}

    content = plan_path.read_text(encoding="utf-8")

    phases = []
    # Match phase headers and their status
    phase_pattern = r"### (Phase \d+:[^\n]+)\n(.*?)(?=### Phase|\n## |$)"
    matches = re.findall(phase_pattern, content, re.DOTALL)

    for phase_title, phase_content in matches:
        status_match = re.search(r"\*\*Status:\*\*\s*(\w+)", phase_content)
        status = status_match.group(1) if status_match else "pending"

        # Extract checklist items
        checklist_items = re.findall(r"- \[([ x])\] (.+)", phase_content)
        total_items = len(checklist_items)
        completed_items = sum(1 for checked, _ in checklist_items if checked == "x")

        phases.append(
            {
                "title": phase_title.strip(),
                "status": status,
                "total_items": total_items,
                "completed_items": completed_items,
                "progress_pct": (completed_items / total_items * 100)
                if total_items > 0
                else 0,
            }
        )

    # Extract current phase
    current_match = re.search(r"## Current Phase\n(Phase \d+)", content)
    current_phase = current_match.group(1) if current_match else "Phase 1"

    return {"phases": phases, "current_phase": current_phase, "content": content}


def update_phase_status(plan_path: Path, phase_name: str, new_status: str) -> bool:
    """Update the status of a specific phase in task_plan.md.

    Args:
        plan_path: Path to the task_plan.md file.
        phase_name: Name of the phase (e.g., "Phase 1" or "Phase 1: Requirements").
        new_status: New status value (pending, in_progress, complete).

    Returns:
        True if update was successful, False otherwise.
    """
    if not plan_path.exists():
        print(f"ERROR: Plan file not found: {plan_path}")
        return False

    content = plan_path.read_text(encoding="utf-8")

    # Build regex pattern to match the phase and its status
    # Match both "Phase 1" and "Phase 1: Title" formats
    phase_pattern = (
        rf"(### {re.escape(phase_name)}[^\n]*\n.*?)(\*\*Status:\*\*\s*)(\w+)"
    )

    match = re.search(phase_pattern, content, re.DOTALL)
    if not match:
        print(f"WARNING: Phase '{phase_name}' not found in plan file")
        return False

    # Replace the status
    old_status = match.group(3)
    new_content = content[: match.start(3)] + new_status + content[match.end(3) :]

    # Also update Started/Completed timestamps within the matched phase block.
    block_pattern = rf"(### {re.escape(phase_name)}[^\n]*\n(.*?))(?=### Phase|\n## |$)"
    block_match = re.search(block_pattern, new_content, re.DOTALL)

    if block_match:
        block_full = block_match.group(1)

        def replace_started_completed(
            block_text: str, started: str | None, completed: str | None
        ) -> str:
            """Replace or insert Started/Completed lines in the phase block."""
            # Use [^\n]* to match only within current line (not across lines like .* with DOTALL)
            # Replace existing Started line if present
            if re.search(r"- \*\*Started:\*\*[^\n]*", block_text):
                block_text = re.sub(
                    r"- \*\*Started:\*\*[^\n]*",
                    f"- **Started:** {started if started else ''}",
                    block_text,
                )
            else:
                block_text = re.sub(
                    r"(\*\*Status:\*\*[^\n]*\n)",
                    rf"\1- **Started:** {started if started else ''}\n",
                    block_text,
                )

            # Replace existing Completed line if present
            if re.search(r"- \*\*Completed:\*\*[^\n]*", block_text):
                block_text = re.sub(
                    r"- \*\*Completed:\*\*[^\n]*",
                    f"- **Completed:** {completed if completed else ''}",
                    block_text,
                )
            else:
                # Ensure Completed line exists after Started
                block_text = re.sub(
                    r"(\- \*\*Started:\*\*[^\n]*\n)",
                    rf"\1- **Completed:** {completed if completed else ''}\n",
                    block_text,
                )

            return block_text

        now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if new_status == "in_progress":
            # Set Started to now (if empty) and clear Completed
            started_val = now_ts
            completed_val = ""
            # If a Started already exists with content, keep it
            # Use [ \t]* to match only spaces/tabs (not newlines), and [^\n]+ for the value
            started_search = re.search(r"- \*\*Started:\*\*[ \t]*([^\n]+)", block_full)
            if started_search and started_search.group(1).strip():
                started_val = started_search.group(1).strip()

        elif new_status == "complete":
            # Ensure Started exists (use existing or now) and set Completed to now
            completed_val = now_ts
            # Use [ \t]* to match only spaces/tabs (not newlines), and [^\n]+ for the value
            started_search = re.search(r"- \*\*Started:\*\*[ \t]*([^\n]+)", block_full)
            if started_search and started_search.group(1).strip():
                started_val = started_search.group(1).strip()
            else:
                started_val = now_ts

        else:  # pending or other
            started_val = ""
            completed_val = ""

        updated_block = replace_started_completed(
            block_full, started_val, completed_val
        )

        # Replace the old block with updated block in the content
        new_content = (
            new_content[: block_match.start(1)]
            + updated_block
            + new_content[block_match.end(1) :]
        )

    # Update the file
    plan_path.write_text(new_content, encoding="utf-8")

    print(f"[planning-with-files] Updated '{phase_name}': {old_status} → {new_status}")
    return True


def update_current_phase(plan_path: Path, phase_name: str) -> bool:
    """Update the 'Current Phase' section in task_plan.md.

    Args:
        plan_path: Path to the task_plan.md file.
        phase_name: Name of the current phase.

    Returns:
        True if update was successful, False otherwise.
    """
    if not plan_path.exists():
        return False

    content = plan_path.read_text(encoding="utf-8")

    # Update Current Phase section
    pattern = r"(## Current Phase\n)([^\n]+)"
    new_content = re.sub(pattern, rf"\1{phase_name}", content)

    plan_path.write_text(new_content, encoding="utf-8")
    print(f"[planning-with-files] Current phase set to: {phase_name}")
    return True


def auto_advance_phase(plan_path: Path) -> bool:
    """Automatically advance to the next phase if current is complete.

    Args:
        plan_path: Path to the task_plan.md file.

    Returns:
        True if advanced, False if no advancement needed.
    """
    parsed = parse_task_plan(plan_path)
    if "error" in parsed:
        print(parsed["error"])
        return False

    phases = parsed["phases"]
    current = parsed["current_phase"]

    # Find current phase index
    current_idx = None
    for i, phase in enumerate(phases):
        if current in phase["title"]:
            current_idx = i
            break

    if current_idx is None:
        print("WARNING: Could not determine current phase")
        return False

    current_phase = phases[current_idx]

    # Check if current phase is complete
    if current_phase["status"] == "complete" and current_idx < len(phases) - 1:
        next_phase = phases[current_idx + 1]
        next_phase_name = next_phase["title"].split(":")[0]  # Extract "Phase N"

        # Update next phase to in_progress
        update_phase_status(plan_path, next_phase_name, "in_progress")
        update_current_phase(plan_path, next_phase_name)

        print(f"[planning-with-files] Auto-advanced to {next_phase['title']}")
        return True

    return False


def generate_status_report(plan_path: Path) -> str:
    """Generate a status report for the task plan.

    Args:
        plan_path: Path to the task_plan.md file.

    Returns:
        Formatted status report string.
    """
    parsed = parse_task_plan(plan_path)
    if "error" in parsed:
        return parsed["error"]

    lines = [
        "╔══════════════════════════════════════════════════════════════╗",
        "║                    TASK PLAN STATUS                          ║",
        "╠══════════════════════════════════════════════════════════════╣",
    ]

    for phase in parsed["phases"]:
        status_icon = {"complete": "✅", "in_progress": "🔄", "pending": "⏳"}.get(
            phase["status"], "❓"
        )

        progress_bar = ""
        if phase["total_items"] > 0:
            filled = int(phase["progress_pct"] / 10)
            progress_bar = f" [{'█' * filled}{'░' * (10 - filled)}] {phase['completed_items']}/{phase['total_items']}"

        current_marker = (
            " ← CURRENT" if parsed["current_phase"] in phase["title"] else ""
        )
        lines.append(
            f"║ {status_icon} {phase['title'][:40]:<40}{progress_bar}{current_marker}"
        )

    lines.extend(
        [
            "╚══════════════════════════════════════════════════════════════╝",
            "",
            f"Current Phase: {parsed['current_phase']}",
        ]
    )

    return "\n".join(lines)


def log_progress(plan_path: Path, message: str) -> None:
    """Append a progress entry to progress.md.

    Args:
        plan_path: Path to the task_plan.md file (used to find progress.md).
        message: Progress message to log.
    """
    progress_path = plan_path.parent / "progress.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = f"\n## [{timestamp}]\n{message}\n"

    if progress_path.exists():
        content = progress_path.read_text(encoding="utf-8")
        progress_path.write_text(content + entry, encoding="utf-8")
    else:
        progress_path.write_text(f"# Progress Log\n{entry}", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Update task_plan.md phase status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--plan-file",
        "-p",
        type=Path,
        default=None,
        help=(
            "Path to task_plan.md "
            "(default: ./.claude/planning/current/task_plan.md, fallback: ./task_plan.md)"
        ),
    )

    parser.add_argument(
        "--phase",
        "-n",
        type=str,
        help="Phase name to update (e.g., 'Phase 1' or 'Phase 1: Requirements')",
    )

    parser.add_argument(
        "--status",
        "-s",
        type=str,
        choices=["pending", "in_progress", "complete"],
        help="New status for the phase",
    )

    parser.add_argument(
        "--auto-advance",
        "-a",
        action="store_true",
        help="Auto-advance to next phase if current is complete",
    )

    parser.add_argument(
        "--status-report", "-r", action="store_true", help="Show current status report"
    )

    parser.add_argument(
        "--log", "-l", type=str, help="Log a progress message to progress.md"
    )

    args = parser.parse_args()
    resolved_plan_path = resolve_plan_path(args.plan_file)

    # Handle status report
    if args.status_report:
        print(generate_status_report(resolved_plan_path))
        return 0

    # Handle progress logging
    if args.log:
        log_progress(resolved_plan_path, args.log)
        print(f"[planning-with-files] Logged progress: {args.log}")
        return 0

    # Handle auto-advance
    if args.auto_advance:
        auto_advance_phase(resolved_plan_path)
        return 0

    # Handle explicit phase update
    if args.phase and args.status:
        success = update_phase_status(resolved_plan_path, args.phase, args.status)
        if success and args.status == "complete":
            # Try to auto-advance after marking complete
            auto_advance_phase(resolved_plan_path)
        return 0 if success else 1

    # No action specified, show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
