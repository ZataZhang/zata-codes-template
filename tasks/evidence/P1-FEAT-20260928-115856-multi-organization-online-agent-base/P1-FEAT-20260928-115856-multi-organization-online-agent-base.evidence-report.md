## 人审导航 / Human Review Navigation

Verified implementation tree: `94f1e11857184941a1f007a3e7d1ec65db17c267` (PRD/evidence delivery records, generated Playwright files, and local package cache excluded). Baseline HEAD: `66f6c4d024fac115e1f31606accdb92992ad44ca`. KedaCode re-executed all seven manifest commands against this tree with `kc evidence check`; all 7 passed, 0 failed, and 0 timed out. The tree identity helper removes excluded committed paths from its temporary index before applying source changes. RV-2's separate primary-demo run used temporary Playwright staging files; those files are not part of the verified tree.

**This tree contains the repair for the independent verifier's BLOCKER.** The verifier's RED verdict on the previous tree was that the member UI showed no partial reply while the model was responding: the page polled `GET /agent-runs/{id}` and rendered `assistant_message` or a placeholder, and the executor used a non-streaming completion. The repair streams the model response (`stream: true`, SSE), persists each text fragment as `message.delta` on the one canonical Run/Event chain, and has the member page poll `GET /agent-runs/{id}/events?after_seq=` so the reply grows while the Run is still `running`. `rv-2-incremental-reply.txt` records the partial reply captured mid-run and `rv-2-streaming-reply.png` is that live screen; the RV-2 workflow now fails unless a non-empty partial reply is seen while the Run is running and the final reply starts with it.

The primary demo was re-recorded and now follows the PRD's five-step script exactly, including the previously missing Skill update/compare/restore and the second Run with frozen versions; `rv-2-caption-trace.txt` lists every on-screen caption with its bounding box, and `scripts/inspect_primary_demo.py` (its output is appended to `rv-2-primary-demo.txt`) confirms each step's caption stays visible for at least five seconds and that the steps are visually distinct.

The KedaCode command re-execution is not an independent verifier verdict. A fresh verifier verdict on this tree is still required; the earlier `REVIEW_INCIDENT / INCONCLUSIVE` runs never produced a valid verdict.

Re-execution was repeated at this tree after the repair: `kc evidence check --evidence tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base --worktree .` reported **7/7 passed**. One earlier attempt lost rv-6 because the image build could not reach `fonts.googleapis.com` (`Failed to fetch 'Geist' from Google Fonts`); the same registered rv-6 command passed on an identical tree, so the production frontend build still needs outbound access to Google Fonts at build time — an external dependency, not a defect introduced here.

