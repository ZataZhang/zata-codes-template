#!/usr/bin/env bash
# Stop hook: lightweight session marker.
# Archiving is now handled by the post-commit git hook.
# This hook only marks the session end time for reference.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CURRENT_DIR="$REPO_ROOT/.claude/planning/current"

# Mark session end in progress file if it exists
if [ -f "$CURRENT_DIR/progress.md" ]; then
    {
        echo ""
        echo "---"
        echo "> Session ended at $(date '+%Y-%m-%d %H:%M:%S %z')"
        echo ""
    } >> "$CURRENT_DIR/progress.md"
fi

# Output empty result (non-blocking)
echo '{"result": ""}'
