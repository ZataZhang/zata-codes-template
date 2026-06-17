# ───────────────────────────────────────────────────────────────────────────────
# justfile — project-private recipes.
#
# Shared recipes live in `justfile.shared` and are kept in sync with the
# upstream template repository via `just sync-template`. Add project-specific
# commands below; same-name recipes here intentionally override shared ones.
# ───────────────────────────────────────────────────────────────────────────────

set allow-duplicate-recipes

import 'justfile.shared'

# Default recipe (runs when you type `just`)
default: _check-completion
    @just --list

# Run the development entrypoint
# Usage:
#   just run                        # start backend + admin frontend + public frontend
#   just run backend                # start backend only
#   just run frontend               # start admin frontend only
#   just run frontend-public        # start public frontend only
#   just run docker                 # start with Docker Compose (one-click deploy)
#   just run backend_port=8010 frontend_port=5178 frontend_public_port=3001
#   just run all frontend_public_cmd="pnpm dev"
run arg1="" arg2="" arg3="" arg4="" arg5="" arg6="" arg7="" arg8="" arg9="": _check-completion
    #!/usr/bin/env bash
    set -euo pipefail

    target="all"
    frontend_dir="frontend-admin"
    frontend_public_dir="frontend-public"
    backend_port=""
    frontend_port=""
    frontend_public_port=""
    backend_cmd="uv run python -m backend.main"
    frontend_cmd="pnpm dev"
    frontend_public_cmd="pnpm dev"
    backend_pid=""
    frontend_pid=""
    frontend_public_pid=""
    run_state_file="$(git rev-parse --git-path vanta-run.env)"
    positional_index=0

    parse_run_arg() {
        cli_arg="$1"
        if [ -z "$cli_arg" ]; then
            return 0
        fi

        case "$cli_arg" in
            target=*)
                target="${cli_arg#target=}"
                ;;
            frontend_dir=*)
                frontend_dir="${cli_arg#frontend_dir=}"
                ;;
            frontend_public_dir=*)
                frontend_public_dir="${cli_arg#frontend_public_dir=}"
                ;;
            backend_port=*)
                backend_port="${cli_arg#backend_port=}"
                ;;
            frontend_port=*)
                frontend_port="${cli_arg#frontend_port=}"
                ;;
            frontend_public_port=*)
                frontend_public_port="${cli_arg#frontend_public_port=}"
                ;;
            backend_cmd=*)
                backend_cmd="${cli_arg#backend_cmd=}"
                ;;
            frontend_cmd=*)
                frontend_cmd="${cli_arg#frontend_cmd=}"
                ;;
            frontend_public_cmd=*)
                frontend_public_cmd="${cli_arg#frontend_public_cmd=}"
                ;;
            *)
                case "$positional_index" in
                    0)
                        target="$cli_arg"
                        ;;
                    1)
                        frontend_dir="$cli_arg"
                        ;;
                    2)
                        backend_cmd="$cli_arg"
                        ;;
                    3)
                        frontend_cmd="$cli_arg"
                        ;;
                    *)
                        echo "ERROR: Unexpected run argument: $cli_arg"
                        echo "Usage: just run [backend|frontend|frontend-public|all|docker] [backend_port=<port>] [frontend_port=<port>] [frontend_public_port=<port>]"
                        exit 1
                        ;;
                esac
                positional_index=$((positional_index + 1))
                ;;
        esac
    }

    for cli_arg in {{quote(arg1)}} {{quote(arg2)}} {{quote(arg3)}} {{quote(arg4)}} {{quote(arg5)}} {{quote(arg6)}} {{quote(arg7)}} {{quote(arg8)}} {{quote(arg9)}}; do
        parse_run_arg "$cli_arg"
    done

    load_run_ports() {
        if [ -f "$run_state_file" ]; then
            # shellcheck disable=SC1090
            source "$run_state_file"
        fi

        backend_port="${backend_port:-${BACKEND_PORT:-8000}}"
        frontend_port="${frontend_port:-${FRONTEND_PORT:-5173}}"
        frontend_public_port="${frontend_public_port:-${FRONTEND_PUBLIC_PORT:-3000}}"
    }

    save_run_ports() {
        mkdir -p "$(dirname "$run_state_file")"
        {
            printf 'BACKEND_PORT=%s\n' "$backend_port"
            printf 'FRONTEND_PORT=%s\n' "$frontend_port"
            printf 'FRONTEND_PUBLIC_PORT=%s\n' "$frontend_public_port"
        } > "$run_state_file"
    }

    check_port() {
        port_label="$1"
        port_value="$2"
        # Use `ps -o comm=` to resolve the full (untruncated) command name;
        # lsof's COMMAND column is truncated to ~9 chars and would miss names
        # like `com.docker.proxy`.
        listening_pids="$(lsof -nP -iTCP:"$port_value" -sTCP:LISTEN -t 2>/dev/null || true)"
        [ -z "$listening_pids" ] && return 0

        conflict_details=()
        for port_pid in $listening_pids; do
            full_command_name="$(ps -p "$port_pid" -o comm= 2>/dev/null || echo "<exited>")"
            conflict_details+=("  - pid=$port_pid command=$full_command_name")
        done

        {
            echo ""
            echo "⚠️  $port_label port $port_value is already in use:"
            printf '%s\n' "${conflict_details[@]}"
            echo ""
            echo "   You can switch to a different port:"
            echo "      just run backend_port=8010 frontend_port=5178"
            echo ""
            echo "   Or stop the existing process:"
            echo "      just down backend_port=$backend_port frontend_port=$frontend_port"
            echo ""
            echo "   For Docker containers, use: just down docker"
            echo ""
        } >&2
        exit 1
    }

    run_backend() {
        check_port "Backend" "$backend_port"
        echo "Starting backend on port $backend_port: $backend_cmd"
        PORT="$backend_port" bash -lc "$backend_cmd"
    }

    run_frontend() {
        if [ ! -d "$frontend_dir" ]; then
            echo "ERROR: Admin frontend directory not found: $frontend_dir"
            echo "   Override it with: just run frontend frontend_dir=<path>"
            exit 1
        fi

        if [ ! -f "$frontend_dir/package.json" ]; then
            echo "ERROR: package.json not found in admin frontend directory: $frontend_dir"
            echo "   Override the directory or command, for example:"
            echo "   just run frontend frontend_dir=<path> frontend_cmd='pnpm dev'"
            exit 1
        fi

        check_port "Admin Frontend" "$frontend_port"
        echo "Starting admin frontend in $frontend_dir on port $frontend_port: $frontend_cmd"
        (
            cd "$frontend_dir"
            BACKEND_PORT="$backend_port" FRONTEND_PORT="$frontend_port" bash -lc "$frontend_cmd"
        )
    }

    run_frontend_public() {
        if [ ! -d "$frontend_public_dir" ]; then
            echo "ERROR: Public frontend directory not found: $frontend_public_dir"
            echo "   Override it with: just run frontend-public frontend_public_dir=<path>"
            exit 1
        fi

        if [ ! -f "$frontend_public_dir/package.json" ]; then
            echo "ERROR: package.json not found in public frontend directory: $frontend_public_dir"
            echo "   Override the directory or command, for example:"
            echo "   just run frontend-public frontend_public_dir=<path> frontend_public_cmd='pnpm dev'"
            exit 1
        fi

        check_port "Public Frontend" "$frontend_public_port"
        echo "Starting public frontend in $frontend_public_dir on port $frontend_public_port: $frontend_public_cmd"
        (
            cd "$frontend_public_dir"
            PORT="$frontend_public_port" BACKEND_PORT="$backend_port" bash -lc "$frontend_public_cmd"
        )
    }

    cleanup_processes() {
        for process_pid in "$backend_pid" "$frontend_pid" "$frontend_public_pid"; do
            if [ -n "$process_pid" ] && kill -0 "$process_pid" 2>/dev/null; then
                kill "$process_pid" 2>/dev/null || true
            fi
        done
        wait 2>/dev/null || true
    }

    wait_for_first_exit() {
        while true; do
            if [ -n "$backend_pid" ] && ! kill -0 "$backend_pid" 2>/dev/null; then
                wait "$backend_pid"
                return $?
            fi

            if [ -n "$frontend_pid" ] && ! kill -0 "$frontend_pid" 2>/dev/null; then
                wait "$frontend_pid"
                return $?
            fi

            if [ -n "$frontend_public_pid" ] && ! kill -0 "$frontend_public_pid" 2>/dev/null; then
                wait "$frontend_public_pid"
                return $?
            fi

            sleep 1
        done
    }

    load_run_ports
    save_run_ports
    echo "Saved run ports to $run_state_file"

    case "$target" in
        backend)
            run_backend
            ;;
        frontend)
            run_frontend
            ;;
        frontend-public)
            run_frontend_public
            ;;
        all)
            trap cleanup_processes EXIT INT TERM
            run_backend &
            backend_pid=$!
            run_frontend &
            frontend_pid=$!
            run_frontend_public &
            frontend_public_pid=$!
            wait_for_first_exit
            ;;
        docker)
            echo "Starting services with Docker Compose..."
            if [ ! -f ".env.local" ]; then
                echo ".env.local is required for 'just run docker'. Copy .env.example to"
                echo ".env.local and set your own service addresses (DATABASE_URL, S3_*, ...)."
                exit 1
            fi
            # Containers cannot reach the host via localhost/127.0.0.1; only the
            # backend-facing DATABASE_URL / S3_ENDPOINT need host.docker.internal.
            # Generate .env.local.docker from .env.local on first run, then keep
            # the generated file so users can tweak it manually without being overwritten.
            compose_env_file=".env.local.docker"
            if [ -f "$compose_env_file" ]; then
                echo "Using existing $compose_env_file (delete it to regenerate from .env.local)"
            else
                sed -E \
                    -e '/^(DATABASE_URL|S3_ENDPOINT)=/ s#(@|//)(localhost|127\.0\.0\.1)#\1host.docker.internal#g' \
                    .env.local > "$compose_env_file"
                echo "Generated $compose_env_file from .env.local (localhost -> host.docker.internal for DATABASE_URL/S3_ENDPOINT)"
            fi
            # Layer env like settings.py: load .env first, then .env.local.docker overrides it.
            env_file_args=()
            [ -f ".env" ] && env_file_args+=(--env-file .env)
            env_file_args+=(--env-file "$compose_env_file")
            COMPOSE_LOCAL_ENV_FILE="$compose_env_file" docker compose "${env_file_args[@]}" up --build
            ;;
        *)
            echo "ERROR: Unknown run target: $target"
            echo "Usage: just run [backend|frontend|frontend-public|all|docker]"
            exit 1
            ;;
    esac

