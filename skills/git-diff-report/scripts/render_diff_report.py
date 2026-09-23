#!/usr/bin/env python3
"""把 git 工作区改动渲染成一份自包含的 HTML 报告。

左侧是改动文件树（可折叠、带改动总结与 +/− 统计，点击跳转、滚动联动），
右侧是全部文件的完整高亮 diff。所有资源内联在单个 HTML 文件里，无外部依赖。

用法示例：

    python3 render_diff_report.py --open
    python3 render_diff_report.py --scope staged --summaries summaries.json
    python3 render_diff_report.py --scope range --base origin/main --include-tests
"""

from __future__ import annotations

import argparse
import codecs
import html
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

DIFF_GIT_HEADER = "diff --git "
#: ``git diff`` 在新增/删除的文件上用 ``/dev/null`` 表示缺失的那一侧。
DIFF_DEV_NULL_PATH = "/dev/null"
HUNK_HEADER_RE = re.compile(r"^@@ -(?P<old>\d+)(?:,\d+)? \+(?P<new>\d+)(?:,\d+)? @@(?P<label>.*)$")

#: 默认排除的测试目录 glob：``tests/**`` 命中的是仓库根，``**/tests/**`` 命中的是
#: 嵌套测试目录（如 ``frontend-public/tests/**``），两者需并存。用 --include-tests 关闭。
DEFAULT_EXCLUDES = ("tests/**", "**/tests/**")

#: 内容在 hunk 之外、但值得展示的元信息行前缀。
METADATA_PREFIXES = (
    "new file mode",
    "deleted file mode",
    "old mode",
    "new mode",
    "similarity index",
    "rename from",
    "rename to",
    "copy from",
    "copy to",
    "Binary files",
)


class DiffReportError(RuntimeError):
    """收集 diff 或渲染报告时的可预期失败。"""


# ─────────────────────────────────────────────────────────────────────────────
# 收集 diff
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DiffScope:
    """一次报告的 diff 范围。

    Attributes:
        name (str): ``staged`` / ``unstaged`` / ``head`` / ``range`` 之一。
        base (str | None): ``range`` 的基线 revision；其它范围为 None。
        excludes (tuple[str, ...]): 追加排除的路径 glob。
        has_head (bool): 仓库是否已有提交。没有 HEAD 时 ``head`` 退化为索引口径，
            因为 ``git diff HEAD`` 在尚无提交的仓库里会直接以 ``bad revision`` 失败，
            而「``git init`` 之后、首次提交之前」正是最常见的看改动场景。
    """

    name: str
    base: str | None
    excludes: tuple[str, ...]
    has_head: bool


