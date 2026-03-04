#!/bin/bash
# Initialize planning files for a new session.
# Usage: ./init-session.sh [--force] [project-name]

set -euo pipefail

FORCE_RESET=false
PROJECT_NAME="project"
SCRIPT_NAME="$(basename "$0")"

print_usage() {
    echo "Usage: ${SCRIPT_NAME} [--force] [project-name]"
    echo ""
    echo "Default mode is safe: if planning files already exist, the script exits"
    echo "without overwriting anything. Use --force to reset existing files."
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
                if [ "$PROJECT_NAME" = "project" ]; then
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

parse_args "$@"

DATE="$(date +%Y-%m-%d)"
PLANNING_FILES=(task_plan.md findings.md progress.md)
EXISTING_FILES=()

for planning_file in "${PLANNING_FILES[@]}"; do
    if [ -f "$planning_file" ]; then
        EXISTING_FILES+=("$planning_file")
    fi
done

if [ "${#EXISTING_FILES[@]}" -gt 0 ] && [ "$FORCE_RESET" = false ]; then
    echo "Detected existing planning files: ${EXISTING_FILES[*]}"
    echo "Safe mode is active: no files were overwritten."
    echo "To reset planning files, run: ${SCRIPT_NAME} --force [project-name]"
    exit 0
fi

echo "Initializing planning files for: $PROJECT_NAME"

if [ "$FORCE_RESET" = true ] && [ "${#EXISTING_FILES[@]}" -gt 0 ]; then
    echo "Force mode enabled: overwriting existing planning files."
fi

cat > task_plan.md << 'EOF'
# Task Plan: [Brief Description]

## Goal
[One sentence describing the end state]

## Current Phase
Phase 1

## Phases

### Phase 1: Requirements & Discovery
- [ ] Understand user intent
- [ ] Identify constraints
- [ ] Document in findings.md
- **Status:** in_progress

### Phase 2: Planning & Structure
- [ ] Define approach
- [ ] Create project structure
- **Status:** pending

### Phase 3: Implementation
- [ ] Execute the plan
- [ ] Write to files before executing
- **Status:** pending

### Phase 4: Testing & Verification
- [ ] Verify requirements met
- [ ] Document test results
- **Status:** pending

### Phase 5: Delivery
- [ ] Review outputs
- [ ] Deliver to user
- **Status:** pending

## Decisions Made
| Decision | Rationale |
|----------|-----------|

## Errors Encountered
| Error | Resolution |
|-------|------------|
EOF

cat > findings.md << 'EOF'
# Findings & Decisions

## Requirements
-

## Research Findings
-

## Technical Decisions
| Decision | Rationale |
|----------|-----------|

## Issues Encountered
| Issue | Resolution |
|-------|------------|

## Resources
-
EOF

cat > progress.md << EOF
# Progress Log

## Session: $DATE

### Current Status
- **Phase:** 1 - Requirements & Discovery
- **Started:** $DATE

### Actions Taken
-

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|

### Errors
| Error | Resolution |
|-------|------------|
EOF

echo ""
echo "Planning files initialized."
echo "Files: task_plan.md, findings.md, progress.md"
