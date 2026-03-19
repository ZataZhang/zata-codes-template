#!/bin/bash
# Check if all phases in task_plan.md are complete
# Exit 0 if complete, exit 1 if incomplete
# Used by Stop hook to verify task completion

set -euo pipefail

resolve_plan_file() {
    local explicit_plan_file="${1:-}"

    if [ -n "$explicit_plan_file" ]; then
        printf '%s\n' "$explicit_plan_file"
        return 0
    fi

    if [ -f ".claude/planning/current/task_plan.md" ]; then
        printf '%s\n' ".claude/planning/current/task_plan.md"
        return 0
    fi

    if [ -f "task_plan.md" ]; then
        printf '%s\n' "task_plan.md"
        return 0
    fi

    printf '%s\n' ".claude/planning/current/task_plan.md"
}

PLAN_FILE="$(resolve_plan_file "${1:-}")"

if [ ! -f "$PLAN_FILE" ]; then
    echo "ERROR: $PLAN_FILE not found"
    echo "Cannot verify completion without a task plan."
    exit 1
fi

echo "=== Task Completion Check ==="
echo ""
echo "Plan file:        $PLAN_FILE"
echo ""

# Count phases by status (using -F for fixed string matching)
TOTAL=$(grep -c "### Phase" "$PLAN_FILE" || true)
COMPLETE=$(grep -cF "**Status:** complete" "$PLAN_FILE" || true)
IN_PROGRESS=$(grep -cF "**Status:** in_progress" "$PLAN_FILE" || true)
PENDING=$(grep -cF "**Status:** pending" "$PLAN_FILE" || true)

# Default to 0 if empty
: "${TOTAL:=0}"
: "${COMPLETE:=0}"
: "${IN_PROGRESS:=0}"
: "${PENDING:=0}"

echo "Total phases:   $TOTAL"
echo "Complete:       $COMPLETE"
echo "In progress:    $IN_PROGRESS"
echo "Pending:        $PENDING"
echo ""

# Check completion
if [ "$COMPLETE" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
    echo "ALL PHASES COMPLETE"
    exit 0
else
    echo "TASK NOT COMPLETE"
    echo ""
    echo "Do not stop until all phases are complete."
    exit 1
fi
