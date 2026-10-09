# Zata Codes Template

English | [简体中文](README.zh.md)

<p align="center">
  <img src="skills/zata-writer/assets/brand/zata-signature-blue-z-black-ata.png" width="180" alt="Zata signature brand logo">
</p>

An extensible starter for Python web projects. It combines a **FastAPI modular monolith with four backend layers** and separate admin and public frontends. The template includes working authentication, database migrations, run-trace diagnostics, and optional sandbox infrastructure; downstream projects add their own business domain.

## Features

- **Clear backend boundaries:** API, core orchestration, pluggable capabilities, and infrastructure are separated, with dependencies pointing inward.
- **Two frontends:** the admin app uses Vite, React, and TanStack Router; the public app uses Next.js 16, React 19, and Tailwind CSS 4.
- **Authentication and sessions:** public registration and login, a separate admin authentication domain, HTTP-only cookie sessions, and Redis-backed session storage.
- **Optional runtime capabilities:** run-trace inspection, health probes, Prometheus metrics, and filesystem, Docker, and E2B sandbox adapters.
- **Development workflow:** Python dependencies managed with `uv`, common tasks run with `just`, plus Alembic migrations, pre-commit hooks, tests, and a MkDocs documentation site.
- **No model-vendor lock-in:** the template does not include an LLM client or provider registry. Downstream projects can load an OpenAI-compatible endpoint configuration and choose their own SDK.

## Architecture

```text
Frontends
├── frontend-admin/       Admin app (Vite + React)
└── frontend-public/      Public app (Next.js + React)

Backend
├── src/backend/api/                 HTTP entry points and validation
├── src/backend/core/                Use cases, domain rules, and interfaces
├── src/backend/engines/             Pluggable platform capabilities
├── src/backend/infrastructure/      Database, configuration, logging, and adapters
└── src/backend/composition/         Application startup and dependency wiring
```

Backend dependencies follow `api → core → engines → infrastructure`. `composition/` wires implementations together and contains no business rules. `engines/` is an extension point for capabilities added by downstream projects.

## Quick Start

### Requirements

- Python `>=3.11` (the repository development version is Python 3.13) and [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)
- Node.js 22 and pnpm 11 (required to run the frontends)
- Docker Compose (to start the local PostgreSQL and Redis services shown below)

### Install and Run

```bash
cp .env.example .env.local
docker compose -f docker-compose.testing.yml up -d postgres redis
```

Set the local database and Redis connection strings in `.env.local`:

```dotenv
DATABASE_URL=postgresql+psycopg2://testuser:testpass@localhost:5432/testdb
REDIS_URL=redis://:redis123@localhost:6379/0
```

Install dependencies, then start the backend and both frontends:

```bash
just sync dev
just run
```

On the first run, `just run` installs frontend dependencies and prints the service URLs. The backend applies database migrations at startup. To sign in to the admin app, set `AUTH_ADMIN_BOOTSTRAP_USERNAME` and `AUTH_ADMIN_BOOTSTRAP_PASSWORD` in `.env.local`. Do not commit real credentials.

## Common Commands

| Command | Purpose |
| --- | --- |
| `just` | List available tasks |
| `just sync dev` | Sync development dependencies and install pre-commit hooks |
| `just run` | Start the backend and both frontends |
| `just run backend` | Start only the backend |
| `just run frontend` | Start only the admin app |
| `just run frontend-public` | Start only the public app |
| `just down` | Stop local services |
| `just test` | Run the local test suite |
| `just test all` | Run the full test suite |
| `just docs-serve` | Preview the documentation site locally |

## Engineering Workflow

### PRD Skill

The repository's [PRD skill](skills/prd/SKILL.md) turns a feature request into an architecture-aware, reviewable implementation plan. It first inspects the existing code, extension points, related PRDs, and frontend surfaces, then favors reuse and the smallest complete change. Each PRD has two reading levels:

- **Part A · Review Layer** explains the problem, expected user outcomes, and the decisions that need human confirmation, without implementation details.
- **Part B · Build Layer** records architecture fit, implementation guidance, dependencies, and a realistic validation plan with evidence requirements.

The PRD workflow has four main stages:

1. **Interpret and inspect:** turn the request into concrete behavior examples, identify assumptions and exclusions, then inspect the architecture, reusable paths, frontend apps, tests, and related pending or archived PRDs.
2. **Challenge the plan:** ask only about unresolved decisions that materially affect scope or behavior; compare reuse options, remove unnecessary scope, and classify meaningful change points by risk (`R0`–`R3`).
3. **Write two audiences into one plan:** Part A gives people the outcome, human decisions, and acceptance view. Part B gives the executor the architecture fit, change impact, dependencies, and realistic validation plan. Risk determines the evidence depth; user-visible changes include real-entry visual evidence.
4. **Execute and close the evidence loop:** claim a pending PRD with `just prd start <prd-file>` before implementation. `just ai implement <prd-file>` runs the implementation and evidence workflow, including an independent verifier. Move the PRD to `tasks/archive/` after executor work is verified and reconciled. Human acceptance is tracked separately: open `Human-Confirmed` items remain marked `🧍 Awaiting human acceptance` until a person reviews them.

