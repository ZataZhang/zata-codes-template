#!/usr/bin/env bash
# 分支清单：输出每个本地分支相对主分支的状态，供 rebase-merge-branches 工作流第一步使用
# 用法: bash branch_inventory.sh [主分支名]  （缺省自动探测 main 或 master）
set -euo pipefail

main_branch="${1:-}"
if [[ -z "$main_branch" ]]; then
  if git show-ref --verify --quiet refs/heads/main; then
    main_branch="main"
  elif git show-ref --verify --quiet refs/heads/master; then
    main_branch="master"
  else
    echo "error: 未找到 main/master 分支，请把主分支名作为第一个参数传入" >&2
    exit 1
  fi
elif ! git show-ref --verify --quiet "refs/heads/$main_branch"; then
  echo "error: 分支 '$main_branch' 不存在" >&2
  exit 1
fi

uncommitted_count="$(git status --porcelain | wc -l | tr -d ' ')"
worktree_count="$(git worktree list | wc -l | tr -d ' ')"

# 收集已被 linked worktree 占用的分支名
occupied_branches="$(git worktree list --porcelain | sed -n 's|^branch refs/heads/||p' || true)"

echo "main_branch=$main_branch"
echo "uncommitted_changes=$uncommitted_count"
echo "worktree_count=$worktree_count"

git for-each-ref --sort=committerdate --format='%(refname:short)' refs/heads/ |
while read -r branch_name; do
  [[ "$branch_name" == "$main_branch" ]] && continue
  branch_commit_counts="$(git rev-list --left-right --count "$main_branch...$branch_name")"
  behind_count="${branch_commit_counts%%$'\t'*}"
  ahead_count="${branch_commit_counts##*$'\t'}"
  merged="no"
  if git merge-base --is-ancestor "$branch_name" "$main_branch" 2>/dev/null; then
    merged="yes"
  fi
  in_worktree="no"
  if printf '%s\n' "$occupied_branches" | grep -Fxq "$branch_name"; then
    in_worktree="yes"
  fi
  echo "branch=$branch_name ahead=$ahead_count behind=$behind_count merged=$merged in_worktree=$in_worktree"
done

echo "done"