# Stop local development services by remembered or provided ports.
# Usage:
#   just down
#   just down backend
#   just down frontend
#   just down frontend-public
#   just down backend_port=8010 frontend_port=5178 frontend_public_port=3001
#   just down docker
down arg1="" arg2="" arg3="" arg4="" arg5="": _check-completion
    #!/usr/bin/env bash
    set -euo pipefail

    target="all"
    backend_port=""
    frontend_port=""
    frontend_public_port=""
    run_state_file="$(git rev-parse --git-path vanta-run.env)"
    positional_index=0

    parse_down_arg() {
        cli_arg="$1"
        if [ -z "$cli_arg" ]; then
            return 0
        fi

        case "$cli_arg" in
            target=*)
                target="${cli_arg#target=}"
                ;;
            backend_port=*)
                backend_port="${cli_arg#backend_port=}"
                ;;
            frontend_port=*)
                frontend_port="${cli_arg#frontend_port=}"
                ;;
            frontend_public_port=*)
                frontend_public_port="${cli_arg#frontend_public_port=}"
                ;;
            *)
                if [ "$positional_index" -eq 0 ]; then
                    target="$cli_arg"
                    positional_index=1
                else
                    echo "ERROR: Unexpected down argument: $cli_arg"
                    echo "Usage: just down [backend|frontend|frontend-public|all|docker] [backend_port=<port>] [frontend_port=<port>] [frontend_public_port=<port>]"
                    exit 1
                fi
                ;;
        esac
    }

    for cli_arg in {{quote(arg1)}} {{quote(arg2)}} {{quote(arg3)}} {{quote(arg4)}} {{quote(arg5)}}; do
        parse_down_arg "$cli_arg"
    done

    load_run_ports() {
        if [ -f "$run_state_file" ]; then
            # shellcheck disable=SC1090
            source "$run_state_file"
        fi

        backend_port="${backend_port:-${BACKEND_PORT:-8000}}"
        frontend_port="${frontend_port:-${FRONTEND_PORT:-5173}}"
        frontend_public_port="${frontend_public_port:-${FRONTEND_PUBLIC_PORT:-3000}}"
    }

    # Filter Docker-related PIDs from a port's listener list. Uses `ps -o comm=`
    # to resolve the full (untruncated) command name; lsof's COMMAND column is
    # truncated to ~9 chars and would miss names like `com.docker.proxy`.
    filter_non_docker_pids() {
        port_value="$1"
        filtered_pids=""
        while read -r port_pid; do
            [ -n "$port_pid" ] || continue
            full_command_name="$(ps -p "$port_pid" -o comm= 2>/dev/null || true)"
            case "$full_command_name" in
                com.docker*|docker|vpnkit|hyperkit) ;;
                *) filtered_pids="$filtered_pids $port_pid" ;;
            esac
        done < <(lsof -nP -iTCP:"$port_value" -sTCP:LISTEN -t 2>/dev/null || true)
        echo "$filtered_pids" | tr ' ' '\n' | grep -v '^$' | sort -u
    }

    stop_port() {
        port_label="$1"
        port_value="$2"
        process_ids="$(filter_non_docker_pids "$port_value")"

        if [ -z "$process_ids" ]; then
            echo "No $port_label process listening on port $port_value (Docker processes skipped; use 'just down docker' for containers)"
            return 0
        fi

        echo "Stopping $port_label process(es) on port $port_value: $process_ids"
        kill $process_ids 2>/dev/null || true
        sleep 1

        remaining_process_ids="$(filter_non_docker_pids "$port_value")"
        if [ -n "$remaining_process_ids" ]; then
            echo "Force stopping $port_label process(es) on port $port_value: $remaining_process_ids"
            kill -9 $remaining_process_ids 2>/dev/null || true
        fi
    }

    load_run_ports

    case "$target" in
        backend)
            stop_port backend "$backend_port"
            ;;
        frontend)
            stop_port "admin frontend" "$frontend_port"
            ;;
        frontend-public)
            stop_port "public frontend" "$frontend_public_port"
            ;;
        all)
            stop_port backend "$backend_port"
            stop_port "admin frontend" "$frontend_port"
            stop_port "public frontend" "$frontend_public_port"
            ;;
        docker)
            docker compose down
            ;;
        *)
            echo "ERROR: Unknown down target: $target"
            echo "Usage: just down [backend|frontend|frontend-public|all|docker]"
            exit 1
            ;;
    esac


