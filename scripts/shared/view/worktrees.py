"""查询 Git worktree，并按需打开对应的 zview 工作区。

分支可能已在另一个 worktree 检出。查看器只在 Git 登记的工作区之间导航，不执行 ``git switch``，
也不创建、删除或改写 worktree。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import projects
import workspace
import workspace_read

_LAUNCH_URL_PATTERN = re.compile(r"http://127\.0\.0\.1:\d+/\?[^\s]+")
_WORKTREE_LAUNCH_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class _WorktreeRecord:
    """一次 ``git worktree list`` 返回的工作区记录。"""

    root_path: Path
    head_revision: str
    branch_ref: str
    is_current: bool


@lru_cache(maxsize=256)
def project_scope_path(view_root: Path) -> Path:
    """将查看目录映射到主工作树的对应目录，用作项目选择器的身份。

    Args:
        view_root: 当前实例实际提供文件服务的目录。

    Returns:
        主工作树内的对应路径；普通目录保留原路径。
    """
    try:
        _, relative_scope, records = _read_worktree_records(view_root)
    except (OSError, RuntimeError, ValueError, workspace.WorkspaceCommandError):
        return view_root
    return records[0].root_path / relative_scope if records else view_root


def project_choices(current_port: int) -> list[dict]:
    """按工作树归属合并菜单项，优先保留本页端口，其次选择主工作树。

    Args:
        current_port: 提供当前页面的实例端口。

    Returns:
        每个项目查看范围的一条可导航记录。
    """
    choices = {}
    for service in projects.active_projects():
        root = Path(service["root"])
        scope = project_scope_path(root)
        rank = (service["port"] != current_port, root != scope, str(root), service["port"])
        if scope not in choices or rank < choices[scope][0]:
            choices[scope] = (
                rank,
                {**service, "root": str(scope), "name": scope.name or str(scope)},
            )
    return [choices[scope][1] for scope in sorted(choices)]


def build_worktree_options_payload(repository_root: Path) -> workspace_read.WorkspacePayload:
    """列出当前仓库里可供查看的已检出 worktree。

    Args:
        repository_root (Path): 当前查看根目录，可以是 Git 仓库子目录。

    Returns:
        workspace_read.WorkspacePayload: 含工作区标识、分支名和当前项标记的
            应答。
    """
    try:
        _, relative_view_path, worktree_records = _read_worktree_records(repository_root)
    except (OSError, RuntimeError, ValueError, workspace.WorkspaceCommandError):
        return workspace_read.build_refusal_payload(500, "无法读取 Git worktree 列表。")

    worktree_options: list[dict[str, object]] = []
    for worktree_record in worktree_records:
        scoped_root_path = worktree_record.root_path / relative_view_path
        try:
            resolved_scoped_root_path = scoped_root_path.resolve(strict=True)
            resolved_scoped_root_path.relative_to(worktree_record.root_path)
        except (OSError, RuntimeError, ValueError):
            continue
        if not resolved_scoped_root_path.is_dir():
            continue
        branch_name = worktree_record.branch_ref.removeprefix("refs/heads/")
        worktree_label = branch_name or f"HEAD {worktree_record.head_revision[:8]}"
        worktree_options.append(
            {
                "id": _worktree_identifier(worktree_record.root_path),
                "label": worktree_label,
                "current": worktree_record.is_current,
            }
        )

    return workspace_read.WorkspacePayload(
        status_code=200,
        payload={"worktrees": worktree_options},
    )


def open_worktree_viewer_payload(
    repository_root: Path,
    worktree_id: str,
    view_name: str,
) -> workspace_read.WorkspacePayload:
    """在目标 worktree 中打开或复用一个 zview 实例。

    Args:
        repository_root (Path): 当前查看根目录，可以是 Git 仓库子目录。
        worktree_id (str): ``/api/worktrees`` 返回的工作区标识。
        view_name (str): 初始视图，只接受 ``files`` 或 ``diff``。

    Returns:
        workspace_read.WorkspacePayload: 成功时含目标 zview URL；失败时含拒绝原因。
    """
    if view_name not in {"files", "diff"}:
        return workspace_read.build_refusal_payload(400, "拒绝：初始视图无效。")

    try:
        _, relative_view_path, worktree_records = _read_worktree_records(repository_root)
    except (OSError, RuntimeError, ValueError, workspace.WorkspaceCommandError):
        return workspace_read.build_refusal_payload(500, "无法读取 Git worktree 列表。")

    selected_worktree_record = next(
        (
            worktree_record
            for worktree_record in worktree_records
            if _worktree_identifier(worktree_record.root_path) == worktree_id
        ),
        None,
    )
    if selected_worktree_record is None:
        return workspace_read.build_refusal_payload(404, "所选 worktree 已不存在，请刷新后重试。")
    if selected_worktree_record.is_current:
        return workspace_read.build_refusal_payload(409, "当前已经在所选 worktree 中。")

    scoped_target_path = selected_worktree_record.root_path / relative_view_path
    try:
        resolved_target_path = scoped_target_path.resolve(strict=True)
        resolved_target_path.relative_to(selected_worktree_record.root_path)
    except (OSError, RuntimeError, ValueError):
        return workspace_read.build_refusal_payload(
            404,
            "所选 worktree 中没有当前查看的子目录，或该目录指向工作区之外。",
        )
    if not resolved_target_path.is_dir():
        return workspace_read.build_refusal_payload(404, "所选 worktree 中没有当前查看的子目录。")

    launch_script_path = Path(__file__).resolve().with_name("launch.py")
    view_argument = "--files" if view_name == "files" else "--diff"
    try:
        launch_process = subprocess.run(
            [
                sys.executable,
                str(launch_script_path),
                "--global",
                "--no-open",
                view_argument,
                str(resolved_target_path),
            ],
            cwd=resolved_target_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=_WORKTREE_LAUNCH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return workspace_read.build_refusal_payload(503, "启动目标 zview 实例失败，请稍后重试。")

    if launch_process.returncode != 0:
        return workspace_read.build_refusal_payload(
            503, "启动目标 zview 实例失败，请检查服务日志。"
        )

    viewer_url = _read_loopback_viewer_url(launch_process.stdout)
    if viewer_url is None:
        return workspace_read.build_refusal_payload(
            503, "目标 zview 实例已启动，但无法读取访问地址。"
        )
    return workspace_read.WorkspacePayload(status_code=200, payload={"url": viewer_url})


def _read_worktree_records(
    repository_root: Path,
) -> tuple[Path, Path, list[_WorktreeRecord]]:
    """读取 worktree 记录，并算出当前查看根在仓库里的相对路径。"""
    resolved_repository_root = repository_root.resolve(strict=True)
    git_root_path = Path(
        workspace._run_git(resolved_repository_root, "rev-parse", "--show-toplevel").strip()
    ).resolve(strict=True)
    relative_view_path = resolved_repository_root.relative_to(git_root_path)
    porcelain_text = workspace._run_git(git_root_path, "worktree", "list", "--porcelain", "-z")
    worktree_records = _parse_worktree_porcelain(porcelain_text, git_root_path)
    return git_root_path, relative_view_path, worktree_records


def _parse_worktree_porcelain(
    porcelain_text: str, current_worktree_root: Path
) -> list[_WorktreeRecord]:
    """把 Git 的 NUL 分隔 porcelain 输出解析成工作区记录。"""
    worktree_records: list[_WorktreeRecord] = []
    current_fields: dict[str, str] = {}

    def add_current_record() -> None:
        raw_worktree_root = current_fields.get("worktree", "")
        if not raw_worktree_root or "bare" in current_fields or "prunable" in current_fields:
            return
        try:
            worktree_root_path = Path(raw_worktree_root).resolve()
        except (OSError, RuntimeError, ValueError):
            return
        if not worktree_root_path.is_dir():
            return
        worktree_records.append(
            _WorktreeRecord(
                root_path=worktree_root_path,
                head_revision=current_fields.get("HEAD", ""),
                branch_ref=current_fields.get("branch", ""),
                is_current=worktree_root_path == current_worktree_root,
            )
        )

    for field_token in porcelain_text.split("\0"):
        if not field_token:
            add_current_record()
            current_fields = {}
            continue
        field_name, _, field_value = field_token.partition(" ")
        current_fields[field_name] = field_value

    if current_fields:
        add_current_record()
    return worktree_records


def _worktree_identifier(worktree_root_path: Path) -> str:
    """用规范化后的 worktree 根路径生成不暴露路径的请求标识。"""
    return hashlib.sha256(os.fsencode(str(worktree_root_path))).hexdigest()


def _read_loopback_viewer_url(launch_output: str) -> str | None:
    """只接受本机回环地址上的 zview URL。"""
    for viewer_url_match in _LAUNCH_URL_PATTERN.finditer(launch_output):
        candidate_url = viewer_url_match.group(0)
        try:
            parsed_viewer_url = urlsplit(candidate_url)
            viewer_port = parsed_viewer_url.port
        except ValueError:
            continue
        if (
            parsed_viewer_url.scheme == "http"
            and parsed_viewer_url.hostname == "127.0.0.1"
            and viewer_port is not None
            and parsed_viewer_url.path == "/"
        ):
            return candidate_url
    return None
