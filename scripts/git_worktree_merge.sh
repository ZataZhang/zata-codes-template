#!/usr/bin/env bash
set -euo pipefail

# git_worktree_merge.sh
# Purpose:
#   Merge a feature branch into a base branch (default: main), then push.
#
# Parameters:
#   1) <feature_branch>            Required. Branch to be merged.
#   2) [base_branch]               Optional. Target branch. Default: main.
#   3) --remote <name>             Optional. Remote name. Default: zata.
#   4) -d, --delete, --delete-only Optional flag. Skip merge/push, only cleanup.
#   5) --cleanup                   Optional flag. After successful merge/push:
#                                  remove worktree and delete local feature branch.
#   6) --delete-remote             Optional flag. Delete remote feature branch.
#                                  Note: effective only when --cleanup is enabled.
#                                  Also works with -d/--delete/--delete-only.
#   7) --worktree-path <path>      Optional. Worktree path used by cleanup.
#                                  Default: auto-detect by <feature_branch>,
#                                           fallback: $(dirname repo_root)/<feature_branch>
#   8) -h, --help                  Show help and exit.
#
# Preconditions:
#   - Must run inside a Git repository.
#   - Merge mode requires a clean working tree.
#   - Merge mode requires local feature/base branches to exist.
#
resolve_worktree_path_by_branch() {
    local target_branch="$1"
    local target_branch_ref="refs/heads/$target_branch"
    local resolved_worktree_path=""
    resolved_worktree_path="$(
        git worktree list --porcelain | awk -v target_branch_ref="$target_branch_ref" '
            $1 == "worktree" {
                current_worktree_path = $2
            }
            $1 == "branch" {
                if ($2 == target_branch_ref) {
                    print current_worktree_path
                    exit
                }
            }
        '
    )"
    printf '%s' "$resolved_worktree_path"
}

usage() {
    cat <<'EOF'
Usage:
  git_worktree_merge.sh <feature_branch> [base_branch] [--remote <name>] [-d|--delete|--delete-only] [--cleanup] [--delete-remote] [--worktree-path <path>]

Arguments:
  <feature_branch>       Required. The feature branch to merge.
  [base_branch]          Optional. The target branch. Defaults to main.

Options:
  --remote <name>       Remote name to pull/push. Default: zata.
  -d, --delete, --delete-only
                        Skip merge/push and only run cleanup for the feature branch.
  --cleanup              Remove worktree and delete local feature branch after merge succeeds.
  --delete-remote        Delete <remote>/<feature_branch> (works with --cleanup/-d/--delete/--delete-only).
  --worktree-path <path> Explicit worktree path to remove during cleanup.
                         Default: auto-detect by <feature_branch>, fallback parent_of_repo_root/<feature_branch>
  -h, --help             Show this help message.

Checks before merge:
  - Current directory must be in a Git repository.
  - Working tree must be clean.
  - Local <feature_branch> and [base_branch] must exist.

Examples:
  ./scripts/git_worktree_merge.sh feature-login
  ./scripts/git_worktree_merge.sh feature-login main --cleanup
  ./scripts/git_worktree_merge.sh feature-login -d
  ./scripts/git_worktree_merge.sh feature-login --delete
  ./scripts/git_worktree_merge.sh feature-login main --remote zata --cleanup
  ./scripts/git_worktree_merge.sh feature-login main --cleanup --delete-remote
EOF
}

