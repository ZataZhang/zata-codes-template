#!/usr/bin/env bash
# Generic PRD Realistic Validation Plan runner for E2E/smoke/manual oracles.
#
# Usage:
#   ./scripts/e2e/run-prd-evidence.sh <prd-file> [rv-id]
#
# Examples:
#   ./scripts/e2e/run-prd-evidence.sh tasks/pending/P2-FEAT-20260701-133736-playwright-e2e-smoke-tests.md rv-2
#   ./scripts/e2e/run-prd-evidence.sh tasks/pending/P2-FEAT-20260701-133736-playwright-e2e-smoke-tests.md
#
# Behavior:
#   1. Parses the first YAML oracle block ("Realistic Validation Plan") in the PRD.
#   2. If rv-id is given, runs only that entry; otherwise runs all entries whose
#      test_layer is one of e2e / smoke / manual.
#   3. Loads repository-root .env.e2e.local if present.
#   4. Executes each oracle's `real_entry` shell command in the repository root.
#   5. Collects evidence to tasks/evidence/<prd-basename>/:
#        - <rv-id>-output.log
#        - <rv-id>-playwright-report/  (if produced)
#        - <rv-id>-test-results/       (if produced)
#
# Note: The commands in the PRD are trusted project commands. Do not point this
# runner at untrusted PRD files.

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: $0 <prd-file> [rv-id]" >&2
  echo "  rv-id: optional oracle id from the PRD's Realistic Validation Plan" >&2
  exit 1
fi

prd_file="$1"
selected_rv="${2:-}"

if [ ! -f "$prd_file" ]; then
  echo "ERROR: PRD file not found: $prd_file" >&2
  exit 1
fi

repo_root_path="$(cd "$(dirname "$0")/../.." && pwd)"
e2e_root_path="$repo_root_path/tests/playwright-e2e"
cd "$repo_root_path"

# Load local E2E env overrides (gitignored, never committed).
# Kept inside the e2e package so each worktree has its own copy.
if [ -f "$e2e_root_path/.env.e2e.local" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$e2e_root_path/.env.e2e.local"
  set +a
fi

prd_name="$(basename "$prd_file" .md)"
evidence_dir="tasks/evidence/${prd_name}"
mkdir -p "$evidence_dir"

uv run python3 - "$prd_file" "$selected_rv" "$evidence_dir" <<'PY'
import pathlib
import re
import shutil
import subprocess
import sys

import yaml

prd_file = pathlib.Path(sys.argv[1])
selected_rv = sys.argv[2] or None
evidence_dir = pathlib.Path(sys.argv[3])

text = prd_file.read_text(encoding="utf-8")
matches = re.findall(r"```yaml\n(.*?)\n```", text, re.DOTALL)
if not matches:
    print("ERROR: no YAML oracle block found in PRD", file=sys.stderr)
    sys.exit(1)

entries = []
for block in matches:
    data = yaml.safe_load(block)
    if isinstance(data, list):
        entries.extend(data)

if selected_rv:
    entries = [e for e in entries if e.get("id") == selected_rv]
    if not entries:
        print(f"ERROR: rv-id '{selected_rv}' not found in {prd_file}", file=sys.stderr)
        sys.exit(1)
else:
    # Run only executable real-entry layers by default.
    entries = [e for e in entries if e.get("test_layer") in ("e2e", "smoke", "manual")]

if not entries:
    print("ERROR: no runnable oracle entries found", file=sys.stderr)
    sys.exit(1)

repo_root = pathlib.Path.cwd()
failed = False

for entry in entries:
    rv_id = entry.get("id", "unknown")
    real_entry = (entry.get("real_entry") or "").strip()
    if not real_entry:
        print(f"SKIP {rv_id}: empty real_entry", file=sys.stderr)
        continue

    log_path = evidence_dir / f"{rv_id}-output.log"
    print(f"Running {rv_id} ...")
    print(f"  log: {log_path}")

    result = subprocess.run(
        ["bash", "-c", real_entry],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    log_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")

    # Collect Playwright artifacts when they exist.
    pw_root = repo_root / "tests" / "playwright-e2e"
    for artifact in ("playwright-report", "test-results"):
        src = pw_root / artifact
        if src.exists():
            dst = evidence_dir / f"{rv_id}-{artifact}"
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst)

    if result.returncode == 0:
        print(f"  ✅ {rv_id} passed")
    else:
        print(f"  ❌ {rv_id} failed (exit={result.returncode})", file=sys.stderr)
        failed = True

sys.exit(1 if failed else 0)
PY
