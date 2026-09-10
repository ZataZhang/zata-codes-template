---
name: rebase-merge-branches
description: "[Updated 2026-09-10] Serially rebase-merge all local branches into main with linear history, detect duplicate fixes produced by parallel worktree/agent work, run tests after each merge, then safely delete merged branches. Use when the user asks to merge branches into main via rebase, consolidate or clean up local branches, sync worktree branches back to main, or prune stale branches after parallel agent work."
---

# Rebase-Merge Branches

## Overview

Serially rebase-merge every local branch into the main branch (linear history, no merge commits), then delete branches that are fully merged. Designed for repos with parallel worktree/agent work, where multiple branches often contain duplicate fixes for the same bug.

This workflow is judgment-heavy: conflicts, ambiguous duplicates, and anything destructive go back to the user. Only mechanical steps are automated.

## Hard Boundaries

Never do any of these without an explicit instruction in the current conversation:

- `git push` of any kind, or changes to remote branches
- `git branch -D` / `--delete --force`; only `git branch -d` is allowed
- `git reset --hard`, `git clean`, `git checkout -- <path>`, `git restore` on user changes
- Silently resolving a rebase conflict or silently choosing between duplicate implementations
- Deleting or rebasing a branch that is checked out in another worktree

## Phase 1: Pre-flight

1. Run `git status --porcelain`. If uncommitted changes exist, stop, list them, and ask: commit, stash, or abort.
2. Identify the main branch (`main` or `master`). If both exist or neither, ask.
3. Run the inventory script from this skill directory:
   ```bash
   bash scripts/branch_inventory.sh [main-branch]
   ```
   It prints one `key=value` line per local branch (`ahead`/`behind` vs main, `merged`, `in_worktree`) plus `uncommitted_changes` and `worktree_count`.
4. Run `git worktree list` and note linked worktrees.

Classify each branch from the inventory:

| Inventory result | Meaning | Action |
|---|---|---|
| `ahead=0 behind=0` | Identical to main | Deletion candidate |
| `ahead=0 behind>0 merged=yes` | Already contained in main | Deletion candidate |
| `ahead>0 merged=no` | Has unique commits | Needs rebase-merge |
| `in_worktree=yes` | Checked out in a worktree | See Worktrees section first |

## Phase 2: Merge Plan

1. Present the inventory to the user and propose a merge order. Default order: oldest commit date first, so the earliest fix lands and later duplicates get auto-skipped by rebase.
2. Ask which branches to discard without merging and which to prioritize. When branches overlap, merge the most complete/authoritative implementation first.
3. Detect likely duplicate work before merging: run `git log main..BRANCH --oneline` for each branch and flag branches whose subjects look like the same fix (e.g. several `fix:` commits for one bug).

## Phase 3: Serial Rebase-Merge Loop

Process one branch at a time, always rebasing onto the **latest** main:

```bash
git log main..BRANCH --oneline    # review what will land
git checkout BRANCH
git rebase main                   # conflict → stop and ask (below)
git checkout main
git merge --ff-only BRANCH        # must fast-forward; never a merge commit
```

After each successful merge, run the project's test suite (or at least the tests covering the merged files). If tests fail, stop and report before touching the next branch.

Interpret rebase output:

- All commits applied → proceed.
- `skipping previously applied commit` / `dropping <commit>` → git auto-skipped a duplicate fix. Record it for the report.
- Branch became empty (every commit already in main) → skip merging, mark as deletion candidate.
- `git merge --ff-only` fails → something is wrong (main moved or history diverged); stop and report, do not force.

### Rebase conflicts

On conflict:

1. Never pick a side silently. Show the user `git status` and the conflicted hunks.
2. Offer: resolve manually with user guidance, or `git rebase --abort` to skip this branch entirely.
3. Run `git rebase --continue` only after the user approves the resolution.

### Duplicate fixes with different implementations

When two branches fix the same bug differently, the second one will conflict or leave redundant code after the first lands:

1. Stop before merging the second branch.
2. Show both implementations (diffs or relevant files) side by side and ask the user which to keep.
3. Merge the chosen one; discard the other per the user's decision.

## Phase 4: Cleanup

1. Delete only after all approved merges are done:
   ```bash
   git branch -d BRANCH
   ```
2. If `-d` refuses (branch not fully merged), list the branch and ask. Use `-D` only with explicit per-branch approval.
3. Never delete a branch checked out in a worktree. Report it and let the user decide whether to remove the worktree first (non-forced `git worktree remove` only, and only when its working tree is clean).

## Phase 5: Final Report

最终汇报必须使用中文，结构如下：

```text
## 分支合并报告

处理结果（每分支一行）: 已合并 / 空分支跳过 / 冲突中止 / 用户放弃
被 git 自动跳过的重复提交: 列出，无则写"无"
删除的分支: 列出
未删除的分支及原因: worktree 占用 / 未合并待确认
main 最新提交: git log --oneline -10 的输出
测试状态: ✅/⚠️ + 实际执行的命令
```

## Resources

- `scripts/branch_inventory.sh` — branch inventory for Phase 1. Usage: `bash scripts/branch_inventory.sh [main-branch]`. Exits non-zero on git errors; all branch lines are machine-readable `key=value` pairs.
