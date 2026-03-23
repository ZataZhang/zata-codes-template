#!/bin/bash
# Initialize planning files for a new session.
# Usage: ./init-session.sh [--force] [project-name]

set -euo pipefail

FORCE_RESET=false
PROJECT_NAME="$(basename "$PWD")"
SCRIPT_NAME="$(basename "$0")"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_DIR="$(cd "${SCRIPT_DIR}/../templates" && pwd)"
PLANNING_SESSION_SCRIPT="${SCRIPT_DIR}/planning_session.py"
PLANNING_ROOT=".claude/planning"
CURRENT_DIR="${PLANNING_ROOT}/current"
ARCHIVE_DIR="${PLANNING_ROOT}/sessions"
PLANNING_BASENAMES=(task_plan.md findings.md progress.md)

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

print_usage() {
    echo "Usage: ${SCRIPT_NAME} [--force] [project-name]"
    echo ""
    echo "Default mode is safe: if an active planning session already exists in"
    echo "${CURRENT_DIR}/, the script exits without changing it."
    echo ""
    echo "Use --force to archive the current planning session into"
    echo "${ARCHIVE_DIR}/ and create a fresh ${CURRENT_DIR}/ workspace."
}

parse_args() {
    local arg
    for arg in "$@"; do
        case "$arg" in
            --force|-f)
                FORCE_RESET=true
                ;;
            --help|-h)
                print_usage
                exit 0
                ;;
            *)
                if [ "$PROJECT_NAME" = "$(basename "$PWD")" ]; then
                    PROJECT_NAME="$arg"
                else
                    echo "Error: unexpected argument '$arg'"
                    print_usage
                    exit 2
                fi
                ;;
        esac
    done
}

slugify_name() {
    local raw_name="$1"
    local slug_name
    slug_name="$(printf '%s' "$raw_name" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"

    if [ -z "$slug_name" ]; then
        slug_name="session"
    fi

    printf '%s\n' "$slug_name"
}

collect_existing_files_in_dir() {
    local target_dir="$1"
    local planning_basename

    for planning_basename in "${PLANNING_BASENAMES[@]}"; do
        if [ -f "${target_dir}/${planning_basename}" ]; then
            printf '%s\n' "${target_dir}/${planning_basename}"
        fi
    done
}

collect_existing_legacy_files() {
    local planning_basename

    for planning_basename in "${PLANNING_BASENAMES[@]}"; do
        if [ -f "${planning_basename}" ]; then
            printf '%s\n' "${planning_basename}"
        fi
    done
}

initialize_current_session_files() {
    mkdir -p "${CURRENT_DIR}"

    "${PYTHON_BIN}" "${PLANNING_SESSION_SCRIPT}" init \
        --template-dir "${TEMPLATE_DIR}" \
        --output-dir "${CURRENT_DIR}" \
        --project-name "${PROJECT_NAME}"
}

reset_current_session_workspace() {
    local archive_decision_output
    local archive_decision_status
    local archive_label
    local archive_slug

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
        rm -rf "${CURRENT_DIR}"
        printf '%s\n' "${archive_decision_output}"
        echo "Skipped archiving previous planning session before reset."
        return 0
    fi

    if [ "${archive_decision_status}" -ne 0 ]; then
        printf '%s\n' "${archive_decision_output}" >&2
        return "${archive_decision_status}"
    fi

    archive_label="$(
        "${PYTHON_BIN}" "${PLANNING_SESSION_SCRIPT}" archive-name \
            --current-dir "${CURRENT_DIR}" \
            --project-name "${PROJECT_NAME}"
    )"
    archive_slug="$(slugify_name "${archive_label}")"
    ARCHIVE_SESSION_DIR="${ARCHIVE_DIR}/$(date +%Y%m%d-%H%M%S)-${archive_slug}"
    mv "${CURRENT_DIR}" "${ARCHIVE_SESSION_DIR}"
    printf '%s\n' "${archive_decision_output}"
    echo "Archived previous planning session to: ${ARCHIVE_SESSION_DIR}"
}

parse_args "$@"

ACTIVE_FILES=()
LEGACY_FILES=()

while IFS= read -r active_file_path; do
    if [ -n "${active_file_path}" ]; then
        ACTIVE_FILES+=("${active_file_path}")
    fi
done < <(collect_existing_files_in_dir "${CURRENT_DIR}")

while IFS= read -r legacy_file_path; do
    if [ -n "${legacy_file_path}" ]; then
        LEGACY_FILES+=("${legacy_file_path}")
    fi
done < <(collect_existing_legacy_files)

if [ "${#ACTIVE_FILES[@]}" -gt 0 ] && [ "$FORCE_RESET" = false ]; then
    echo "Detected active planning session:"
    printf '  - %s\n' "${ACTIVE_FILES[@]}"
    echo "Safe mode is active: no files were changed."
    echo "To start a fresh session, run: ${SCRIPT_NAME} --force [project-name]"
    exit 0
fi

mkdir -p "${PLANNING_ROOT}" "${ARCHIVE_DIR}"

if [ "$FORCE_RESET" = true ] && [ -d "${CURRENT_DIR}" ]; then
    reset_current_session_workspace
fi

if [ "${#ACTIVE_FILES[@]}" -eq 0 ] && [ "${#LEGACY_FILES[@]}" -gt 0 ] && [ "$FORCE_RESET" = false ]; then
    mkdir -p "${CURRENT_DIR}"
    for legacy_file in "${LEGACY_FILES[@]}"; do
        cp "${legacy_file}" "${CURRENT_DIR}/$(basename "${legacy_file}")"
    done

    echo "Migrated legacy root planning files into: ${CURRENT_DIR}"
    echo "Legacy files were left untouched in the project root for backward compatibility."
    echo ""
    echo "Planning session ready."
    echo "Files:"
    printf '  - %s/%s\n' "${CURRENT_DIR}" "task_plan.md"
    printf '  - %s/%s\n' "${CURRENT_DIR}" "findings.md"
    printf '  - %s/%s\n' "${CURRENT_DIR}" "progress.md"
    exit 0
fi

echo "Initializing planning files for: ${PROJECT_NAME}"
initialize_current_session_files

echo ""
echo "Planning session initialized."
echo "Files:"
printf '  - %s/%s\n' "${CURRENT_DIR}" "task_plan.md"
printf '  - %s/%s\n' "${CURRENT_DIR}" "findings.md"
printf '  - %s/%s\n' "${CURRENT_DIR}" "progress.md"
