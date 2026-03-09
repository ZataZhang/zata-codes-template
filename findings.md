# Findings & Decisions

## Requirements
- User wants the copied `.github` folder adapted into a reusable workflow template for this repository.
- Changes should stay inside the project template context and avoid app-specific deployment assumptions.

## Research Findings
- `.github/workflows/ci.yml` currently references `demo-frontend`, `admin-frontend`, `docs/Dockerfile`, and `just lint`, none of which match this repo.
- `.github/workflows/cd.yml` is a Dokploy/private-registry deployment pipeline copied from another project.
- The repo is a Python template using `uv`, `just`, `pre-commit`, `pytest`, MkDocs, and `scripts/release.py`.
- `git status` shows `.github/` is currently untracked, so replacing these workflows is safe relative to committed history.

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Keep CI focused on code quality, tests, docs, and release package verification | That is the stable reusable contract of this template. |
| Convert CD into tag-driven release automation instead of environment deployment | A template registry benefits from packaged releases more than repo-specific Dokploy deploys. |
| Prefer GitHub-native artifacts/releases over external registry dependencies | Makes the template reusable without private infrastructure. |
| Run docs with `mkdocs build --strict` in automation | The project instructions require docs verification without warnings. |
| Run checks with direct `uv run ...` commands instead of `just` wrappers | The existing `justfile` lacks a `lint` recipe and direct commands are clearer inside template workflows. |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| Existing workflows are from another application | Replace them completely with generic template workflows. |
| Local `pre-commit` hook bootstrap needs network access in this sandbox | Use a local YAML parse as the syntax verification fallback and keep the workflow itself configured for GitHub-hosted runners. |

## Resources
- `justfile`
- `.pre-commit-config.yaml`
- `mkdocs.yml`
- `scripts/release.py`
- `docs/guides/deployment.md`
