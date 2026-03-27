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
    # Exact filenames that are always project-specific
    case "$p" in
        README.md|pyproject.toml|config.toml|mkdocs.yml|uv.lock) return 0 ;;
    esac
    # Directory prefixes to ignore entirely
    case "$p" in
        .git/*|.venv/*|.uv-cache/*|__pycache__/*|logs/*|site/*) return 0 ;;
        .pytest_cache/*|.ruff_cache/*|prompt/*|skills/*) return 0 ;;
    esac
    # File patterns to ignore
    case "$p" in
        *.pyc|*.egg-info|.env|.env.*) return 0 ;;
    esac
    return 1
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

count_changed=0
count_new=0
count_accepted=0
count_user_skipped=0

# ──────────────────────────────────────────────────────────────
# Walk every file in the template
# ──────────────────────────────────────────────────────────────
while IFS= read -r rel_path; do

    if ! $SHOW_ALL && _is_skipped "$rel_path"; then
        continue
    fi

    local_file="$LOCAL_ROOT/$rel_path"
    tmpl_file="$TEMPLATE_ROOT/$rel_path"

    # ── New file (exists in template but not locally) ──────────
    if [ ! -f "$local_file" ]; then
        ((count_new++)) || true
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "📄 NEW FILE: $rel_path"
        echo "   (this file does not exist locally)"
        printf "   Add this file? [y/N] "
        read -r choice </dev/tty
        case "$choice" in
            y|Y)
                mkdir -p "$(dirname "$local_file")"
                cp "$tmpl_file" "$local_file"
                echo "   ✅ Added."
                ((count_accepted++)) || true
                ;;
            *)
                echo "   ⏭  Skipped."
                ((count_user_skipped++)) || true
                ;;
        esac
        echo ""
        continue
    fi

    # ── Identical — nothing to do ──────────────────────────────
    if diff -q "$local_file" "$tmpl_file" > /dev/null 2>&1; then
        continue
    fi

    # ── Changed ────────────────────────────────────────────────
    ((count_changed++)) || true
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📝 CHANGED: $rel_path"
    echo "   (--- local file   +++ template)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    # shellcheck disable=SC2086
    diff $DIFF_COLOR_FLAG -u "$local_file" "$tmpl_file" || true
    echo ""
    printf "Update local file? [y/N/q(uit)] "
    read -r choice </dev/tty
    case "$choice" in
        y|Y)
            cp "$tmpl_file" "$local_file"
            echo "✅ Updated: $rel_path"
            ((count_accepted++)) || true
            ;;
        q|Q)
            echo ""
            echo "Aborted by user."
            exit 0
            ;;
        *)
            echo "⏭  Skipped."
            ((count_user_skipped++)) || true
            ;;
    esac
    echo ""

done < <(
    find "$TEMPLATE_ROOT" -type f \
        ! -path '*/.git/*' \
        | sed "s|$TEMPLATE_ROOT/||" \
        | sort
)

# ──────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
total_found=$(( count_changed + count_new ))
if [ "$total_found" -eq 0 ]; then
    echo "✨ Everything is up to date with the template."
else
    echo "Summary: $count_changed changed + $count_new new file(s) found."
    echo "         $count_accepted accepted, $count_user_skipped skipped."
fi