See the [PRD skill](skills/prd/SKILL.md), [tooling standards](docs/ai-standards/tooling.md), and [testing standards](docs/ai-standards/testing.md) for the complete contracts.

### Justfile Design

The command line uses two `just` layers so template-wide tooling can be synchronized without overwriting project-specific entry points:

- [`justfile`](justfile) is the private adapter for this repository. It imports `justfile.shared`, lists available tasks by default, and owns project-shaped commands such as `run`, `down`, and `copy`.
- [`justfile.shared`](justfile.shared) contains reusable template recipes such as `sync`, `lint`, `test`, `worktree`, `prd`, and `e2e`. `just sync-template` updates this shared layer; keep repository-specific recipes in `justfile`.

The private layer enables duplicate recipe names so a repository can override a shared command without editing the upstream-owned file. `just run` coordinates the backend and both frontends. It stores per-worktree ports in the ignored `.env.run-state`, so `just down` can stop the right services and parallel worktrees avoid port collisions. `just copy <dir>` creates a derived project with its own database and ports. Quality commands support different scopes: `just lint` for staged changes, `just lint --full` for the full repository, `just lint --reuse` for reuse and architecture diagnostics, and `just lint --repo` for repository-level checks. On a cold `just test`, the shared recipe runs full lint, checks the migration graph when Alembic is available, and then runs the local pytest selection; successful local lint/test markers are bound to the current branch, commit, and effective file tree. CI always runs the checks instead of trusting those local markers. The [tooling standards](docs/ai-standards/tooling.md) explain the ownership and override rules.

### Tests and Validation

Validation combines behavior tests with checks of repository contracts and real application paths:

- **Python:** `tests/` contains unit and integration tests; `tests/guards/` protects repository conventions and shared tooling contracts. The default `just test` run excludes `slow`, `real_api`, and `redis` tests; `just test all` includes the complete pytest suite, and `just test real` opts into tests requiring live APIs.
- **Frontend:** `frontend-admin/` has Vitest tests (`cd frontend-admin && pnpm test`). Both frontends also expose lint, type-check, and build commands; `frontend-public/` currently has no standalone test script.
- **End to end:** `tests/playwright-e2e/` is a separate TypeScript/Node package. `just e2e no-auth` runs the credential-free flow; `just e2e` runs the broader suite when its seed credentials are configured.
- **Database compatibility:** PostgreSQL and MySQL are supported targets. Database and migration changes need validation against the affected dialects, not SQLite alone.

Tests that write to a real database use the explicit `realdb` marker and cleanup/sentinel protections. For UI evidence, distinguish a component preview from production composition and a real user flow; screenshots must state which level they prove. Choose the highest-fidelity validation that fits the change: unit and integration tests for logic and module boundaries, a real API/CLI/startup path for executable behavior, and Playwright for user-visible flows. Live services are opt-in when credentials or external systems are required. See the [testing standards](docs/ai-standards/testing.md) and [E2E guide](docs/guides/e2e.md).

## Create a Project from the Template

From the template repository, run:

```bash
just copy my-app
```

This creates `my-app/` in the parent directory, applies the project name, initializes Git, and creates an initial commit. Before running it, make sure the local database is configured and your Git username and email are set. Then enter the new directory:

```bash
cd ../my-app
just sync dev
just run
```

## Configuration and Extension

- Keep non-sensitive defaults in `config.toml`; put local environment variables and secrets in `.env.local`.
- To use an LLM, set `MODEL_BASE_URL`, `MODEL_API_KEY`, and `MODEL_NAME` in `.env.local`. Set all three together; the template does not create the model client.
- Sandbox configuration is optional. The available adapters are filesystem-only, isolated Docker containers, and E2B sandboxes.
- The application exposes `/health`, `/ready`, and `/live` health probes by default. `/metrics` is available when metrics are enabled.

## Documentation

- [Getting Started](docs/getting-started.md)
- [PRD Skill Guide](docs/guides/prd-skill.md)
- [Configuration](docs/guides/configuration.md)
- [System Architecture](docs/architecture/system-design.md)
- [Sandbox Runtime](docs/guides/sandbox-runtime.md)
- [Observability](docs/guides/observability.md)
- [Deployment](docs/guides/deployment.md)
- [Documentation Index](docs/index.md)

## Main Directories

```text
src/backend/             FastAPI backend
frontend-admin/          Admin app
frontend-public/         Public app
alembic/                 Database migrations
tests/                   Python tests
tests/playwright-e2e/    Standalone Playwright end-to-end test package
docs/                    MkDocs documentation
deploy/                  Sandbox and deployment assets
```