def _run_git_process(repo: Path, args: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """运行 git 命令并原样返回结果（供需要自行解读退出码的探测使用）。"""
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _run_git(repo: Path, args: Sequence[str]) -> str:
    """在指定仓库运行 git 命令并返回标准输出。"""
    completed = _run_git_process(repo, args)
    if completed.returncode != 0:
        raise DiffReportError(
            f"git {' '.join(args)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout


def resolve_repo(repo: str | None) -> Path:
    """解析仓库根目录，未指定时按当前工作目录回溯。"""
    if repo:
        root = Path(repo).expanduser().resolve()
        if not (root / ".git").exists():
            raise DiffReportError(f"Not a git repository: {root}")
        return root
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise DiffReportError("Not inside a git repository; pass --repo explicitly.")
    return Path(completed.stdout.strip())


def has_head_commit(repo: Path) -> bool:
    """判断仓库是否已有提交（HEAD 是否存在）。"""
    return _run_git_process(repo, ["rev-parse", "--verify", "--quiet", "HEAD"]).returncode == 0


def current_branch(repo: Path) -> str | None:
    """返回当前分支名（detached 时返回短 hash）；尚无提交时返回 None。"""
    branch_probe = _run_git_process(repo, ["rev-parse", "--abbrev-ref", "HEAD"])
    if branch_probe.returncode != 0:
        return None
    branch = branch_probe.stdout.strip()
    if branch and branch != "HEAD":
        return branch
    short_hash_probe = _run_git_process(repo, ["rev-parse", "--short", "HEAD"])
    return short_hash_probe.stdout.strip() if short_hash_probe.returncode == 0 else None


def build_diff_args(scope: DiffScope) -> list[str]:
    """把范围与排除规则翻译成 `git diff` 参数列表。"""
    if scope.name == "staged":
        args = ["diff", "--staged"]
    elif scope.name == "unstaged":
        args = ["diff"]
    elif scope.name == "head":
        args = ["diff", "HEAD"] if scope.has_head else ["diff", "--staged"]
    elif scope.name == "range":
        if not scope.base:
            raise DiffReportError("--scope range requires --base <rev>.")
        args = ["diff", f"{scope.base}...HEAD"]
    else:
        raise DiffReportError(f"Unknown scope: {scope.name}")
    if scope.excludes:
        args += ["--", *[f":(exclude){pattern}" for pattern in scope.excludes]]
    return args


def _unescape_git_quoted_path(quoted_token: str) -> str:
    """还原 git 引号包裹的路径（``"a/\\346\\226\\207.md"`` → ``a/文.md``）。

    引号里的 ``\\346`` 这类转义是 **UTF-8 字节**，必须在字节层还原再按 utf-8 解码；
    把 ``\\346`` 当码点解释（``ast.literal_eval`` 就是这么干的）会让中文路径变成乱码。
    """
    quoted_body = quoted_token[1:-1] if quoted_token.endswith('"') else quoted_token[1:]
    try:
        escaped_bytes, _ = codecs.escape_decode(quoted_body.encode("utf-8"))
    except ValueError:
        return quoted_body
    return escaped_bytes.decode("utf-8", errors="replace")


def _quoted_token_end(text: str) -> int:
    """返回以 ``text[0] == '"'`` 开头的引号 token 的结束下标（闭合引号处）。"""
    index = 1
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == '"':
            return index
        index += 1
    return len(text) - 1


def _split_new_path_token(header_rest: str) -> str | None:
    """取出 ``diff --git`` 头部里新路径（第二个）token 的原文。

    引号包裹的 token 按引号读。未加引号时 git 只用空格分隔两个路径，而空格本身也可以
    是路径的一部分（git 只为特殊字符加引号），所以按「``a/`` 与 ``b/`` 前缀之后两侧
    相同」挑分隔点——修改、新增、删除、二进制与纯模式变更都满足这条不变量；改名两侧
    不同，取最后一个 ``" b/"`` 候选，其真实路径随后由 ``rename to`` 行给出。
    """
    if header_rest.startswith('"'):
        first_token_end = _quoted_token_end(header_rest)
        remainder = header_rest[first_token_end + 1 :].lstrip(" ")
        if not remainder:
            return None
        if remainder.startswith('"'):
            return remainder[: _quoted_token_end(remainder) + 1]
        return remainder
    separator_offsets = [
        offset for offset in range(len(header_rest)) if header_rest.startswith(" b/", offset)
    ]
    for offset in separator_offsets:
        old_side, new_side = header_rest[:offset], header_rest[offset + 1 :]
        if old_side.startswith("a/") and new_side.startswith("b/") and old_side[2:] == new_side[2:]:
            return new_side
    if separator_offsets:
        return header_rest[separator_offsets[-1] + 1 :]
    return None


def _decode_diff_path(raw_token: str, *, drop_git_prefix: bool = True) -> str:
    """把 git 写的路径 token 还原成仓库相对路径。

    要处理三种修饰：路径含空格时 git 补在 token 末尾的 TAB 终止符（用来和「路径 + 时间戳」
    的老格式消歧，实测引号内外都会出现）、特殊字符的 C 风格引号，以及 ``a/`` / ``b/`` 前缀。
    前缀只属于正文行：``rename from`` / ``rename to`` 给的是不带前缀的真实路径，不能去——
    否则一个真的叫 ``a/foo`` 的文件会被削成 ``foo``。含 TAB 的路径由 git 引号保护，因此
    一个未被引号包裹、却以 TAB 结尾的 token 只会是终止符。
    """
    trimmed_token = raw_token[:-1] if raw_token.endswith("\t") else raw_token
    decoded_path = (
        _unescape_git_quoted_path(trimmed_token) if trimmed_token.startswith('"') else trimmed_token
    )
    if drop_git_prefix:
        for prefix in ("a/", "b/"):
            if decoded_path.startswith(prefix):
                return decoded_path[len(prefix) :]
    return decoded_path


def parse_diff(diff_text: str) -> list[dict[str, Any]]:
    """把 unified diff 文本解析成「文件 → hunk」结构。

    路径以正文行（``+++ b/<路径>``、``--- a/<路径>``、``rename to <路径>``）为准：那些行
    一直写到行尾，不会被路径里的空格切断；只有没有正文行的条目（二进制、纯模式变更）才
    退回 ``diff --git`` 头。重命名（``git mv``）的元信息会被解析成结构化字段 ``is_rename``
    / ``old_path`` / ``similarity``，供树与文件区块渲染「移动」；它们不进 ``meta``，避免
    同一事实渲染两次。
    """
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_old_path: str | None = None
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith(DIFF_GIT_HEADER):
            new_path_token = _split_new_path_token(line[len(DIFF_GIT_HEADER) :])
            current = {
                "path": _decode_diff_path(new_path_token) if new_path_token else "unknown",
                "is_rename": False,
                "old_path": None,
                "similarity": None,
                "meta": [],
                "hunks": [],
            }
            files.append(current)
            current_old_path = None
            in_hunk = False
            continue
        if current is None:
            continue
        hunk_match = HUNK_HEADER_RE.match(line)
        if hunk_match:
            current["hunks"].append(
                {
                    "old_start": int(hunk_match.group("old")),
                    "new_start": int(hunk_match.group("new")),
                    "label": hunk_match.group("label").strip(),
                    "lines": [],
                }
            )
            in_hunk = True
            continue
        if in_hunk:
            current["hunks"][-1]["lines"].append(line)
            continue
        if line.startswith("similarity index "):
            current["similarity"] = line[len("similarity index ") :].strip()
            continue
        if line.startswith("rename from "):
            current["is_rename"] = True
            # rename 行给的是不带 a/ b/ 前缀的真实路径，不能当带前缀的正文行去削。
            current["old_path"] = _decode_diff_path(
                line[len("rename from ") :], drop_git_prefix=False
            )
            continue
        if line.startswith("rename to "):
            current["path"] = _decode_diff_path(line[len("rename to ") :], drop_git_prefix=False)
            continue
        if line.startswith("--- "):
            current_old_path = _decode_diff_path(line[len("--- ") :])
            continue
        if line.startswith("+++ "):
            new_path = _decode_diff_path(line[len("+++ ") :])
            if new_path == DIFF_DEV_NULL_PATH:
                # 删除的文件新侧是 /dev/null，路径得留旧侧那一份。
                current["path"] = current_old_path or current["path"]
            else:
                current["path"] = new_path
            continue
        if line.startswith(METADATA_PREFIXES):
            current["meta"].append(line)
    return files


def moved_from_path(file_entry: dict[str, Any]) -> str:
    """返回该文件的移动来源路径；不是重命名时返回空串。"""
    if not file_entry.get("is_rename"):
        return ""
    return str(file_entry.get("old_path") or "")


def count_changes(file_entry: dict[str, Any]) -> tuple[int, int]:
    """统计单个文件的增删行数。"""
    added = 0
    removed = 0
    for hunk in file_entry["hunks"]:
        for line in hunk["lines"]:
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
    return added, removed


# ─────────────────────────────────────────────────────────────────────────────
# 摘要 JSON
# ─────────────────────────────────────────────────────────────────────────────


def load_summaries(path: str | None) -> dict[str, Any]:
    """读取摘要 JSON；未提供时返回空配置。"""
    if not path:
        return {}
    summaries_path = Path(path).expanduser()
    if not summaries_path.exists():
        raise DiffReportError(f"Summaries file not found: {summaries_path}")
    payload = json.loads(summaries_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DiffReportError("Summaries JSON must be an object.")
    file_entries = payload.get("files", {})
    if not isinstance(file_entries, dict):
        raise DiffReportError("Summaries JSON 'files' must be an object keyed by path.")
    return payload


def file_summary(summaries: dict[str, Any], path: str) -> str:
    """取某个文件的一句话总结。"""
    entry = summaries.get("files", {}).get(path) or {}
    value = entry.get("summary", "")
    return value if isinstance(value, str) else ""


def hunk_note(summaries: dict[str, Any], path: str, index: int) -> str:
    """取某个文件第 index 个 hunk 的说明，缺失时返回空串。"""
    entry = summaries.get("files", {}).get(path) or {}
    notes = entry.get("hunk_notes") or []
    if not isinstance(notes, list) or index >= len(notes):
        return ""
    value = notes[index]
    return value if isinstance(value, str) else ""


# ─────────────────────────────────────────────────────────────────────────────
# 左侧文件树
# ─────────────────────────────────────────────────────────────────────────────


def build_tree(files: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """把文件路径折叠成目录树（node = {"dirs": {...}, "leaves": [...]}）。"""
    root: dict[str, Any] = {"dirs": {}, "leaves": []}
    for index, file_entry in enumerate(files):
        parts = file_entry["path"].split("/")
        node = root
        for part in parts[:-1]:
            node = node["dirs"].setdefault(part, {"dirs": {}, "leaves": []})
        added, removed = count_changes(file_entry)
        node["leaves"].append(
            {
                "name": parts[-1],
                "index": index,
                "added": added,
                "removed": removed,
            }
        )
    return root


def collapse_chain(name: str, child: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """把「只有一个子目录且自身无文件」的目录链合并成一个标签。"""
    while not child["leaves"] and len(child["dirs"]) == 1:
        next_name, next_child = next(iter(child["dirs"].items()))
        name = f"{name}/{next_name}"
        child = next_child
    return name, child


def render_tree(
    node: dict[str, Any],
    summaries: dict[str, Any],
    files: Sequence[dict[str, Any]],
) -> str:
    """递归渲染文件树 HTML。"""
    rows: list[str] = []
    for dir_name in sorted(node["dirs"]):
        label, child = collapse_chain(dir_name, node["dirs"][dir_name])
        rows.append(
            '<details class="node dir" open>'
            f'<summary class="dir-row"><span class="dir-name">{esc(label)}</span>'
            f'<span class="dir-count">{count_files(child)}</span></summary>'
            f'<div class="children">{render_tree(child, summaries, files)}</div>'
            "</details>"
        )
    for leaf in sorted(node["leaves"], key=lambda item: item["name"]):
        file_entry = files[leaf["index"]]
        path = str(file_entry["path"])
        summary = file_summary(summaries, path)
        moved_from = moved_from_path(file_entry)
        # 移动过的文件要一眼看出来：名字旁边给徽标，下面单独一行写清从哪来
        badge_html = '<span class="move-badge">移动</span>' if moved_from else ""
        move_html = f'<span class="file-move-path">← {esc(moved_from)}</span>' if moved_from else ""
        rows.append(
            f'<a class="node file-row" href="#f{leaf["index"]}" data-index="{leaf["index"]}" '
            f'title="{esc(path)}">'
            f'<span class="file-name">{esc(leaf["name"])}</span>'
            f'<span class="file-hit">{badge_html}<span class="add-stat">+{leaf["added"]}</span>'
            f'<span class="del-stat">-{leaf["removed"]}</span></span>'
            f'<span class="file-summary">{esc(summary)}</span>'
            f"{move_html}</a>"
        )
    return "".join(rows)


def count_files(node: dict[str, Any]) -> int:
    """统计子树内的文件数。"""
    return len(node["leaves"]) + sum(count_files(child) for child in node["dirs"].values())


# ─────────────────────────────────────────────────────────────────────────────
# 右侧 diff
# ─────────────────────────────────────────────────────────────────────────────


def esc(text: str) -> str:
    """HTML 转义。

    引号一并转义：``&quot;`` 在元素文本里照样渲染成 ``"``，可读性不变；但同一个函数
    落在属性位（``title="…"``）时，不转义引号就会被路径里的 ``"`` 提前闭合，等于把
    任意属性——包括事件处理器——注进这份要发给别人的报告。路径来自被检查的仓库，
    不是可信内容。
    """
    return html.escape(text, quote=True)


def render_line(line: str) -> str:
    """渲染单行 diff，按增/删/上下文/元信息着色。"""
    if line.startswith("+"):
        css_class, body = "add", line[1:]
    elif line.startswith("-"):
        css_class, body = "del", line[1:]
    elif line.startswith("\\"):
        css_class, body = "meta", line
    else:
        css_class, body = "ctx", line
    return f'<div class="line {css_class}"><span class="txt">{esc(body) or "&nbsp;"}</span></div>'


def move_lines_html(pair_path: str, path: str) -> str:
    """渲染「← 来源 / → 现址」两行路径，左侧汇总卡与右侧横幅共用。"""
    return (
        f'<span class="mv-line"><span class="mv-glyph">←</span>'
        f'<span class="mv-old">{esc(pair_path)}</span></span>'
        f'<span class="mv-line"><span class="mv-glyph">→</span>'
        f'<span class="mv-new">{esc(path)}</span></span>'
    )


def render_move_banner(file_entry: dict[str, Any], moved_from: str) -> str:
    """渲染文件移动横幅，替代原先低对比度的 rename 元信息行。"""
    similarity = file_entry.get("similarity")
    similarity_html = (
        f'<span class="mv-sim">内容相似度 {esc(str(similarity))}</span>' if similarity else ""
    )
    return (
        '<div class="move-banner"><span class="move-badge">移动</span>'
        f"{move_lines_html(moved_from, str(file_entry['path']))}"
        f"{similarity_html}</div>"
    )


def render_moves_card(files: Sequence[dict[str, Any]]) -> str:
    """渲染左侧栏顶部的「文件移动」汇总卡；没有移动时返回空串。"""
    moved_entries = [
        (index, file_entry) for index, file_entry in enumerate(files) if moved_from_path(file_entry)
    ]
    if not moved_entries:
        return ""
    items: list[str] = []
    for index, file_entry in moved_entries:
        added, removed = count_changes(file_entry)
        detail = "内容未变更" if added + removed == 0 else f"另有 {added + removed} 行改动"
        similarity = file_entry.get("similarity")
        detail_text = f"相似度 {esc(str(similarity))} · {detail}" if similarity else detail
        items.append(
            f'<li><a href="#f{index}">'
            f"{move_lines_html(moved_from_path(file_entry), str(file_entry['path']))}"
            f'<span class="mv-sim">{detail_text}</span></a></li>'
        )
    return (
        '<div class="moves-card">'
        f'<div class="moves-title">文件移动<span class="move-badge">'
        f"{len(moved_entries)} 个文件换了路径</span></div>"
        f'<ol class="moves-list">{"".join(items)}</ol></div>'
    )


def render_section(index: int, file_entry: dict[str, Any], summaries: dict[str, Any]) -> str:
    """渲染右侧单个文件的完整 diff 区块。"""
    path = file_entry["path"]
    added, removed = count_changes(file_entry)
    blocks: list[str] = []

    if file_entry["meta"]:
        meta_html = "".join(
            f'<div class="line meta"><span class="txt">{esc(line)}</span></div>'
            for line in file_entry["meta"]
        )
        blocks.append(f'<div class="hunk-body meta-only">{meta_html}</div>')

    moved_from = moved_from_path(file_entry)
    if moved_from:
        blocks.append(render_move_banner(file_entry, moved_from))

    for hunk_index, hunk in enumerate(file_entry["hunks"]):
        note = hunk_note(summaries, path, hunk_index)
        note_html = f'<div class="hunk-note">{esc(note)}</div>' if note else ""
        lines_html = "".join(render_line(line) for line in hunk["lines"])
        blocks.append(
            f'<div class="hunk">{note_html}'
            f'<div class="hunk-head">@@ -{hunk["old_start"]} +{hunk["new_start"]} @@ '
            f'{esc(hunk["label"])}</div>'
            f'<div class="hunk-body">{lines_html}</div></div>'
        )

    if not file_entry["hunks"]:
        if moved_from:
            blocks.append('<p class="empty-hunk">纯移动：文件内容未变更，没有可展示的 hunk。</p>')
        else:
            blocks.append('<p class="empty-hunk">无内容变更（模式变更或二进制文件）。</p>')

    summary = file_summary(summaries, path)
    summary_html = f'<p class="summary">{esc(summary)}</p>' if summary else ""
    return (
        f'<section class="file" id="f{index}">'
        f'<header class="file-head"><h2>{esc(path)}</h2>'
        f'<div class="stats"><span class="add-stat">+{added}</span>'
        f'<span class="del-stat">-{removed}</span></div></header>'
        f"{summary_html}{''.join(blocks)}</section>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 页面骨架
# ─────────────────────────────────────────────────────────────────────────────

STYLE = """
  :root {
    --bg: #0f1420; --panel: #161d2d; --panel2: #1b2334; --line: #263148;
    --fg: #d7dee9; --muted: #8b98ad; --add: #1f3a2c; --add-fg: #7ee2a8;
    --del: #3d2230; --del-fg: #ff9aa8; --accent: #6aa9ff;
  }
  * { box-sizing: border-box; }
  html { scroll-behavior: smooth; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font-family: -apple-system, "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 14px; line-height: 1.6;
  }
  .layout { display: grid; grid-template-columns: 470px 1fr; min-height: 100vh; }

  /* ── 左侧改动树 ───────────────────────────────────────── */
  aside {
    position: sticky; top: 0; height: 100vh; overflow-y: auto;
    background: var(--panel); border-right: 1px solid var(--line);
    padding: 16px 12px 40px;
    /* 侧栏滚到底后不再把滚动链给页面，否则联动高亮会把侧栏拽回上方 */
    overscroll-behavior: contain;
  }
  aside h1 { font-size: 15px; margin: 0 0 4px 4px; }
  aside .meta-line { color: var(--muted); font-size: 12px; margin: 0 0 4px 4px; }
  aside .totals { font-size: 12px; color: var(--muted); margin: 0 0 14px 4px; }
  .tree { display: flex; flex-direction: column; }

  details.dir { margin: 0; }
  details.dir > summary {
    list-style: none; cursor: pointer; display: flex; align-items: center;
    gap: 6px; padding: 5px 8px; border-radius: 6px; font-size: 13px;
    font-weight: 600; color: #b9c6db;
  }
  details.dir > summary::-webkit-details-marker { display: none; }
  details.dir > summary:hover { background: var(--panel2); }
  details.dir > summary::before {
    content: "\25B8"; color: var(--muted); font-size: 10px; width: 10px;
    transition: transform .12s ease;
  }
  details.dir[open] > summary::before { transform: rotate(90deg); }
  .dir-row { padding-left: 8px; }
  .dir-name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
  .dir-count {
    margin-left: auto; color: var(--muted); font-size: 11px; font-weight: 400;
    background: var(--panel2); border-radius: 8px; padding: 0 6px;
  }
  .children { border-left: 1px dashed var(--line); margin-left: 8px; }

  .file-row {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px;
    text-decoration: none; color: var(--fg); padding: 6px 8px;
    border-radius: 6px; border-left: 2px solid transparent; padding-left: 8px;
  }
  .file-row:hover { background: var(--panel2); }
  .file-row.active { background: var(--panel2); border-left-color: var(--accent); }
  .file-name {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 12.5px; overflow-wrap: anywhere; white-space: normal; min-width: 0;
  }
  .file-hit {
    font-variant-numeric: tabular-nums; font-size: 11px; white-space: nowrap;
    display: flex; gap: 5px;
  }
  .file-summary {
    grid-column: 1 / -1; color: var(--muted); font-size: 12px; line-height: 1.5;
    overflow: hidden; display: -webkit-box; -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
  }
  .file-row.active .file-summary { -webkit-line-clamp: unset; color: #b3c0d4; }

  /* ── 文件移动（重命名）───────────────────────────────── */
  .moves-card {
    margin: 0 4px 12px; padding: 9px 11px; background: var(--panel2);
    border: 1px solid var(--line); border-radius: 8px;
  }
  .moves-title {
    display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
    font-size: 12px; font-weight: 600; color: #b9c6db;
  }
  .moves-list {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 9px;
  }
  .moves-list a { text-decoration: none; display: block; border-radius: 5px; padding: 2px 3px; }
  .moves-list a:hover { background: var(--panel); }
  .moves-list a:hover .mv-new { color: #a8cdff; }
  .mv-line {
    display: flex; gap: 6px; align-items: baseline;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 10.5px; line-height: 1.45; overflow-wrap: anywhere;
  }
  .mv-glyph { flex: 0 0 9px; color: var(--muted); font-weight: 700; }
  .mv-old { color: var(--muted); text-decoration: line-through; text-decoration-color: #4a586f; }
  .mv-new { color: var(--accent); }
  .mv-sim { display: block; margin-left: 15px; color: var(--muted); font-size: 10px; }

  .move-badge {
    font-size: 10px; font-weight: 600; letter-spacing: .3px;
    background: #24344f; color: #9dc0ff; border: 1px solid #35507a;
    border-radius: 4px; padding: 0 5px; white-space: nowrap;
  }
  .file-move-path {
    grid-column: 1 / -1; color: var(--muted); opacity: .85; font-size: 10.5px;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    overflow-wrap: anywhere;
  }
  .move-banner {
    display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline;
    background: #172439; border: 1px solid #2f4a72; border-radius: 8px;
    padding: 10px 12px; margin-bottom: 8px;
  }

  /* ── 右侧全部文件 ─────────────────────────────────────── */
  main { padding: 24px 28px 80px; max-width: 1100px; }
  .file {
    background: var(--panel); border: 1px solid var(--line); border-radius: 10px;
    padding: 16px 18px; margin-bottom: 26px; scroll-margin-top: 20px;
  }
  .file-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
  .file h2 {
    font-size: 15px; margin: 0;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  .stats span { font-variant-numeric: tabular-nums; font-size: 12px; margin-left: 8px; }
  .add-stat { color: var(--add-fg); }
  .del-stat { color: var(--del-fg); }
  .summary {
    color: #b6c2d6; background: var(--panel2); border-left: 3px solid var(--accent);
    padding: 9px 12px; border-radius: 0 6px 6px 0; margin: 12px 0 16px; font-size: 13px;
  }
  .empty-hunk { color: var(--muted); font-size: 12px; margin: 8px 0 0; }
  .hunk { margin-bottom: 14px; }
  .hunk-note { font-size: 12px; color: var(--muted); margin-bottom: 5px; }
  .hunk-head {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
    color: var(--accent); background: #131a28; padding: 4px 10px;
    border-radius: 6px 6px 0 0; border: 1px solid var(--line); border-bottom: none;
  }
  .hunk-body {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px;
    border: 1px solid var(--line); border-radius: 0 0 6px 6px; overflow-x: auto;
    background: #111826;
  }
  .hunk-body.meta-only { border-radius: 6px; margin-bottom: 8px; }
  .line { display: flex; white-space: pre; }
  .line .txt { padding: 0 12px 0 14px; width: 100%; }
  .line.add { background: var(--add); }
  .line.add .txt { color: var(--add-fg); }
  .line.del { background: var(--del); }
  .line.del .txt { color: var(--del-fg); }
  .line.ctx .txt { color: #aab6c8; }
  .line.meta .txt { color: var(--muted); }
  .empty { padding: 40px; color: var(--muted); }
"""

SCRIPT = """
  // 缩进交给 .children 的层级 margin，这里只负责滚动高亮
  var rows = Array.prototype.slice.call(document.querySelectorAll('.file-row'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('main .file'));
  var aside = document.querySelector('aside');
  var byIndex = {};
  rows.forEach(function (row) { byIndex[row.dataset.index] = row; });

  var ticking = false;
  var activeId = null;
  var sidebarTouchedAt = 0;
  // 用户主动操作侧栏（滚轮 / 触摸 / 按下）时，短暂抑制自动滚动。
  // 否则「把侧栏滚到底再继续滚」会因滚动链把页面滚起来，再被这里拽回上方。
  ['wheel', 'touchmove', 'pointerdown'].forEach(function (eventName) {
    aside.addEventListener(eventName, function () {
      sidebarTouchedAt = Date.now();
    }, { passive: true });
  });

  function syncActive() {
    ticking = false;
    var bestId = null;
    var bestDelta = Infinity;
    sections.forEach(function (sec, i) {
      var delta = Math.abs(sec.getBoundingClientRect().top - 24);
      if (delta < bestDelta) { bestDelta = delta; bestId = String(i); }
    });
    var active = byIndex[bestId];
    if (!active) { return; }

    if (bestId !== activeId) {
      rows.forEach(function (row) { row.classList.remove('active'); });
      active.classList.add('active');
      activeId = bestId;
      // 展开所在目录，保证高亮项可见
      var parent = active.parentElement;
      while (parent && parent !== document.body) {
        if (parent.tagName === 'DETAILS') { parent.open = true; }
        parent = parent.parentElement;
      }
    }

    if (Date.now() - sidebarTouchedAt < 1200) { return; }

    var box = active.getBoundingClientRect();
    var asideBox = aside.getBoundingClientRect();
    if (box.top < asideBox.top + 8 || box.bottom > asideBox.bottom - 8) {
      active.scrollIntoView({ block: 'nearest' });
    }
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; window.requestAnimationFrame(syncActive); }
  }, { passive: true });
  window.addEventListener('load', syncActive);
  syncActive();
"""


def render_page(
    *,
    files: Sequence[dict[str, Any]],
    summaries: dict[str, Any],
    title: str,
    meta_line: str,
) -> str:
    """组装完整 HTML 页面。"""
    total_added = sum(count_changes(file_entry)[0] for file_entry in files)
    total_removed = sum(count_changes(file_entry)[1] for file_entry in files)
    tree_html = render_tree(build_tree(files), summaries, files)
    moves_html = render_moves_card(files)
    sections = "".join(
        render_section(index, file_entry, summaries) for index, file_entry in enumerate(files)
    )
    if not files:
        sections = '<p class="empty">没有匹配的改动。</p>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>{esc(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="layout">
  <aside>
    <h1>{esc(title)}</h1>
    <div class="meta-line">{esc(meta_line)}</div>
    <div class="totals">{len(files)} 个文件 ·
      <span class="add-stat">+{total_added}</span>
      <span class="del-stat">-{total_removed}</span></div>
    {moves_html}
    <div class="tree">{tree_html}</div>
  </aside>
  <main>{sections}</main>
</div>
<script>{SCRIPT}</script>
</body>
</html>
"""


def open_in_browser(path: Path) -> None:
    """用系统默认方式打开报告（失败时静默，不影响生成结果）。"""
    if sys.platform == "darwin":
        opener = ["open", str(path)]
    elif shutil.which("xdg-open"):
        opener = ["xdg-open", str(path)]
    else:
        return
    subprocess.run(opener, check=False, capture_output=True)


def default_output_path(repo: Path) -> Path:
    """默认输出到临时目录，避免污染被检查的仓库。"""
    return Path("/tmp") / f"{repo.name}-diff-report.html"


def build_meta_line(scope: DiffScope, *, branch: str | None) -> str:
    """生成左侧顶部的一行环境说明。"""
    scope_label = {
        "staged": "已暂存改动",
        "unstaged": "未暂存改动",
        "head": "相对 HEAD 的全部改动" if scope.has_head else "全部改动（按索引计）",
        "range": f"{scope.base}...HEAD",
    }.get(scope.name, scope.name)
    parts = [f"分支 {branch}" if branch else "尚无提交", scope_label]
    if scope.excludes:
        parts.append("已排除 " + "、".join(scope.excludes))
    else:
        parts.append("未排除任何路径")
    return " · ".join(parts)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="把 git 改动渲染成自包含的 HTML 报告（文件树 + 摘要 + 高亮 diff）。"
    )
    parser.add_argument("--repo", help="仓库根目录，默认按当前工作目录回溯。")
    parser.add_argument(
        "--scope",
        choices=("staged", "unstaged", "head", "range"),
        default="head",
        help="diff 范围：staged=已暂存，unstaged=未暂存，head=相对 HEAD，range=--base...HEAD。",
    )
    parser.add_argument("--base", help="--scope range 的基准 revision。")
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        help="追加排除的路径 glob，可重复；默认已排除 tests/** 与 **/tests/**。",
    )
    parser.add_argument("--include-tests", action="store_true", help="不排除 tests/**。")
    parser.add_argument(
        "--summaries",
        help="摘要 JSON：{title, meta_line, files:{<path>:{summary, hunk_notes}}}。",
    )
    parser.add_argument("--title", help="页面标题，默认按仓库名生成。")
    parser.add_argument("--out", help="输出 HTML 路径，默认 /tmp/<repo>-diff-report.html。")
    parser.add_argument("--open", action="store_true", help="生成后用系统默认浏览器打开。")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """命令行入口。"""
    args = parse_args(argv)
    try:
        repo = resolve_repo(args.repo)
        # 用户 --exclude 是追加而非替换：--include-tests 只关掉默认的测试排除。
        excludes = list(args.exclude or [])
        if not args.include_tests:
            excludes = [*DEFAULT_EXCLUDES, *excludes]
        scope = DiffScope(
            name=args.scope,
            base=args.base,
            excludes=tuple(excludes),
            has_head=has_head_commit(repo),
        )
        diff_text = _run_git(repo, build_diff_args(scope))
        files = parse_diff(diff_text)
        summaries = load_summaries(args.summaries)
        title = args.title or summaries.get("title") or f"{repo.name} 改动报告"
        meta_line = summaries.get("meta_line") or build_meta_line(
            scope, branch=current_branch(repo)
        )
        page = render_page(files=files, summaries=summaries, title=title, meta_line=str(meta_line))
        out_path = Path(args.out).expanduser() if args.out else default_output_path(repo)
        out_path.write_text(page, encoding="utf-8")
    except DiffReportError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"wrote {out_path} ({len(files)} files, {out_path.stat().st_size} bytes)")
    if args.open:
        open_in_browser(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
