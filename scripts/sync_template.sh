#!/usr/bin/env bash
# sync_template.sh — Compare local project files with the upstream template
# repository and interactively offer to apply updates.
#
# Usage:
#   ./scripts/sync_template.sh
#   ./scripts/sync_template.sh --all   # also show project-specific files

set -euo pipefail

TEMPLATE_REPO="https://github.com/zata-zhangtao/zata-codes-template.git"
LOCAL_ROOT="$(git rev-parse --show-toplevel)"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

SHOW_ALL=false
if [ "${1:-}" = "--all" ]; then
    SHOW_ALL=true
fi

# ──────────────────────────────────────────────────────────────
# Skip rules — project-specific files that should not be synced
# ──────────────────────────────────────────────────────────────
_is_skipped() {
    local p="$1"
    case "$p" in
        README.md|pyproject.toml|config.toml|mkdocs.yml|uv.lock) return 0 ;;
        CLAUDE.md|main.py) return 0 ;;
        findings.md|progress.md|task_plan.md) return 0 ;;
        .DS_Store) return 0 ;;
    esac
    case "$p" in
        .git/*|.venv/*|.uv-cache/*|__pycache__/*|logs/*|site/*) return 0 ;;
        .pytest_cache/*|.ruff_cache/*|prompt/*|skills/*) return 0 ;;
        .claude/*|tests/*|docs/*) return 0 ;;
        utils/*|crawler/*|ai_agent/*|playwright-e2e/*) return 0 ;;
    esac
    case "$p" in
        *.pyc|*.egg-info|.env|.env.*) return 0 ;;
    esac
    return 1
}

# ──────────────────────────────────────────────────────────────
# OS detection & fzf install
# ──────────────────────────────────────────────────────────────
_detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif grep -qi microsoft /proc/version 2>/dev/null; then
        echo "wsl"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    else
        echo "unknown"
    fi
}

_install_fzf() {
    local os
    os="$(_detect_os)"
    case "$os" in
        macos)
            if ! command -v brew &>/dev/null; then
                echo "  ❌ Homebrew not found. Install fzf manually: https://github.com/junegunn/fzf"
                return 1
            fi
            echo "  Running: brew install fzf"
            brew install fzf
            ;;
        wsl|linux)
            if command -v apt-get &>/dev/null; then
                echo "  Running: sudo apt-get install -y fzf"
                sudo apt-get install -y fzf
            elif command -v apt &>/dev/null; then
                echo "  Running: sudo apt install -y fzf"
                sudo apt install -y fzf
            else
                echo "  ❌ apt not found. Install fzf manually: https://github.com/junegunn/fzf"
                return 1
            fi
            ;;
        *)
            echo "  ❌ Cannot auto-install on this platform. Install manually: https://github.com/junegunn/fzf"
            return 1
            ;;
    esac
}

# Returns 0 if fzf is available (installed or user chose to install), 1 to fall back
_ensure_fzf() {
    if command -v fzf &>/dev/null; then
        return 0
    fi
    echo "⚠️  fzf is not installed (used for interactive file selection)."
    printf "   Install now? [y/N] "
    read -r choice </dev/tty
    case "$choice" in
        y|Y)
            if _install_fzf; then
                echo "  ✅ fzf installed."
                return 0
            else
                return 1
            fi
            ;;
        *)
            echo "   Falling back to numbered list mode."
            return 1
            ;;
    esac
}

# ──────────────────────────────────────────────────────────────
# Detect diff color support
# ──────────────────────────────────────────────────────────────
DIFF_COLOR_FLAG=""
diff --color=always /dev/null /dev/null 2>/dev/null && DIFF_COLOR_FLAG="--color=always"

# ──────────────────────────────────────────────────────────────
# Clone template
# ──────────────────────────────────────────────────────────────
echo "🔍 Fetching template from $TEMPLATE_REPO ..."
git clone --depth=1 --quiet "$TEMPLATE_REPO" "$TEMP_DIR/template"
TEMPLATE_ROOT="$TEMP_DIR/template"
echo "✅ Template fetched."
echo ""

# ──────────────────────────────────────────────────────────────
# Phase 1: Scan — collect changed / new files
# ──────────────────────────────────────────────────────────────
changed_files=()
new_files=()

while IFS= read -r rel_path; do
    if ! $SHOW_ALL && _is_skipped "$rel_path"; then
        continue
    fi
    local_file="$LOCAL_ROOT/$rel_path"
    tmpl_file="$TEMPLATE_ROOT/$rel_path"
    if [ ! -f "$local_file" ]; then
        new_files+=("$rel_path")
    elif ! diff -q "$local_file" "$tmpl_file" > /dev/null 2>&1; then
        changed_files+=("$rel_path")
    fi
done < <(
    find "$TEMPLATE_ROOT" -type f \
        ! -path '*/.git/*' \
        | sed "s|$TEMPLATE_ROOT/||" \
        | sort
)

total_found=$(( ${#changed_files[@]} + ${#new_files[@]} ))

if [ "$total_found" -eq 0 ]; then
    echo "✨ Everything is up to date with the template."
    exit 0
fi

echo "Found ${#changed_files[@]} changed + ${#new_files[@]} new file(s)."
echo ""

# ──────────────────────────────────────────────────────────────
# Phase 2: Select files — fzf UI or numbered fallback
# ──────────────────────────────────────────────────────────────

# Build display list: "📝 CHANGED\trel_path" or "📄 NEW    \trel_path"
file_list_lines=()
for f in "${changed_files[@]}"; do
    file_list_lines+=("📝 CHANGED	$f")
done
for f in "${new_files[@]}"; do
    file_list_lines+=("📄 NEW    	$f")
done

selected_paths=()

if _ensure_fzf; then
    # ── fzf interactive mode ──────────────────────────────────
    # Export paths so the preview subshell can reference them
    export FZF_SYNC_LOCAL="$LOCAL_ROOT"
    export FZF_SYNC_TMPL="$TEMPLATE_ROOT"
    export FZF_DIFF_COLOR="$DIFF_COLOR_FLAG"

    preview_cmd='
        rel=$(echo {} | cut -f2)
        local_f="$FZF_SYNC_LOCAL/$rel"
        tmpl_f="$FZF_SYNC_TMPL/$rel"
        if [ ! -f "$local_f" ]; then
            echo "(new file — showing template content)"
            echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            cat "$tmpl_f"
        else
            diff '"$DIFF_COLOR_FLAG"' -u "$local_f" "$tmpl_f" || true
        fi
    '

    mapfile -t selected_lines < <(
        printf '%s\n' "${file_list_lines[@]}" \
        | fzf \
            --multi \
            --ansi \
            --delimiter=$'\t' \
            --with-nth=1,2 \
            --preview="$preview_cmd" \
            --preview-window=right:60%:wrap \
            --header=$'TAB: toggle select  ENTER: apply selected  ESC: quit\n' \
            --bind='tab:toggle+down' \
            --prompt='Select files > ' \
        || true
    )

    for line in "${selected_lines[@]}"; do
        rel=$(echo "$line" | cut -f2)
        selected_paths+=("$rel")
    done

else
    # ── Numbered list fallback ────────────────────────────────
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    idx=1
    declare -A file_map
    declare -A file_type_map
    for f in "${changed_files[@]}"; do
        printf "  [%2d] 📝 CHANGED  %s\n" "$idx" "$f"
        file_map[$idx]="$f"
        file_type_map[$idx]="changed"
        ((idx++))
    done
    for f in "${new_files[@]}"; do
        printf "  [%2d] 📄 NEW      %s\n" "$idx" "$f"
        file_map[$idx]="$f"
        file_type_map[$idx]="new"
        ((idx++))
    done

    echo ""
    echo "Enter numbers to update (e.g. 1 3 5), 'all', or 'q' to quit."
    echo "Prefix with 'd' to preview diff (e.g. d2)."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    while true; do
        printf "Your choice: "
        read -r input </dev/tty

        case "$input" in
            q|Q) echo "Aborted."; exit 0 ;;
            all|ALL)
                for key in "${!file_map[@]}"; do
                    selected_paths+=("${file_map[$key]}")
                done
                break
                ;;
            d\ *|d[0-9]*)
                num="${input#d }"; num="${num#d}"; num="${num// /}"
                if [ -n "${file_map[$num]+_}" ]; then
                    rel="${file_map[$num]}"
                    local_file="$LOCAL_ROOT/$rel"
                    tmpl_file="$TEMPLATE_ROOT/$rel"
                    echo ""
                    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    if [ ! -f "$local_file" ]; then
                        echo "(new file)"; cat "$tmpl_file"
                    else
                        # shellcheck disable=SC2086
                        diff $DIFF_COLOR_FLAG -u "$local_file" "$tmpl_file" || true
                    fi
                    echo ""
                else
                    echo "  Invalid number: $num"
                fi
                ;;
            "")  echo "  Nothing selected." ;;
            *)
                valid=true
                nums=()
                for num in $input; do
                    if [ -n "${file_map[$num]+_}" ]; then
                        nums+=("$num")
                    else
                        echo "  Invalid number: $num"; valid=false
                    fi
                done
                if $valid; then
                    for num in "${nums[@]}"; do
                        selected_paths+=("${file_map[$num]}")
                    done
                    break
                fi
                ;;
        esac
    done
fi

# ──────────────────────────────────────────────────────────────
# Phase 3: Apply selected changes
# ──────────────────────────────────────────────────────────────
if [ "${#selected_paths[@]}" -eq 0 ]; then
    echo "Nothing selected. No changes applied."
    exit 0
fi

echo ""
count_accepted=0
for rel in "${selected_paths[@]}"; do
    local_file="$LOCAL_ROOT/$rel"
    tmpl_file="$TEMPLATE_ROOT/$rel"
    mkdir -p "$(dirname "$local_file")"
    cp "$tmpl_file" "$local_file"
    if [ ! -f "$LOCAL_ROOT/$rel" ] 2>/dev/null; then
        echo "  ✅ Added:   $rel"
    else
        echo "  ✅ Updated: $rel"
    fi
    ((count_accepted++)) || true
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done. $count_accepted file(s) applied, $(( total_found - count_accepted )) skipped."
