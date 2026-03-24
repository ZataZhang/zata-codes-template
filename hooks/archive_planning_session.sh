#!/usr/bin/env bash
# post-commit hook: archive planning state on every commit.
# Delegates to the skill's archive-session.sh if available, otherwise
# performs a lightweight snapshot with commit metadata.
#
# Works with any AI tool (Claude Code, Codex, Cursor, etc.) since
# it hooks into git, not a specific tool's lifecycle.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
CURRENT_DIR="$REPO_ROOT/.claude/planning/current"
SESSIONS_DIR="$REPO_ROOT/.claude/planning/sessions"

# Skip if no planning files exist
if [ ! -d "$CURRENT_DIR" ]; then
    exit 0
fi

# Check if there's meaningful content to archive
has_content=false
for f in "$CURRENT_DIR"/*.md; do
    if [ -f "$f" ] && [ "$(wc -c < "$f" | tr -d ' ')" -gt 50 ]; then
        has_content=true
        break
    fi
done

if [ "$has_content" = false ]; then
    exit 0
fi

# Try to use the skill's archive script (handles dedup, naming, etc.)
SKILL_ARCHIVE="$HOME/.claude/skills/planning-with-files/scripts/archive-session.sh"
if [ -x "$SKILL_ARCHIVE" ] || [ -f "$SKILL_ARCHIVE" ]; then
    cd "$REPO_ROOT"
    bash "$SKILL_ARCHIVE" "$(basename "$REPO_ROOT")" || true
fi

# Append commit metadata to the latest snapshot
commit_hash=$(git rev-parse --short HEAD)
commit_msg=$(git log -1 --pretty=%s)
commit_date=$(git log -1 --pretty=%ci)
branch=$(git branch --show-current 2>/dev/null || echo "detached")
changed_files=$(git diff-tree --no-commit-id --name-only -r HEAD)

# Find the most recent snapshot directory (just created by archive-session.sh)
latest_snapshot=$(ls -1td "$SESSIONS_DIR"/*/ 2>/dev/null | head -1 || true)

if [ -n "$latest_snapshot" ]; then
    {
        echo "# Commit Info"
        echo ""
        echo "- Commit: $commit_hash"
        echo "- Message: $commit_msg"
        echo "- Date: $commit_date"
        echo "- Branch: $branch"
        echo ""
        echo "## Changed Files"
        echo "$changed_files" | while read -r f; do
            [ -n "$f" ] && echo "- $f"
        done
    } > "$latest_snapshot/commit-info.md"
fi
