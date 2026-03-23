#!/bin/bash
# Snapshot the active planning session from current/ into sessions/.
#
# Uses COPY, not move — current/ stays intact for multi-turn sessions.
# Only init-session.sh --force should remove current/.
#
# Designed for non-interactive use (Codex, CI, hooks).
# - Idempotent: exits cleanly if there is nothing to archive.
# - No prompts, no stdin reads.
# - Exit 0 on success or no-op; exit 1 only on real errors.
#
# Usage: ./archive-session.sh [project-name]

set -euo pipefail

PROJECT_NAME="${1:-$(basename "$PWD")}"
PLANNING_ROOT=".claude/planning"
CURRENT_DIR="${PLANNING_ROOT}/current"
ARCHIVE_DIR="${PLANNING_ROOT}/sessions"

# Nothing to archive — exit cleanly.
if [ ! -d "${CURRENT_DIR}" ]; then
    exit 0
fi

# Check if current/ has any planning files worth archiving.
HAS_FILES=false
for planning_file in task_plan.md findings.md progress.md; do
    if [ -f "${CURRENT_DIR}/${planning_file}" ]; then
        HAS_FILES=true
        break
    fi
done

if [ "${HAS_FILES}" = false ]; then
    exit 0
fi

# Build a slug from the project name for the archive directory.
slugify_name() {
    local raw_name="$1"
    local slug_name
    slug_name="$(printf '%s' "$raw_name" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
    if [ -z "$slug_name" ]; then
        slug_name="session"
    fi
    printf '%s\n' "$slug_name"
}

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
SESSION_SLUG="$(slugify_name "${PROJECT_NAME}")"
ARCHIVE_SESSION_DIR="${ARCHIVE_DIR}/${TIMESTAMP}-${SESSION_SLUG}"

# Prevent overwriting an existing archive (paranoia for rapid re-runs).
if [ -d "${ARCHIVE_SESSION_DIR}" ]; then
    ARCHIVE_SESSION_DIR="${ARCHIVE_SESSION_DIR}-$(shuf -i 1000-9999 -n 1 2>/dev/null || echo $$)"
fi

mkdir -p "${ARCHIVE_SESSION_DIR}"
cp -R "${CURRENT_DIR}/." "${ARCHIVE_SESSION_DIR}/"

echo "[planning] Snapshot saved to: ${ARCHIVE_SESSION_DIR}"
