# Source verification of documentation-only retrieval

Read-only source/test inspection after writing `reader-result.md`. No tests executed and no candidate files changed. This report corrects the earlier documentation-derived statements; the earlier report remains intact.

## Case 1

Modification and domain-impact location succeeded. Source confirms `api/dependencies.py::PUBLIC_SESSION_COOKIE_NAME` is `session_id`; the public router imports it for set, clear, logout extraction, and `/me` extraction. Consequently changing that constant updates those operations together; the prior report's missing explicit logout location is a documentation navigation gap, not evidence of a separate hard-coded logout name. Public browser expiry is `api/auth_router.py::_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 60`; admin has its own equivalent constant. `composition/auth_wiring.py` supplies the same `config.auth.session_sliding_days` and `session_absolute_days` to both session stores, with different prefixes. The public-only versus shared-server-lifetime distinction in the first report is correct.

Verification location succeeded, but the documented coverage is overstated. In `tests/backend/test_redis_session_store.py`, `test_slide_expiration_returns_record` only creates a session, calls slide, and asserts non-None/user ID. No test in this file advances time, asserts TTL/expiry timestamps, or checks the absolute cutoff. The docs' claim that this file checks renewal and absolute cutoff does not hold as written. Existing fakeredis tests establish basic roundtrip, unknown-token behavior, and prefix isolation; optional `test_real_redis_roundtrip` requires `REDIS_URL` and only checks create/get/delete. A lifetime change needs assertions of actual expiry semantics and browser Max-Age in addition to running this file.

`test_auth_domains.py` does contain public-to-admin 401, forged public token in `admin_session_id` 401, and admin-to-public `/auth/me` 401 assertions. It hard-codes `session_id` when extracting the forged token, so a Cookie rename requires updating this test consumer too. The docs led to the relevant file but did not enumerate this hard-coded consumer.

## Case 2

Modification location succeeded: `api/health_router.py::ready` is decorated with `/readiness`, has no `/ready` alias, and returns a fixed `{"status": "ok"}` without dependency checks.

Correction to test initialization: `tests/test_health.py` does **not** instantiate a bare temporary FastAPI. It imports `create_app` from `backend.main`, calls it, then redundantly includes `health_router` again. `main.create_app` delegates to the production composition root. That root runs migrations, builds dependencies and seed users, and registers health routes. Thus the documentation and prior report incorrectly describe this as router-only initialization. However, the explicit extra `include_router` masks a missing production registration: the test cannot independently prove that composition root registered the probe. ASGITransport request coverage also does not prove a server/proxy or lifespan startup. The correct limitation is production construction with redundant registration and in-process requests, not no production construction.

Actual assertions confirm the stale `/ready` request followed by expected 200 and OK JSON, so the predicted mismatch is justified if app construction succeeds. This was not executed.

Impact/verification retrieval was incomplete. Additional current source consumers missed by the health map are:

- `api/middleware/prometheus_metrics.py::_EXCLUDED_PATHS` still contains `/ready`, not `/readiness`; the renamed endpoint will be recorded as business traffic when this middleware is enabled.
- `tests/test_metrics.py::test_middleware_ignores_excluded_paths` requests `/ready` and asserts no metric for that label. It uses bare FastAPI without health routes, so it tests exclusion even on an unregistered path, and does not check renamed probe exclusion.
- `tests/guards/test_openapi_schema.py::REQUIRED_PATHS` includes `/ready`; `test_openapi_schema_has_required_paths` checks the production factory OpenAPI and would detect the missing old path if construction succeeds. Any change to this guard must follow the repository's contract-change policy rather than simply weakening it.
- Root `README.md` and `README.zh.md` still advertise `/ready`.

The docs successfully identify the renamed handler and `tests/test_health.py`, but “sync callers and tests” is too generic to reveal these concrete middleware/OpenAPI/README impacts. `guides/probe-client.md` says clients use `/readiness` without identifying an actual deployed client configuration, so external migration remains unverified.

## Case 3

Modification location and current behavior retrieval succeeded: `api/health_router.py::ready` handles `/ready`, returns fixed OK, and contains no DB/Redis work or failure branch. Production factory registration and observability independence are confirmed by the unconditional router loop preceding the observability conditional. Legacy names are unnecessary for locating the active implementation.

The same test-initialization correction as case 2 applies: `tests/test_health.py::test_health_endpoints_return_ok` calls the production `backend.main.create_app`, then includes the health router a second time. Its real assertions check 200 and OK JSON for `/health`, `/ready`, `/live`. The docs find a useful verification entry, but misstate its setup and omit that the duplicate inclusion hides a production-registration regression. It does not assert DB/Redis success/failure behavior, observability enabled/disabled variants, deployment proxy behavior, or real lifespan execution. The doc's proposed curl checks remain a plan, not evidence.

Overall: all three cases gave usable implementation starting points. Case 1's lifetime verification description and cases 2/3's health-test characterization require correction; case 2's change-impact map omits concrete active consumers and a contract guard.
