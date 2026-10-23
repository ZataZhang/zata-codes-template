# Retest grading

This review is **not blinded and not paired**. Reviewer had seen first-round findings. Retest tasks/source variants differ, so scores cannot establish a controlled improvement effect or replace the original blind results. Original blind reports remain unchanged. Same six dimensions and factual standards are used; credit comes from source-supported output, not matching a checklist. Product tests, requests and builds that were not executed are not passes.

Case 1 is pending completion notification and is not yet graded. Final three-case mean is therefore not available.

| Case | Scope /20 | Investigation /20 | Accuracy, traceability, actionability /20 | References, navigation /15 | Verification honesty, usability /15 | Lightweight portability /10 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2 | 20 | 20 | 20 | 15 | 14 | 10 | 99 |
| 3 | 20 | 20 | 20 | 15 | 14 | 10 | 99 |

## Case 2

Task asks to synchronize the patch's probe rename across function docs, caller instructions and navigation, docs only. `changes.patch` and actual router both use `/operational-ready`, retaining Python `ready`. Health page, feature index, probe-client guide, observability guide and MkDocs navigation consistently reflect it. Old `/ready` appears only in clearly identified migration/test-mismatch context. Generic external deployment settings are recommended changes, with actual migration explicitly unconfirmed.

Source checks: `src/backend/main.py` creates the module app through delegated production factory. `composition/app_factory.py` invokes `run_migrations()` during factory execution, constructs auth components, conditionally seeds users, includes health_router without prefix, then configures observability middleware conditionally. `bootstrap.py` really invokes Alembic upgrade. `auth_wiring.py` really obtains Redis client via config.redis.url. Health handlers return fixed dictionaries, ignore Request and have no auth/DB/Redis calls. This supports the useful distinction between request behavior and app construction dependencies.

`tests/test_health.py` really imports backend.main.create_app, calls it, then redundantly registers health_router, uses ASGITransport, and asserts both status and JSON for all three paths. Page accurately explains that duplicate registration can mask absent production registration without falsely calling it a standalone FastAPI test. It notes no explicit lifespan or service substitutes and module import's app construction. Root conftest really limits residue sentinel to realdb-marked tests; disabling OTLP is not DB/Redis isolation. The stale `/ready` test mismatch is identified rather than silently recommending a passing test. Proposed follow-up commands are labeled unexecuted, with environment requirements.

Deduction: verification/usability −1 because actual MkDocs render/strict build was not completed and layout/anchor usability is not established by static links alone. This is a disclosed environment limitation, **not false success**. No product-pass credit is given. No critical factual error, wrong main path or unsupported passing claim found. Scope and lightweight scores remain full: expanded factory/test context is relevant to the actual readiness interpretation, and no executable machinery or source change is introduced.

## Case 3

Task targets stale health documentation and existing navigation. Health page replaces nonexistent legacy implementation/check function/test claims with real router, registered factory chain and fixed anonymous responses for `/health`, `/ready`, `/live`. Actual router agrees; no accidental case-2 URL transfer. It does not misread ready's future-extension docstring as implemented dependency checks or 503. App-construction/request distinction and test fidelity match the same sources described above. All three JSON assertions are correctly stated; no product-test execution claim appears.

Existing feature index and MkDocs nav already point to health.md with service-probe labels, so preserving them is sufficient maintenance and avoids unnecessary edits. Relative references route maintainers to observability, architecture, tests, deployment and feature index. Suggested changes have concrete symbols and affected contracts. Verification proposes actual anonymous requests plus route/OpenAPI inspection, while preserving deployment uncertainty.

Deduction: verification/usability −1 for uncompleted strict/rendered documentation build, disclosed honestly as missing dependency tooling. No invented pass, wrong production path or critical factual error found. Product behavior and deployment remain unverified, appropriately labeled rather than awarded execution credit.

## Evidence limitations

Reviewed task, delivery, final documentation and relevant actual source/tests directly. No dependency installation, service startup or product test run was performed by reviewer. DELIVERY reports hash-based change-scope checking because snapshots lack .git; this review did not reconstruct their complete before/after hash ledger, and changed-files.json/changes.diff are absent from these retest case directories at review time. Therefore document-only scope is supported by declared file list and inspected artifacts, not an independently reproduced full-tree diff. Missing MkDocs was truthfully disclosed; no external post-hoc build is counted as executor validation.

Retest deliveries do not report full task timing and explicitly decline estimates. Tokens unavailable. No speed or token comparison is possible.

## Post-audit adjustment and completed case 1

This section supersedes the provisional case-2 score and the pending-case-1 status above. Earlier text is retained as an audit trail. A parent-initiated independent audit named downstream consumers for reinspection; this is additional nonblind information. First-round grading files remain untouched.

| Case | Scope /20 | Investigation /20 | Accuracy, traceability, actionability /20 | References, navigation /15 | Verification honesty, usability /15 | Lightweight portability /10 | Final total |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 20 | 20 | 19 | 15 | 14 | 10 | 98 |
| 2 | 18 | 15 | 18 | 14 | 12 | 10 | 87 |
| 3 | 20 | 20 | 20 | 15 | 14 | 10 | 99 |

