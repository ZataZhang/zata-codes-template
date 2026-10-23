# Blind grading

Read only blind A/B case directories, tasks, diffs, deliveries and relevant source/tests; no skill or mapping consulted. Static source review only; no product tests or dependency installation. Scores measure delivered evidence and utility, not prose length. Missing MkDocs is a disclosed limitation, not a false pass.

| Output | Scope /20 | Investigation /20 | Accuracy, traceability, actionability /20 | References, navigation /15 | Verification honesty, usability /15 | Lightweight portability /10 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| A case 1 | 20 | 18 | 16 | 15 | 11 | 10 | 90 |
| A case 2 | 20 | 18 | 17 | 14 | 12 | 10 | 91 |
| A case 3 | 20 | 18 | 17 | 15 | 12 | 10 | 92 |
| B case 1 | 20 | 18 | 18 | 15 | 12 | 10 | 93 |
| B case 2 | 20 | 18 | 19 | 15 | 13 | 10 | 95 |
| B case 3 | 20 | 17 | 17 | 15 | 11 | 10 | 90 |

Mean: A **91.00**, B **92.67**. Small descriptive difference, not a statistically established superiority claim.

## A case 1

Correctly reuses the existing architecture page and existing MkDocs navigation. Added map follows frontend → router → shared AuthService → injected per-domain repositories/session stores; app_factory really registers both routers and auth_wiring really uses separate ORM classes and Redis prefixes. Cookie names, fixed 60-day max_age, secure=False, 15/60 AuthSettings defaults, no rememberMe API effect, renewal-before-account-check and possible reuse after re-enabling match source. No wrong main path or invented product-test pass.

Deductions:
- Investigation −2 and accuracy −2: map says test_redis_session_store.py checks renewal and absolute cutoff. Actual test_slide_expiration_returns_record only checks non-None/user_id; file has no controlled clock, expiry-boundary or absolute-cutoff assertion. This is overstated existing coverage, not evidence of an executed pass.
- Accuracy −2: integration leaves ambiguous older claims beside the new precise map: §7 still calls disabling “即时失效其会话” although retained Redis records can become usable after re-enable; §3.1 still says HttpOnly “防 XSS”, which overstates protection (it prevents script reading that Cookie). New appended text improves semantics but does not reconcile the whole reused authoritative page.
- Verification −4: the expiry-test coverage overstatement materially weakens the suggested validation; direct pytest plan does not identify the realdb marker/fixture conditions as B does. E2E README reference and disclosure of unexecuted tests are good. Static path/whitespace checks and failed build disclosed; rendered links/anchors not established.

## A case 2

All direct old URL references in the affected guides are replaced; function name ready is correctly retained; app_factory registers health_router unconditionally before observability conditional middleware. No dependency checks or old alias exist. Correctly discovers stale tests still request /ready and anticipates failure without claiming to run them.

Deductions:
- Investigation −2, accuracy −3, verification −3: health.md says the current test “只把 router 注册到临时 FastAPI” and cannot replace production composition-root verification. Actual tests/test_health.py imports backend.main.create_app and calls app = create_app(), then redundantly includes health_router. src/backend/main.py delegates to composition/app_factory.py. The duplicate include can mask missing production registration, and ASGITransport does not establish deployed startup/proxy behavior, but the test is not an isolated temporary FastAPI/router-only test. Claimed limitation should describe that precise setup.
- References/navigation −1: changed existing feature nav title, but does not add the directly affected probe-client guide to site navigation. Existing in-content link does make it reachable, so this is a small discoverability loss, not an invalid navigation result.

## A case 3

Correct production path, fixed three responses, no DB/Redis/503 branch, proper observability distinction. Existing erroneous legacy module/function/test guidance is replaced. Index and existing navigation remain useful; no code changes. /ready correctly remains this case's URL.

Deductions:
- Investigation −2, accuracy −3, verification −3: same false “temporary FastAPI/router contract only” test setup characterization as A case 2. Actual test constructs the production app via backend.main.create_app and then redundantly registers the router. All three JSON assertions are correctly described here. This does not invalidate the production behavior documented, but misleads maintainers about current test fidelity and where a new regression test is needed.

## B case 1

Good reuse of existing page/navigation, source paths and change-oriented route table. Accurately documents admin beforeLoad /me recovery, seven-day UI cookie cache, response fields, password strip asymmetry, fixed Cookie attributes, separate session namespaces and non-permanent disable semantics. Existing §7 disable wording and HttpOnly overstatement are also repaired. Defaults still correctly match source.

Deductions:
- Investigation −2 and accuracy −2: test_redis_session_store.py is said to verify session windows and absolute maximum. It does not test those boundaries; only round-trip, non-None renewal, unknown token, namespace isolation and optional real Redis round-trip are asserted.
- Verification −3: that test-coverage overstatement gives false assurance for a sensitive expiry change. Source-path checks and explicit realdb/environment caveats otherwise help; no executed test pass is invented, and failed strict build is honestly reported.

## B case 2

Minimal effective incremental update. All affected doc URL references updated, existing generic feature index remains valid (it contained no renamed URL), and probe-client is added to navigation. Correct fixed responses, dependency limitations and no alias. Real HTTP verification is concrete, including old-path 404; no false passing claim.

Deductions:
- Investigation −2 and verification −2: misses that existing tests/test_health.py still requests /ready and will need follow-up when this source patch lands. User required docs-only, so leaving test code intact is correct; identifying its known mismatch would make verification guidance materially better.
- Accuracy/actionability −1: no executable curl or automated test command in the new probe guide, only a clear manual request procedure. Usable but less immediately repeatable than a copyable command. No penalty for leaving generic feature-index wording unchanged or not expanding into a full feature rewrite.

## B case 3

Correctly fixes obsolete production entry, nonexistent legacy references and invented dependency behavior, and handles index without gratuitous nav change. Actual three endpoint contract and no-auth/state boundaries match source.

Deductions:
- Investigation −3, accuracy −3 and verification −4: explicitly says /live only has HTTP-status assertion; actual tests/test_health.py ends with assert live_response.json() == {"status": "ok"}. DELIVERY repeats the incorrect reading. Also says explicit router registration means the test cannot independently establish production assembly, which is a reasonable masking caveat, but omits that app = create_app() already invokes the actual production composition root. This omission is less false than A's isolated-FastAPI wording, yet combined with wrong assertion detail leaves a materially inaccurate test map. No claim that tests actually passed.

## Verification and uncertainty

All outputs disclose missing MkDocs and unexecuted product tests/HTTP. Deliveries report static checks; this review corroborated relevant source/contracts but did not rerun their complete link-check algorithms or render pages. No unsupported product-test passing claim was found. Changed-files/diffs stay within docs/navigation. Sources prove registration/configured behavior, not actual deployment Cookie override, external client migration, production connectivity or full startup readiness; the documents generally preserve those boundaries.

Timing is only self-reported and excludes differing follow-up work: A initial case intervals 65/32/32 seconds; B 48/38/28 seconds. These are not comparable complete end-to-end measurements (deliveries explicitly mention extra checks/writing and A interleaving). Tokens unavailable. No efficiency conclusion is warranted from those timings.
