# VPS + Traefik Deployment

This directory is an optional deployment path for template-derived projects.
Dokploy remains the default production path documented in `docs/guides/deployment.md`.

Use this package when you manage a plain Ubuntu/Debian VPS yourself and want:

- Docker Engine and Compose installed on the host.
- A host-level Traefik gateway on an external Docker network.
- A private project network for the backend and frontend-to-backend traffic.
- An application directory such as `/opt/apps/zata-codes-template`.
- GitHub Actions or local SSH deploys that update immutable image tags.

> **Where did the shell scripts go?** `install-docker-traefik.sh`,
> `bootstrap.sh`, and `fix-acme-email.sh` moved into the standalone
> [`zata-ops`](../../../zata-ops/README.md) CLI. Install it once
> (`uv tool install --force /path/to/zata-ops`) and use
> `zata-ops env provision` / `zata-ops env fix`. Pass `--dry-run` first to
> see the exact remote commands before they run.

## Files

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Production app compose file with a private backend network and Traefik API limits. |
| `.env.example` | Deployment metadata template: domain, network, image references. |
| `app.env.example` | Runtime configuration and secrets template. |
| `github-actions-deploy.yml.example` | Optional workflow example for build-push-SSH deployment. |

## First Server Setup

```bash
zata-ops env provision \
    --host 1.2.3.4 \
    --user root \
    --acme-email you@your-domain.com \
    --traefik-network traefik \
    --dry-run
```

Drop `--dry-run` to actually SSH into the host and run the bundled
`install-docker-traefik.sh` template. The installer is idempotent — it creates
the external Docker network named `traefik` by default and starts Traefik with
the `letsencrypt` resolver when a real `ACME_EMAIL` is provided.

If the server already has Traefik but browsers show Traefik's default
certificate:

```bash
zata-ops env fix --host 1.2.3.4 --user root --email you@your-domain.com
```

## App Directory

Copy `docker-compose.yml`, `.env.example`, and `app.env.example` into
`/opt/apps/<slug>/` on the server, rename the `.example` files, fill in the
values, then `docker compose up -d`. The compose file references images via
`${BACKEND_IMAGE}` / `${FRONTEND_IMAGE}`; the GitHub Actions example rewrites
those on every release.

Only the frontend containers join the shared Traefik network. Backend traffic
uses the project-scoped `backend-app` network, and the backend has no published
host port. The Compose file enables Uvicorn proxy headers because only the
frontends can reach the backend there; do not attach unrelated containers to
that private network. Configure CDN/WAF trusted forwarding and origin firewall
rules on the host/provider as described in the repository's security guide.

The `/api/` routers have per-source rate limits, in-flight request caps, and a
1 MiB body limit. Tune those at the edge with the `*_API_*` values in `.env`;
keep `TRAEFIK_CLIENT_IP_DEPTH=0` for direct clients. If a CDN/load balancer is
in front, first configure Traefik to trust only that provider's forwarding
addresses, then set the depth for the sanitized `X-Forwarded-For` chain.
Application-side API and login limits are configured separately in `app.env`.

`app.env` no longer contains S3 / backup variables — backup-related settings
live alongside `zata-ops` (typically in the same project's `.env.local`).

## Optional GitHub Actions Deployment

The template repository's default `.github/workflows/cd.yml` builds a release
archive. It does not deploy a server.

To enable this optional VPS path in a derived project:

```bash
cp deploy/vps-traefik/github-actions-deploy.yml.example \
  .github/workflows/deploy-vps-traefik.yml
```

Configure repository secrets:

```text
REGISTRY_HOST
REGISTRY_NAMESPACE
REGISTRY_USERNAME
REGISTRY_PASSWORD
```

Configure the `production` environment secrets:

```text
SERVER_HOST
SERVER_USER
SERVER_SSH_KEY
SERVER_KNOWN_HOSTS
# SERVER_PORT (optional; default 22)
```

To use Nacos runtime configuration, set `NACOS_SERVER_ADDR`, `NACOS_USERNAME`,
and `NACOS_PASSWORD` in the server's `app.env` file. The backend image already
includes the Nacos SDK. Namespace, Group, and Data ID use the defaults in
`config.toml` unless you need to customize them.

Use a project-specific deployment user and key, such as `<slug>-deploy`. Verify
the host key through an existing trusted channel before setting
`SERVER_KNOWN_HOSTS`. Production deployments are serialized across Git refs.
Docker group membership grants privileges close to root. This Compose example
does not implement background-task draining or automatic rollback; see the
[deployment guide](../../docs/guides/deployment.md).

Optional `production` environment variables:

```text
PRODUCTION_DOMAIN
PRODUCTION_APP_DIR
```

The workflow builds backend and frontend images tagged by commit SHA, updates
image references in `/opt/apps/<slug>/.env`, and runs
`docker compose pull && docker compose up -d --remove-orphans`. Backup images
are no longer built by template CD; install `zata-ops` on the deploy host (or
in a sidecar CI workflow) for scheduled backups.
