# Task Plan: Fix nested frontend dependency installation for new worktrees

## Goal
Update the worktree bootstrap script so new worktrees install frontend dependencies for nested subprojects such as `demo-frontend` and `admin-frontend`, instead of only handling the repository root.

## Current Phase
Phase 4

## Phases

### Phase 1: Requirements & Discovery
- [x] Confirm user-reported failure mode
- [x] Identify the current installation entrypoint
- [x] Capture findings in findings.md
- **Status:** complete

### Phase 2: Implementation
- [x] Extend worktree frontend dependency discovery
- [x] Keep existing strategy toggles compatible
- [x] Update relevant documentation
- **Status:** complete

### Phase 3: Testing & Verification
- [x] Run targeted script checks
- [x] Run docs verification
- [x] Record outcomes in progress.md
- **Status:** complete

### Phase 4: Delivery
- [ ] Summarize behavior changes and caveats
- **Status:** in_progress

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Keep `install-per-worktree` as the default strategy | The current interface should remain backward compatible for repos without nested frontends. |
| Fix discovery inside `scripts/git_worktree.sh` rather than adding repo-specific hardcoding | The template must work for arbitrary downstream subproject names, not only `demo-frontend` and `admin-frontend`. |
| Keep `symlink-from-main` on the same discovery path as install mode | Root-level and nested frontend projects should follow the same project detection rules. |

## Errors Encountered
| Error | Resolution |
|-------|------------|
| Existing planning files described an older workflow task | Replaced them with task state for the current worktree dependency fix. |
| `uv run mkdocs build --strict` crashed under `PyYAML` C bindings, then failed again in `griffe` on Python 3.14.0a6 | Verified the script change with shell-level checks and documented the environment incompatibility as a separate repo issue. |
| `uv run pytest ...` exited with code 139 in the current Python 3.14.0a6 environment | Kept verification focused on bash syntax and a targeted shell harness for the changed worktree logic. |

## Completion Summary
- **Status:** In progress (awaiting user delivery)
- **Tests:** Passed (`bash -n scripts/git_worktree.sh`, targeted shell harness for nested frontend installs and symlink reuse, `git diff --check`); blocked by environment (`UV_CACHE_DIR=/tmp/uv-cache uv run mkdocs build --strict`, `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/ -v --ignore=tests/test_model_loader_real.py -m "not expensive"`)
- **Deliverables:** `scripts/git_worktree.sh`, `docs/getting-started.md`, `docs/guides/configuration.md`, `docs/prototypes/worktree-frontend-demo.html`
- **Notes:** Worktree bootstrap now handles nested frontend projects, but full repo verification is limited by Python 3.14 alpha compatibility issues in the current virtual environment.
