# Default recipe (runs when you type 'just')
default:
    @just --list

# NOTE:
#   Run `just sync all` once on a local machine to install shell completion
#   for `just` in the current shell profile.

# Sync dependencies
# Usage:
#   just sync           # dev deps (default)
#   just sync prod      # production only, no dev
#   just sync all       # all extras + install just shell completion
#   just sync dev       # all extras + pre-commit hooks
sync mode="":
    #!/usr/bin/env bash
    set -euo pipefail
    case "{{mode}}" in
        prod)
            uv sync --no-dev
            ;;
        all)
            uv sync --all-extras
            if [ -z "${CI:-}" ]; then
                shell_name="$(basename "${SHELL:-}")"
                case "$shell_name" in
                    zsh)
                        completion_dir="$HOME/.zsh/completions"
                        completion_dst="$completion_dir/_just"
                        mkdir -p "$completion_dir"
                        just --completions zsh > "$completion_dst"
                        fpath_line="fpath=(\"$completion_dir\" \$fpath)"
                        autoload_line="autoload -Uz compinit && compinit"
                        if ! grep -Fqx "$fpath_line" "$HOME/.zshrc" 2>/dev/null; then
                            printf '\n%s\n' "$fpath_line" >> "$HOME/.zshrc"
                        fi
                        if ! grep -Fqx "$autoload_line" "$HOME/.zshrc" 2>/dev/null; then
                            printf '%s\n' "$autoload_line" >> "$HOME/.zshrc"
                        fi
                        echo "Installed zsh completion: $completion_dst"
                        echo "Reload your shell with: source ~/.zshrc"
                        echo "Or open a new terminal session to activate just completions."
                        ;;
                    bash)
                        completion_dir="$HOME/.config/just"
                        completion_dst="$completion_dir/just_completion.bash"
                        source_line="[ -f \"$completion_dst\" ] && source \"$completion_dst\""
                        mkdir -p "$completion_dir"
                        just --completions bash > "$completion_dst"
                        if ! grep -Fqx "$source_line" "$HOME/.bashrc" 2>/dev/null; then
                            printf '\n%s\n' "$source_line" >> "$HOME/.bashrc"
                        fi
                        echo "Installed bash completion: $completion_dst"
                        echo "Reload your shell with: source ~/.bashrc"
                        echo "Or open a new terminal session to activate just completions."
                        ;;
                    *)
                        echo "Skipped shell completion install for unsupported shell: $shell_name"
                        ;;
                esac
            fi
            ;;
        dev)
            uv sync --all-extras
            uv run pre-commit install
            ;;
        "")
            uv sync
            ;;
        *)
            echo "❌ Unknown mode: {{mode}}"
            echo "Usage: just sync [prod|all|dev]"
            exit 1
            ;;
    esac

# Run the development entrypoint
# Usage:
#   just run                 # start backend + frontend
#   just run backend         # start backend only
#   just run frontend        # start frontend only
#   just run all frontend_dir=web frontend_cmd="pnpm dev"
run target="all" frontend_dir="frontend" backend_cmd="uv run python main.py" frontend_cmd="npm run dev":
    #!/usr/bin/env bash
    set -euo pipefail

    target="{{target}}"
    frontend_dir="{{frontend_dir}}"
    backend_cmd='{{backend_cmd}}'
    frontend_cmd='{{frontend_cmd}}'
    backend_pid=""
    frontend_pid=""

    run_backend() {
        echo "Starting backend: $backend_cmd"
        bash -lc "$backend_cmd"
    }

    run_frontend() {
        if [ ! -d "$frontend_dir" ]; then
            echo "❌ Frontend directory not found: $frontend_dir"
            echo "   Override it with: just run frontend frontend_dir=<path>"
            exit 1
        fi

        if [ ! -f "$frontend_dir/package.json" ]; then
            echo "❌ package.json not found in frontend directory: $frontend_dir"
            echo "   Override the directory or command, for example:"
            echo "   just run frontend frontend_dir=<path> frontend_cmd='pnpm dev'"
            exit 1
        fi

        echo "Starting frontend in $frontend_dir: $frontend_cmd"
        (
            cd "$frontend_dir"
            bash -lc "$frontend_cmd"
        )
    }

    cleanup_processes() {
        for process_pid in "$backend_pid" "$frontend_pid"; do
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

            sleep 1
        done
    }

    case "$target" in
        backend)
            run_backend
            ;;
        frontend)
            run_frontend
            ;;
        all)
            trap cleanup_processes EXIT INT TERM
            run_backend &
            backend_pid=$!
            run_frontend &
            frontend_pid=$!
            wait_for_first_exit
            ;;
        *)
            echo "❌ Unknown run target: $target"
            echo "Usage: just run [backend|frontend|all]"
            exit 1
            ;;
    esac

# Run local lint/format checks via pre-commit (matches CI)
lint:
    uv run pre-commit run --all-files --show-diff-on-failure

