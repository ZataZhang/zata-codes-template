# Progress Log

## Session: 2026-03-09

### Current Status
- **Phase:** 2 - Planning & Structure
- **Started:** 2026-03-09

### Actions Taken
- Inspected `.github/workflows/ci.yml` and `.github/workflows/cd.yml`.
- Confirmed the copied workflows reference non-existent frontends, Dockerfiles, Dokploy hooks, and a private registry.
- Inspected `pyproject.toml`, `README.md`, `justfile`, and `.pre-commit-config.yaml` to determine the real automation surface of this repository.
- Initialized planning files and captured requirements/findings for the workflow rewrite.
- Confirmed the template’s stable automation contract is `uv sync`, `pre-commit`, local `pytest`, strict MkDocs build, and release zip generation.
- Identified a documentation gap in `docs/guides/deployment.md`, which still has a TODO for CI/CD and references a non-existent `just docs-build` command.
- Replaced the copied CI workflow with a generic template validation pipeline for PRs, `main`, and manual dispatch.
- Replaced the copied Dokploy CD workflow with a tag-driven GitHub Release pipeline that builds and uploads the template zip.
- Updated deployment docs to describe the new GitHub Actions template and the main knobs downstream repos should customize.

### Test Results
| Test | Expected | Actual | Status |
|------|----------|--------|--------|
| `UV_CACHE_DIR=/tmp/uv-cache uv sync --all-groups --frozen` | Dependencies resolve from lock file | Passed | ✅ |
| `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v --ignore=tests/test_model_loader_real.py -m "not expensive"` | Local CI test selection passes | 39 passed, 10 skipped, 2 deselected | ✅ |
| `UV_CACHE_DIR=/tmp/uv-cache uv run mkdocs build --strict` | Docs build without warnings promoted to errors | Passed | ✅ |
| `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/release.py` | Release zip builds successfully | Passed | ✅ |
| `yaml.safe_load()` for `.github/workflows/ci.yml` and `.github/workflows/cd.yml` | Workflow YAML parses cleanly | Passed | ✅ |

### Errors
| Error | Resolution |
|-------|------------|
| `uv` cache initialization failed under `~/.cache/uv` | Reran commands with `UV_CACHE_DIR=/tmp/uv-cache`. |
| `pre-commit` wrote to a read-only cache and then tried to fetch hook repos over the blocked network | Used `/tmp/pre-commit` for cache and replaced hook bootstrap validation with a local YAML parse. |
