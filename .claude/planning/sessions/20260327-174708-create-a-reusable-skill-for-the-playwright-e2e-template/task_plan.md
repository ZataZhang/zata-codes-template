# Task Plan: Create a reusable skill for the Playwright e2e template

## Goal
Package the existing `e2e-template/` workflow into a repository skill under `skills/` so future agents can scaffold and adapt Playwright end-to-end tests with a consistent process.

## Current Phase
Phase 4

## Phases

### Phase 1: Discovery
- [x] Read repository instructions and session hook output
- [x] Inspect `e2e-template/` structure and adaptation points
- [x] Inspect existing `skills/` patterns and skill authoring guidance
- **Status:** complete

### Phase 2: Skill Design
- [x] Choose the skill scope and name
- [x] Define the core workflow and validation steps
- [x] Decide whether supporting references are needed
- **Status:** complete

### Phase 3: Implementation
- [x] Create the new skill directory and files
- [x] Keep instructions concise and repository-specific
- [x] Add any supporting reference material
- **Status:** complete

### Phase 4: Verification & Delivery
- [x] Validate the created files and structure
- [x] Update planning records with outcomes
- [x] Summarize deliverables and caveats
- **Status:** complete

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Create a repo-local skill rather than modifying `e2e-template/README.md` only | The user explicitly asked for a skill under `skills/`. |
| Base the skill on the existing `e2e-template/` directory instead of duplicating the template files | The repo already ships the template, so the skill should guide reuse instead of creating a second source of truth. |
| Add one small reference file instead of putting the entire checklist into `SKILL.md` | This keeps the trigger instructions concise while preserving the adaptation details. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Existing planning files belonged to an unrelated prior task | Replaced the active planning files with the current skill-creation task. |

## Completion Summary
- **Status:** Complete (2026-03-27)
- **Tests:** Passed (`find skills/playwright-e2e-template -maxdepth 3 -type f | sort`, `git status --short -- skills/playwright-e2e-template .claude/planning/current`, `git diff --check -- skills/playwright-e2e-template .claude/planning/current`)
- **Deliverables:** `skills/playwright-e2e-template/SKILL.md`, `skills/playwright-e2e-template/references/adaptation-checklist.md`
- **Notes:** The new skill intentionally reuses `e2e-template/` as the source of truth instead of embedding a duplicate template copy under `skills/`.
