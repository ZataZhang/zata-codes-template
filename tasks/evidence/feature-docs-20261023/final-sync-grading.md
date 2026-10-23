# Final targeted sync grading

This is a targeted **nonblind supplementary case**, with a fresh executor and `/service-ready` variant. Reviewer had seen prior evaluations and parent-named downstream consumer findings. It is neither a replacement for the original paired experiment nor statistically validated evidence of improvement. Previous grading reports are unchanged.

| Scope /20 | Source investigation /20 | Accuracy, traceability, actionability /20 | Incremental references/navigation /15 | Verification honesty/usability /15 | Lightweight portability /10 | Total |
|---:|---:|---:|---:|---:|---:|---:|
| 20 | 20 | 20 | 15 | 14 | 10 | **99** |

## Source-supported findings

Task explicitly permits documentation including root READMEs and asks for unmodifiable code impacts. Output follows this scope: README.md and README.zh.md advertise `/service-ready` in their respective languages; feature map, feature index, probe-client and observability guides agree; existing probe-client page is made navigable in MkDocs. Search of current docs and root READMEs finds old `/ready` references only in migration, negative-request and pending-code explanations. Historical archived records need not be rewritten.

`changes.patch` and actual `src/backend/api/health_router.py` replace only the readiness decorator. Handler remains `ready`, three functions directly return fixed JSON, and no old alias or redirect is registered. Actual `src/backend/main.py` delegates to production composition; `app_factory.py` runs migrations, builds auth dependencies/seeds and unconditionally includes health_router without prefix before observability middleware setup. Source supports the distinction between fixed handler response and dependency readiness, plus probes remaining available with observability disabled. No incorrect production main path found.

Direct consumers are now accurately identified:

- `prometheus_metrics.py::_EXCLUDED_PATHS` retains `/ready`, omitting `/service-ready`; `_should_record` checks route/request path against it. Renamed readiness requests will therefore be recorded when metrics middleware is enabled. Guides and DELIVERY explicitly explain this and state that later exclusion validation cannot currently be expected to pass.
- `tests/test_health.py` uses actual `backend.main.create_app`, then redundantly registers health_router, sends requests via ASGITransport and asserts status plus JSON for all three endpoints. It still requests old `/ready`. The document does not claim standalone temporary app or missing `/live` JSON assertions; it identifies static incompatibility without inventing a run result.
- `tests/guards/test_openapi_schema.py::REQUIRED_PATHS` still requires `/ready`; actual schema derives from production factory. Current router conflicts with that requirement. Map reports the contract-change follow-up and cites guard policy rather than advising arbitrary relaxation.
- `tests/test_metrics.py::test_middleware_ignores_excluded_paths` really builds temporary FastAPI with metrics middleware/router, does not include health_router and checks exclusion of old paths. Map correctly says these assertions do not protect the renamed readiness endpoint or production mounting. It does not falsely assert this old metrics test must fail.

Change table routes maintainers to decorator/handler, app factory, metrics exclusion function and dependent tests. Commands are concrete, and the client guide includes status/body checks, old-path 404, OpenAPI membership, observability toggle and proxy provenance. DELIVERY places tests after consumer/test synchronization and explicitly distinguishes expected later behavior from currently unfixed metrics code. Documentation remains plain Markdown in existing structure; no validators, dependencies or executable code changes are introduced.

## Deduction and limitations

Verification/usability **−1**: executor's strict MkDocs build failed due to unavailable executable; rendered navigation/layout remains unconfirmed by executor. This is an honestly disclosed tooling limitation, not false success. DELIVERY also distinguishes static source findings from tests, HTTP requests and fixture behavior that were not executed/confirmed. No product-test passing credit is awarded. Guidelines consistency and relative-link/navigation/whitespace checks are self-reported actual checks; reviewer did not reproduce their full algorithms.

No critical factual error, unsupported executed passing claim, wrong main path or material unreported direct consumer was found in inspected output. No deduction is made for retaining source/test mismatches because the task expressly forbids those edits and the output reports them.

At review time parent-generated baseline diff/manifest had not yet arrived; scope initially rests on reported changed paths and inspected outputs. Reviewer did not install dependencies, start services or execute product tests. Deployment/client configuration, real external dependency health and proxy behavior remain unverified. Complete task duration and tokens are unavailable; no efficiency comparison is possible.

## Later artifact/provenance note

Parent supplied `changed-files.json` and `changes.diff`; inspected manifest lists exactly seven documentation/navigation files (four docs pages, mkdocs.yml, two READMEs), agreeing with declared scope. Parent reports supplementary strict build success. Parent also disclosed that artifact collection after executor freeze accidentally created a .venv and installed snapshot dependencies, then removed that environment and duplicate generated evidence; frozen docs remained unchanged. This is parent-only post-execution activity, not executor action or product testing. It does not make the executor's earlier missing-dependency report false and is not credited as executor validation. Score remains 99.
