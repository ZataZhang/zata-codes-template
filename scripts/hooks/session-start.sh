#!/usr/bin/env bash
# SessionStart hook: restore latest session context for Claude Code
# Reads the most recent session from .claude/planning/sessions/ and injects
# progress + findings into the conversation context via stdout JSON.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SESSIONS_DIR="$REPO_ROOT/.claude/planning/sessions"
CURRENT_DIR="$REPO_ROOT/.claude/planning/current"

# Collect context parts
context_parts=()

# 1. Load latest archived session (most recently modified directory)
if [ -d "$SESSIONS_DIR" ]; then
    latest_session=$(ls -1td "$SESSIONS_DIR"/*/ 2>/dev/null | head -1)
    if [ -n "$latest_session" ]; then
        session_name=$(basename "$latest_session")

        # Check if session is within last 7 days
        if [ "$(uname)" = "Darwin" ]; then
            session_mtime=$(stat -f %m "$latest_session")
        else
            session_mtime=$(stat -c %Y "$latest_session")
        fi
        now=$(date +%s)
        age_days=$(( (now - session_mtime) / 86400 ))

        if [ "$age_days" -le 7 ]; then
            context_parts+=("## Previous Session: $session_name")

            if [ -f "$latest_session/progress.md" ]; then
                # Extract last session block (last ## Session section, max 80 lines)
                progress_tail=$(tail -80 "$latest_session/progress.md")
                context_parts+=("### Progress (tail)")
                context_parts+=("$progress_tail")
            fi

            if [ -f "$latest_session/findings.md" ]; then
                findings_tail=$(tail -40 "$latest_session/findings.md")
                context_parts+=("### Key Findings (tail)")
                context_parts+=("$findings_tail")
            fi
        fi
    fi
fi

# 2. Load current in-progress planning if it exists and has content
if [ -f "$CURRENT_DIR/progress.md" ]; then
    current_size=$(wc -c < "$CURRENT_DIR/progress.md" | tr -d ' ')
    if [ "$current_size" -gt 50 ]; then
        context_parts+=("## Current In-Progress Work")

        current_progress=$(tail -60 "$CURRENT_DIR/progress.md")
        context_parts+=("### Current Progress")
        context_parts+=("$current_progress")

        if [ -f "$CURRENT_DIR/task_plan.md" ]; then
            # Only first 30 lines of plan (title + current phase)
            plan_head=$(head -30 "$CURRENT_DIR/task_plan.md")
            context_parts+=("### Current Task Plan (head)")
            context_parts+=("$plan_head")
        fi
    fi
fi

# 3. List available archived sessions
if [ -d "$SESSIONS_DIR" ]; then
    session_list=$(ls -1td "$SESSIONS_DIR"/*/ 2>/dev/null | head -5 | while read -r d; do basename "$d"; done)
    if [ -n "$session_list" ]; then
        context_parts+=("## Available Sessions")
        context_parts+=("$session_list")
    fi
fi

# 4. Git branch context
current_branch=$(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo "unknown")
context_parts+=("## Environment")
context_parts+=("- Branch: $current_branch")
context_parts+=("- Sessions dir: .claude/planning/sessions/")

# Output as Claude Code hook result
if [ ${#context_parts[@]} -gt 0 ]; then
    # Join all parts with newlines, escape for JSON
    full_context=""
    for part in "${context_parts[@]}"; do
        full_context+="$part"$'\n\n'
    done

    # Escape for JSON string
    json_context=$(printf '%s' "$full_context" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

    echo "{\"result\": $json_context}"
fi