# Serve MkDocs site locally with live reload (configurable port, default 8000)
docs-serve port="8000":
    WATCHDOG_USE_POLLING=1 uv run mkdocs serve -a 127.0.0.1:{{port}}

# Remove cache files and build artifacts
clean:
    @echo "Cleaning cache files..."
    @rm -rf .ruff_cache
    @rm -rf __pycache__
    @find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    @find . -type f -name "*.pyc" -delete 2>/dev/null || true
    @find . -type f -name "*.pyo" -delete 2>/dev/null || true
    @find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
    @echo "Clean complete!"

# Build a release zip (does NOT modify local workspace)
release:
    uv run python scripts/release.py

# Check the current terminal network environment for Claude access.
check-net:
    ./scripts/diagnostics/check_claude_code.sh

staged_changes:
    git diff --cached > staged_changes.diff

# Git worktree helper (implemented in scripts/worktree/)
# Usage:
#   just worktree <branch>                            # create/enter worktree
#   just worktree <branch> --cmd trae                 # open in editor
#   just worktree <branch> enter_shell=false          # no shell
#   just worktree -d <branch>                         # delete worktree
#   just worktree -m <feature> [base=main] [flags]    # merge worktree
#   just worktree --doctor [branch]                   # doctor / cleanup-check
worktree arg1 arg2="" arg3="" arg4="" arg5="":
    #!/usr/bin/env bash
    set -euo pipefail

    # -d: delete worktree
    if [ "{{arg1}}" = "-d" ]; then
        if [ -z "{{arg2}}" ]; then
            echo "❌ Usage: just worktree -d <branch_name>"
            exit 1
        fi
        ./scripts/worktree/merge.sh "{{arg2}}" -d
        exit 0
    fi

    # -m: merge worktree
    if [ "{{arg1}}" = "-m" ]; then
        if [ -z "{{arg2}}" ]; then
            echo "❌ Usage: just worktree -m <feature_branch> [base_branch=main] [flags]"
            exit 1
        fi
        base_branch_value="{{arg3}}"
        [ -z "$base_branch_value" ] && base_branch_value="main"
        extra_flags_value="{{arg4}}"
        if [ -n "$extra_flags_value" ]; then
            ./scripts/worktree/merge.sh "{{arg2}}" "$base_branch_value" $extra_flags_value
        else
            ./scripts/worktree/merge.sh "{{arg2}}" "$base_branch_value"
        fi
        exit 0
    fi

    # --doctor: cleanup-check
    if [ "{{arg1}}" = "--doctor" ]; then
        if [ -n "{{arg2}}" ]; then
            ./scripts/worktree/merge.sh --doctor "{{arg2}}"
        else
            ./scripts/worktree/merge.sh --doctor
        fi
        exit 0
    fi

    # Default: create/enter worktree
    branch_name="{{arg1}}"
    worktree_command=(./scripts/worktree/create.sh "$branch_name")
    enter_shell_value="true"
    expect_code_command="false"

    for raw_arg in "{{arg2}}" "{{arg3}}" "{{arg4}}" "{{arg5}}"; do
        if [ -z "$raw_arg" ]; then
            continue
        fi

        if [ "$expect_code_command" = "true" ]; then
            case "$raw_arg" in
                --cmd|--cmd=*|enter_shell=true|enter_shell=false)
                    expect_code_command="false"
                    ;;
                *)
                    worktree_command+=("$raw_arg")
                    expect_code_command="false"
                    continue
                    ;;
            esac
        fi

        case "$raw_arg" in
            --cmd)
                worktree_command+=(--cmd)
                expect_code_command="true"
                ;;
            --cmd=*)
                worktree_command+=("$raw_arg")
                ;;
            enter_shell=true)
                enter_shell_value="true"
                ;;
            enter_shell=false)
                enter_shell_value="false"
                ;;
            *)
                echo "❌ Invalid argument: $raw_arg"
                echo "Usage:"
                echo "  just worktree <branch> [--cmd [editor]] [enter_shell=false]"
                echo "  just worktree -d <branch>"
                echo "  just worktree -m <feature> [base=main] [flags]"
                echo "  just worktree --doctor [branch]"
                exit 1
                ;;
        esac
    done

    "${worktree_command[@]}"

    if [ "$enter_shell_value" = "true" ]; then
        target_worktree_path="$(dirname "$(git rev-parse --show-toplevel)")/$branch_name"
        echo "Entering worktree shell: $target_worktree_path"
        echo "Run 'exit' to return to previous shell."
        cd "$target_worktree_path"
        if [ -n "${TERM:-}" ] && [ "${TERM}" != "dumb" ]; then
            printf '\033]0;%s\007' "wt:$branch_name"
        fi
        worktree_shell_rcfile="$(mktemp)"
        printf '%s\n' \
            'if [ -f "$HOME/.bashrc" ]; then' \
            '    source "$HOME/.bashrc"' \
            'fi' \
            'if [ -n "${WORKTREE_BRANCH_NAME:-}" ]; then' \
            '    PS1="(wt:${WORKTREE_BRANCH_NAME}) ${PS1:-\u@\h:\w\$ }"' \
            'fi' \
            'if [ -n "${WORKTREE_SHELL_RCFILE:-}" ] && [ -f "${WORKTREE_SHELL_RCFILE}" ]; then' \
            '    rm -f "${WORKTREE_SHELL_RCFILE}" 2>/dev/null || true' \
            '    unset WORKTREE_SHELL_RCFILE' \
            'fi' \
            > "$worktree_shell_rcfile"
        exec env WORKTREE_BRANCH_NAME="$branch_name" WORKTREE_SHELL_RCFILE="$worktree_shell_rcfile" bash --rcfile "$worktree_shell_rcfile" -i
    fi


