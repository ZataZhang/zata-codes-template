# Verification Plan — 多组织通用在线 Agent 底座

## Identity and boundaries

- PRD: `tasks/archive/P1-FEAT-20260928-115856-multi-organization-online-agent-base.md` (runner archived it during execution)
- Baseline HEAD: `66f6c4d024fac115e1f31606accdb92992ad44ca`
- Verified HEAD: `1f0e635a47c8abdab1ed010226f128f3ea3317fa`
- Verified working tree (delivery records, generated Playwright files, and local package cache excluded): `33a6ed4205fae48c94da25940609fedc564e2e86`
- Every RV script lives under `scripts/` in this evidence directory and is excluded from the code diff.
- Paid model transport is replaced by a local OpenAI-compatible fixture that now answers with SSE chunks, so the incremental-reply path is exercised through the real HTTP contract. A2A interoperability uses the independent official `a2a-sdk[all]==1.0.0` client and server. Authentication, UI, proxies, routes, migrations, transactions, persistence, and fresh reads remain real.
- No real model or public external Agent is claimed as verified.

## Oracle commands

| Oracle | Real entry and proof |
|---|---|
| rv-1 | `uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv1_org_isolation.py --db pg` and `--db mysql`; `--db pg --mutant` is the expected-red scope negative control. |
| rv-2 | `uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv_ui.py --rv 2`, which executes the real Agent Run workflow; `--rv 2 --primary-demo` captures the separate five-step, captioned presentation. |
| rv-3 | `uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv_ui.py --rv 3`, which executes `just e2e tests/workflows/skill-version.auth.spec.ts`. |
| rv-4 | `uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv4_distribution_audit.py` |
| rv-5 | `uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv5_copy_template.py`; the real copy/sync/startup path uses a local upstream URL because two GitHub fetches truncated. |
| rv-6 | `uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv6_compose.py` |
| rv-7 | `UV_CACHE_DIR=/tmp/uv-cache-issue58 UV_TOOL_DIR=/tmp/uv-tool-issue58 UV_TOOL_BIN_DIR=/tmp/uv-tool-bin-issue58 uv run --no-sync python tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/rv7_a2a.py`; real management pages register and approve a peer, then create an Agent with that peer selected before official 1.0 HTTP+JSON client/server checks. It verifies the persisted Agent allowlist and rejects a second approved but unbound peer before HTTP. Negative control adds `--negative-control --mutant`. |

## Repository gates

- `just lint --full`
- `just lint --reuse`
- `just test`
- `just test-changed` (the captured run had one failure in an admin concurrency test outside the changed files; disclose it without claiming it is pre-existing)
- `pnpm build` in both frontend directories
- `pnpm exec tsc --noEmit` in `tests/playwright-e2e`
- `uv run mkdocs build --strict`
- `uv run alembic heads` (exactly one head)
- `scripts/shared/just/scan_evidence_secrets.sh tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base`

## Evidence freshness

Final tree identity is computed with `rv_stack.git_identity()` using a temporary Git index. The helper removes committed PRD/evidence records and the local package cache from that temporary index before applying source changes, so excluded paths are absent from the resulting tree. On 2026-11-19, `kc evidence check --evidence tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base --worktree . --timeout 300 --json` re-executed every manifest command at HEAD `1f0e635a47c8abdab1ed010226f128f3ea3317fa` / verified tree `33a6ed4205fae48c94da25940609fedc564e2e86`: 7 passed, 0 failed, 0 timed out. Durations were RV-1 31.125s, RV-2 49.445s, RV-3 47.450s, RV-4 10.999s, RV-5 19.729s, RV-6 43.928s, and RV-7 48.691s. All seven negative controls were separately rerun on the same identity and produced their expected failures. The independent verifier returned PASS (risk=yellow) on that same HEAD/tree and found no unresolved product blocker. RV-2's separate primary demo was recorded on the same identity; six clips cover the five scripted steps, total 169.48 seconds, and frame inspection measured distinct captions visible for 5–18 seconds. The video SHA-256 is `cbf7b94e858cf79cf0a9445abe9941dbde558acfd54b67fbdd5746b33477b6b8`.

`just test` passed on this source tree (540 passed, 1 skipped; local OIDC package 17 passed). `just lint --reuse`, `just lint --full`, `uv run --no-sync mkdocs build --strict`, and `git diff --check` passed. GitHub CI run [44462357584](https://github.com/ZataZhang/zata-codes-template/actions/runs/44462357584) passed Frontend Build, Playwright E2E (no-auth), PostgreSQL, and MySQL. An earlier `just test-changed` run had one failure in `tests/backend/test_admin_user_management.py::test_admin_api_rejects_disabling_the_last_enabled_platform_admin`, outside the changed files; this report does not call it pre-existing and does not use it to waive the required `just test` or CI gates.

Any further change to the SSE path, event projection, member page, or Run/Event contract invalidates rv-2 and requires a fresh recording. Any relevant route, proxy, persistence, permission, protocol, or UI change after an RV run invalidates that RV evidence and requires recollection. The five Human-Confirmed checkboxes remain untouched pending the declared PR merge and merged-tree reconciliation.

The verifier recorded two non-blocking risks: the A2A admin UI permits registering a private peer address, although outbound policy rejects private DNS results before HTTP; and RV-2 negative-control cleanup relies on `finally`, so forced termination could leave a temporary source mutation behind. The captured run completed and the final source file is restored. Historical debug artifacts are excluded from the current review bundle.