# ── Frontend ──────────────────────────────────────────────────────────────────

# Generate the "what's new" manifest for the admin frontend.
# Reads git history and writes frontend-admin/public/versions.json.
# Usage:
#   just whats-new-manifest
#   just whats-new-manifest --output frontend-public/public/versions.json
whats-new-manifest *args:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{justfile_directory()}}"
    uv run python scripts/build/build_whats_new_manifest.py {{args}}

# Frontend helper
# Usage:
#   just frontend dev
#   just frontend build
#   just frontend install
frontend action="dev":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{action}}" in
        dev)
            cd "{{justfile_directory()}}/frontend-admin"
            pnpm dev
            ;;
        build)
            just whats-new-manifest
            cd "{{justfile_directory()}}/frontend-admin"
            pnpm build
            ;;
        install)
            cd "{{justfile_directory()}}/frontend-admin"
            pnpm install
            ;;
        *)
            echo "ERROR: Unknown action: {{action}}"
            echo "Usage: just frontend [dev|build|install]"
            exit 1
            ;;
    esac


# Public frontend helper
# Usage:
#   just frontend-public dev
#   just frontend-public build
#   just frontend-public install
frontend-public action="dev":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{action}}" in
        dev)
            cd "{{justfile_directory()}}/frontend-public"
            pnpm dev
            ;;
        build)
            cd "{{justfile_directory()}}/frontend-public"
            pnpm build
            ;;
        install)
            cd "{{justfile_directory()}}/frontend-public"
            pnpm install
            ;;
        *)
            echo "ERROR: Unknown action: {{action}}"
            echo "Usage: just frontend-public [dev|build|install]"
            exit 1
            ;;
    esac