if [[ $# -ge 1 && ( "$1" == "-h" || "$1" == "--help" ) ]]; then
    usage
    exit 0
fi

if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

feature_branch="$1"
shift
base_branch="main"
remote_name="zata"
delete_only_mode="false"
cleanup_mode="false"
delete_remote_branch="false"
worktree_path=""

if [[ $# -gt 0 && "$1" != -* ]]; then
    base_branch="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case "$1" in
        --cleanup)
            cleanup_mode="true"
            ;;
        -d|--delete|--delete-only)
            delete_only_mode="true"
            cleanup_mode="true"
            ;;
        --remote)
            if [[ $# -lt 2 ]]; then
                echo "❌ --remote requires a remote name."
                exit 1
            fi
            remote_name="$2"
            shift
            ;;
        --delete-remote)
            delete_remote_branch="true"
            ;;
        --worktree-path)
            if [[ $# -lt 2 ]]; then
                echo "❌ --worktree-path requires a path value."
                exit 1
            fi
            worktree_path="$2"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            usage
            exit 1
            ;;
    esac
    shift
done

if [[ "$feature_branch" == "$base_branch" ]]; then
    echo "❌ feature_branch and base_branch cannot be the same: $feature_branch"
    exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "❌ Current directory is not inside a Git repository."
    exit 1
fi

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

cleanup_feature_branch() {
    local resolved_cleanup_worktree_path="$worktree_path"
    local current_checked_out_branch=""

    if [[ -z "$resolved_cleanup_worktree_path" ]]; then
        resolved_cleanup_worktree_path="$(resolve_worktree_path_by_branch "$feature_branch")"
        if [[ -z "$resolved_cleanup_worktree_path" ]]; then
            resolved_cleanup_worktree_path="$(dirname "$repo_root")/$feature_branch"
        fi
    fi

    current_checked_out_branch="$(git symbolic-ref --short -q HEAD || true)"
    if [[ "$current_checked_out_branch" == "$feature_branch" ]]; then
        if git show-ref --verify --quiet "refs/heads/$base_branch"; then
            git checkout "$base_branch"
        else
            echo "❌ Cannot cleanup checked-out branch '$feature_branch' because base branch '$base_branch' does not exist."
            exit 1
        fi
    fi

    echo "🧹 Cleanup enabled."
    if git worktree list --porcelain | grep -Fq "worktree $resolved_cleanup_worktree_path"; then
        git worktree remove "$resolved_cleanup_worktree_path"
        echo "✅ Removed worktree: $resolved_cleanup_worktree_path"
    else
        echo "⚠️ Worktree not found, skipped: $resolved_cleanup_worktree_path"
    fi

    if git show-ref --verify --quiet "refs/heads/$feature_branch"; then
        git branch -d "$feature_branch"
        echo "✅ Deleted local branch: $feature_branch"
    else
        echo "⚠️ Local branch not found, skipped: $feature_branch"
    fi

    if [[ "$delete_remote_branch" == "true" ]]; then
        if ! git remote get-url "$remote_name" >/dev/null 2>&1; then
            echo "❌ Remote not found: $remote_name"
            exit 1
        fi

        if git push "$remote_name" --delete "$feature_branch"; then
            echo "✅ Deleted remote branch: $feature_branch"
        else
            echo "⚠️ Remote branch delete failed or branch not found on remote: $feature_branch"
        fi
    fi
}

if [[ "$delete_only_mode" == "true" ]]; then
    echo "🗑️ Delete-only mode enabled. Skipping merge and push."
    cleanup_feature_branch
    echo "✅ Delete-only flow completed successfully."
    exit 0
fi

if [[ -n "$(git status --porcelain)" ]]; then
    echo "❌ Working tree is not clean. Please commit/stash changes before merging."
    exit 1
fi

if ! git show-ref --verify --quiet "refs/heads/$feature_branch"; then
    echo "❌ Local feature branch not found: $feature_branch"
    exit 1
fi

if ! git show-ref --verify --quiet "refs/heads/$base_branch"; then
    echo "❌ Local base branch not found: $base_branch"
    exit 1
fi

if ! git remote get-url "$remote_name" >/dev/null 2>&1; then
    echo "❌ Remote not found: $remote_name"
    exit 1
fi

echo "🚀 Switching to $base_branch and updating from $remote_name..."
git checkout "$base_branch"
git pull --ff-only "$remote_name" "$base_branch"

echo "🔀 Merging $feature_branch into $base_branch..."
git merge --no-ff "$feature_branch"

echo "📤 Pushing $base_branch to $remote_name..."
git push "$remote_name" "$base_branch"

if [[ "$cleanup_mode" == "true" ]]; then
    cleanup_feature_branch
fi

echo "✅ Merge flow completed successfully."
