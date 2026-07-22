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
#   just run backend_port=8010 frontend_admin_port=13173 frontend_public_port=3001
#   just run all frontend_public_cmd="pnpm dev"
run arg1="" arg2="" arg3="" arg4="" arg5="" arg6="" arg7="" arg8="" arg9="": _check-completion
    #!/usr/bin/env bash
    set -euo pipefail

    target="all"
    frontend_dir="frontend-admin"
    frontend_public_dir="frontend-public"
    backend_port=""
    frontend_admin_port=""
    frontend_public_port=""
    backend_cmd="uv run python -m backend.main"
    frontend_cmd="pnpm dev"
    frontend_public_cmd="pnpm dev"
    backend_pid=""
    frontend_pid=""
    frontend_public_pid=""
    run_state_file="{{justfile_directory()}}/.env.run-state"
    positional_index=0

    parse_run_arg() {
        cli_arg="$1"
        if [ -z "$cli_arg" ]; then
            return 0
        fi

        case "$cli_arg" in
            -h|--help)
                echo "Usage: just run [backend|frontend|frontend-public|all|docker] [OPTIONS]"
                echo ""
                echo "Targets:"
                echo "  backend              Start backend only"
                echo "  frontend             Start admin frontend only"
                echo "  frontend-public      Start public frontend only"
                echo "  all                  Start backend + admin frontend + public frontend (default)"
                echo "  docker               Start with Docker Compose"
                echo ""
                echo "Options:"
                echo "  backend_port=<port>          Fallback without run-state: 8000"
                echo "  frontend_admin_port=<port>   Fallback without run-state: 5173"
                echo "  frontend_public_port=<port>  Fallback without run-state: 3000"
                echo "  backend_cmd=<cmd>            Default: uv run python -m backend.main"
                echo "  frontend_cmd=<cmd>           Default: pnpm dev"
                echo "  frontend_public_cmd=<cmd>    Default: pnpm dev"
                echo "  frontend_dir=<path>          Default: frontend-admin"
                echo "  frontend_public_dir=<path>   Default: frontend-public"
                exit 0
                ;;
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
            frontend_admin_port=*)
                frontend_admin_port="${cli_arg#frontend_admin_port=}"
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
                        echo "Usage: just run [backend|frontend|frontend-public|all|docker] [backend_port=<port>] [frontend_admin_port=<port>] [frontend_public_port=<port>]"
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
        frontend_admin_port="${frontend_admin_port:-${FRONTEND_ADMIN_PORT:-5173}}"
        frontend_public_port="${frontend_public_port:-${FRONTEND_PUBLIC_PORT:-3000}}"
    }

    save_run_ports() {
        mkdir -p "$(dirname "$run_state_file")"
        {
            printf 'BACKEND_PORT=%s\n' "$backend_port"
            printf 'FRONTEND_ADMIN_PORT=%s\n' "$frontend_admin_port"
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
            echo "      just run backend_port=8010 frontend_admin_port=13173"
            echo ""
            echo "   Or stop the existing process:"
            echo "      just down backend_port=$backend_port frontend_admin_port=$frontend_admin_port"
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

    ensure_frontend_deps() {
        target_dir="$1"
        if [ -d "$target_dir/node_modules" ]; then
            return 0
        fi

        if ! command -v pnpm >/dev/null 2>&1; then
            echo "ERROR: pnpm is required to install frontend dependencies but was not found."
            echo "   Install it first, for example: npm install -g pnpm"
            echo "   Or install the frontend dependencies manually before running 'just run'."
            exit 1
        fi

        # 项目根存在 pnpm-workspace.yaml 时，把 frontend-admin / frontend-public
        # 当作 pnpm workspace 的成员统一安装，避免在每个子目录里重复 install
        # 且子目录里 pnpm 11 会自动创建带 allowBuilds 占位的 pnpm-workspace.yaml
        # 覆盖根配置。
        workspace_root="{{justfile_directory()}}"
        if [ -f "$workspace_root/pnpm-workspace.yaml" ]; then
            echo "Workspace detected at $workspace_root, running pnpm install at workspace root..."
            (
                cd "$workspace_root"
                pnpm install
            )
            return 0
        fi

        echo "Dependencies missing in $target_dir, running pnpm install..."
        (
            cd "$target_dir"
            pnpm install
        )
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

        ensure_frontend_deps "$frontend_dir"
        check_port "Admin Frontend" "$frontend_admin_port"
        echo "Starting admin frontend in $frontend_dir on port $frontend_admin_port: $frontend_cmd"
        (
            cd "$frontend_dir"
            BACKEND_PORT="$backend_port" FRONTEND_ADMIN_PORT="$frontend_admin_port" bash -lc "$frontend_cmd"
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

        ensure_frontend_deps "$frontend_public_dir"
        check_port "Public Frontend" "$frontend_public_port"
        echo "Starting public frontend in $frontend_public_dir on port $frontend_public_port: $frontend_public_cmd"
        (
            cd "$frontend_public_dir"
            PORT="$frontend_public_port" BACKEND_PORT="$backend_port" BACKEND_URL="http://localhost:$backend_port" bash -lc "$frontend_public_cmd"
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

            # Inject a build-time apt proxy so deb.debian.org is reachable
            # inside the build container when the host network cannot reach it
            # directly (e.g. GFW).
            #
            # Why we do NOT re-use the host shell's $http_proxy: inside the
            # build container 127.0.0.1 refers to the container itself, not the
            # host, so a host-side value like http://127.0.0.1:7897 is
            # useless (and even causes Connection refused). We always default
            # to host.docker.internal which Docker Desktop resolves to the host
            # loopback. Override via APT_PROXY=http://host:port for any other
            # proxy setup.
            apt_proxy_url="${APT_PROXY:-http://host.docker.internal:7897}"
            echo "Docker build will use APT_PROXY=${apt_proxy_url}"

            export APT_PROXY="$apt_proxy_url"
            export HTTP_PROXY="$apt_proxy_url"
            export HTTPS_PROXY="$apt_proxy_url"

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
            # Keep host-side Compose bindings aligned with the same ports used
            # by the non-Docker run targets. This file is intentionally last so
            # its generated runtime values win over project configuration.
            env_file_args+=(--env-file "$run_state_file")
            BACKEND_PORT="$backend_port" \
                FRONTEND_ADMIN_PORT="$frontend_admin_port" \
                FRONTEND_PUBLIC_PORT="$frontend_public_port" \
                COMPOSE_LOCAL_ENV_FILE="$compose_env_file" \
                docker compose "${env_file_args[@]}" build \
                    --build-arg "APT_PROXY=${APT_PROXY}" \
                    --build-arg "HTTP_PROXY=${HTTP_PROXY}" \
                    --build-arg "HTTPS_PROXY=${HTTPS_PROXY}"
            # `docker compose up` does not accept --env (that is `run`'s flag).
            # Compose auto-injects the calling shell's HTTP_PROXY / HTTPS_PROXY
            # into every container unless the service explicitly sets them in
            # its environment: block, so the same proxy reaches uv / curl at
            # container runtime without rebuilding.
            BACKEND_PORT="$backend_port" \
                FRONTEND_ADMIN_PORT="$frontend_admin_port" \
                FRONTEND_PUBLIC_PORT="$frontend_public_port" \
                COMPOSE_LOCAL_ENV_FILE="$compose_env_file" \
                docker compose "${env_file_args[@]}" up
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
#   just down backend_port=8010 frontend_admin_port=13173 frontend_public_port=3001
#   just down docker
down arg1="" arg2="" arg3="" arg4="" arg5="": _check-completion
    #!/usr/bin/env bash
    set -euo pipefail

    target="all"
    backend_port=""
    frontend_admin_port=""
    frontend_public_port=""
    run_state_file="{{justfile_directory()}}/.env.run-state"
    positional_index=0

    parse_down_arg() {
        cli_arg="$1"
        if [ -z "$cli_arg" ]; then
            return 0
        fi

        case "$cli_arg" in
            -h|--help)
                echo "Usage: just down [backend|frontend|frontend-public|all|docker] [OPTIONS]"
                echo ""
                echo "Targets:"
                echo "  backend              Stop backend only"
                echo "  frontend             Stop admin frontend only"
                echo "  frontend-public      Stop public frontend only"
                echo "  all                  Stop all local services (default)"
                echo "  docker               Stop Docker Compose services"
                echo ""
                echo "Options:"
                echo "  backend_port=<port>          Fallback without run-state: 8000"
                echo "  frontend_admin_port=<port>   Fallback without run-state: 5173"
                echo "  frontend_public_port=<port>  Fallback without run-state: 3000"
                exit 0
                ;;
            target=*)
                target="${cli_arg#target=}"
                ;;
            backend_port=*)
                backend_port="${cli_arg#backend_port=}"
                ;;
            frontend_admin_port=*)
                frontend_admin_port="${cli_arg#frontend_admin_port=}"
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
                    echo "Usage: just down [backend|frontend|frontend-public|all|docker] [backend_port=<port>] [frontend_admin_port=<port>] [frontend_public_port=<port>]"
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
        frontend_admin_port="${frontend_admin_port:-${FRONTEND_ADMIN_PORT:-5173}}"
        frontend_public_port="${frontend_public_port:-${FRONTEND_PUBLIC_PORT:-3000}}"
    }

    # Filter Docker-related PIDs from a port's listener list. Uses both the
    # command name and the full argument string so app-bundled binaries like
    # `/Applications/Docker.app/.../com.docker.backend` are reliably detected.
    filter_non_docker_pids() {
        port_value="$1"
        filtered_pids=""
        while read -r port_pid; do
            [ -n "$port_pid" ] || continue
            process_info="$(ps -p "$port_pid" -o comm=,args= 2>/dev/null || true)"
            case "$process_info" in
                *com.docker*|*Docker.app*|*docker*vpnkit*|*docker*hyperkit*) ;;
                *) filtered_pids="$filtered_pids $port_pid" ;;
            esac
        done < <(lsof -nP -iTCP:"$port_value" -sTCP:LISTEN -t 2>/dev/null || true)
        if [ -z "$filtered_pids" ]; then
            return 0
        fi
        echo "$filtered_pids" | tr ' ' '\n' | grep -v '^$' | sort -u
    }

    list_docker_pids() {
        port_value="$1"
        while read -r port_pid; do
            [ -n "$port_pid" ] || continue
            process_info="$(ps -p "$port_pid" -o comm=,args= 2>/dev/null || true)"
            case "$process_info" in
                *com.docker*|*Docker.app*|*docker*vpnkit*|*docker*hyperkit*)
                    echo "  - pid=$port_pid command=$process_info"
                    ;;
            esac
        done < <(lsof -nP -iTCP:"$port_value" -sTCP:LISTEN -t 2>/dev/null || true)
    }

    stop_port() {
        port_label="$1"
        port_value="$2"
        process_ids="$(filter_non_docker_pids "$port_value")"
        docker_pids_info="$(list_docker_pids "$port_value")"

        if [ -n "$docker_pids_info" ]; then
            echo "Skipping Docker-related process(es) on $port_label port $port_value;"
            echo "terminate them manually if you really want this port free:"
            printf '%s\n' "$docker_pids_info"
        fi

        if [ -z "$process_ids" ]; then
            if [ -z "$docker_pids_info" ]; then
                echo "No $port_label process listening on port $port_value"
            fi
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
            stop_port "admin frontend" "$frontend_admin_port"
            ;;
        frontend-public)
            stop_port "public frontend" "$frontend_public_port"
            ;;
        all)
            stop_port backend "$backend_port"
            stop_port "admin frontend" "$frontend_admin_port"
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
            cd "{{justfile_directory()}}"
            just run frontend
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
            cd "{{justfile_directory()}}"
            just run frontend-public
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

    # Pick random default ports so multiple copies of the template can run
    # side-by-side without colliding on 8000/5173/3000. Ranges stay close to the
    # well-known defaults and are mutually disjoint, so a single invocation
    # cannot collide with itself.
    backend_random_port=$((8000 + RANDOM % 1000))
    frontend_admin_random_port=$((5180 + RANDOM % 820))
    frontend_public_random_port=$((3010 + RANDOM % 990))
    echo "Picked random ports: backend=$backend_random_port, admin frontend=$frontend_admin_random_port, public frontend=$frontend_public_random_port"

    echo "Updating project name in config files..."
    python3 -c 'from pathlib import Path; import sys; old_project_name = sys.argv[1]; new_project_name = sys.argv[2]; target_root = Path(sys.argv[3]); project_file_paths = [target_root / path for path in sys.argv[4:]]; [project_file_path.write_text(project_file_path.read_text(encoding="utf-8").replace(old_project_name, new_project_name), encoding="utf-8") for project_file_path in project_file_paths if project_file_path.exists()]' "$OLD_NAME" "$PROJECT_NAME" "$NEW_DIR" config.toml mkdocs.yml pyproject.toml uv.lock docker-compose.dokploy.yml docker-compose.yml frontend-admin/nginx.conf frontend-public/Dockerfile deploy/vps-traefik/README.md deploy/vps-traefik/docker-compose.yml deploy/vps-traefik/.env.example deploy/vps-traefik/app.env.example deploy/vps-traefik/github-actions-deploy.yml.example

    echo "Setting up project-specific database..."
    uv run python "$TEMPLATE_DIR/scripts/shared/template/setup_copied_database.py" "$PROJECT_NAME" "$NEW_DIR"

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

    echo "Running database migrations..."
    (cd "$NEW_DIR" && uv run alembic upgrade head)

    # Seed the destination's single source of truth for host-side runtime ports.
    # Keep the copied justfile's fallback values unchanged so future recipe
    # updates cannot drift from project-specific values embedded in source.
    run_state_file="$NEW_DIR/.env.run-state"
    mkdir -p "$(dirname "$run_state_file")"
    {
        printf 'BACKEND_PORT=%s\n' "$backend_random_port"
        printf 'FRONTEND_ADMIN_PORT=%s\n' "$frontend_admin_random_port"
        printf 'FRONTEND_PUBLIC_PORT=%s\n' "$frontend_public_random_port"
    } > "$run_state_file"

    # Check git identity so the initial commit below fails with a clear hint
    # rather than git's default "Author identity unknown" error.
    if ! git config --get-all user.name >/dev/null 2>&1; then
        echo "Error: git user.name and user.email must be configured before 'just copy' can create the initial commit."
        echo "  Set them globally, for example:"
        echo "    git config --global user.name \"Your Name\""
        echo "    git config --global user.email \"you@example.com\""
        exit 1
    fi

    echo "Creating initial commit..."
    git -C "$NEW_DIR" add -A
    # Skip hooks that only apply to changes after repository initialization:
    # a fresh repo has no .last_tested_commit, and its initial commit naturally
    # stages the complete tests/guards/ directory.
    # Other hooks (ruff, yaml, architecture) still run to validate the template.
    SKIP=check-test-flag,check-guard-test-modification \
        git -C "$NEW_DIR" commit -m "chore: initial commit from template"


# Run a single E2E oracle from a PRD's Realistic Validation Plan and collect evidence.
# Usage:
#   just e2e-evidence tasks/pending/<prd-file>.md rv-2
#   just e2e-evidence tasks/pending/<prd-file>.md       # runs all e2e/smoke/manual oracles
# Evidence is written to tasks/evidence/<prd-basename>/.
e2e-evidence prd_file rv_id="":
    cd "{{justfile_directory()}}" && ./scripts/e2e/run-prd-evidence.sh "{{prd_file}}" "{{rv_id}}"


# Measure `just test` end-to-end latency to verify the 30s budget.
# Runs warm + after-edit scenarios by default; pass --include-cold to also
# force a full pre-commit run (may exceed 30s).
# Usage:
#   just bench-test
#   just bench-test --include-cold
#   just bench-test --budget 25
bench-test *args:
    cd "{{justfile_directory()}}" && uv run python scripts/dev/measure_just_test.py {{args}}