# ── Ops Toolkit (zata-ops) ────────────────────────────────────────────────────
# Delegates to the standalone `zata-ops` CLI, which must be installed globally first:
#   cd /path/to/zata-ops && uv tool install --force .
#
# Loads this project's .env / .env.local via `zata-ops`'s own pydantic-settings
# layer; additional CLI flags can be passed after `--`.

# Ops helper
# Usage:
#   just ops backup                # real backup
#   just ops backup --dry-run      # plan-only, no network calls
#   just ops backup --force-full
#   just ops restore --from 2026-06-07_180000 --restore-db --yes
#   just ops provision --host example.com --user deploy --dry-run
#   just ops check
#   just ops dashboard
ops action *args="":
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v zata-ops >/dev/null 2>&1; then
        echo "ERROR: zata-ops is not installed. Install it with:"
        echo "  cd /path/to/zata-ops && uv tool install --force ."
        exit 1
    fi
    cd "{{justfile_directory()}}"
    case "{{action}}" in
        backup)
            zata-ops db backup {{args}}
            ;;
        restore)
            zata-ops db restore {{args}}
            ;;
        check)
            zata-ops db check {{args}}
            ;;
        provision)
            zata-ops env provision {{args}}
            ;;
        dashboard)
            zata-ops dashboard {{args}}
            ;;
        *)
            echo "ERROR: Unknown action: {{action}}"
            echo "Usage: just ops [backup|restore|check|provision|dashboard]"
            exit 1
            ;;
    esac


