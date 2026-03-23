#!/usr/bin/env bash
# Compatibility wrapper for the repository session-start hook.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec bash "${REPO_ROOT}/scripts/claude_code_hooks/session-start.sh" "$@"
