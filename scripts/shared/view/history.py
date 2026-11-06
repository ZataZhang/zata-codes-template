"""按需读取包含本地与远程分支的 Git 提交图及单提交改动。"""

from __future__ import annotations

import re
from pathlib import Path

import workspace
import workspace_read

#: 每次请求的默认提交数；图历史不是查看器启动流程的一部分，只在用户打开该视图时读取。
DEFAULT_HISTORY_PAGE_SIZE = 50
MAX_HISTORY_PAGE_SIZE = 100
MAX_HISTORY_OFFSET = 100_000

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
    branch_refs, refs_by_commit = _read_branch_refs(repository_root)
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
) -> tuple[list[dict[str, str]], dict[str, list[dict[str, str]]]]:
    """读取分支引用及其指向的提交，区分本地分支与远程跟踪分支。"""
    raw_ref_output = workspace._run_git(
        repository_root,
        "for-each-ref",
        "--format=%(objectname)%00%(refname:short)%00%(refname)%00%(objecttype)",
        "refs/heads",
        "refs/remotes",
    )
    branch_refs: list[dict[str, str]] = []
    refs_by_commit: dict[str, list[dict[str, str]]] = {}
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
        branch_ref = {"name": short_name, "kind": ref_kind, "hash": commit_hash}
        branch_refs.append(branch_ref)
        refs_by_commit.setdefault(commit_hash, []).append({"name": short_name, "kind": ref_kind})

    kind_order = {"local": 0, "remote": 1}
    branch_refs.sort(key=lambda branch_ref: (kind_order[branch_ref["kind"]], branch_ref["name"]))
    for commit_refs in refs_by_commit.values():
        commit_refs.sort(key=lambda ref_label: (kind_order[ref_label["kind"]], ref_label["name"]))
    return branch_refs, refs_by_commit


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