Issue: [GitHub Issue #58](https://github.com/ZataZhang/zata-codes-template/issues/58). [Draft PR #62](https://github.com/ZataZhang/zata-codes-template/pull/62) remains open at the earlier WIP head `857691169b7bb66846cba12e23b0ea9c542ae1c6`; its last PostgreSQL and MySQL CI checks failed. The validated local head has not yet been published, so PR checks must be refreshed after the verifier gate is resolved. The listed presentations were cross-checked against their corresponding evidence reports.

| Outcome | Presentation and open command | Expected value |
|---|---|---|
| Agent publication → member Run → fresh-session history → admin trace (rv-2) | `tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-prototype.png` + `tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-agent-run.png` + `tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-multi-organization-agent.mp4`; `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-multi-organization-agent.mp4"` | Prototype and real page are paired below; video shows the same Run ID, successful reply, reopened history, and low-sensitivity admin trace. Captions disclose the mock model. |
| Skill v1 → v2 comparison → restored v3 and frozen Run versions (rv-3) | `tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-3-prototype.png` + `tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-3-skill-version.png`; `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-3-skill-version.png"` | Prototype and real management page are paired below; linear v1/v2/v3 history, restored body equals v1, old Run remains v1 and new Run freezes v3. |

### rv-2 target prototype and real user flow

Target prototype (`interactive prototype / component preview`, 1440×1200):

![rv-2 target prototype](rv-2-prototype.png)

Local image: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-prototype.png"`

Real implementation (`real user flow`, 1440×1200, English, light theme; model transport mock, not a live model claim):

![rv-2 real Agent Run](rv-2-agent-run.png)

Local image: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-agent-run.png"`

The comparison checks Agent selection, persisted reply/status, Run ID, and recent history. Layout differs intentionally: production uses the existing Next.js sidebar/card system rather than the prototype’s custom shell.

The separate primary recording is a real-browser walkthrough of the PRD's five scripted steps, not the regression-test recording: publish a model-configured Agent, member Run with a visibly growing reply, reopen the same Run and inspect the admin trace, update/compare/restore the Skill, then a second Run that freezes the restored version while the old Run stays on v1. `rv-2-caption-trace.txt` lists each on-screen caption with its timestamp and box, `rv-2-primary-demo-clips.json` records the clip durations, and `scripts/inspect_primary_demo.py` (output in `rv-2-primary-demo.txt`) reports that every step's caption stayed visible for at least five seconds and that no two steps share the same caption frame. The model steps are labelled as mock on screen; real model behaviour is not claimed.

<video controls src="rv-2-demo-multi-organization-agent.mp4"></video>

![RV-2 增量可见：运行未结束时回复已增长](rv-2-streaming-reply.png)

Local image, `real user flow`: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-streaming-reply.png"` — captured by the RV-2 workflow while the status line still read `Status: running`; the same moment is logged in `rv-2-incremental-reply.txt`.

#### RV-2 workflow screenshots (local-only evidence)

Each screenshot is a real rendered browser step with its Chinese caption. The MP4 above is the presentation; these frames provide still-image review.

![RV-2 主演示步骤 1：管理员创建 Skill](rv-2-demo-step-1-skill.png)

Local image, `real user flow`: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-step-1-skill.png"`

![RV-2 主演示步骤 2：管理员发布 Agent](rv-2-demo-step-2-publish.png)

Local image, `real user flow`: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-step-2-publish.png"`

![RV-2 主演示步骤 3：成员运行 Agent](rv-2-demo-step-3-run.png)

Local image, `real user flow`: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-step-3-run.png"`

![RV-2 主演示步骤 4：重新打开历史](rv-2-demo-step-4-history.png)

Local image, `real user flow`: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-step-4-history.png"`

![RV-2 主演示步骤 5：管理员查看低敏轨迹](rv-2-demo-step-5-trace.png)

Local image, `real user flow`: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-2-demo-step-5-trace.png"`

### rv-3 target prototype and real user flow

Target prototype (`interactive prototype / component preview`, 1440×1200):

![rv-3 target prototype](rv-3-prototype.png)

Local image: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-3-prototype.png"`

Real implementation (`real user flow`, 1440×1200, English, light theme):

![rv-3 real Skill versions](rv-3-skill-version.png)

Local image: `open "tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/rv-3-skill-version.png"`

The comparison checks v1/v2/v3 ordering, v1/v2 comparison text, restored-current version, and A2A publication status. The production page additionally exposes the approved-peer directory and real Run list.

## Evidence by oracle

### rv-1 — organization isolation and dual-database migration: PASS

- `rv-1-org-isolation-pg.txt` and `rv-1-org-isolation-mysql.txt`: real `uvicorn backend.main:app`, real login cookies, server-derived organization scope, and fresh HTTP/SQL reads.
- Both databases prove `upgrade head` with a pre-existing Run and two events, backfill to the default organization, downgrade to `b93aa5cf0228`, and re-upgrade to single head `26e8967fcd01`; Run/Event counts and foreign-key relationships remain intact.
- Organization B member/admin exact-ID reads of A Agent, Run, events, assets, Skill, credentials, and management traces return 403/404 without A names, content, credentials, or existence leaks.
- Platform admin has no default member-content access. Request-body organization IDs are not trusted.
- After a platform-admin organization move, the member and new org admin cannot read old data or append to the old conversation; old org admin still sees its low-sensitivity trace.
- `rv-1-negative-control-pg.txt`: a temporary source mutant with organization/owner filtering removed returns HTTP 200 and the A payload, producing the expected red result. No production fault-injection switch exists.

### rv-2 — real Agent Run workflow: PASS

- `rv-2-browser-handshake.txt`: the host Playwright client connects to the isolated Chromium service through the published loopback endpoint before starting the real UI flow.
- `rv-2-real-user-flow.txt`: `just e2e tests/rv58-workflows/agent-run.auth.spec.ts`, two tests passed. The spec is staged from the evidence scripts into a visible, temporary Playwright test directory and removed after each run.
- `rv-2-incremental-reply.txt` + `rv-2-streaming-reply.png`: while the Run status line still read `Status: running`, the reply paragraph already showed a 30-character partial reply; the workflow asserts the terminal reply starts with that partial text and grew, and that the page requested `/api/agent-runs/{id}/events`.
- `rv-2-negative-control.txt`: a malformed streamed model response makes the real UI show `failed`; the expected `succeeded` assertion goes red before the corrected flow passes.
- Browser requests use `POST /api/agent-runs`, never `/api/api/agent-runs`. The displayed Agent ID and Run ID are used for subsequent reads.
- The fresh browser context reopens the same Run and sees the terminal reply and frozen Skill v1. Admin sees `model.call.completed` without the original message.
- `rv-2-demo-multi-organization-agent.mp4` is the separate primary demo, following the PRD's five scripted steps with Chinese captions; `rv-2-primary-demo.txt` records the assembly and the `scripts/inspect_primary_demo.py` verdict (`PRIMARY_DEMO_INSPECTION: PASS`), and `rv-2-caption-trace.txt` maps each caption to its on-screen box. The model transport is mocked; no live model behavior is claimed.

### rv-3 — Skill version and Run snapshots: PASS

- `rv-3-real-user-flow.txt`: `just e2e tests/rv58-workflows/skill-version.auth.spec.ts`, two tests passed.
- `rv-3-negative-control.txt`: a temporary altered v1 response makes the immutable-history assertion fail; the green flow then verifies exact v1/v2/v3 content and Run snapshots.
- The real admin page appends v2, compares v1/v2, and restores v1 as new v3 without modifying v1 or v2.
- The original Run remains frozen on v1; the post-restore Run displays frozen v3 and reads the restored v1 body. A fresh browser context confirms it.
- Repeated Skill creation with one `Idempotency-Key` returns the same ID and `current_version=1`.

### rv-4 — neutral distribution audit: PASS

- `rv-4-distribution-audit.txt`: the actual `just copy` output contains 889 files; the scan includes source/config/docs, media metadata, binary/package inventory, and Git-history review.
- `rv-4-negative-control.txt`: the same copy auditor rejects a deliberately injected CargoX marker in the actual copied output.
- No CargoX/Outlook/freight/cost-rate/vendor text remains in the publish surface. Legacy freight test/prototype names were replaced with generic support examples.
- No archive or binary package is tracked. No source-repository migration, lockfile, font, image, brand package, or credential was imported.
- FreshAI/ai-assistant references are provenance only, not runtime dependencies. The distribution decision is a clean history for the audited current tree, not an unreviewed full-history publication.

### rv-5 — actual template copy and sync: PASS

- `rv-5-template-copy.txt`: real `just copy`, Alembic migration, sync clone/compare, and copied backend `/health` = 200. Sync found one changed shared file (`tests/playwright-e2e/playwright.config.ts`) and zero new entries.
- `rv-5-negative-control.txt`: removing the copied backend entry point prevents startup and `/health`, which makes the startup check red.
- Copied output excludes `.agent-runner/` and `.env.view-state`. Nested copies do not install hooks, stage, or commit in the parent repository; standalone behavior is unchanged.
- Two GitHub fetches failed with early EOF. The final proof therefore uses the real sync script with this worktree as `SYNC_TEMPLATE_TEMPLATE_REPO`; clone/compare completed and listed one changed candidate. This is not a claim that GitHub connectivity was verified.

### rv-6 — production Compose and secret boundary: PASS

- `rv-6-production-compose.txt`: all three images build and all three containers start. Backend `/health` returns 200. The recorded run is the successful re-execution after a first attempt failed while the image build fetched `fonts.googleapis.com`; that dependency on outbound font access is listed under limits.
- `rv-6-negative-control.txt`: the real production frontend fails its login assertion when the upstream base is faulted with a duplicated `/api` prefix.
- Public `/api/auth/login` and `/api/agent-runs` return 200; admin `/api/admin/auth/login` and `/api/admin/auth/me` return 200. `/api/api/agent-runs` returns 404 and the A2A proxy preserves its independent route.
- The production Dockerfile supplies `API_BASE_URL` at build time; Next.js no longer serializes `localhost:8000`.
- Admin `dist` (96 files) and public `.next` (2031 files) contain zero model-key markers. Browser-facing responses contain no model key. No public deployment was performed.

### rv-7 — official A2A interoperability and failure closure: PASS

- `rv-7-a2a-admin.png`: a real organization administrator publishes an Agent, issues its inbound credential, and registers the external peer; a separate platform-admin session approves the peer on the actual review page. The same UI flow exposed a Vite proxy collision, fixed by limiting the dev proxy to `^/a2a/`; `/a2a-approvals/` now remains a frontend route.
- `rv-7-negative-control.txt`, `rv-7-a2a-bidirectional.txt`, and `rv-7-official-client.json`: independent official `a2a-sdk[all]==1.0.0` client and server. A temporary source mutant disables credential-Agent and Task organization/Agent/owner checks; B's credential then reads A's exact Task and input, making the isolation oracle red. The unmutated tree returns 404 with no task content.
- Inbound: Agent Card, send, same-message retry, fresh get, list, subscribe, cancel, and fresh cancel-state read. Retry returns the same Run/Task ID.
- Organization B credentials cannot read A’s exact Task ID; responses do not reveal its existence.
- Outbound: the UI-approved peer is called from the formal member Run API; the parent Run links its remote Task and contains the remote result in canonical events.
- Skill append/restore retries return the first version IDs and preserve `[1,2,3]`; same-key different content returns 422.
- Unsafe tool and unregistered-peer Runs fail without `run.completed`; redirect targets are not followed; disabled Agent and missing model return 409 without new success records; organization shutdown returns 401 for browser and 404 for A2A.
- `tests/backend/test_a2a_outbound_policy.py`: card shape, no-DNS/no-HTTP rejection for unlisted and loopback targets, private DNS rebinding, public allowlist acceptance, and cross-organization rejection before HTTP construction.

## Architecture and transaction evidence

- `rv-7-run-a2a-architecture.txt`: one `RunModel`, one `RunEventModel`, one canonical Run transaction, and one `append_skill_revision` write path. No A2A Task ORM model or second task/asset state store exists. Its captured source tree is recorded inside the file; the official protocol run and final tree are independently reported in the rv-7 files.
- Run/Event commits use the existing repository. Skill create/append/restore serializes through row locks and unique idempotency constraints. A2A tasks are projections of those same Runs; remote Task IDs are metadata in canonical tool events.
- `just lint --reuse`: jscpd, pylint duplicate-code, architecture, guideline consistency, and max-file-lines all pass on the current tree.
- `just lint --full`: PASS on the current tree, including whitespace, Ruff, PRD checklist, archive, architecture, and migration/schema guards.
- `uv run alembic heads`: exactly `26e8967fcd01 (head)`.

## Repository validation summary

- `just test`: **543 passed, 1 skipped**; local OIDC package **17 passed** on the current tree, using an isolated temporary PostgreSQL database. The three new cases are `tests/backend/test_agent_streaming_deltas.py`: SSE fragments reach the delta callback in order, a non-streaming endpoint is reported as not streamed, and fragments are batched into `message.delta` events. The changed Vite proxy was exercised by the RV-7 real admin UI flow.
- Re-execution in this round: `git diff --check`, `uv run mkdocs build --strict`, `just test` (540 passed, 1 skipped plus 17 OIDC) and `SKIP=check-test-flag uv run pre-commit run --all-files` all pass on the same tree, alongside `kc evidence check` 7/7.
- `just test` re-run after the lint-gate repair (see the PRD Change Log entry on `.pnpm-store`): **543 passed, 1 skipped** and local OIDC package **17 passed** again; `just lint --full` now passes on the current tree instead of failing on the accidentally committed local pnpm cache.
- Historical cache incident resolved by runner checkpoint: current HEAD tracks zero .pnpm-store files (git ls-files .pnpm-store). Earlier residual-cache warning no longer applies.
- `pnpm build` in `frontend-admin` and `frontend-public`: PASS. The current admin build completed; Vite reports the existing large-chunk advisory.
- Playwright package `pnpm exec tsc --noEmit`: PASS.
- `uv run mkdocs build --strict`: PASS on the current tree, with existing informational notices for unlisted pages and unresolved anchors.
- `scripts/shared/just/scan_evidence_secrets.sh`: no credential-shaped strings found.
- Focused Run trace tests: `tests/backend/test_run_trace_projection.py` and `tests/backend/test_run_trace_export.py`, **23 passed**.
- `skills/prd/scripts/check_prd_acceptance_checklist.py --check-provided`: PASS; all required PRD/oracle structures parse.
- `skills/prd/scripts/check_human_review_checklist.py --fail-on-warning`: PASS; the HTML checklist also passed an isolated real-browser check with zero `pageerror`, a visible first decision, visible primary demo, and navigation through all five decisions.
- `evidence.json` manifest structure check: seven numbered RV groups, all required fields and referenced evidence files present, five primary-demo steps, and every still image embedded in the PRD/report.
- `just test-changed`: 126 passed and one failure in `tests/backend/test_admin_user_management.py::test_admin_api_rejects_disabling_the_last_enabled_platform_admin`, outside the changed files. This report does not claim that failure is pre-existing; it remains disclosed and is not used to waive feature gates.

## Limits and unresolved external dependencies

- Real paid model behavior is **not verified**; only the OpenAI-compatible request construction and controlled transport fixture were exercised.
- Real public external Agent connectivity is **not verified**; A2A interoperability used the independent official local SDK client/server, which is the PRD’s permitted substitute.
- GitHub-hosted sync fetching failed twice; local-upstream sync behavior is proven instead. No external credential is required to finish the local gates.
- The production public frontend build fetches Google Fonts (`next/font`) at image-build time; one rv-6 attempt failed on that network call and the successful re-run is what is recorded. A build host without outbound access to `fonts.googleapis.com` will fail rv-6 for environmental reasons.
- Independent verifier verdict and runner-owned PR/archive gates are pending. Human-Confirmed items remain open by design.

## Pre-PR review repair (2026-11-17)

- SECURITY / high: outbound credential aliases previously accepted arbitrary environment variable names. Registration and rotation now require a deployment grant bound to organization and exact endpoint; empty grants deny all references.
- BLOCKER / high: SSE previously defaulted finish_reason to stop, allowing a normal EOF after partial text to become successful output. Missing finish_reason now raises model_stream_incomplete and follows the Run failure path.
- Five focused tests passed: successful SSE, non-streaming fallback, delta batching, truncated SSE rejection, and credential scope rejection/authorized reads.
- RV-2 repeated the real admin/member browser, API, database, incremental reply, reopened history and trace flow successfully; model transport alone is stubbed. RV-7 repeated real admin UI and official a2a-sdk==1.0.0 interoperability with added HTTP 422 assertions for B referencing platform/A credentials. See each raw file for its captured tree identity. Historical evidence retains its original tree and is not claimed as recaptured on this repair tree.
- Existing configuration documentation was updated; no new page or navigation entry was added. Runner must apply independent verification and final RV gates to this repair tree; prior verdicts do not cover these edits.

- Repair verification: just test passed (545 passed, 1 skipped; OIDC 17 passed); just lint --full and mkdocs build --strict passed; git diff --check HEAD and manifest naming/reference checks passed. RV-2 and RV-7 both passed on source tree 7255cbdd1bb9168b3deccd7d54002cbb5be1665f. First just test was blocked by the active RV stack; it was rerun after cleanup without overriding the shared-database guard.
