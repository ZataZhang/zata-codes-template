# Adaptation Checklist

Use this file when turning `playwright-e2e/` into a project-specific Playwright package.

## Required File Mapping

### `support/env.ts`

- Set the default UI URL for docker mode and dev mode.
- Set the API base URL default.
- Set the health-check URL if the app does not expose `/healthz`.
- Confirm which environment variables should provide credentials.

### `scripts/stack-control.mjs`

- Replace the default `docker compose up -d --wait` and `docker compose down` commands if the project uses custom startup commands.
- Update readiness URLs so both the primary app and API checks match the real stack.
- Keep `PLAYWRIGHT_SKIP_STACK_BOOT=1` working for remote or already-running environments.

### `page-objects/LoginPage.ts`

- Replace the placeholder form locator in `waitForReady()`.
- Replace the username, password, and submit button selectors in `login()`.
- If the product uses magic links, SSO, or MFA, redesign the page object instead of forcing the placeholder login flow.

### `tests/setup/auth.setup.ts`

- Replace the placeholder protected route in `page.goto(...)`.
- Replace the post-login URL assertion with a real success signal.
- Keep storage-state persistence unless the project intentionally avoids cookie/session reuse.

### `fixtures/session.fixture.ts`

- Add project-specific page objects or fixtures that tests will reuse.
- Keep the cleanup registry only when tests create mutable data.
- Remove unused fixture scaffolding rather than leaving dead examples behind.

### `support/api-client.ts`

- Replace `/auth/login` and its payload shape with the project's real auth API.
- Add typed helpers for common seed and cleanup actions if the suite needs them.
- If there is no stable API for setup/cleanup, reduce the client to the minimal required surface.

## Example Test Files

### `tests/smoke/pages.spec.ts`

- Replace placeholder routes with real smoke coverage.
- Use one assertion per page that proves the page finished loading meaningfully.

### `tests/workflows/no-auth-example.no-auth.spec.ts`

- Keep this only when the app has public pages, a public proxy, or a health-checked demo surface.
- Otherwise remove it and the `no-auth` project to avoid fake coverage.

### `tests/workflows/screenshot.spec.ts`

- Keep screenshot tests only for stable UI states.
- Mask timestamps, animations, rotating banners, avatars, or any other nondeterministic elements.

## Environment Variables

These variables appear in the template and should be mapped deliberately:

- `PLAYWRIGHT_SKIP_STACK_BOOT`
- `PLAYWRIGHT_STACK_MODE`
- `PLAYWRIGHT_STACK_UP_COMMAND`
- `PLAYWRIGHT_STACK_DOWN_COMMAND`
- `PLAYWRIGHT_STACK_TIMEOUT_MS`
- `PLAYWRIGHT_STACK_POLL_INTERVAL_MS`
- `PLAYWRIGHT_KEEP_STACK`
- `PLAYWRIGHT_BASE_URL`
- `PLAYWRIGHT_API_BASE_URL`
- `PLAYWRIGHT_HEALTH_URL`
- `PLAYWRIGHT_IDENTIFIER`
- `PLAYWRIGHT_PASSWORD`
- `PLAYWRIGHT_TEST_RESULTS_DIR`
- `PLAYWRIGHT_HTML_OUTPUT_DIR`
- `PLAYWRIGHT_JUNIT_OUTPUT_FILE`

## Verification Order

1. Install dependencies and browsers.
2. Run `npm run lint`.
3. Run `npm run typecheck`.
4. Run `npm test`.
5. Run `npm run test:no-auth` only if the `no-auth` project remains.
6. Run visual commands only if snapshot testing was requested.