# Sync files from the upstream template repository.
# Compares local files against the template and offers to apply updates.
# Usage:
#   just sync-template         # skip project-specific files (recommended)
#   just sync-template --all   # include project-specific files too
sync-template flags="":
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -n "{{flags}}" ]; then
        ./scripts/sync_template.sh {{flags}}
    else
        ./scripts/sync_template.sh
    fi

# Run tests (usage: just test [all|local|real])
#   just test        - Run local tests (no API keys needed)
#   just test all    - Run all tests
#   just test real   - Run tests requiring API keys
@test type="local":
    #!/usr/bin/env bash
    set -e
    if [ "{{type}}" = "all" ]; then
        uv run pytest tests/ -v
    elif [ "{{type}}" = "real" ]; then
        uv run pytest tests/ -v -k "expensive or not expensive"
    else
        uv run pytest tests/ -v --ignore=tests/test_model_loader_real.py -m "not expensive"
    fi


# Run Playwright e2e tests (requires: just e2e-install first)
# Usage:
#   just e2e            # all tests (excluding visual regression)
#   just e2e smoke      # smoke tests only
#   just e2e no-auth    # public-page tests (no login required)
#   just e2e report     # open HTML test report
e2e type="":
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{justfile_directory()}}/playwright-e2e"
    case "{{type}}" in
        smoke)   npm run test:smoke ;;
        no-auth) npm run test:no-auth ;;
        report)  npm run report ;;
        "")      npm test ;;
        *)
            echo "❌ Unknown type: {{type}}"
            echo "Usage: just e2e [smoke|no-auth|report]"
            exit 1
            ;;
    esac

# Install e2e dependencies and Playwright browsers (run once before first just e2e)
e2e-install:
    cd "{{justfile_directory()}}/playwright-e2e" && npm install && npx playwright install chromium


# Pack all gitignored .env* files into a password-protected encrypted zip.
# Output: ./<project_name>_secrets.zip  (one fixed file per project root)
# Password is prompted interactively at compression time; required again to extract.
export-env-encrypted:
    ./scripts/secrets/export_env_encrypted.sh


# Copy template to a new directory (excluding .git and cache directories)
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
        --exclude='logs' \
        --exclude='site' \
        --exclude='*.egg-info' \
        --exclude='__pycache__' \
        --exclude='prompt' \
        --exclude='skills' \
        --exclude='scripts/template/generate_readme.py' \
        "$TEMPLATE_DIR/" "$NEW_DIR/"

    NEW_JUSTFILE="$NEW_DIR/justfile"
    python3 -c 'from pathlib import Path; import sys; justfile_path = Path(sys.argv[1]); justfile_text = justfile_path.read_text(encoding="utf-8"); copy_section_marker = "\n# Copy template to a new directory"; copy_section_index = justfile_text.find(copy_section_marker); trimmed_justfile_text = justfile_text[:copy_section_index].rstrip() + "\n" if copy_section_index != -1 else justfile_text; justfile_path.write_text(trimmed_justfile_text, encoding="utf-8")' "$NEW_JUSTFILE"

    echo "Updating project name in config files..."
    python3 -c 'from pathlib import Path; import sys; project_file_paths = [Path(path) for path in sys.argv[1:5]]; old_project_name = sys.argv[5]; new_project_name = sys.argv[6]; [project_file_path.write_text(project_file_path.read_text(encoding="utf-8").replace(old_project_name, new_project_name), encoding="utf-8") for project_file_path in project_file_paths]' "$NEW_DIR/config.toml" "$NEW_DIR/mkdocs.yml" "$NEW_DIR/pyproject.toml" "$NEW_DIR/uv.lock" "$OLD_NAME" "$PROJECT_NAME"

    echo "Resetting README.md to template..."
    python3 "$TEMPLATE_DIR/scripts/template/generate_readme.py" "$PROJECT_NAME" "$NEW_DIR/README.md"
