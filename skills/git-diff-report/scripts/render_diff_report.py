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
import ast
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

DIFF_GIT_HEADER = "diff --git "
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


def _run_git(repo: Path, args: Sequence[str]) -> str:
    """在指定仓库运行 git 命令并返回标准输出。"""
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
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


def current_branch(repo: Path) -> str:
    """返回当前分支名（detached 时返回短 hash）。"""
    branch = _run_git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if branch and branch != "HEAD":
        return branch
    return _run_git(repo, ["rev-parse", "--short", "HEAD"]).strip()


def build_diff_args(scope: str, base: str | None, excludes: Sequence[str]) -> list[str]:
    """把 scope/排除规则翻译成 `git diff` 参数列表。"""
    if scope == "staged":
        args = ["diff", "--staged"]
    elif scope == "unstaged":
        args = ["diff"]
    elif scope == "head":
        args = ["diff", "HEAD"]
    elif scope == "range":
        if not base:
            raise DiffReportError("--scope range requires --base <rev>.")
        args = ["diff", f"{base}...HEAD"]
    else:
        raise DiffReportError(f"Unknown scope: {scope}")
    if excludes:
        args += ["--", *[f":(exclude){pattern}" for pattern in excludes]]
    return args


def _split_git_path_tokens(rest: str) -> list[str]:
    """拆分 `diff --git` 后面的两个路径 token，兼容 git 的引号转义。"""
    tokens: list[str] = []
    index = 0
    length = len(rest)
    while index < length and len(tokens) < 2:
        while index < length and rest[index] == " ":
            index += 1
        if index < length and rest[index] == '"':
            end = index + 1
            while end < length:
                if rest[end] == "\\":
                    end += 2
                    continue
                if rest[end] == '"':
                    break
                end += 1
            raw = rest[index : end + 1]
            try:
                tokens.append(ast.literal_eval(raw))
            except (SyntaxError, ValueError):
                tokens.append(raw.strip('"'))
            index = end + 1
        else:
            end = rest.find(" ", index)
            if end == -1:
                end = length
            tokens.append(rest[index:end])
            index = end
    return tokens


def parse_diff(diff_text: str) -> list[dict[str, Any]]:
    """把 unified diff 文本解析成「文件 → hunk」结构。"""
    files: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    in_hunk = False
    for line in diff_text.splitlines():
        if line.startswith(DIFF_GIT_HEADER):
            tokens = _split_git_path_tokens(line[len(DIFF_GIT_HEADER) :])
            path = tokens[1] if len(tokens) == 2 else (tokens[0] if tokens else "unknown")
            if path.startswith("b/"):
                path = path[2:]
            current = {"path": path, "meta": [], "hunks": []}
            files.append(current)
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
        elif line.startswith(METADATA_PREFIXES):
            current["meta"].append(line)
    return files


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


def render_tree(node: dict[str, Any], summaries: dict[str, Any], paths: Sequence[str]) -> str:
    """递归渲染文件树 HTML。"""
    rows: list[str] = []
    for dir_name in sorted(node["dirs"]):
        label, child = collapse_chain(dir_name, node["dirs"][dir_name])
        rows.append(
            '<details class="node dir" open>'
            f'<summary class="dir-row"><span class="dir-name">{esc(label)}</span>'
            f'<span class="dir-count">{count_files(child)}</span></summary>'
            f'<div class="children">{render_tree(child, summaries, paths)}</div>'
            "</details>"
        )
    for leaf in sorted(node["leaves"], key=lambda item: item["name"]):
        summary = file_summary(summaries, paths[leaf["index"]])
        rows.append(
            f'<a class="node file-row" href="#f{leaf["index"]}" data-index="{leaf["index"]}" '
            f'title="{esc(paths[leaf["index"]])}">'
            f'<span class="file-name">{esc(leaf["name"])}</span>'
            f'<span class="file-hit"><span class="add-stat">+{leaf["added"]}</span>'
            f'<span class="del-stat">-{leaf["removed"]}</span></span>'
            f'<span class="file-summary">{esc(summary)}</span>'
            "</a>"
        )
    return "".join(rows)


def count_files(node: dict[str, Any]) -> int:
    """统计子树内的文件数。"""
    return len(node["leaves"]) + sum(count_files(child) for child in node["dirs"].values())


# ─────────────────────────────────────────────────────────────────────────────
# 右侧 diff
# ─────────────────────────────────────────────────────────────────────────────


def esc(text: str) -> str:
    """HTML 转义（不转义引号，保持 diff 原样可读）。"""
    return html.escape(text, quote=False)


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
        blocks.append('<p class="empty-hunk">无内容变更（重命名、模式变更或二进制文件）。</p>')

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
  var byIndex = {};
  rows.forEach(function (row) { byIndex[row.dataset.index] = row; });

  var ticking = false;
  function syncActive() {
    ticking = false;
    var bestId = null;
    var bestDelta = Infinity;
    sections.forEach(function (sec, i) {
      var delta = Math.abs(sec.getBoundingClientRect().top - 24);
      if (delta < bestDelta) { bestDelta = delta; bestId = String(i); }
    });
    rows.forEach(function (row) { row.classList.remove('active'); });
    var active = byIndex[bestId];
    if (!active) { return; }
    active.classList.add('active');
    // 展开所在目录，保证高亮项可见
    var parent = active.parentElement;
    while (parent && parent !== document.body) {
      if (parent.tagName === 'DETAILS') { parent.open = true; }
      parent = parent.parentElement;
    }
    var box = active.getBoundingClientRect();
    var aside = document.querySelector('aside');
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
    paths = [file_entry["path"] for file_entry in files]
    total_added = sum(count_changes(file_entry)[0] for file_entry in files)
    total_removed = sum(count_changes(file_entry)[1] for file_entry in files)
    tree_html = render_tree(build_tree(files), summaries, paths)
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


def build_meta_line(scope: str, base: str | None, excludes: Sequence[str], branch: str) -> str:
    """生成左侧顶部的一行环境说明。"""
    scope_label = {
        "staged": "已暂存改动",
        "unstaged": "未暂存改动",
        "head": "相对 HEAD 的全部改动",
        "range": f"{base}...HEAD",
    }.get(scope, scope)
    parts = [f"分支 {branch}", scope_label]
    if excludes:
        parts.append("已排除 " + "、".join(excludes))
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
        diff_text = _run_git(repo, build_diff_args(args.scope, args.base, excludes))
        files = parse_diff(diff_text)
        summaries = load_summaries(args.summaries)
        title = args.title or summaries.get("title") or f"{repo.name} 改动报告"
        meta_line = summaries.get("meta_line") or build_meta_line(
            args.scope, args.base, excludes, current_branch(repo)
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