Final three-case mean: **94.67/100**. It is not a paired or blinded comparison with the original runs.

### Case 2 downstream impact omissions

Additional actual-source inspection identifies directly affected consumers not reported by the executor:

- `src/backend/api/middleware/prometheus_metrics.py::_EXCLUDED_PATHS` still includes `/ready`, not `/operational-ready`; `_should_record` compares the registered route template against this set. Thus the renamed readiness endpoint will now be counted in RED metrics when middleware is enabled. The docs mention metrics middleware but do not disclose this route-change impact. No execution is needed to identify the static mismatch; exact runtime observations remain unconfirmed.
- `tests/test_metrics.py::test_middleware_ignores_excluded_paths` requests old `/ready` in a separate FastAPI app without the health router and only asserts absence of old-path labels. It does not protect exclusion of the renamed readiness endpoint. This is a coverage gap, not a justified claim that the metrics test necessarily fails.
- `tests/guards/test_openapi_schema.py::REQUIRED_PATHS` still requires `/ready`. `_get_openapi_schema` uses actual create_app and `test_openapi_schema_has_required_paths` compares that required set with app.openapi(). Current route source supplies only `/operational-ready`. The missing-path assertion is therefore inconsistent with the new router and expected to fail if execution reaches it. Docs-only authorization correctly prohibits fixing this test, but should not prevent reporting the dependency and future validation step.
- Root `README.md` and `README.zh.md` still advertise `/ready` in their default health-probe descriptions (line 147 in both). They are human-facing documentation affected by the rename. Their exclusion from a narrowly interpreted docs/ plus mkdocs write scope is partly a harness/scope issue, so the deduction is primarily for failure to identify/report the stale references, not for refusing unauthorized edits.

Case-2 adjustment from provisional 99 to **87**: scope −2 for incomplete affected-document inventory/reporting; investigation −5 for missing middleware, metrics-test and guard consumers; accuracy/actionability −2 because the change map guides maintainers to only health tests and misses actual metrics behavior change; references/navigation −1 for stale root documentation not surfaced; verification −2 additional to the existing build limitation for omitting the OpenAPI guard mismatch and metrics-regression verification. No source/test modifications were required or permitted. These are material impact-completeness omissions, **not fabricated executed passes**. The actual new URL and production main path remain correct.

This downstream audit concerns a real URL rename; case 3 makes no source-interface change and retains `/ready`, so it does not incur the same mismatch deduction. Its map could be richer, but exhaustive future consumers are not required for the bounded stale-page correction task.

### Case 1 completed review

The existing architecture page is reused with no parallel authority or unnecessary nav churn. Actual AuthService, RedisSessionStore, auth_wiring, two routers, settings source order, user-directory/repository methods, frontend API calls, backend fixtures, Redis tests and browser setups substantiate the lifecycle/change map. Correctly documents per-domain models/prefixes/Cookies, fixed 60-day Cookie and hard-coded secure=False, 15/60 defaults, renewal before active-account lookup, no record deletion on disable, and possible token reuse after re-enable explicitly as inference. Also notes initial Redis create uses sliding TTL without absolute cutoff capping, and registration commits user before creating Redis session. Bootstrap really updates an existing seed admin's password, unlike the older description.

Test map now correctly separates production-factory/real-DB backend tests with fakeredis injection from actual Redis opt-in; `pytest.ini` defaults exclude redis, the explicit `-m redis` override enables it. The Redis unit tests do not assert TTL/absolute boundaries and the document says so. Browser login setups really use fetch through each frontend proxy and save storageState; they are correctly distinguished from full form interaction. `admin-users.admin.spec.ts` does not independently prove original-session rejection, appropriately delegated to backend coverage. Commands are future checks, not passes.

Deductions: accuracy −1 because §7 still labels disable “即时失效其会话” while the improved adjacent sections carefully distinguish rejection from permanent revocation. This is residual shorthand ambiguity, not a critical contradiction given the explicit lifecycle description. Verification/usability −1 for uncompleted rendered/strict documentation build (honestly disclosed). No critical error, wrong main path or unsupported executed pass found.

Final caveats: full-tree change scope remains based on executor-described hash checks rather than an independently reconstructed baseline diff. No timing/token metrics are available. Subsequent fresh sync runs are outside this report until explicitly assigned.

### Later scope evidence

Parent subsequently supplied baseline-derived `changed-files.json` and `changes.diff` for each frozen retest case. Inspected manifests agree with DELIVERY: case 1 only authentication.md, case 2 the four listed docs plus mkdocs.yml, case 3 only health.md. This resolves the earlier absence-of-diff artifact caveat at the supplied-evidence level; reviewer did not independently regenerate the parent baseline comparison. Parent also reports all three strict builds passed using a separate existing executable. That is supplementary validation, not executor validation; scores above remain unchanged and no unexecuted product check becomes a pass.
