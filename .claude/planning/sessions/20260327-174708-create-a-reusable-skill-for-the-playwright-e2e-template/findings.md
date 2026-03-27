# Findings & Decisions

## Requirements
- The user asked to turn `/Users/zata/code/zata_code_template/e2e-template` into a reusable skill under `/Users/zata/code/zata_code_template/skills`.
- The result should live in the repository's `skills/` directory and follow the existing skill format.

## Research Findings
- `e2e-template/README.md` already documents the template structure, adaptation checklist, run commands, and the `chromium` / `no-auth` project split.
- The highest-signal adaptation points are `support/env.ts`, `scripts/stack-control.mjs`, `page-objects/LoginPage.ts`, `tests/setup/auth.setup.ts`, `fixtures/session.fixture.ts`, and `support/api-client.ts`.
- Existing repo skills are lightweight. Most only ship `SKILL.md`; some add `references/`, `templates/`, or `scripts/` when the extra files materially help.
- The bundled `skill-creator` guidance recommends keeping `SKILL.md` concise and moving detailed operational material into supporting files only when needed.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Name the new skill around Playwright E2E template adaptation | The trigger should match how users will ask for this workflow. |
| Reference the existing `e2e-template/` files directly from the skill | Avoids duplicating the template and keeps `e2e-template/` as the single source of truth. |
| Add one focused reference file for adaptation checkpoints | The checklist is useful but would make `SKILL.md` noisy if copied inline in full. |

## Outcome
- Created `skills/playwright-e2e-template/SKILL.md` with scope, workflow, guardrails, and verification commands.
- Created `skills/playwright-e2e-template/references/adaptation-checklist.md` with file-level mapping, environment variables, and validation order.
- The new skill is concise, repo-specific, and leaves `e2e-template/` as the only template source of truth.

## Resources
- `e2e-template/README.md`
- `e2e-template/playwright.config.ts`
- `e2e-template/support/env.ts`
- `e2e-template/scripts/stack-control.mjs`
- `e2e-template/page-objects/LoginPage.ts`
- `e2e-template/tests/setup/auth.setup.ts`
- `e2e-template/fixtures/session.fixture.ts`
- `e2e-template/support/api-client.ts`
- `skills/code-reviewer/SKILL.md`
- `skills/planning-with-files/SKILL.md`
- `skills/.system/skill-creator/SKILL.md`
