---
name: docker-grandmaster
description: Production-grade Dockerization guidance that infers a project's stack and runtime needs from file structure or snippets, then outputs a detective report, optimized multi-stage Dockerfile with comments, .dockerignore, docker-compose.yml with healthcheck/resources/restart policy, and stack-specific expert advice. Use when a user asks to containerize an app, generate Dockerfile/docker-compose/.dockerignore, or needs best-practice Docker deployment artifacts.
---

# Docker Grandmaster

## Overview
Generate production-grade Docker deliverables by inferring the tech stack, entrypoint, dependencies, and external services from project files or snippets. Produce outputs in a fixed order and enforce security, size, and build-cache best practices.

## Workflow
1) Infer the stack and runtime needs
- Scan the file tree and read key files to detect language, framework, build tool, and entrypoint.
- Identify dependency manifests and lockfiles, and infer install/build commands.
- Detect external services from config, environment variables, or library usage (databases, caches, queues).
- Ask for a file tree or key files when the entrypoint or stack is ambiguous.

2) Choose a build strategy
- Enforce a multi-stage build: builder stage for compilation/install, runtime stage for minimal execution.
- Prefer minimal base images (distroless or alpine) when compatible; fall back to slim images when required by native deps.
- Run as a non-root user in the final stage; create a dedicated user/group and set ownership.
- Order COPY steps to maximize layer caching: dependency files first, install/build, then source.

3) Produce deliverables in this exact order
- Detective report: summarize inferred stack, entrypoint, dependencies, and external services.
- Dockerfile: full multi-stage file with comments on every key instruction (base choice, caching, user, entrypoint).
- .dockerignore: include standard and stack-specific ignores.
- docker-compose.yml: define app service plus any inferred dependencies; include healthcheck, deploy.resources, and restart policy.
- Expert advice: stack-specific runtime tips (memory, logging, buffering, process model).

## Detection Checklist
- Language and framework: presence of files like `package.json`, `pyproject.toml`, `requirements.txt`, `go.mod`, `pom.xml`, `build.gradle`, `Cargo.toml`.
- Build tool and commands: lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `poetry.lock`) and scripts sections.
- Entrypoint: framework conventions (e.g., `app.py`, `main.py`, `server.js`, `cmd/`, `src/main/java`), or `Procfile` and config.
- External services: env vars and config (`DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`), or client libraries.

## Dockerfile Requirements
- Use multi-stage builds only.
- Use a minimal runtime image compatible with the stack.
- Create and use a non-root user in the final stage.
- Comment key lines to explain intent (cache layers, user, base selection, entrypoint).
- Prefer deterministic installs (lockfiles, frozen versions) and clean build artifacts.

## docker-compose.yml Requirements
- Include `healthcheck` for the app service.
- Include `deploy.resources` limits and reservations.
- Set a `restart` policy.
- Add dependent services when inferred (database/cache/queue) and connect them via networks/volumes.
- Use explicit ports, environment variables, and volumes only when required by the stack.

## .dockerignore Baseline
- Always ignore: `.git`, `node_modules`, `.venv`, `venv`, `dist`, `build`, `target`, `__pycache__`, `*.pyc`, `.pytest_cache`, `.mypy_cache`, `.idea`, `.vscode`, `.DS_Store`.
- Add stack-specific entries as needed (e.g., `coverage/`, `.next/`, `vendor/`).

## Expert Advice Patterns
- Node.js: use `NODE_ENV=production`, prefer `npm ci`, avoid dev dependencies in runtime.
- Python: set `PYTHONUNBUFFERED=1`, disable bytecode, and keep pip cache off.
- Java: set `-XX:MaxRAMPercentage` and tune heap for containers.
- Go/Rust: prefer static builds when possible and slim runtime images.
- Ask for clarification when entrypoint or service dependencies are ambiguous.
