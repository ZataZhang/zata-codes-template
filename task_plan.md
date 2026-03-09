# Task Plan: Convert copied GitHub Actions into template workflows

## Goal
Replace the copied app-specific `.github/workflows` files with reusable CI/CD workflows that match this Python template registry.

## Current Phase
Phase 5

## Phases

### Phase 1: Requirements & Discovery
- [x] Understand user intent
- [x] Identify constraints
- [x] Document in findings.md
- **Status:** complete

### Phase 2: Planning & Structure
- [x] Define approach
- [x] Confirm workflow scope from repository capabilities
- **Status:** complete

### Phase 3: Implementation
- [x] Replace mismatched workflows
- [x] Keep workflows generic for downstream template users
- [x] Update docs to describe the template CI/CD contract
- **Status:** complete

### Phase 4: Testing & Verification
- [x] Validate workflow YAML
- [x] Run relevant repo checks where practical
- [x] Document test results
- **Status:** complete

### Phase 5: Delivery
- [x] Review outputs
- [ ] Deliver to user
- **Status:** in_progress

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Remove app-specific frontend and Dokploy logic | Those services and deployment targets do not exist in this repository. |
| Align CI with `uv`, `pre-commit`, `pytest`, `mkdocs`, and release packaging | These are the actual tools and scripts present in the template repo. |
| Keep release automation tag-driven and GitHub-native | Template consumers should not inherit private registry or Dokploy dependencies. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| `uv` and `pre-commit` defaulted to read-only cache directories in the sandbox | Reran validation with writable cache directories under `/tmp`. |
| `pre-commit` hook bootstrap required network access to GitHub | Validated workflow YAML with local `yaml.safe_load(...)` instead and documented the limitation. |

## Completion Summary
- **Status:** In progress (awaiting user delivery)
- **Tests:** Passed (`UV_CACHE_DIR=/tmp/uv-cache uv sync --all-groups --frozen`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v --ignore=tests/test_model_loader_real.py -m "not expensive"`, `UV_CACHE_DIR=/tmp/uv-cache uv run mkdocs build --strict`, `UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/release.py`, local YAML parse for `.github/workflows/*.yml`)
- **Deliverables:** `.github/workflows/ci.yml`, `.github/workflows/cd.yml`, `docs/guides/deployment.md`
- **Notes:** `pre-commit run check-yaml` could not complete in the sandbox because hook repositories are fetched from GitHub.
