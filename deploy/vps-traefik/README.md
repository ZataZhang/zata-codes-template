# VPS + Traefik Deployment

This directory is an optional deployment path for template-derived projects.
Dokploy remains the default production path documented in `docs/guides/deployment.md`.

Use this package when you manage a plain Ubuntu/Debian VPS yourself and want:

- Docker Engine and Compose installed on the host.
- A host-level Traefik gateway on an external Docker network.
- An application directory such as `/opt/apps/zata-codes-template`.
- GitHub Actions or local SSH deploys that update immutable image tags.

## Files

| File | Purpose |
| --- | --- |
| `install-docker-traefik.sh` | Installs Docker Engine, Compose plugin, and host-level Traefik. |
| `fix-acme-email.sh` | Repairs a Traefik install that used a placeholder Let's Encrypt email. |
| `bootstrap.sh` | Prepares deploy user, SSH key, app directory, compose file, and initial env files. |
| `docker-compose.yml` | Production app compose file behind the external Traefik network. |
| `.env.example` | Deployment metadata template: domain, network, image references. |
| `app.env.example` | Runtime configuration and secrets template. |
| `github-actions-deploy.yml.example` | Optional workflow example for build-push-SSH deployment. |

## First Server Setup

Run on the VPS as root or a sudo-capable user:

```bash
ACME_EMAIL=you@your-domain.com bash deploy/vps-traefik/install-docker-traefik.sh
```

The installer is idempotent. It creates the external Docker network named
`traefik` by default and starts Traefik with the `letsencrypt` resolver when a
real `ACME_EMAIL` is provided.

If the server already has Traefik but browsers show Traefik's default
certificate, repair the ACME email on the server:

```bash
sudo bash fix-acme-email.sh --email you@your-domain.com
```

## App Bootstrap

Run from your local machine:

```bash
./deploy/vps-traefik/bootstrap.sh --server 1.2.3.4 --domain app.example.com
```

For a template-derived project, `just copy <slug>` rewrites the default
`zata-codes-template` slug in these deployment files. You can still override it
manually:

```bash
./deploy/vps-traefik/bootstrap.sh \
  --app-slug my-app \
  --server 1.2.3.4 \
  --domain app.example.com
```

`bootstrap.sh` does not overwrite existing `.env` or `app.env` on the server.
After it completes, edit `/opt/apps/<slug>/app.env` and fill the database,
admin password hash, provider keys, and optional backup storage values.

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
```

Optional `production` environment variables:

```text
PRODUCTION_DOMAIN
PRODUCTION_APP_DIR
```

The workflow builds backend, frontend, and backup images tagged by commit SHA,
updates image references in `/opt/apps/<slug>/.env`, and runs
`docker compose pull && docker compose up -d --remove-orphans`.
