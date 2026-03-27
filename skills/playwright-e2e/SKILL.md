---
name: playwright-e2e
description: "[Updated 2026-03-27] Scaffold or adapt the repository's Playwright `playwright-e2e/` package into a project-ready end-to-end test suite. Use when copying the bundled Playwright e2e package, wiring auth and no-auth projects, mapping env vars, updating stack boot commands, or replacing placeholder login and page-object logic."
---

# Playwright E2E

Use this skill when the user wants Playwright end-to-end coverage based on the repository's bundled `playwright-e2e/`.

## Source of Truth

- Template package: `playwright-e2e/`
- Quick-start commands and project layout: `playwright-e2e/README.md`
- File-by-file adaptation checklist: [references/adaptation-checklist.md](references/adaptation-checklist.md)

Do not create a second long-lived copy of the template inside `skills/`. The skill should guide reuse of `playwright-e2e/` as the source of truth.

## Workflow

1. Inspect the target application before editing anything:
   - base UI URL, API URL, and health endpoint
   - whether tests should boot a local stack or attach to an existing environment
   - login route, form selectors, and post-login success signal
   - whether the app has public pages that justify the `no-auth` project
   - which pages or workflows are stable enough for smoke or screenshot coverage
2. Decide the target package path.
   - If the user wants a fresh Playwright package, copy `playwright-e2e/` to the requested destination and adapt it there.
   - If the target package already exists, patch it in place using the template as reference.
3. Update the required adaptation files first:
   - `support/env.ts`
   - `scripts/stack-control.mjs`
   - `page-objects/LoginPage.ts`
   - `tests/setup/auth.setup.ts`
   - `fixtures/session.fixture.ts`
   - `support/api-client.ts`
4. Adapt the example tests to real product behavior.
   - Replace placeholder selectors and routes.
   - Keep `chromium` for authenticated flows.
   - Keep `no-auth` only if the product has meaningful unauthenticated coverage.
   - Keep screenshot or visual tests only when the UI is stable enough to avoid noisy snapshots.
5. Verify with the package's Node.js toolchain.

## Guardrails

- Inside `playwright-e2e/` or any copied Playwright package, follow TypeScript and Node.js conventions. Do not force the repository's Python SSA naming rules into the Playwright package.
- Do not leave placeholder TODOs in delivered code without either resolving them or calling them out explicitly.
- Keep credentials and endpoints in environment variables. Do not hardcode secrets.
- Preserve `PLAYWRIGHT_SKIP_STACK_BOOT=1` support so the suite can target already-running staging or local environments.
- If the repo has no authenticated API seeding workflow, simplify `ApiClient` instead of keeping dead helpers.

## Verification

Run the relevant commands inside the Playwright package:

- `npm install`
- `npx playwright install chromium`
- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run test:no-auth` when the `no-auth` project is kept
- `npm run test:visual` or `npm run test:update` only when snapshot tests are part of the requested outcome

If the work stays inside this repository's bundled template, the repo-level wrappers are also valid:

- `just e2e-install`
- `just e2e`
- `just e2e smoke`
- `just e2e no-auth`
- `just e2e report`
