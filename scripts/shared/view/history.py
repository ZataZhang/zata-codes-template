"""按需读取包含本地与远程分支的 Git 提交图及单提交改动。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import workspace
import workspace_read

#: 每次请求的默认提交数；图历史不是查看器启动流程的一部分，只在用户打开该视图时读取。
DEFAULT_HISTORY_PAGE_SIZE = 50
MAX_HISTORY_PAGE_SIZE = 100
MAX_HISTORY_OFFSET = 100_000

#: 分支相对基准分支的位置。`merged` 是基准分支的祖先，`replayed` 是提交已以其他 SHA
#: 进入基准分支（squash / rebase 合并），两者在提交图上都画成独立泳道，只能靠补丁内容区分。
MERGE_STATE_BASE = "base"
MERGE_STATE_MERGED = "merged"
MERGE_STATE_REPLAYED = "replayed"
MERGE_STATE_AHEAD = "ahead"
MERGE_STATE_DIVERGED = "diverged"
MERGE_STATE_UNKNOWN = "unknown"

#: 首个历史请求最多计算多少个本地分支的合并状态；分支极多的仓库上宁可报「未知」也不拖慢首屏。
MAX_MERGE_STATE_BRANCHES = 40
#: 逐补丁比对（`git cherry`）的提交数上限；超过只看领先/落后，不判「内容已合入」。
MAX_REPLAY_PROBE_COMMITS = 200
#: 整体补丁比对时，从分叉点往后取多少个基准分支提交。GitHub 的 squash merge 会把整条
#: 分支压成一个提交，逐提交比对永远不命中，只能拿分支的整体补丁去比这几个提交。
MAX_SQUASH_PROBE_COMMITS = 8
#: 已合入分支在提交图上最多标出多少个自己的提交；只用于高亮，超出部分照常显示。
MAX_MERGED_LANE_COMMITS = 100

_HISTORY_RECORD_MARKER = "\x1e"
_HISTORY_FIELD_SEPARATOR = "\x1f"
_HISTORY_FORMAT = "%x1e%H%x1f%h%x1f%as%x1f%D%x1f%s"
_COMMIT_HASH_PATTERN = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


def build_git_history_payload(
    repository_root: Path,
    *,
    offset: int,
    limit: int = DEFAULT_HISTORY_PAGE_SIZE,
) -> workspace_read.WorkspacePayload:
    """读取一页 Git 提交图，附带本地分支和远程跟踪分支标记。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        offset (int): 跳过的提交数。
        limit (int): 本页最多返回的提交数。

    Returns:
        workspace_read.WorkspacePayload: 含图形行、分支引用和分页状态的应答。
    """
    if offset < 0 or offset > MAX_HISTORY_OFFSET:
        return workspace_read.build_refusal_payload(
            400, f"拒绝：Git 历史偏移量必须在 0 到 {MAX_HISTORY_OFFSET} 之间。"
        )
    if limit < 1 or limit > MAX_HISTORY_PAGE_SIZE:
        return workspace_read.build_refusal_payload(
            400, f"拒绝：每页提交数必须在 1 到 {MAX_HISTORY_PAGE_SIZE} 之间。"
        )

    raw_graph_output = workspace._run_git(
        repository_root,
        "log",
        "--all",
        "--graph",
        "--decorate=short",
        "--date=short",
        "--date-order",
        "--color=never",
        f"--skip={offset}",
        f"--max-count={limit}",
        f"--pretty=format:{_HISTORY_FORMAT}",
        "--",
        ".",
    )
    branch_refs, refs_by_commit, base_branch_name = _read_branch_refs(repository_root)
    try:
        current_head_hash = workspace._run_git(
            repository_root, "rev-parse", "--verify", "HEAD"
        ).strip()
    except workspace_read.WorkspaceCommandError:
        current_head_hash = ""
    history_rows: list[dict[str, object]] = []
    commit_count = 0

    # ``str.splitlines()`` 会把格式字段里的 ASCII 记录分隔符 ``\x1e`` 也当成换行。
    graph_output_lines = raw_graph_output.split("\n") if raw_graph_output else []
    for raw_graph_line in graph_output_lines:
        if _HISTORY_RECORD_MARKER not in raw_graph_line:
            if raw_graph_line:
                history_rows.append({"kind": "edge", "graph": raw_graph_line})
            continue

        graph_prefix, raw_commit_fields = raw_graph_line.split(_HISTORY_RECORD_MARKER, 1)
        commit_fields = raw_commit_fields.split(_HISTORY_FIELD_SEPARATOR, maxsplit=4)
        if len(commit_fields) != 5:
            history_rows.append(
                {"kind": "edge", "graph": raw_graph_line.replace(_HISTORY_RECORD_MARKER, "")}
            )
            continue

        full_hash, short_hash, authored_date, raw_decorations, raw_subject = commit_fields
        ref_names = list(refs_by_commit.get(full_hash, []))
        ref_names.extend(
            {"name": decoration.removeprefix("tag: "), "kind": "tag"}
            for decoration in raw_decorations.split(", ")
            if decoration.startswith("tag: ")
        )
        clean_subject = "".join(
            character for character in raw_subject if character >= " " and character != "\x7f"
        )
        history_rows.append(
            {
                "kind": "commit",
                "graph_prefix": graph_prefix,
                "hash": full_hash,
                "short_hash": short_hash,
                "date": authored_date,
                "subject": clean_subject,
                "refs": ref_names,
                "is_head": full_hash == current_head_hash,
            }
        )
        commit_count += 1

    next_offset = offset + commit_count
    limit_reached = next_offset >= MAX_HISTORY_OFFSET and commit_count == limit
    return workspace_read.WorkspacePayload(
        status_code=200,
        payload={
            "offset": offset,
            "limit": limit,
            "commit_count": commit_count,
            # 整页时保留「加载更多」；若仓库恰好在页边界结束，下一次空页会收起按钮。
            "has_more": commit_count == limit and not limit_reached,
            "limit_reached": limit_reached,
            "rows": history_rows,
            "branch_refs": branch_refs,
            # 基准分支为空表示没找到可比较的默认分支，此时各分支状态都是 unknown。
            "base_branch": base_branch_name,
        },
    )


def build_git_commit_payload(
    repository_root: Path,
    requested_commit_hash: str,
) -> workspace_read.WorkspacePayload:
    """读取提交详情和相对首个父提交发生变化的文件列表。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        requested_commit_hash (str): 提交的完整 SHA-1 或 SHA-256 哈希。

    Returns:
        workspace_read.WorkspacePayload: 含作者、提交说明、父提交与文件状态的应答。
    """
    commit_metadata = _read_commit_metadata(repository_root, requested_commit_hash)
    if commit_metadata is None:
        return workspace_read.build_refusal_payload(404, "未找到该 Git 提交。")

    commit_files = _read_commit_file_changes(repository_root, commit_metadata)
    return workspace_read.WorkspacePayload(
        status_code=200,
        payload={**commit_metadata, "files": commit_files},
    )


def build_git_commit_diff_payload(
    repository_root: Path,
    requested_commit_hash: str,
    requested_path: str,
) -> workspace_read.WorkspacePayload:
    """读取指定提交中一个已变更文件的逐行 diff。

    合并提交按首个父提交比较；根提交按空树比较。路径必须先匹配该提交的文件列表，再以
    ``--literal-pathspecs`` 和 ``--`` 传给 Git，避免路径被解释为选项或 pathspec 语法。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        requested_commit_hash (str): 提交的完整 SHA-1 或 SHA-256 哈希。
        requested_path (str): 提交中变更文件的仓库相对路径。

    Returns:
        workspace_read.WorkspacePayload: 含逐行 diff、二进制状态与截断标记的应答。
    """
    commit_metadata = _read_commit_metadata(repository_root, requested_commit_hash)
    if commit_metadata is None:
        return workspace_read.build_refusal_payload(404, "未找到该 Git 提交。")

    commit_files = _read_commit_file_changes(repository_root, commit_metadata)
    matched_file = next(
        (commit_file for commit_file in commit_files if commit_file["path"] == requested_path),
        None,
    )
    if matched_file is None:
        return workspace_read.build_refusal_payload(404, "该文件不属于所选提交。")

    diff_pathspecs = [matched_file["path"]]
    old_path = matched_file["old_path"]
    if old_path:
        diff_pathspecs.insert(0, old_path)
    parent_hashes = commit_metadata["parents"]
    diff_text = _read_git_commit_diff_text(repository_root, commit_metadata, diff_pathspecs)
    parsed_diff = workspace._parse_unified_diff_rows(diff_text)
    return workspace_read.WorkspacePayload(
        status_code=200,
        payload={
            "path": matched_file["path"],
            "old_path": old_path,
            "comparison": "首个父提交" if parent_hashes else "空树",
            "rows": parsed_diff.rows,
            "truncated": parsed_diff.is_truncated,
            "binary": parsed_diff.is_binary,
            "empty": not parsed_diff.rows,
        },
    )


def _read_git_commit_diff_text(
    repository_root: Path,
    commit_metadata: dict[str, object],
    pathspecs: list[str] | None = None,
) -> str:
    """读取一次提交的 unified diff；路径筛选仅用于经过文件列表校验的单文件请求。"""
    parent_hashes = commit_metadata["parents"]
    if parent_hashes:
        git_arguments = [
            "--literal-pathspecs",
            "diff",
            "--no-ext-diff",
            "--no-color",
            "--unified=3",
            "-M",
            str(parent_hashes[0]),
            str(commit_metadata["hash"]),
        ]
    else:
        git_arguments = [
            "--literal-pathspecs",
            "show",
            "--root",
            "--format=",
            "--no-ext-diff",
            "--no-color",
            "--unified=3",
            str(commit_metadata["hash"]),
        ]
    if pathspecs:
        git_arguments.extend(["--", *pathspecs])
    return workspace._run_git(repository_root, *git_arguments)


def _read_branch_refs(
    repository_root: Path,
) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]], str]:
    """读取分支引用及其指向的提交，并标注每个分支相对基准分支的合并状态。

    Args:
        repository_root (Path): 被查看仓库的根目录。

    Returns:
        tuple[list[dict[str, object]], dict[str, list[dict[str, object]]], str]: 分支引用列表、
        按提交归集的引用标签，以及基准分支的短名（没有可比较的默认分支时为空串）。
    """
    raw_ref_output = workspace._run_git(
        repository_root,
        "for-each-ref",
        "--format=%(objectname)%00%(refname:short)%00%(refname)%00%(objecttype)",
        "refs/heads",
        "refs/remotes",
    )
    branch_refs: list[dict[str, object]] = []
    for raw_ref_line in raw_ref_output.split("\n"):
        if not raw_ref_line:
            continue
        ref_fields = raw_ref_line.split("\x00")
        if len(ref_fields) != 4:
            continue
        commit_hash, short_name, full_name, object_type = ref_fields
        if object_type != "commit":
            continue
        ref_kind = "remote" if full_name.startswith("refs/remotes/") else "local"
        branch_refs.append({"name": short_name, "kind": ref_kind, "hash": commit_hash})

    base_branch_name = _annotate_branch_merge_states(repository_root, branch_refs)
    refs_by_commit: dict[str, list[dict[str, object]]] = {}
    for branch_ref in branch_refs:
        refs_by_commit.setdefault(str(branch_ref["hash"]), []).append(
            {
                "name": branch_ref["name"],
                "kind": branch_ref["kind"],
                "merge_state": branch_ref["merge_state"],
            }
        )

    kind_order = {"local": 0, "remote": 1}
    branch_refs.sort(
        key=lambda branch_ref: (kind_order[str(branch_ref["kind"])], str(branch_ref["name"]))
    )
    for commit_refs in refs_by_commit.values():
        commit_refs.sort(
            key=lambda ref_label: (kind_order[str(ref_label["kind"])], str(ref_label["name"]))
        )
    return branch_refs, refs_by_commit, base_branch_name


def _annotate_branch_merge_states(
    repository_root: Path, branch_refs: list[dict[str, object]]
) -> str:
    """就地为分支引用补上 `merge_state` / `ahead` / `behind`，返回基准分支短名。

    只为本地分支逐个调用 Git；远程跟踪分支复用同名本地分支的结果，避免在远端分支很多的
    仓库里把首个历史请求拖成几十次子进程。没有可用基准分支时全部标为 `unknown`。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        branch_refs (list[dict[str, object]]): 待补全的分支引用，会被直接修改。

    Returns:
        str: 基准分支短名；找不到默认分支时返回空串。
    """
    base_ref = _resolve_base_branch(repository_root)
    base_branch_name = _short_branch_name(base_ref) if base_ref else ""
    local_merge_states: dict[str, dict[str, object]] = {}
    local_branch_names = [
        str(branch_ref["name"]) for branch_ref in branch_refs if branch_ref["kind"] == "local"
    ]
    for branch_name in local_branch_names[:MAX_MERGE_STATE_BRANCHES]:
        if base_ref and branch_name == base_branch_name:
            local_merge_states[branch_name] = {
                "merge_state": MERGE_STATE_BASE,
                "ahead": 0,
                "behind": 0,
                "merged_into": None,
                "lane_commits": [],
            }
            continue
        local_merge_states[branch_name] = (
            _read_branch_merge_state(repository_root, f"refs/heads/{branch_name}", base_ref)
            if base_ref
            else _unknown_merge_state()
        )

    for branch_ref in branch_refs:
        branch_name = str(branch_ref["name"])
        if branch_ref["kind"] == "local":
            branch_ref.update(local_merge_states.get(branch_name, _unknown_merge_state()))
            continue
        # `origin/feature` 与本地 `feature` 指向同一提交时状态相同，直接复用而不再问 Git。
        shared_merge_state = local_merge_states.get(
            _short_branch_name(branch_name), _unknown_merge_state()
        )
        branch_ref.update(shared_merge_state)
    return base_branch_name


def _resolve_base_branch(repository_root: Path) -> str:
    """解析用于比较合并状态的基准分支引用；没有默认分支时返回空串。"""
    try:
        remote_head_name = workspace._run_git(
            repository_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"
        ).strip()
    except workspace_read.WorkspaceCommandError:
        remote_head_name = ""

    candidate_names = [
        candidate_name
        for candidate_name in (_short_branch_name(remote_head_name), "main", "master")
        if candidate_name
    ]
    seen_names: set[str] = set()
    for candidate_name in candidate_names:
        if candidate_name in seen_names:
            continue
        seen_names.add(candidate_name)
        candidate_refs = (
            f"refs/heads/{candidate_name}",
            f"refs/remotes/origin/{candidate_name}",
        )
        for candidate_ref in candidate_refs:
            if _git_ref_exists(repository_root, candidate_ref):
                return candidate_ref
    return ""


def _read_branch_merge_state(
    repository_root: Path, branch_ref: str, base_ref: str
) -> dict[str, object]:
    """读取一个分支相对基准分支的位置。

    领先数为 0 即「已合并」；有独有提交时用 `git cherry` 比对补丁内容，全部命中说明提交
    已以其他 SHA 进入基准分支（squash / rebase 合并），这是提交图上看不出来的那一类。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        branch_ref (str): 分支的完整引用名或分支名。
        base_ref (str): 基准分支的完整引用名或分支名。

    Returns:
        dict[str, object]: 含 `merge_state`、`ahead`、`behind` 的映射；读取失败时状态为
        `unknown`，领先/落后为 `None`。
    """
    try:
        # `--left-right --count` 先输出「只在基准分支」的数，再输出「只在该分支」的数。
        behind_text, ahead_text = workspace._run_git(
            repository_root, "rev-list", "--left-right", "--count", f"{base_ref}...{branch_ref}"
        ).split()
        ahead_count, behind_count = int(ahead_text), int(behind_text)
    except (workspace_read.WorkspaceCommandError, ValueError):
        return _unknown_merge_state()

    merged_into_hash = ""
    if ahead_count == 0:
        merge_state = MERGE_STATE_MERGED
    elif ahead_count <= MAX_REPLAY_PROBE_COMMITS and _is_content_already_on_base(
        repository_root, branch_ref, base_ref
    ):
        merge_state = MERGE_STATE_REPLAYED
    elif ahead_count <= MAX_REPLAY_PROBE_COMMITS:
        merged_into_hash = _find_squash_target_commit(repository_root, branch_ref, base_ref)
        if merged_into_hash:
            merge_state = MERGE_STATE_REPLAYED
        else:
            merge_state = MERGE_STATE_DIVERGED if behind_count else MERGE_STATE_AHEAD
    elif behind_count:
        merge_state = MERGE_STATE_DIVERGED
    else:
        merge_state = MERGE_STATE_AHEAD

    is_merged = merge_state in (MERGE_STATE_MERGED, MERGE_STATE_REPLAYED)
    return {
        "merge_state": merge_state,
        "ahead": ahead_count,
        "behind": behind_count,
        # 已进入基准分支的那个提交；只有整体补丁比对命中时才知道是哪一个。
        "merged_into": _read_commit_summary(repository_root, merged_into_hash),
        # 该分支自己的提交，供提交图标出「这条分支已经在 main 里」。
        "lane_commits": _read_branch_lane_commits(repository_root, branch_ref, base_ref)
        if is_merged
        else [],
    }


def _find_squash_target_commit(repository_root: Path, branch_ref: str, base_ref: str) -> str:
    """找出承载分支整体补丁的基准分支提交（N 个提交 squash 成 1 个）。

    ``git cherry`` 只能配 1:1 的补丁；squash merge 会把整条分支压成一个提交，逐提交
    比对永远不命中。这里把分支自分叉点的全部改动当成一段补丁，与基准分支在分叉点之后
    最早的几个提交比对——squash 出来的那个提交就落在这几个里。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        branch_ref (str): 分支的完整引用名或分支名。
        base_ref (str): 基准分支的完整引用名或分支名。

    Returns:
        str: 命中时返回该基准提交的完整哈希；未命中或无法判定时返回空串。
    """
    try:
        merge_base_ref = workspace._run_git(
            repository_root, "merge-base", base_ref, branch_ref
        ).strip()
        if not merge_base_ref:
            return ""
        branch_patch_text = workspace._run_git(
            repository_root, "diff", merge_base_ref, branch_ref, "--", "."
        )
        if not branch_patch_text.strip():
            # 分叉点之后分支自己没有改动，内容显然已在基准分支里，但没有可指认的提交。
            return ""
        candidate_output = workspace._run_git(
            repository_root,
            "log",
            "--no-merges",
            "--reverse",
            "--format=%H",
            f"{merge_base_ref}..{base_ref}",
            "--",
            ".",
        )
        candidate_hashes = [
            candidate_hash for candidate_hash in candidate_output.split("\n") if candidate_hash
        ][:MAX_SQUASH_PROBE_COMMITS]
        if not candidate_hashes:
            return ""
        candidate_patch_text = workspace._run_git(
            repository_root,
            "show",
            "--patch",
            "--format=commit %H",
            *candidate_hashes,
            "--",
            ".",
        )
    except workspace_read.WorkspaceCommandError:
        return ""
    branch_patch_identifier = _read_patch_identifier(repository_root, branch_patch_text)
    if not branch_patch_identifier:
        return ""
    return _read_patch_identifiers(repository_root, candidate_patch_text).get(
        branch_patch_identifier, ""
    )


def _read_patch_identifier(repository_root: Path, patch_text: str) -> str:
    """计算一段补丁的 patch-id；空补丁或计算失败时返回空串。"""
    for patch_identifier_line in _run_patch_id(repository_root, patch_text).splitlines():
        identifier_fields = patch_identifier_line.split()
        if identifier_fields:
            return identifier_fields[0]
    return ""


def _read_patch_identifiers(repository_root: Path, patch_text: str) -> dict[str, str]:
    """把多段补丁算成 ``patch-id → 提交哈希`` 映射（每段以 ``commit <SHA>`` 分段）。

    ``git patch-id`` 只从标准输入读补丁，``workspace._run_git`` 没有 stdin 通道，因此这里
    单独调用一次 git。它只对补丁文本做规范化哈希、不读取仓库内容，工作目录仅用于保持
    与其它调用一致的路径语义。
    """
    patch_identifiers: dict[str, str] = {}
    for patch_identifier_line in _run_patch_id(repository_root, patch_text).splitlines():
        identifier_fields = patch_identifier_line.split()
        if len(identifier_fields) == 2:
            patch_identifiers[identifier_fields[0]] = identifier_fields[1]
    return patch_identifiers


def _run_patch_id(repository_root: Path, patch_text: str) -> str:
    """把补丁文本喂给 ``git patch-id --stable``，返回 ``<patch-id> <commit>`` 行。"""
    if not patch_text.strip():
        return ""
    completed_process = subprocess.run(
        ["git", "--no-pager", "patch-id", "--stable"],
        cwd=repository_root,
        input=patch_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    return completed_process.stdout


def _read_commit_summary(repository_root: Path, commit_hash: str) -> dict[str, str] | None:
    """读取一个提交的短哈希与标题；哈希为空或读取失败时返回 ``None``。"""
    if not commit_hash:
        return None
    try:
        summary_output = workspace._run_git(
            repository_root, "show", "-s", "--format=%H%x1f%h%x1f%s", commit_hash
        )
        summary_fields = summary_output.rstrip("\n").split(_HISTORY_FIELD_SEPARATOR)
    except workspace_read.WorkspaceCommandError:
        return None
    if len(summary_fields) != 3:
        return None
    return {
        "hash": summary_fields[0],
        "short_hash": summary_fields[1],
        "subject": summary_fields[2],
    }


def _read_branch_lane_commits(repository_root: Path, branch_ref: str, base_ref: str) -> list[str]:
    """列出该分支独有的提交，供提交图标出「这条分支的内容已经在基准分支里」。

    只列分叉点之后的提交：分叉点及更早的历史与基准分支共享，标出来没有意义。

    Args:
        repository_root (Path): 被查看仓库的根目录。
        branch_ref (str): 分支的完整引用名或分支名。
        base_ref (str): 基准分支的完整引用名或分支名。

    Returns:
        list[str]: 提交完整哈希列表；无法读取时返回空列表。
    """
    try:
        merge_base_ref = workspace._run_git(
            repository_root, "merge-base", base_ref, branch_ref
        ).strip()
        if not merge_base_ref:
            return []
        lane_commit_output = workspace._run_git(
            repository_root,
            "rev-list",
            f"--max-count={MAX_MERGED_LANE_COMMITS}",
            f"{merge_base_ref}..{branch_ref}",
            "--",
            ".",
        )
    except workspace_read.WorkspaceCommandError:
        return []
    return [
        lane_commit_hash for lane_commit_hash in lane_commit_output.split("\n") if lane_commit_hash
    ]


def _is_content_already_on_base(repository_root: Path, branch_ref: str, base_ref: str) -> bool:
    """用补丁标识判断分支提交是否已进入基准分支（`git cherry` 输出全为 `-`）。"""
    try:
        cherry_output = workspace._run_git(repository_root, "cherry", base_ref, branch_ref)
    except workspace_read.WorkspaceCommandError:
        return False
    cherry_marks = [cherry_line[:1] for cherry_line in cherry_output.splitlines() if cherry_line]
    return bool(cherry_marks) and all(cherry_mark == "-" for cherry_mark in cherry_marks)


def _git_ref_exists(repository_root: Path, candidate_ref: str) -> bool:
    """判断一个引用是否指向提交；`rev-parse --quiet` 对不存在的引用返回非零。"""
    try:
        workspace._run_git(repository_root, "rev-parse", "--verify", "--quiet", candidate_ref)
    except workspace_read.WorkspaceCommandError:
        return False
    return True


def _short_branch_name(ref_name: str) -> str:
    """把 `refs/heads/main` / `refs/remotes/origin/main` / `origin/main` 收敛成短名。"""
    if ref_name.startswith("refs/heads/"):
        return ref_name.removeprefix("refs/heads/")
    if ref_name.startswith("refs/remotes/"):
        return ref_name.removeprefix("refs/remotes/").split("/", 1)[-1]
    return ref_name.split("/", 1)[-1]


def _unknown_merge_state() -> dict[str, object]:
    """返回「无法判定」的合并状态；调用方需要独立副本，故每次新建。"""
    return {
        "merge_state": MERGE_STATE_UNKNOWN,
        "ahead": None,
        "behind": None,
        "merged_into": None,
        "lane_commits": [],
    }


def _read_commit_metadata(
    repository_root: Path,
    requested_commit_hash: str,
) -> dict[str, object] | None:
    """读取并校验一个提交的完整元信息。"""
    normalized_commit_hash = requested_commit_hash.lower()
    if not _COMMIT_HASH_PATTERN.fullmatch(normalized_commit_hash):
        return None

    try:
        raw_metadata = workspace._run_git(
            repository_root,
            "show",
            "--no-patch",
            "--format=%H%x1f%h%x1f%P%x1f%an%x1f%ae%x1f%aI%x1f%B",
            normalized_commit_hash,
        )
    except workspace_read.WorkspaceCommandError:
        return None

    metadata_fields = raw_metadata.rstrip("\n").split(_HISTORY_FIELD_SEPARATOR, maxsplit=6)
    if len(metadata_fields) != 7:
        return None
    full_hash, short_hash, raw_parents, author_name, author_email, authored_at, message = (
        metadata_fields
    )
    return {
        "hash": full_hash,
        "short_hash": short_hash,
        "parents": raw_parents.split(),
        "author_name": author_name,
        "author_email": author_email,
        "authored_at": authored_at,
        "message": message.rstrip(),
    }


def _read_commit_file_changes(
    repository_root: Path,
    commit_metadata: dict[str, object],
) -> list[dict[str, str | None]]:
    """读取相对首个父提交的文件状态，保留 rename 的旧路径。"""
    commit_hash = str(commit_metadata["hash"])
    parent_hashes = commit_metadata["parents"]
    if parent_hashes:
        raw_change_output = workspace._run_git(
            repository_root,
            "diff-tree",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-M",
            "-z",
            "--relative",
            str(parent_hashes[0]),
            commit_hash,
            "--",
            ".",
        )
    else:
        raw_change_output = workspace._run_git(
            repository_root,
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-status",
            "-r",
            "-M",
            "-z",
            "--relative",
            commit_hash,
            "--",
            ".",
        )

    change_tokens = raw_change_output.split("\x00")
    commit_files: list[dict[str, str | None]] = []
    token_index = 0
    while token_index < len(change_tokens):
        status_label = change_tokens[token_index]
        token_index += 1
        if not status_label:
            continue
        if status_label.startswith(("R", "C")):
            if token_index + 1 >= len(change_tokens):
                break
            old_path = change_tokens[token_index]
            new_path = change_tokens[token_index + 1]
            token_index += 2
            commit_files.append({"status": status_label, "path": new_path, "old_path": old_path})
            continue
        if token_index >= len(change_tokens):
            break
        changed_path = change_tokens[token_index]
        token_index += 1
        commit_files.append({"status": status_label, "path": changed_path, "old_path": None})
    return commit_files
