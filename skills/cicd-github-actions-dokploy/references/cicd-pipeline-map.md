# CI/CD Pipeline Map

## Workflow files

- `.github/workflows/ci.yml`: Pull-request quality gate.
- `.github/workflows/cd.yml`: Build, push, deploy, and rollback pipeline.

## CI topology (`ci.yml`)

### Trigger

- `pull_request` on `main`.
- Concurrency group: `ci-${{ github.event.pull_request.number || github.ref }}`.

### Jobs

- `backend`: `uv sync --all-groups`, `just lint`, `just test`, `uv run mkdocs build`.
- `demo_frontend`: `npm ci` + `npm run build` in `demo-frontend/`.
- `admin_frontend`: `npm ci` + `npm run build` in `admin-frontend/`.

### Failure diagnostics

- Upload per-job logs as artifacts only on failure.

## CD topology (`cd.yml`)

### Triggers

- `push` on `main`: build images, deploy staging, then deploy production.
- `workflow_dispatch`:
  - Empty `rollback_tag`: run build and deploy flow.
  - Non-empty `rollback_tag`: run rollback-only flow.

### Global env

- `REGISTRY_HOST=registry.zata.cafe`
- `IMAGE_NAMESPACE=${{ vars.IMAGE_NAMESPACE || 'aibot' }}`

### Jobs and dependencies

1. `build_and_push`
2. `deploy_staging` (needs `build_and_push`, only on `push`)
3. `deploy_production` (needs `deploy_staging`, only on `push`, environment `production`)
4. `rollback_production` (only on dispatch with `rollback_tag`)

### Image matrix

- `ai-service` from `ai_service/Dockerfile`
- `demo-backend` from `demo-backend/Dockerfile`
- `demo-frontend` from `demo-frontend/Dockerfile`
- `admin-frontend` from `admin-frontend/Dockerfile`
- `docs-site` from `docs/Dockerfile`

### Tagging contract

- Immutable tag only: `${GITHUB_SHA}`.
- Persist image metadata in `image-tag-<service>.env` artifacts.
- Persist deployment metadata in `deployment-metadata-${{ github.sha }}` artifact.

### Dokploy update pattern

- Resolve compose ID from secret override first, then parse from deploy hook URL.
- Resolve API base from hook URL first, then fallback to `DOKPLOY_API_BASE_URL`.
- Read compose env from `compose.one`.
- Upsert `*_IMAGE` keys in env block.
- Write env back with `compose.update`.
- Trigger deploy via deploy hook.

### Docs image fallback

- If docs image for target SHA/tag is missing, keep current `DOCS_SITE_IMAGE` value.
- Fail if no current docs value is present.

## Secrets and variables

### Repository variable

- `IMAGE_NAMESPACE` (optional).

### Shared secrets

- `REGISTRY_USERNAME`
- `REGISTRY_PASSWORD`
- `DOKPLOY_API_KEY`
- `DOKPLOY_API_BASE_URL` (optional when derivable from hook)

### Staging secrets

- `DOKPLOY_STAGING_DEPLOY_HOOK`
- `DOKPLOY_STAGING_COMPOSE_ID` (optional override)

### Production secrets

- `DOKPLOY_PROD_DEPLOY_HOOK`
- `DOKPLOY_PROD_COMPOSE_ID` (optional override)
- `PROD_HEALTHCHECK_URL`

## Safe edit checklist

- Keep `needs` chain (`build_and_push` -> `deploy_staging` -> `deploy_production`).
- Keep environment gate for production jobs.
- Keep rollback path independent from push path.
- Keep docker login before manifest checks and Dokploy image updates.
- Keep health-check loop after production deploy and rollback.
- Keep failure logs or summaries for operational traceability.
