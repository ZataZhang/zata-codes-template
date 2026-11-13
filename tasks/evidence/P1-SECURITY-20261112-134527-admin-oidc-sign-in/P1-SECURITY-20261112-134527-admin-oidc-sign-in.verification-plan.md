# 管理员 OIDC PRD 验证计划

- Worktree: `feat/keycloak-oidc-prd`
- PRD: `tasks/pending/P1-SECURITY-20261112-134527-admin-oidc-sign-in.md`
- Approved architecture: `packages/oidc-client/` ships an installable OIDC protocol package (`zata-oidc`, import `zata_oidc`); host application owns account policy, Redis transactions, sessions, API, UI, and database.
- Approval record: user approved implementation with the independent package boundary; existing human-owned checkboxes are preserved. For public-domain same-email conflict, use the PRD's recommended secure behavior (reject association), without marking the old checkbox.
- Evidence rule: command output is captured on its first run under this directory; secrets must not be printed or recorded.

## Baseline and package gates

1. Existing auth baseline: `DATABASE_URL` points to the worktree-isolated PostgreSQL database `template_oidc_prd_pg`; `REDIS_URL` points to the local test Redis instance. The first baseline run is retained in `rv-1-baseline-admin-auth.log`.
2. New package protocol tests: `uv run pytest packages/oidc-client/tests`.
3. Build distributable artifacts and install the wheel into a temporary environment outside the checkout; exercise public API against the local RS256 identity issuer, including a rejected invalid signature.
4. Backend OIDC unit/integration and migration tests on PostgreSQL and MySQL, with logs under this evidence directory.
5. Real admin login flow via Playwright against local issuer and existing Vite/API boundary; verify success and failure routes and inspect screenshots/video.
6. Verify normal password admin login when OIDC is not configured.
7. Verify app source install, `just copy` output, and production Docker build/runtime dependency resolution include the local package.
8. Run `just lint --reuse`, `just lint --full`, `just test` and applicable `just test all`; run `uv run mkdocs build --strict` after docs/navigation updates.

External IdP is replaced only by the controlled local RS256 issuer. Application routes, composition, database, Redis transaction/session behavior, frontend, package build and installation stay real. If either database or production runtime validation cannot run, record the exact blocker and leave its acceptance item open.
