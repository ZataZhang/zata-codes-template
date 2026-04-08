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
# Skip rules — files that should never or optionally be synced
# ──────────────────────────────────────────────────────────────
_is_never_synced() {
    local p="$1"
    case "$p" in
        tasks/*) return 0 ;;
    esac
    return 1
}

_is_skipped_by_default() {
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
# Justfile recipe-level helper (written once to $TEMP_DIR)
# ──────────────────────────────────────────────────────────────
JF_HELPER="$TEMP_DIR/jf.py"
cat > "$JF_HELPER" << 'PYEOF'
#!/usr/bin/env python3
"""Justfile recipe parser used by sync_template.sh.

Commands:
  names  <file>              print all recipe names, one per line
  block  <file> <name>       print the full block for a recipe (with preceding comments)
  append <file>              append stdin content to file
  replace <file> <name>      replace a recipe block with stdin content
"""
import sys, re

RECIPE_RE = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_-]*)[^\S\n]*[^:\n]*:(?![=])')
ASSIGN_RE = re.compile(r'^[a-zA-Z_]\w*\s*(:=|::=)')


def read_lines(path: str) -> list[str]:
    with open(path, encoding="utf-8") as f:
        return f.readlines()


def find_headers(lines: list[str]) -> list[tuple[int, str]]:
    """Return [(line_idx, recipe_name), ...] for every recipe header."""
    headers = []
    for i, line in enumerate(lines):
        m = RECIPE_RE.match(line)
        if m and not ASSIGN_RE.match(line):
            headers.append((i, m.group(1)))
    return headers


def block_range(lines: list[str], headers: list[tuple[int, str]], pos: int) -> tuple[int, int]:
    """Return (start, end) line indices for the recipe block at headers[pos].

    'start' walks back to include preceding comment/blank lines.
    'end' is the line just before the next recipe's comment block.
    """
    line_idx = headers[pos][0]
    start = line_idx
    while start > 0:
        prev = lines[start - 1]
        if prev.startswith("#") or prev.strip() == "":
            start -= 1
        else:
            break
    if pos + 1 < len(headers):
        end = headers[pos + 1][0]
        while end > line_idx + 1 and lines[end - 1].strip() == "":
            end -= 1
    else:
        end = len(lines)
    return start, end


if __name__ == "__main__":
    cmd = sys.argv[1]

    if cmd == "names":
        lines = read_lines(sys.argv[2])
        for _, name in find_headers(lines):
            print(name)

    elif cmd == "block":
        lines = read_lines(sys.argv[2])
        headers = find_headers(lines)
        for pos, (_, name) in enumerate(headers):
            if name == sys.argv[3]:
                s, e = block_range(lines, headers, pos)
                sys.stdout.write("".join(lines[s:e]))
                sys.exit(0)
        sys.exit(1)  # recipe not found

    elif cmd == "append":
        content = sys.stdin.read()
        with open(sys.argv[2], "a", encoding="utf-8") as f:
            if content and not content.startswith("\n"):
                f.write("\n")
            f.write(content)

    elif cmd == "replace":
        content = sys.stdin.read()
        lines = read_lines(sys.argv[2])
        headers = find_headers(lines)
        for pos, (_, name) in enumerate(headers):
            if name == sys.argv[3]:
                s, e = block_range(lines, headers, pos)
                with open(sys.argv[2], "w", encoding="utf-8") as f:
                    f.writelines(lines[:s])
                    f.write(content)
                    f.writelines(lines[e:])
                sys.exit(0)
        sys.exit(1)
PYEOF

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
# Phase 1: Scan — collect changed / new entries
#
# Normal files   → "changed" or "new" entry with the rel path
# justfile       → expanded into per-recipe entries: "justfile::recipe-name"
#                  (new file → single "justfile" entry, no expansion needed)
# ──────────────────────────────────────────────────────────────
changed_entries=()  # may include "justfile::recipe" entries
new_entries=()

while IFS= read -r rel_path; do
    if _is_never_synced "$rel_path"; then
        continue
    fi

    if ! $SHOW_ALL && _is_skipped_by_default "$rel_path"; then
        continue
    fi

    local_file="$LOCAL_ROOT/$rel_path"
    tmpl_file="$TEMPLATE_ROOT/$rel_path"

    # ── New file ──────────────────────────────────────────────
    if [ ! -f "$local_file" ]; then
        new_entries+=("$rel_path")
        continue
    fi

    # ── Identical ─────────────────────────────────────────────
    if diff -q "$local_file" "$tmpl_file" > /dev/null 2>&1; then
        continue
    fi

    # ── Changed: justfile gets recipe-level expansion ─────────
    if [ "$rel_path" = "justfile" ]; then
        # macOS ships Bash 3.2, so avoid Bash 4-only mapfile/readarray here.
        local_recipes=()
        while IFS= read -r recipe_name; do
            local_recipes+=("$recipe_name")
        done < <(python3 "$JF_HELPER" names "$local_file" 2>/dev/null || true)

        tmpl_recipes=()
        while IFS= read -r recipe_name; do
            tmpl_recipes+=("$recipe_name")
        done < <(python3 "$JF_HELPER" names "$tmpl_file" 2>/dev/null || true)

        for recipe in "${tmpl_recipes[@]}"; do
            local_block=$(python3 "$JF_HELPER" block "$local_file" "$recipe" 2>/dev/null || true)
            tmpl_block=$(python3  "$JF_HELPER" block "$tmpl_file"  "$recipe" 2>/dev/null || true)

            if [ -z "$local_block" ]; then
                new_entries+=("justfile::$recipe")
            elif [ "$local_block" != "$tmpl_block" ]; then
                changed_entries+=("justfile::$recipe")
            fi
        done
        continue
    fi

    # ── Changed: normal file ──────────────────────────────────
    changed_entries+=("$rel_path")

done < <(
    find "$TEMPLATE_ROOT" -type f \
        ! -path '*/.git/*' \
        | sed "s|$TEMPLATE_ROOT/||" \
        | sort
)

total_found=$(( ${#changed_entries[@]} + ${#new_entries[@]} ))

if [ "$total_found" -eq 0 ]; then
    echo "✨ Everything is up to date with the template."
    exit 0
fi

echo "Found ${#changed_entries[@]} changed + ${#new_entries[@]} new entry/entries."
echo ""

# ──────────────────────────────────────────────────────────────
# Phase 2: Select — fzf UI or numbered fallback
# ──────────────────────────────────────────────────────────────

# Build tab-separated display lines: "<icon> <label>\t<entry>"
file_list_lines=()
for e in "${changed_entries[@]}"; do
    if [[ "$e" == justfile::* ]]; then
        file_list_lines+=("📝 CHANGED	$e")
    else
        file_list_lines+=("📝 CHANGED	$e")
    fi
done
for e in "${new_entries[@]}"; do
    file_list_lines+=("📄 NEW    	$e")
done

selected_entries=()

if _ensure_fzf; then
    # ── fzf interactive mode ──────────────────────────────────
    export FZF_SYNC_LOCAL="$LOCAL_ROOT"
    export FZF_SYNC_TMPL="$TEMPLATE_ROOT"
    export FZF_JF_HELPER="$JF_HELPER"

    preview_cmd='
        entry=$(echo {} | cut -f2)
        if [[ "$entry" == justfile::* ]]; then
            recipe="${entry#justfile::}"
            local_block=$(python3 "$FZF_JF_HELPER" block "$FZF_SYNC_LOCAL/justfile" "$recipe" 2>/dev/null || true)
            tmpl_block=$(python3  "$FZF_JF_HELPER" block "$FZF_SYNC_TMPL/justfile"  "$recipe" 2>/dev/null || true)
            if [ -z "$local_block" ]; then
                echo "(new recipe — template content:)"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                echo "$tmpl_block"
            else
                diff '"$DIFF_COLOR_FLAG"' -u \
                    <(echo "$local_block") \
                    <(echo "$tmpl_block") || true
            fi
        else
            local_f="$FZF_SYNC_LOCAL/$entry"
            tmpl_f="$FZF_SYNC_TMPL/$entry"
            if [ ! -f "$local_f" ]; then
                echo "(new file — template content:)"
                echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                cat "$tmpl_f"
            else
                diff '"$DIFF_COLOR_FLAG"' -u "$local_f" "$tmpl_f" || true
            fi
        fi
    '

    selected_lines=()
    while IFS= read -r selected_line; do
        selected_lines+=("$selected_line")
    done < <(
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
            --prompt='Select entries > ' \
        || true
    )

    for line in "${selected_lines[@]}"; do
        selected_entries+=("$(echo "$line" | cut -f2)")
    done

else
    # ── Numbered list fallback ────────────────────────────────
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    idx=1
    entry_map=()
    for e in "${changed_entries[@]}"; do
        if [[ "$e" == justfile::* ]]; then
            printf "  [%2d] 📝 CHANGED  %s\n" "$idx" "${e/justfile::/justfile (recipe: }"
        else
            printf "  [%2d] 📝 CHANGED  %s\n" "$idx" "$e"
        fi
        entry_map[$idx]="$e"
        ((idx++))
    done
    for e in "${new_entries[@]}"; do
        if [[ "$e" == justfile::* ]]; then
            printf "  [%2d] 📄 NEW      %s\n" "$idx" "${e/justfile::/justfile (recipe: }"
        else
            printf "  [%2d] 📄 NEW      %s\n" "$idx" "$e"
        fi
        entry_map[$idx]="$e"
        ((idx++))
    done

    echo ""
    echo "Enter numbers to update (e.g. 1 3 5), 'all', or 'q' to quit."
    echo "Prefix with 'd' to preview diff (e.g. d2)."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    _show_entry_diff() {
        local entry="$1"
        if [[ "$entry" == justfile::* ]]; then
            local recipe="${entry#justfile::}"
            local local_block tmpl_block
            local_block=$(python3 "$JF_HELPER" block "$LOCAL_ROOT/justfile" "$recipe" 2>/dev/null || true)
            tmpl_block=$(python3  "$JF_HELPER" block "$TEMPLATE_ROOT/justfile" "$recipe" 2>/dev/null || true)
            if [ -z "$local_block" ]; then
                echo "(new recipe)"; echo "$tmpl_block"
            else
                # shellcheck disable=SC2086
                diff $DIFF_COLOR_FLAG -u <(echo "$local_block") <(echo "$tmpl_block") || true
            fi
        else
            local local_f="$LOCAL_ROOT/$entry" tmpl_f="$TEMPLATE_ROOT/$entry"
            if [ ! -f "$local_f" ]; then
                echo "(new file)"; cat "$tmpl_f"
            else
                # shellcheck disable=SC2086
                diff $DIFF_COLOR_FLAG -u "$local_f" "$tmpl_f" || true
            fi
        fi
    }

    while true; do
        printf "Your choice: "
        read -r input </dev/tty
        case "$input" in
            q|Q) echo "Aborted."; exit 0 ;;
            all|ALL)
                for key in "${!entry_map[@]}"; do selected_entries+=("${entry_map[$key]}"); done
                break
                ;;
            d\ *|d[0-9]*)
                num="${input#d }"; num="${num#d}"; num="${num// /}"
                if [ -n "${entry_map[$num]+_}" ]; then
                    echo ""; echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    _show_entry_diff "${entry_map[$num]}"
                    echo ""
                else
                    echo "  Invalid number: $num"
                fi
                ;;
            "") echo "  Nothing selected." ;;
            *)
                valid=true; nums=()
                for num in $input; do
                    if [ -n "${entry_map[$num]+_}" ]; then nums+=("$num")
                    else echo "  Invalid number: $num"; valid=false; fi
                done
                if $valid; then
                    for num in "${nums[@]}"; do selected_entries+=("${entry_map[$num]}"); done
                    break
                fi
                ;;
        esac
    done
fi

# ──────────────────────────────────────────────────────────────
# Phase 3: Apply selected entries
# ──────────────────────────────────────────────────────────────
if [ "${#selected_entries[@]}" -eq 0 ]; then
    echo "Nothing selected. No changes applied."
    exit 0
fi

echo ""
count_accepted=0

# Collect justfile recipe operations separately so we apply them in one pass
jf_new_recipes=()
jf_changed_recipes=()

for entry in "${selected_entries[@]}"; do
    if [[ "$entry" == justfile::* ]]; then
        recipe="${entry#justfile::}"
        # Check if it's new or changed
        local_block=$(python3 "$JF_HELPER" block "$LOCAL_ROOT/justfile" "$recipe" 2>/dev/null || true)
        if [ -z "$local_block" ]; then
            jf_new_recipes+=("$recipe")
        else
            jf_changed_recipes+=("$recipe")
        fi
        continue
    fi

    # Normal file
    local_file="$LOCAL_ROOT/$entry"
    tmpl_file="$TEMPLATE_ROOT/$entry"
    mkdir -p "$(dirname "$local_file")"
    if [ ! -f "$local_file" ]; then
        cp "$tmpl_file" "$local_file"
        echo "  ✅ Added:   $entry"
    else
        cp "$tmpl_file" "$local_file"
        echo "  ✅ Updated: $entry"
    fi
    ((count_accepted++)) || true
done

# Apply justfile changed recipes (replace in-place)
for recipe in "${jf_changed_recipes[@]}"; do
    python3 "$JF_HELPER" block "$TEMPLATE_ROOT/justfile" "$recipe" \
        | python3 "$JF_HELPER" replace "$LOCAL_ROOT/justfile" "$recipe"
    echo "  ✅ Updated: justfile (recipe: $recipe)"
    ((count_accepted++)) || true
done

# Apply justfile new recipes (append)
for recipe in "${jf_new_recipes[@]}"; do
    python3 "$JF_HELPER" block "$TEMPLATE_ROOT/justfile" "$recipe" \
        | python3 "$JF_HELPER" append "$LOCAL_ROOT/justfile"
    echo "  ✅ Added:   justfile (recipe: $recipe)"
    ((count_accepted++)) || true
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Done. $count_accepted entry/entries applied, $(( total_found - count_accepted )) skipped."
