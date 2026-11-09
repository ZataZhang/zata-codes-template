"""查看器中文本文件编辑、版本校验与原子保存。

保存接口只处理已有的仓库内 UTF-8 文本文件，复用工作区的 256 KiB 上限和大小格式化；路径边界
统一由 :mod:`workspace_read` 解析。工作区浏览与 Git 读取仍由 :mod:`workspace` 负责。
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

import rendering
import workspace
from workspace_read import (
    OUTSIDE_REPOSITORY_REFUSAL_MESSAGE,
    WorkspacePayload,
    build_refusal_payload,
    file_content_revision_digest,
    resolve_repository_path,
)

_EDITABLE_LINE_ENDINGS = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}
_FILE_REVISION_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class FileEditRequest:
    """一个带版本校验的文本文件保存请求。

    Attributes:
        path (str): 仓库相对路径。
        source_text (str): 编辑器中的规范化文本，换行符统一为 LF。
        expected_revision (str): 读取文件时返回的 SHA-256 摘要。
        line_ending (str): 原文件换行名，取 ``lf``、``crlf`` 或 ``cr``。
    """

    path: str
    source_text: str
    expected_revision: str
    line_ending: str


@dataclass(frozen=True)
class MarkdownTaskToggleRequest:
    """一个带预览版本校验的 Markdown 任务状态切换请求。

    Attributes:
        path (str): 仓库相对路径。
        expected_revision (str): 生成预览时返回的 SHA-256 摘要。
        checkbox_index (int): Markdown 预览中的零基任务序号。
        is_checked (bool): 保存后的任务勾选状态。
    """

    path: str
    expected_revision: str
    checkbox_index: int
    is_checked: bool


@dataclass(frozen=True)
class EditableFileSnapshot:
    """一个可编辑文本文件的原始字节、文本和换行格式。

    Attributes:
        raw_file_bytes (bytes): 文件原始 UTF-8 字节。
        source_text (str): 解码后且换行规范化为 LF 的文本。
        line_ending (str): 原文件统一换行格式名。
    """

    raw_file_bytes: bytes
    source_text: str
    line_ending: str


def build_editable_source_payload(repository_root: Path, requested_path: str) -> WorkspacePayload:
    """按需读取一份可编辑的 UTF-8 文本和它的版本摘要。

    Args:
        repository_root (Path): 被查看目录的根绝对路径。
        requested_path (str): 界面传来的仓库相对路径。

    Returns:
        WorkspacePayload: 成功时包含文本、换行格式与 SHA-256 摘要；不支持编辑、越界或缺失
            时返回拒绝应答。
    """
    resolved_path = resolve_repository_path(repository_root, requested_path)
    if resolved_path is None:
        return build_refusal_payload(403, OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)

    normalized_relative_path = Path(requested_path).as_posix() if requested_path else ""
    if not normalized_relative_path:
        return build_refusal_payload(400, "拒绝：编辑需要给出一个仓库内的文件路径。")
    if resolved_path.is_dir():
        return build_refusal_payload(400, "拒绝：只能编辑文件，不能编辑目录。")

    editable_snapshot = _read_editable_file_snapshot(resolved_path, normalized_relative_path)
    if isinstance(editable_snapshot, WorkspacePayload):
        return editable_snapshot
    return WorkspacePayload(
        status_code=200,
        payload={
            "path": normalized_relative_path,
            "source": editable_snapshot.source_text,
            "revision": _file_revision(editable_snapshot.raw_file_bytes),
            "line_ending": editable_snapshot.line_ending,
        },
    )


def save_file_content(
    repository_root: Path, file_edit_request: FileEditRequest
) -> WorkspacePayload:
    """原子保存一份已有文本文件，并拒绝覆盖读取后发生变化的版本。

    Args:
        repository_root (Path): 被查看目录的根绝对路径。
        file_edit_request (FileEditRequest): 路径、文本、读取版本摘要和原换行格式。

    Returns:
        WorkspacePayload: 保存结果；越界、非文本、过大、只读或版本冲突时返回拒绝应答。
    """
    resolved_path = resolve_repository_path(repository_root, file_edit_request.path)
    if resolved_path is None:
        return build_refusal_payload(403, OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)
    normalized_relative_path = Path(file_edit_request.path).as_posix()
    if not normalized_relative_path:
        return build_refusal_payload(400, "拒绝：保存需要给出一个仓库内的文件路径。")
    if file_edit_request.line_ending not in _EDITABLE_LINE_ENDINGS:
        return build_refusal_payload(400, "拒绝：文件换行格式无效，请重新读取文件后再保存。")
    if not _FILE_REVISION_PATTERN.fullmatch(file_edit_request.expected_revision):
        return build_refusal_payload(400, "拒绝：文件版本标识无效，请重新读取文件后再保存。")
    if "\r" in file_edit_request.source_text or "\x00" in file_edit_request.source_text:
        return build_refusal_payload(400, "拒绝：编辑内容包含不支持的控制字符。")

    replacement_text = file_edit_request.source_text.replace(
        "\n", _EDITABLE_LINE_ENDINGS[file_edit_request.line_ending]
    )
    try:
        replacement_file_bytes = replacement_text.encode("utf-8")
    except UnicodeEncodeError:
        return build_refusal_payload(400, "拒绝：编辑内容不是有效的 UTF-8 文本。")
    if len(replacement_file_bytes) > workspace.MAX_FILE_BYTES:
        return build_refusal_payload(
            413, f"拒绝：编辑后的文件超过 {workspace.MAX_FILE_BYTES_LABEL} 上限。"
        )

    original_snapshot = _read_editable_file_snapshot(resolved_path, normalized_relative_path)
    if isinstance(original_snapshot, WorkspacePayload):
        return original_snapshot
    if _file_revision(original_snapshot.raw_file_bytes) != file_edit_request.expected_revision:
        return _file_edit_conflict_payload()

    try:
        original_file_mode = stat.S_IMODE(resolved_path.stat().st_mode)
    except OSError:
        return _file_edit_conflict_payload()
    if not original_file_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
        return build_refusal_payload(403, "拒绝：这个文件已设置为只读。")

    temporary_file_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=".zview-save-",
            suffix=".tmp",
            dir=resolved_path.parent,
            delete=False,
        ) as temporary_file:
            temporary_file_path = Path(temporary_file.name)
            temporary_file.write(replacement_file_bytes)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.chmod(temporary_file_path, original_file_mode)

        latest_snapshot = _read_editable_file_snapshot(resolved_path, normalized_relative_path)
        if isinstance(latest_snapshot, WorkspacePayload):
            return _file_edit_conflict_payload()
        if _file_revision(latest_snapshot.raw_file_bytes) != file_edit_request.expected_revision:
            return _file_edit_conflict_payload()

        os.replace(temporary_file_path, resolved_path)
    except OSError:
        return build_refusal_payload(500, "保存失败，请检查文件和所在目录是否可写。")
    finally:
        if temporary_file_path is not None:
            try:
                temporary_file_path.unlink(missing_ok=True)
            except OSError:
                pass

    return WorkspacePayload(
        status_code=200,
        payload={
            "path": normalized_relative_path,
            "revision": _file_revision(replacement_file_bytes),
            "size": len(replacement_file_bytes),
            "size_label": workspace.format_size_label(len(replacement_file_bytes)),
            "saved": True,
        },
    )


def toggle_markdown_task_checkbox(
    repository_root: Path, toggle_request: MarkdownTaskToggleRequest
) -> WorkspacePayload:
    """按 Markdown 预览序号切换任务项，并校验预览期间文件没有变化。

    Args:
        repository_root (Path): 被查看目录的根绝对路径。
        toggle_request (MarkdownTaskToggleRequest): 路径、版本、任务序号和目标状态。

    Returns:
        WorkspacePayload: 保存结果；越界、非 Markdown、不可编辑或版本冲突时为拒绝应答。
    """
    resolved_path = resolve_repository_path(repository_root, toggle_request.path)
    if resolved_path is None:
        return build_refusal_payload(403, OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)
    normalized_relative_path = Path(toggle_request.path).as_posix()
    if workspace.resolve_preview_descriptor(normalized_relative_path) != {"mode": "markdown"}:
        return build_refusal_payload(400, "拒绝：只能切换 Markdown 文件中的任务复选框。")
    if toggle_request.checkbox_index < 0:
        return build_refusal_payload(400, "拒绝：任务复选框序号无效。")
    if not _FILE_REVISION_PATTERN.fullmatch(toggle_request.expected_revision):
        return build_refusal_payload(400, "拒绝：文件版本标识无效，请重新读取预览后再试。")

    current_snapshot = _read_editable_file_snapshot(resolved_path, normalized_relative_path)
    if isinstance(current_snapshot, WorkspacePayload):
        return current_snapshot
    if _file_revision(current_snapshot.raw_file_bytes) != toggle_request.expected_revision:
        return _markdown_task_conflict_payload()

    replacement_source = rendering.replace_markdown_task_checkbox(
        current_snapshot.source_text,
        toggle_request.checkbox_index,
        toggle_request.is_checked,
    )
    if replacement_source is None:
        return build_refusal_payload(400, "拒绝：预览中的任务复选框已无法定位，请重新读取预览。")
    if replacement_source == current_snapshot.source_text:
        return WorkspacePayload(
            status_code=200,
            payload={
                "path": normalized_relative_path,
                "revision": toggle_request.expected_revision,
                "saved": False,
            },
        )

    save_payload = save_file_content(
        repository_root,
        FileEditRequest(
            path=toggle_request.path,
            source_text=replacement_source,
            expected_revision=toggle_request.expected_revision,
            line_ending=current_snapshot.line_ending,
        ),
    )
    if save_payload.status_code == 409:
        return _markdown_task_conflict_payload()
    return save_payload


def _read_editable_file_snapshot(
    file_path: Path, normalized_relative_path: str
) -> EditableFileSnapshot | WorkspacePayload:
    """读取并校验单个可编辑文本文件，统一大小、二进制、编码和换行判定。

    Args:
        file_path (Path): 已通过仓库边界校验的绝对路径。
        normalized_relative_path (str): 用于错误说明的仓库相对路径。

    Returns:
        EditableFileSnapshot | WorkspacePayload: 文件快照，或说明拒绝原因的应答。
    """
    try:
        if not file_path.is_file():
            return build_refusal_payload(404, f"未找到文件：{normalized_relative_path}")
        file_byte_count = file_path.stat().st_size
        if file_byte_count > workspace.MAX_FILE_BYTES:
            return build_refusal_payload(
                413,
                f"拒绝：文件超过 {workspace.MAX_FILE_BYTES_LABEL} 上限，不能在查看器中编辑。",
            )
        raw_file_bytes = file_path.read_bytes()
    except OSError:
        return build_refusal_payload(500, "读取文件失败，请检查文件是否仍存在且可读。")

    if len(raw_file_bytes) > workspace.MAX_FILE_BYTES:
        return build_refusal_payload(
            413,
            f"拒绝：文件超过 {workspace.MAX_FILE_BYTES_LABEL} 上限，不能在查看器中编辑。",
        )
    if b"\x00" in raw_file_bytes:
        return build_refusal_payload(415, "拒绝：查看器只编辑 UTF-8 文本文件。")
    try:
        source_text = raw_file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return build_refusal_payload(415, "拒绝：文件不是有效的 UTF-8 文本，不能在查看器中编辑。")

    raw_line_endings = raw_file_bytes.replace(b"\r\n", b"")
    has_crlf = b"\r\n" in raw_file_bytes
    has_lone_lf = b"\n" in raw_line_endings
    has_lone_cr = b"\r" in raw_line_endings
    if (has_crlf and (has_lone_lf or has_lone_cr)) or (has_lone_lf and has_lone_cr):
        return build_refusal_payload(
            415, "拒绝：文件混用了多种换行格式，请先在本地编辑器中统一换行。"
        )
    line_ending = "crlf" if has_crlf else "cr" if has_lone_cr else "lf"
    return EditableFileSnapshot(
        raw_file_bytes=raw_file_bytes,
        source_text=source_text.replace("\r\n", "\n").replace("\r", "\n"),
        line_ending=line_ending,
    )


def _file_revision(raw_file_bytes: bytes) -> str:
    """返回原始文件字节的 SHA-256 摘要，用于检测并发编辑。"""
    return file_content_revision_digest(raw_file_bytes)


def _file_edit_conflict_payload() -> WorkspacePayload:
    """构造编辑期间文件改变或消失时的统一冲突应答。"""
    return build_refusal_payload(
        409, "文件在编辑期间已更改或被删除。你的草稿仍保留，请取消编辑后重新读取。"
    )


def _markdown_task_conflict_payload() -> WorkspacePayload:
    """构造任务状态保存期间文件发生变化时的提示。"""
    return build_refusal_payload(409, "文件在打开预览后已更改。任务状态未保存，请重新读取后再试。")
