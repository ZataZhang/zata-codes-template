---
name: cicd-github-actions-dokploy
description: "[Updated 2026-03-04] Maintain and evolve the repository CI/CD system implemented with GitHub Actions and Dokploy. Use when updating or debugging `.github/workflows/ci.yml` or `.github/workflows/cd.yml`, including trigger/concurrency changes, build matrix updates, immutable SHA image tagging, Dokploy compose env updates, staging/production deployment hooks, rollback flows, and CI/CD documentation synchronization."
---

# CI/CD GitHub Actions Dokploy

## Overview

Apply safe and minimal changes to the monorepo CI/CD pipeline.
Preserve immutable image rollout and production rollback reliability while evolving checks and deploy logic.

## Workflow

1. Read [references/cicd-pipeline-map.md](references/cicd-pipeline-map.md) to understand current topology, image contract, and secrets.
2. Classify the requested change as one of: CI checks, build/push logic, staging deploy, production deploy, or rollback.
3. Edit only the necessary workflow sections and keep existing gates (`needs`, `environment`, `if`) intact unless the request explicitly changes them.
4. Verify syntax and project-level documentation requirements before finishing.

## Implementation Rules

- Keep deploy artifacts and image tags immutable by commit SHA.
- Keep production deployment gated by the `production` environment.
- Keep staging deployment ahead of production deployment for `push` on `main`.
- Keep rollback execution isolated to `workflow_dispatch` with non-empty `rollback_tag`.
- Preserve docs-site fallback behavior when a docs image for a SHA/tag does not exist.
- Preserve retry behavior for image build/push failures unless explicitly requested otherwise.
- Preserve CRLF trimming and secret normalization around Dokploy hook and compose ID parsing.

## Common Change Tasks

### Update CI checks

- Edit `.github/workflows/ci.yml` jobs (`backend`, `demo_frontend`, `admin_frontend`) with minimal scope.
- Keep PR trigger target (`main`) unless branch strategy changes are requested.
- Keep failure log artifact upload paths aligned with working directories.

### Add or remove deployable services

- Update CD matrix entries in `build_and_push`.
- Update compose env upsert keys in `deploy_staging`, `deploy_production`, and `rollback_production`.
- Keep image naming consistent across all jobs (`SERVICE_NAME`, `*_IMAGE` keys, metadata artifacts).

### Adjust Dokploy deployment behavior

- Update `compose.one` read and `compose.update` write payload logic consistently in staging/production/rollback paths.
- Keep API base URL resolution from deploy hook as fallback for custom Dokploy endpoints.
- Keep failure messages actionable for missing secrets and unresolved compose IDs.

### Adjust rollback behavior

- Validate required rollback images with `docker manifest inspect` before writing compose env values.
- Keep rollback health-check verification and summary output.

## Validation Checklist

Run relevant checks after edits:

- `uv run pre-commit run check-yaml --files .github/workflows/ci.yml .github/workflows/cd.yml`
- `uv run mkdocs build`
- `just lint` and `just test` when pipeline contract or backend quality commands are changed

## Deliverable Format

When reporting completion:

- List modified workflow and docs files.
- Explain behavioral change in CI/CD flow.
- List added/removed secret or variable requirements.
- Note what was validated locally and what remains for GitHub runtime validation.

## References

- [references/cicd-pipeline-map.md](references/cicd-pipeline-map.md)
