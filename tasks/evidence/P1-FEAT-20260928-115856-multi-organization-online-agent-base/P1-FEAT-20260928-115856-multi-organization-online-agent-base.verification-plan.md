# Verification Plan — 多组织通用在线 Agent 底座

## Identity and boundaries

- PRD: `tasks/archive/P1-FEAT-20260928-115856-multi-organization-online-agent-base.md` (runner archived it during execution)
- Baseline HEAD: `66f6c4d024fac115e1f31606accdb92992ad44ca`
- Verified working tree (delivery records and local package cache excluded): `94f1e11857184941a1f007a3e7d1ec65db17c267`
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

Final tree identity is computed with `rv_stack.git_identity()` using a temporary Git index. The helper removes committed PRD/evidence records and the local package cache from that temporary index before applying source changes, so excluded paths are absent from the resulting tree. `kc evidence check --evidence tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base --worktree . --json` re-executed all seven manifest commands on tree `94f1e11857184941a1f007a3e7d1ec65db17c267`: 7 passed, 0 failed, 0 timed out. The check was repeated after the verifier-repair round (streaming deltas at the executor and event polling in the member UI, plus the tracked `tests/backend/test_agent_streaming_deltas.py`) and again reported 7/7 on this tree. Any further change to the SSE path, the event projection, the member page, or the Run/Event contract invalidates rv-2 and requires reverting to a fresh recording. Any relevant route, proxy, persistence, permission, protocol, or UI change after an RV run invalidates that RV evidence and requires recollection. Human-Confirmed checkboxes remain untouched; the independent verifier verdict is still pending.
