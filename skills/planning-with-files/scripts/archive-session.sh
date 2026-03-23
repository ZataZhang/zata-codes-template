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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/../templates" && pwd)"
PLANNING_SESSION_SCRIPT="${SCRIPT_DIR}/planning_session.py"
PLANNING_ROOT=".claude/planning"
CURRENT_DIR="${PLANNING_ROOT}/current"
ARCHIVE_DIR="${PLANNING_ROOT}/sessions"

resolve_python_bin() {
    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi

    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi

    echo "Error: python3 or python is required to manage planning sessions." >&2
    exit 127
}

PYTHON_BIN="$(resolve_python_bin)"

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

archive_decision_output=""
archive_decision_status=0
archive_label=""
archive_slug=""

set +e
archive_decision_output="$(
    "${PYTHON_BIN}" "${PLANNING_SESSION_SCRIPT}" should-archive \
        --template-dir "${TEMPLATE_DIR}" \
        --current-dir "${CURRENT_DIR}" \
        --archive-dir "${ARCHIVE_DIR}" \
        --project-name "${PROJECT_NAME}" 2>&1
)"
archive_decision_status=$?
set -e

if [ "${archive_decision_status}" -eq 10 ]; then
    printf '%s\n' "${archive_decision_output}"
    exit 0
fi

if [ "${archive_decision_status}" -ne 0 ]; then
    printf '%s\n' "${archive_decision_output}" >&2
    exit "${archive_decision_status}"
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
archive_label="$(
    "${PYTHON_BIN}" "${PLANNING_SESSION_SCRIPT}" archive-name \
        --current-dir "${CURRENT_DIR}" \
        --project-name "${PROJECT_NAME}"
)"
archive_slug="$(slugify_name "${archive_label}")"
ARCHIVE_SESSION_DIR="${ARCHIVE_DIR}/${TIMESTAMP}-${archive_slug}"

# Prevent overwriting an existing archive (paranoia for rapid re-runs).
if [ -d "${ARCHIVE_SESSION_DIR}" ]; then
    ARCHIVE_SESSION_DIR="${ARCHIVE_SESSION_DIR}-$(shuf -i 1000-9999 -n 1 2>/dev/null || echo $$)"
fi

mkdir -p "${ARCHIVE_SESSION_DIR}"
cp -R "${CURRENT_DIR}/." "${ARCHIVE_SESSION_DIR}/"

printf '%s\n' "${archive_decision_output}"
echo "[planning] Snapshot saved to: ${ARCHIVE_SESSION_DIR}"