# Sync skills from the local project to the AI assistant's skill directory.
# Usage:
#   just sync-local-skills
sync-local-skills:
    ./scripts/sync_template.sh --local-skills


# Copy template to a new directory (excluding .git, caches, and generated dependencies/build outputs)
# Usage: just copy <new-directory-name|target-directory-path> [--force]
copy name force='':
    #!/usr/bin/env bash
    set -e

    if [ -z "{{name}}" ]; then
        echo "Error: Please provide a target directory name or path"
        echo "Usage: just copy <new-directory-name|target-directory-path> [--force]"
        exit 1
    fi

    TEMPLATE_DIR="{{justfile_directory()}}"
    COPY_TARGET_INPUT="{{name}}"
    FORCE_FLAG="{{force}}"
    if [[ "$COPY_TARGET_INPUT" = /* || "$COPY_TARGET_INPUT" = ./* || "$COPY_TARGET_INPUT" = ../* || "$COPY_TARGET_INPUT" = ~/* || "$COPY_TARGET_INPUT" == *"/"* ]]; then
        NEW_DIR="$COPY_TARGET_INPUT"
    else
        NEW_DIR="$(dirname "$TEMPLATE_DIR")/$COPY_TARGET_INPUT"
    fi
    PROJECT_NAME="$(basename "$NEW_DIR")"
    OLD_NAME="zata-codes-template"

    if [ -e "$NEW_DIR" ] && [ ! -d "$NEW_DIR" ]; then
        echo "Error: Target '$NEW_DIR' exists and is not a directory"
        exit 1
    fi

    if [ -d "$NEW_DIR" ]; then
        if [ -n "$(find "$NEW_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]; then
            if [ "$FORCE_FLAG" = "--force" ]; then
                :
            else
                echo "Error: Directory '$NEW_DIR' already exists and is not empty"
                echo "Hint: Use 'just copy $COPY_TARGET_INPUT --force' to copy into an existing non-empty directory."
                exit 1
            fi
        fi
    else
        mkdir -p "$NEW_DIR"
    fi

    if [ "$FORCE_FLAG" = "--force" ]; then
        echo "Force-copying template to $NEW_DIR..."
    else
        echo "Copying template to $NEW_DIR..."
    fi
    mkdir -p "$(dirname "$NEW_DIR")"

    rsync -av \
        --exclude='.git' \
        --exclude='.venv' \
        --exclude='.uv-cache' \
        --exclude='.pytest_cache' \
        --exclude='.ruff_cache' \
        --exclude='node_modules' \
        --exclude='dist' \
        --exclude='logs' \
        --exclude='site' \
        --exclude='*.egg-info' \
        --exclude='__pycache__' \
        --exclude='prompt' \
        --exclude='skills' \
        --exclude='tasks/archive/*.md' \
        --exclude='tasks/pending/*.md' \
        --exclude='tasks/inbox/*.md' \
        --exclude='/findings.md' \
        --exclude='/progress.md' \
        --exclude='/task_plan.md' \
        --exclude='docker-compose.testing.yml' \
        --exclude='.claude/planning' \
        "$TEMPLATE_DIR/" "$NEW_DIR/"

    # Strip this `copy` recipe from the destination's justfile — only the
    # template maintainer needs it. The marker is the comment line above the
    # `copy name force=':` recipe header in this file.
    NEW_JUSTFILE="$NEW_DIR/justfile"
    python3 -c 'from pathlib import Path; import sys; justfile_path = Path(sys.argv[1]); justfile_text = justfile_path.read_text(encoding="utf-8"); copy_section_marker = "\n# Copy template to a new directory"; copy_section_index = justfile_text.find(copy_section_marker); trimmed_justfile_text = justfile_text[:copy_section_index].rstrip() + "\n" if copy_section_index != -1 else justfile_text; justfile_path.write_text(trimmed_justfile_text, encoding="utf-8")' "$NEW_JUSTFILE"

    echo "Updating project name in config files..."
    python3 -c 'from pathlib import Path; import sys; old_project_name = sys.argv[1]; new_project_name = sys.argv[2]; target_root = Path(sys.argv[3]); project_file_paths = [target_root / path for path in sys.argv[4:]]; [project_file_path.write_text(project_file_path.read_text(encoding="utf-8").replace(old_project_name, new_project_name), encoding="utf-8") for project_file_path in project_file_paths if project_file_path.exists()]' "$OLD_NAME" "$PROJECT_NAME" "$NEW_DIR" config.toml mkdocs.yml pyproject.toml uv.lock docker-compose.dokploy.yml docker-compose.yml frontend-admin/nginx.conf frontend-public/Dockerfile deploy/vps-traefik/README.md deploy/vps-traefik/docker-compose.yml deploy/vps-traefik/.env.example deploy/vps-traefik/app.env.example deploy/vps-traefik/github-actions-deploy.yml.example

    echo "Resetting README.md to template..."
    python3 "$TEMPLATE_DIR/scripts/shared/template/generate_readme.py" "$PROJECT_NAME" "$NEW_DIR/README.md"

    echo "Cleaning up empty directories..."
    find "$NEW_DIR" -type d -empty -delete

    echo "Setting up git and pre-commit hooks..."
    if git -C "$NEW_DIR" rev-parse --git-dir > /dev/null 2>&1; then
        echo "Git repository already exists, running pre-commit install..."
    else
        echo "Initializing git repository..."
        git -C "$NEW_DIR" init
    fi
    (cd "$NEW_DIR" && uv run pre-commit install)
