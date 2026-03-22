#!/usr/bin/env bash
# Stop hook: persist a lightweight session summary for Claude Code or Codex.
# Reads the transcript path from stdin JSON, extracts key info, and appends
# a summary block to the current session file.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SESSIONS_DIR="$REPO_ROOT/.claude/planning/sessions"
PROJECT_NAME="$(basename "$REPO_ROOT")"

# Read stdin JSON to get transcript path
input=$(cat)
transcript_path=$(echo "$input" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get("transcript_path", ""))
except:
    print("")
' 2>/dev/null || echo "")

# Generate session ID for today
today=$(date +%Y%m%d)
session_id="${today}-$(date +%H%M%S)-${PROJECT_NAME}"
session_file="$SESSIONS_DIR/.session-${today}.tmp"

# Create sessions dir if needed
mkdir -p "$SESSIONS_DIR"

# Extract summary from transcript if available
summary=""
if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    summary=$(TRANSCRIPT_PATH="$transcript_path" python3 - <<'PY'
import json
import os
import re
import sys
from pathlib import Path

transcript_path = os.environ.get("TRANSCRIPT_PATH", "")
if not transcript_path:
    raise SystemExit(0)

transcript_path_obj = Path(transcript_path)
if not transcript_path_obj.exists():
    raise SystemExit(0)

user_messages = []
tools_used = set()
files_modified = set()


def add_user_message(message_text: str) -> None:
    if len(message_text) > 5:
        user_messages.append(message_text[:150])


def collect_message_blocks(content_blocks: object) -> None:
    if isinstance(content_blocks, str):
        add_user_message(content_blocks)
        return
    if not isinstance(content_blocks, list):
        return

    for content_block in content_blocks:
        if not isinstance(content_block, dict):
            continue
        message_text = content_block.get("text", "")
        if isinstance(message_text, str):
            add_user_message(message_text)


def collect_patch_files(arguments_text: str) -> None:
    for line in arguments_text.splitlines():
        matched_file = re.match(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", line)
        if matched_file:
            files_modified.add(matched_file.group(1).strip())


with transcript_path_obj.open("r", encoding="utf-8") as transcript_file:
    for raw_line in transcript_file:
        line = raw_line.strip()
        if not line:
            continue

        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Claude-style transcript entries
        if entry.get("role") == "user":
            collect_message_blocks(entry.get("content", ""))

        if entry.get("role") == "assistant":
            content_blocks = entry.get("content", [])
            if isinstance(content_blocks, list):
                for content_block in content_blocks:
                    if not isinstance(content_block, dict):
                        continue
                    if content_block.get("type") != "tool_use":
                        continue
                    tool_name = content_block.get("name", "unknown")
                    tools_used.add(tool_name)
                    tool_input = content_block.get("input", {})
                    if tool_name in {"Write", "Edit"} and isinstance(tool_input, dict):
                        file_path = tool_input.get("file_path", "")
                        if isinstance(file_path, str) and file_path:
                            files_modified.add(file_path)

        # Codex-style transcript entries
        if entry.get("type") != "response_item":
            continue

        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            continue

        payload_type = payload.get("type")
        payload_role = payload.get("role")

        if payload_type == "message" and payload_role == "user":
            collect_message_blocks(payload.get("content", []))

        if payload_type == "function_call":
            tool_name = payload.get("name", "unknown")
            tools_used.add(tool_name)
            arguments_text = payload.get("arguments", "")
            if tool_name == "apply_patch" and isinstance(arguments_text, str):
                collect_patch_files(arguments_text)

output_parts = []
if user_messages:
    output_parts.append("User messages (last 5):")
    for message_text in user_messages[-5:]:
        output_parts.append(f"  - {message_text}")
if tools_used:
    output_parts.append(f"Tools used: {', '.join(sorted(tools_used)[:15])}")
if files_modified:
    output_parts.append("Files modified:")
    for file_path in sorted(files_modified)[:20]:
        output_parts.append(f"  - {file_path}")

print("\n".join(output_parts))
PY
    2>/dev/null || echo "")
fi

# Write/update session temp file
{
    # Header (only if file is new)
    if [ ! -f "$session_file" ]; then
        echo "# Session Summary: $(date +%Y-%m-%d)"
        echo "- Project: $PROJECT_NAME"
        echo "- Branch: $(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo 'unknown')"
        echo "- Working dir: $REPO_ROOT"
        echo "- Created: $(date '+%Y-%m-%d %H:%M:%S %z')"
        echo ""
    fi

    # Append update block
    echo "---"
    echo "### Update at $(date '+%H:%M:%S %z')"
    if [ -n "$summary" ]; then
        echo "$summary"
    else
        echo "(no transcript data available)"
    fi
    echo ""
} >> "$session_file"

# Output empty result (non-blocking)
echo '{"result": ""}'
