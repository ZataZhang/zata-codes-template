# Default recipe (runs when you type 'just')
default:
    @just --list

# Sync dependencies
# Usage:
#   just sync           # dev deps (default)
#   just sync prod      # production only, no dev
#   just sync all       # all extras + worktree completion
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
                completion_src="{{justfile_directory()}}/scripts/just_worktree_completion.bash"
                completion_dir="$HOME/.config/just"
                completion_dst="$completion_dir/worktree_completion.bash"
                source_line="[ -f \"$completion_dst\" ] && source \"$completion_dst\""
                mkdir -p "$completion_dir"
                cp "$completion_src" "$completion_dst"
                if ! grep -Fqx "$source_line" "$HOME/.bashrc" 2>/dev/null; then
                    printf '\n%s\n' "$source_line" >> "$HOME/.bashrc"
                fi
                echo "Installed worktree completion: $completion_dst"
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

# Run the main application
run:
    uv run python main.py

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

staged_changes:
    git diff --cached > staged_changes.diff

# Git worktree helper (wrapper for scripts/git_worktree.sh / git_worktree_merge.sh)
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
        ./scripts/git_worktree_merge.sh "{{arg2}}" -d
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
            ./scripts/git_worktree_merge.sh "{{arg2}}" "$base_branch_value" $extra_flags_value
        else
            ./scripts/git_worktree_merge.sh "{{arg2}}" "$base_branch_value"
        fi
        exit 0
    fi

    # --doctor: cleanup-check
    if [ "{{arg1}}" = "--doctor" ]; then
        if [ -n "{{arg2}}" ]; then
            ./scripts/git_worktree_merge.sh --doctor "{{arg2}}"
        else
            ./scripts/git_worktree_merge.sh --doctor
        fi
        exit 0
    fi

    # Default: create/enter worktree
    branch_name="{{arg1}}"
    worktree_command=(./scripts/git_worktree.sh "$branch_name")
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
    cd "{{justfile_directory()}}/e2e-template"
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
    cd "{{justfile_directory()}}/e2e-template" && npm install && npx playwright install chromium


# Pack all gitignored .env* files into a password-protected encrypted zip.
# Output: ./<project_name>_secrets.zip  (one fixed file per project root)
# Password is prompted interactively at compression time; required again to extract.
export-env-encrypted:
    ./scripts/export_env_encrypted.sh


# Copy template to a new directory (excluding .git and cache directories)
# Usage: just copy <new-directory-name>
copy name:
    #!/usr/bin/env bash
    set -e

    if [ -z "{{name}}" ]; then
        echo "Error: Please provide a directory name"
        echo "Usage: just copy <new-directory-name>"
        exit 1
    fi

    TEMPLATE_DIR="{{justfile_directory()}}"
    NEW_DIR="$(dirname "$TEMPLATE_DIR")/{{name}}"
    OLD_NAME="zata-codes-template"

    if [ -d "$NEW_DIR" ]; then
        echo "Error: Directory '$NEW_DIR' already exists"
        exit 1
    fi

    echo "Copying template to $NEW_DIR..."

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
        --exclude='scripts/generate_readme.py' \
        "$TEMPLATE_DIR/" "$NEW_DIR/"

    NEW_JUSTFILE="$NEW_DIR/justfile"
    sed -i '/^# Copy template to a new directory/,$d' "$NEW_JUSTFILE"

    echo "Updating project name in config files..."
    sed -i "s/$OLD_NAME/{{name}}/g" "$NEW_DIR/config.toml"
    sed -i "s/$OLD_NAME/{{name}}/g" "$NEW_DIR/mkdocs.yml"
    sed -i "s/$OLD_NAME/{{name}}/g" "$NEW_DIR/pyproject.toml"

    echo "Resetting README.md to template..."
    uv run python "$TEMPLATE_DIR/scripts/generate_readme.py" "{{name}}" "$NEW_DIR/README.md"
