# Findings & Decisions

## Requirements
- User reports that only root-level Python dependencies are installed automatically in a fresh worktree.
- Nested frontend subprojects such as `demo-frontend` and `admin-frontend` keep their `package.json` files in subdirectories, so they currently miss `npm ci` during worktree bootstrap.
- The fix should make worktree creation usable in downstream repos without forcing repo-specific hardcoded directory names.

## Research Findings
- `scripts/git_worktree.sh` currently calls `install_frontend_dependencies` once after `cd "$target_abs_path"`.
- `install_frontend_dependencies` only checks lock files and `package.json` in the current directory.
- The script already contains nested frontend traversal logic for the `symlink-from-main` strategy via `setup_frontend_node_modules_symlinks`.
- The default strategy remains `install-per-worktree`, so nested install behavior must be fixed there as well.
- Existing repo docs do not explain how nested frontend packages are handled during worktree bootstrap.
- The prototype page under `docs/prototypes/worktree-frontend-demo.html` still described `install-per-worktree` as a failure path, so it needed to be aligned with the new behavior.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Add a frontend project discovery helper that walks subdirectories for `package.json` files | This keeps the script generic for arbitrary downstream app layouts. |
| Reuse lock-file-driven installation rules per discovered frontend directory | This preserves deterministic installs and existing package manager support. |
| Skip rootless duplicates and internal directories such as `.git` and `node_modules` | Avoids redundant installs and accidental traversal into dependency trees. |
| Update the worktree prototype copy to show `install-per-worktree` as slower-but-successful instead of broken | User-facing docs should match the implemented script behavior. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Planning files in the repo were still tracking an unrelated CI/CD task | Reset planning files to the current worktree dependency task before implementation. |
| Full docs/test verification in `.venv` is blocked by Python 3.14.0a6 compatibility issues (`PyYAML` C extension segfault and `griffe` import failure) | Recorded targeted shell verification for the changed code path and documented the environment problem. |

## Resources
- `scripts/git_worktree.sh`
- `justfile`
- `README.md`
- `docs/getting-started.md`
- `docs/guides/configuration.md`
- `docs/prototypes/worktree-frontend-demo.html`
- `tasks/20260312-180937-prd-worktree-frontend-deps.md`
