"""守护 zview 分支合并状态判定的守卫测试（guard test）。

本文件位于 ``tests/guards/shared/``，失败意味着源代码、配置或脚本违反了仓库约定。
正确做法是修复触发它的源代码或配置，而不是修改本文件让测试通过；仅当约定
本身需要变更时才改本文件，并同步更新相关约定文档。详见
``docs/ai-standards/testing.md`` 的 Guard Tests 小节。

被测对象：``scripts/shared/view/history.py``。核心不变量：

1. **squash 合入必须与「未合并」区分开。** 提交图上两者都是独立泳道，只有补丁内容能
   说明分支的改动已经在基准分支里。判据必须落在 ``git cherry`` 上（按 patch-id），
   不能退化成「提交说明相同」之类的猜测。
2. **领先/落后的方向不能反。** ``rev-list --left-right --count A...B`` 先输出「只在 A」
   的提交数；把两侧读反会让每个已合并分支都显示成领先。
3. **没有默认分支时不猜基准。** 找不到 ``origin/HEAD`` 或本地 ``main``/``master`` 时，
   所有分支状态都是 ``unknown``，界面不展示任何合并结论。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
VIEW_DIRECTORY = PROJECT_ROOT / "scripts" / "shared" / "view"
if str(VIEW_DIRECTORY) not in sys.path:
    # history.py 以同级模块方式导入 workspace，需要先把查看器目录放进导入路径。
    sys.path.insert(0, str(VIEW_DIRECTORY))

import history  # noqa: E402  （必须在上面的 sys.path 调整之后导入）

_GIT_ENVIRONMENT = {
    **os.environ,
    "GIT_AUTHOR_NAME": "zview test",
    "GIT_AUTHOR_EMAIL": "zview@example.invalid",
    "GIT_COMMITTER_NAME": "zview test",
    "GIT_COMMITTER_EMAIL": "zview@example.invalid",
    # 隔离本机的 git 全局配置：签名、默认分支之类的设置会让用例结果随机器漂移。
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def _run_git(repository_root: Path, *git_arguments: str) -> str:
    """在临时仓库里执行一次 git 并返回标准输出。"""
    completed_process = subprocess.run(
        ["git", *git_arguments],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        env=_GIT_ENVIRONMENT,
    )
    return completed_process.stdout


def _write_and_commit(repository_root: Path, file_name: str, content: str, message: str) -> None:
    """写一个文件并提交，模拟一次普通提交。"""
    (repository_root / file_name).write_text(content, encoding="utf-8")
    _run_git(repository_root, "add", "-A")
    _run_git(repository_root, "commit", "-m", message)


def _initialize_repository(repository_root: Path, default_branch_name: str = "main") -> None:
    """建一个有一个初始提交的临时仓库。"""
    _run_git(repository_root, "init", "-q", "-b", default_branch_name)
    _write_and_commit(repository_root, "notes.txt", "first\n", "chore: initial commit")


def _build_merge_states_by_name(repository_root: Path) -> dict[str, dict[str, object]]:
    """读取一次历史应答，把分支状态按分支名归集。"""
    history_payload = history.build_git_history_payload(repository_root, offset=0, limit=50).payload
    return {
        str(branch_ref["name"]): dict(branch_ref) for branch_ref in history_payload["branch_refs"]
    }


def test_squash_merged_branch_is_reported_as_replayed(tmp_path: Path) -> None:
    """补丁内容已进入基准分支的分支必须报 ``replayed``，而不是普通领先。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)

    _run_git(repository_root, "checkout", "-q", "-b", "codex/website-only")
    _write_and_commit(repository_root, "notes.txt", "first\nsecond\n", "feat: add second line")
    _run_git(repository_root, "checkout", "-q", "main")
    # squash 合并：补丁内容相同、提交 SHA 不同，祖先关系不成立。
    _run_git(repository_root, "cherry-pick", "codex/website-only")
    _run_git(repository_root, "commit", "-q", "--amend", "-m", "feat: add second line (#2)")

    branch_merge_state = _build_merge_states_by_name(repository_root)["codex/website-only"]

    assert branch_merge_state["merge_state"] == history.MERGE_STATE_REPLAYED
    assert branch_merge_state["ahead"] == 1


def test_ancestor_branch_is_reported_as_merged(tmp_path: Path) -> None:
    """停在基准分支祖先上的分支必须报 ``merged``。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)
    _write_and_commit(repository_root, "notes.txt", "first\nsecond\n", "feat: add second line")
    _run_git(repository_root, "branch", "feature/merged", "HEAD~1")

    branch_merge_state = _build_merge_states_by_name(repository_root)["feature/merged"]

    assert branch_merge_state["merge_state"] == history.MERGE_STATE_MERGED
    assert branch_merge_state["ahead"] == 0
    assert branch_merge_state["behind"] == 1


def test_ahead_and_behind_counts_keep_their_direction(tmp_path: Path) -> None:
    """领先数必须来自分支独有提交，落后数来自基准分支独有提交。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)

    _run_git(repository_root, "checkout", "-q", "-b", "feature/ahead")
    _write_and_commit(repository_root, "ahead.txt", "ahead\n", "feat: ahead work")
    _run_git(repository_root, "checkout", "-q", "main")

    ahead_only_state = _build_merge_states_by_name(repository_root)["feature/ahead"]
    assert ahead_only_state["merge_state"] == history.MERGE_STATE_AHEAD
    assert ahead_only_state["ahead"] == 1
    assert ahead_only_state["behind"] == 0

    _write_and_commit(repository_root, "main.txt", "main\n", "feat: main moves")
    diverged_state = _build_merge_states_by_name(repository_root)["feature/ahead"]
    assert diverged_state["merge_state"] == history.MERGE_STATE_DIVERGED
    assert diverged_state["ahead"] == 1
    assert diverged_state["behind"] == 1


