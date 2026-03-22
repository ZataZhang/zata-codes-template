#!/usr/bin/env bash
# PreCompact hook: save state before Claude Code compresses context.
# Marks the current planning progress with a compaction timestamp
# and copies a snapshot to the sessions archive.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CURRENT_DIR="$REPO_ROOT/.claude/planning/current"
SESSIONS_DIR="$REPO_ROOT/.claude/planning/sessions"

timestamp=$(date '+%Y-%m-%d %H:%M:%S %z')

# 1. Mark compaction in current progress file
if [ -f "$CURRENT_DIR/progress.md" ]; then
    echo "" >> "$CURRENT_DIR/progress.md"
    echo "---" >> "$CURRENT_DIR/progress.md"
    echo "> Context compaction at $timestamp. Information above may have been summarized." >> "$CURRENT_DIR/progress.md"
    echo "" >> "$CURRENT_DIR/progress.md"
fi

# 2. Archive a snapshot to sessions dir
snapshot_id="$(date +%Y%m%d-%H%M%S)-compact"
snapshot_dir="$SESSIONS_DIR/$snapshot_id"

if [ -d "$CURRENT_DIR" ]; then
    mkdir -p "$snapshot_dir"
    for f in "$CURRENT_DIR"/*.md; do
        [ -f "$f" ] && cp "$f" "$snapshot_dir/"
    done

    # Add compaction metadata
    {
        echo "# Compaction Snapshot"
        echo "- Timestamp: $timestamp"
        echo "- Branch: $(git -C "$REPO_ROOT" branch --show-current 2>/dev/null || echo 'unknown')"
        echo "- Reason: automatic context compaction"
    } > "$snapshot_dir/compaction.md"
fi

# 3. Append to compaction log
mkdir -p "$SESSIONS_DIR"
echo "[$timestamp] Context compacted. Snapshot: $snapshot_id" >> "$SESSIONS_DIR/compaction-log.txt"

# Output context reminder for Claude
reminder="Context was compacted at $timestamp. Current planning files are in .claude/planning/current/. Check progress.md for the latest state."
json_reminder=$(printf '%s' "$reminder" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
echo "{\"result\": $json_reminder}"
