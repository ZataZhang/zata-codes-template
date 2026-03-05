#!/usr/bin/env bash

# 将此函数放入 .zshrc 或 .bashrc
# 用法:
#   source ./scripts/git_worktree.sh && ai_worktree <新分支名> [--cmd [code_cmd]]
#   或直接执行:
#   ./scripts/git_worktree.sh <新分支名> [--cmd [code_cmd]]

ai_worktree_usage() {
    cat <<'EOF'
Usage:
  ai_worktree <new_branch_name> [--cmd [code_cmd]]

Options:
  --cmd [code_cmd]  创建完成后自动执行: <code_cmd> --add <worktree_path>
                    不传 code_cmd 时默认使用: code
  -h, --help        显示帮助

Examples:
  ai_worktree feature-login
  ai_worktree feature-login --cmd
  ai_worktree feature-login --cmd code-insiders
  ./scripts/git_worktree.sh feature-login
  ./scripts/git_worktree.sh feature-login --cmd
  ./scripts/git_worktree.sh feature-login --cmd code-insiders
EOF
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

install_frontend_dependencies() {
    # Priority: lock-file driven install for reproducible frontend environments.
    if [ -f pnpm-lock.yaml ]; then
        if ! command_exists pnpm; then
            echo "⚠️ 检测到 pnpm-lock.yaml，但未找到 pnpm，跳过前端依赖安装。"
            return 0
        fi
        echo "📦 检测到 pnpm-lock.yaml，正在执行 pnpm install --ignore-scripts ..."
        if ! pnpm install --ignore-scripts; then
            echo "❌ pnpm install 失败。"
            return 1
        fi
        return 0
    fi

    if [ -f package-lock.json ]; then
        if ! command_exists npm; then
            echo "⚠️ 检测到 package-lock.json，但未找到 npm，跳过前端依赖安装。"
            return 0
        fi
        echo "📦 检测到 package-lock.json，正在执行 npm ci --ignore-scripts ..."
        if ! npm ci --ignore-scripts; then
            echo "❌ npm ci 失败。"
            return 1
        fi
        return 0
    fi

    if [ -f yarn.lock ]; then
        if ! command_exists yarn; then
            echo "⚠️ 检测到 yarn.lock，但未找到 yarn，跳过前端依赖安装。"
            return 0
        fi
        echo "📦 检测到 yarn.lock，正在执行 yarn install --ignore-scripts ..."
        if ! yarn install --ignore-scripts; then
            echo "❌ yarn install 失败。"
            return 1
        fi
        return 0
    fi

    if [ -f bun.lock ] || [ -f bun.lockb ]; then
        if ! command_exists bun; then
            echo "⚠️ 检测到 bun lock 文件，但未找到 bun，跳过前端依赖安装。"
            return 0
        fi
        echo "📦 检测到 bun lock 文件，正在执行 bun install --ignore-scripts ..."
        if ! bun install --ignore-scripts; then
            echo "❌ bun install 失败。"
            return 1
        fi
        return 0
    fi

    if [ -f package.json ]; then
        if ! command_exists npm; then
            echo "⚠️ 检测到 package.json，但未找到 npm，跳过前端依赖安装。"
            return 0
        fi
        echo "📦 检测到 package.json（无 lock 文件），正在执行 npm install --ignore-scripts ..."
        if ! npm install --ignore-scripts; then
            echo "❌ npm install 失败。"
            return 1
        fi
    fi

    return 0
}

install_python_dependencies() {
    if [ ! -f pyproject.toml ]; then
        return 0
    fi

    if ! command_exists uv; then
        echo "⚠️ 检测到 pyproject.toml，但未找到 uv，跳过 Python 依赖安装。"
        return 0
    fi

    echo "📦 检测到 pyproject.toml，正在执行 uv sync --all-extras ..."
    if ! uv sync --all-extras; then
        echo "❌ uv sync 失败。"
        return 1
    fi
    return 0
}

function ai_worktree() {
    local branch_name=""
    local enable_vscode_add="false"
    local vscode_command_name="code"
    local repo_root_path=""
    local repo_parent_path=""
    local target_abs_path=""
    local source_env_example_path=""
    local copied_env_file_count=0
    local source_env_file_path=""
    local relative_env_file_path=""
    local target_env_file_path=""

    while [ "$#" -gt 0 ]; do
        case "$1" in
            -h|--help)
                ai_worktree_usage
                return 0
                ;;
            --cmd)
                enable_vscode_add="true"
                if [ "$#" -gt 1 ] && [[ "$2" != -* ]]; then
                    vscode_command_name="$2"
                    shift
                fi
                ;;
            --cmd=*)
                enable_vscode_add="true"
                vscode_command_name="${1#--cmd=}"
                if [ -z "$vscode_command_name" ]; then
                    echo "❌ --cmd= 后需要提供命令名，例如: --cmd=code-insiders"
                    return 1
                fi
                ;;
            -*)
                echo "❌ 未知参数: $1"
                ai_worktree_usage
                return 1
                ;;
            *)
                if [ -z "$branch_name" ]; then
                    branch_name="$1"
                else
                    echo "❌ 只允许一个分支名参数，收到多余参数: $1"
                    ai_worktree_usage
                    return 1
                fi
                ;;
        esac
        shift
    done

    if [ -z "$branch_name" ]; then
        echo "请提供分支名称！例如: ai_worktree feature-login"
        ai_worktree_usage
        return 1
    fi

    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "❌ 当前目录不是 Git 仓库，无法创建 worktree。"
        return 1
    fi

    repo_root_path="$(git rev-parse --show-toplevel)"
    repo_parent_path="$(dirname "$repo_root_path")"
    # 1. 约定 worktree 建立在仓库根目录上级的同名文件夹中
    target_abs_path="$repo_parent_path/$branch_name"
    if [ -e "$target_abs_path" ]; then
        echo "❌ 目标目录已存在: $target_abs_path"
        return 1
    fi

    echo "🚀 正在创建 Git Worktree: $target_abs_path ..."
    if ! git -C "$repo_root_path" worktree add -b "$branch_name" "$target_abs_path" main; then
        echo "❌ Git worktree 创建失败。"
        return 1
    fi

    echo "🔗 正在处理 .env ..."
    # 2. 复制仓库中所有以 .env 结尾的文件（保持相对路径），避免子目录环境文件丢失
    copied_env_file_count=0
    while IFS= read -r source_env_file_path; do
        relative_env_file_path="${source_env_file_path#"$repo_root_path"/}"
        target_env_file_path="$target_abs_path/$relative_env_file_path"
        mkdir -p "$(dirname "$target_env_file_path")"
        cp "$source_env_file_path" "$target_env_file_path"
        copied_env_file_count=$((copied_env_file_count + 1))
    done < <(
        find "$repo_root_path" -type f -name ".env*" \
            -not -path "$repo_root_path/.git/*" \
            -not -path "$repo_root_path/.venv/*" \
            -not -path "$repo_root_path/.uv-cache/*" \
            -not -path "$repo_root_path/site/*"
    )

    source_env_example_path="$repo_root_path/.env.example"
    if [ "$copied_env_file_count" -gt 0 ]; then
        echo "✅ 已复制 $copied_env_file_count 个 .env 文件到新 worktree。"
    elif [ -f "$source_env_example_path" ]; then
        cp "$source_env_example_path" "$target_abs_path/.env"
        echo "⚠️ 仓库根目录没有 .env，已使用 .env.example 创建 .env。"
    else
        echo "⚠️ 仓库根目录未找到 .env/.env.example，跳过。"
    fi

    # 3. 自动安装依赖 (极速模式)
    echo "📦 正在使用全局缓存安装依赖 ..."
    if ! cd "$target_abs_path"; then
        echo "❌ 无法进入目录: $target_abs_path"
        return 1
    fi

    if ! install_frontend_dependencies; then
        return 1
    fi

    if ! install_python_dependencies; then
        return 1
    fi

    if [ "$enable_vscode_add" = "true" ]; then
        if ! command -v "$vscode_command_name" >/dev/null 2>&1; then
            echo "❌ 未找到命令: $vscode_command_name"
            echo "   请确认该 CLI 已安装并在 PATH 中。"
            return 1
        fi
        if ! "$vscode_command_name" --add "$target_abs_path"; then
            echo "❌ 执行失败: $vscode_command_name --add \"$target_abs_path\""
            return 1
        fi
        echo "🧩 已将目录加入工作区: $target_abs_path"
    fi

    echo "✅ 准备完毕！AI 可以开始在 $target_abs_path 愉快地写代码了。"
}

# If executed directly with bash, run ai_worktree with all CLI args.
# If sourced in shell profile, only function definitions are loaded.
if [ -n "${BASH_VERSION:-}" ] && [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    ai_worktree "$@"
fi