def test_base_branch_is_marked_and_exposed_in_payload(tmp_path: Path) -> None:
    """基准分支自身标成 ``base``，并把基准分支名放进应答供界面汇总。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)

    history_payload = history.build_git_history_payload(repository_root, offset=0, limit=50).payload
    branch_refs_by_name = {
        str(branch_ref["name"]): branch_ref for branch_ref in history_payload["branch_refs"]
    }

    assert history_payload["base_branch"] == "main"
    assert branch_refs_by_name["main"]["merge_state"] == history.MERGE_STATE_BASE


def test_commit_rows_carry_merge_state_for_ref_badges(tmp_path: Path) -> None:
    """提交行上的引用标签也要带状态，否则提交行无法标出「已合入」。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)
    _write_and_commit(repository_root, "notes.txt", "first\nsecond\n", "feat: add second line")
    _run_git(repository_root, "branch", "feature/merged", "HEAD~1")

    history_payload = history.build_git_history_payload(repository_root, offset=0, limit=50).payload
    commit_row_refs = [
        ref_label
        for history_row in history_payload["rows"]
        if history_row["kind"] == "commit"
        for ref_label in history_row["refs"]
        if ref_label["name"] == "feature/merged"
    ]

    assert commit_row_refs
    assert all(
        ref_label["merge_state"] == history.MERGE_STATE_MERGED for ref_label in commit_row_refs
    )


def test_repository_without_default_branch_reports_unknown(tmp_path: Path) -> None:
    """没有 main/master/origin 默认分支时，不猜基准分支，全部标为未知。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root, default_branch_name="trunk")
    _run_git(repository_root, "branch", "feature/ahead")

    history_payload = history.build_git_history_payload(repository_root, offset=0, limit=50).payload

    assert history_payload["base_branch"] == ""
    assert all(
        branch_ref["merge_state"] == history.MERGE_STATE_UNKNOWN
        for branch_ref in history_payload["branch_refs"]
    )


def test_multi_commit_branch_squashed_into_one_commit_is_replayed(tmp_path: Path) -> None:
    """整条分支被 squash 成一个提交时，逐提交比对必然落空，必须靠整体补丁识别。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)

    _run_git(repository_root, "checkout", "-q", "-b", "feature/two-commits")
    _write_and_commit(repository_root, "notes.txt", "first\nsecond\n", "feat: add second line")
    _write_and_commit(repository_root, "extra.txt", "extra\n", "feat: add extra file")
    _run_git(repository_root, "checkout", "-q", "main")
    # GitHub 的 squash merge 形态：两个提交压成一个新提交，SHA 与分支上的都不同。
    _run_git(repository_root, "merge", "--squash", "feature/two-commits")
    _run_git(repository_root, "commit", "-q", "-m", "feat: two commits squashed (#3)")

    branch_merge_state = _build_merge_states_by_name(repository_root)["feature/two-commits"]

    assert branch_merge_state["merge_state"] == history.MERGE_STATE_REPLAYED
    assert branch_merge_state["ahead"] == 2
    # 界面要给一个可点的落点，所以必须能说出「进到基准分支的哪个提交」。
    squash_commit_hash = _run_git(repository_root, "rev-parse", "main").strip()
    assert branch_merge_state["merged_into"]["hash"] == squash_commit_hash
    assert branch_merge_state["merged_into"]["short_hash"] == squash_commit_hash[:7]
    assert branch_merge_state["merged_into"]["subject"] == "feat: two commits squashed (#3)"
    # 分支自己的两个提交要能被标出来，供提交图高亮整条泳道。
    assert len(branch_merge_state["lane_commits"]) == 2


def test_partially_applied_branch_is_not_reported_as_replayed(tmp_path: Path) -> None:
    """只有部分补丁进入基准分支时不得声称「内容已合入」。"""
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    _initialize_repository(repository_root)

    _run_git(repository_root, "checkout", "-q", "-b", "feature/partial")
    _write_and_commit(repository_root, "notes.txt", "first\nsecond\n", "feat: add second line")
    _write_and_commit(repository_root, "extra.txt", "extra\n", "feat: add extra file")
    _run_git(repository_root, "checkout", "-q", "main")
    _run_git(repository_root, "cherry-pick", "feature/partial~1")
    # 改写提交说明，避免 cherry-pick 产出与分支上完全相同的 SHA（同父、同树、同时间）。
    _run_git(repository_root, "commit", "-q", "--amend", "-m", "feat: add second line only")

    branch_merge_state = _build_merge_states_by_name(repository_root)["feature/partial"]

    assert branch_merge_state["merge_state"] == history.MERGE_STATE_DIVERGED
