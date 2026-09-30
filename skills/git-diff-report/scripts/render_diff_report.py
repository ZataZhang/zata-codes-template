#!/usr/bin/env python3
"""把 git 工作区改动渲染成一份自包含的 HTML 报告。

左侧是改动文件树（可折叠、带改动总结与 +/− 统计，点击跳转、滚动联动），
右侧是全部文件的完整 diff：浅色主题与 just view 同源，逐行带新旧行号双列，
长行折行不横滚。所有资源内联在单个 HTML 文件里，无外部依赖。

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
from typing import Any, Iterator, Sequence

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


#: 文件角色在「重点文件清单」里的展示顺序：越靠前越是必须先读的落地代码。
FILE_ROLE_ORDER: tuple[str, ...] = (
    "核心逻辑",
    "接入装配",
    "基础设施",
    "配置",
    "导出",
    "文档",
    "任务/流程",
    "测试",
    "其他",
)

#: 默认「必读」的角色——改动要理解清楚就绕不开这几类。
MUST_READ_ROLES: frozenset[str] = frozenset({"核心逻辑", "接入装配", "基础设施"})

_CONFIG_FILENAMES: frozenset[str] = frozenset(
    {"config.toml", "pyproject.toml", "justfile", "mkdocs.yml", "package.json"}
)


def _heuristic_file_role(path: str) -> str:
    """按路径推断文件角色，作为摘要 JSON 未给 ``role`` 时的兜底。"""
    basename = path.rsplit("/", 1)[-1]
    if basename == "__init__.py":
        return "导出"
    if path.startswith("tests/") or "/tests/" in f"/{path}" or basename.startswith("test_"):
        return "测试"
    if path.startswith("docs/") or basename.endswith(".md"):
        return "文档"
    if path.startswith("tasks/"):
        return "任务/流程"
    if path.startswith("src/backend/engines/") or path.startswith("src/backend/core/"):
        return "核心逻辑"
    if path.startswith("src/backend/composition/") or path.startswith("src/backend/api/"):
        return "接入装配"
    if path.startswith("src/backend/infrastructure/"):
        return "基础设施"
    if (
        basename in _CONFIG_FILENAMES
        or path.startswith(".env")
        or basename.endswith((".yml", ".yaml", ".toml"))
    ):
        return "配置"
    return "其他"


def file_role(summaries: dict[str, Any], path: str) -> str:
    """取文件角色：优先用摘要 JSON 的 ``role``，否则按路径推断。"""
    entry = summaries.get("files", {}).get(path) or {}
    authored_role = entry.get("role")
    if isinstance(authored_role, str) and authored_role.strip():
        return authored_role.strip()
    return _heuristic_file_role(path)


def is_must_read(summaries: dict[str, Any], path: str) -> bool:
    """判断文件是否「必读」：摘要 JSON 的 ``must_read`` 优先，否则按角色兜底。"""
    entry = summaries.get("files", {}).get(path) or {}
    authored_flag = entry.get("must_read")
    if isinstance(authored_flag, bool):
        return authored_flag
    return file_role(summaries, path) in MUST_READ_ROLES


def authored_key_hunks(summaries: dict[str, Any], path: str, hunk_count: int) -> set[int] | None:
    """取摘要 JSON 显式指定的关键 hunk 序号；未指定或全部越界时返回 ``None``。"""
    entry = summaries.get("files", {}).get(path) or {}
    raw_indexes = entry.get("key_hunks")
    if not isinstance(raw_indexes, list):
        return None
    valid_indexes = {
        raw_index for raw_index in raw_indexes if _is_int(raw_index) and 0 <= raw_index < hunk_count
    }
    return valid_indexes or None


def _is_int(value: Any) -> bool:
    """判断是否为非布尔整数（``bool`` 是 ``int`` 的子类，必须排除）。"""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class FocusRange:
    """hunk 内要展开的行区间（**新侧行号**，闭区间）。

    用在「一个 hunk 覆盖整个新文件」这类场景：hunk 级折叠帮不上忙（只有一个 hunk），
    只能把注意力收到区间内，其余折成一行可点开的占位。
    """

    start: int
    end: int
    label: str = ""

    def contains(self, line_number: int) -> bool:
        """判断某个新侧行号是否落在本区间内。"""
        return self.start <= line_number <= self.end


def authored_focus_ranges(summaries: dict[str, Any], path: str) -> tuple[FocusRange, ...]:
    """取摘要 JSON 的 ``focus_ranges`` 解析成行区间；未提供或全部非法时返回空元组。

    区间端点写反会自动归正；端点不是整数、或 ``start`` 大于 ``end`` 修正后仍为空的条目
    直接跳过——聚焦是给人减负的，宁可退化成整段展开，也不要因为一处笔误把代码藏起来。
    """
    entry = summaries.get("files", {}).get(path) or {}
    raw_ranges = entry.get("focus_ranges")
    if not isinstance(raw_ranges, list):
        return ()
    parsed_ranges: list[FocusRange] = []
    for raw_range in raw_ranges:
        if not isinstance(raw_range, dict):
            continue
        raw_start = raw_range.get("start")
        raw_end = raw_range.get("end")
        if not _is_int(raw_start) or not _is_int(raw_end):
            continue
        start, end = sorted((int(raw_start), int(raw_end)))
        raw_label = raw_range.get("label")
        label_text = str(raw_label).strip() if raw_label else ""
        parsed_ranges.append(FocusRange(start=start, end=end, label=label_text))
    return tuple(parsed_ranges)


def resolve_key_hunks(summaries: dict[str, Any], path: str, hunk_count: int) -> set[int]:
    """决定一个文件哪些 hunk 算「关键」：显式 ``key_hunks`` → 有 ``hunk_notes`` 的 → 全部。

    返回的集合只用来决定折叠态的**默认展开**，不隐藏任何内容——非关键 hunk 仍以可展开的
    摘要行呈现。
    """
    authored_indexes = authored_key_hunks(summaries, path, hunk_count)
    if authored_indexes is not None:
        return authored_indexes
    noted_indexes = {
        hunk_index for hunk_index in range(hunk_count) if hunk_note(summaries, path, hunk_index)
    }
    return noted_indexes or set(range(hunk_count))


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
) -> tuple[str, list[int]]:
    """递归渲染文件树 HTML，并返回与可见顺序相同的文件索引。"""
    rows: list[str] = []
    file_indexes: list[int] = []
    for dir_name in sorted(node["dirs"]):
        label, child = collapse_chain(dir_name, node["dirs"][dir_name])
        child_html, child_indexes = render_tree(child, summaries, files)
        rows.append(
            '<details class="node dir" open>'
            f'<summary class="dir-row"><span class="dir-name">{esc(label)}</span>'
            f'<span class="dir-count">{count_files(child)}</span></summary>'
            f'<div class="children">{child_html}</div>'
            "</details>"
        )
        file_indexes.extend(child_indexes)
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
        file_indexes.append(leaf["index"])
    return "".join(rows), file_indexes


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


def render_line(line: str, *, old_show: str = "", new_show: str = "", anchor: str = "") -> str:
    """渲染单行 diff：新旧行号双列 + 按增/删/上下文/元信息着色。

    行号口径与 ``git diff`` 的 hunk 头一致：增行只显示新侧行号、删行只显示旧侧
    行号、上下文行两侧都显示，与 just view 改动视图同款。

    Args:
        line (str): 带 ``+`` / ``-`` / 空格前缀的原始 diff 行。
        old_show (str): 旧侧行号文本;删行与上下文行有值。
        new_show (str): 新侧行号文本;增行与上下文行有值。
        anchor (str): 可选的行级锚点 id(``f<文件序号>-l<新侧行号>``),供 ``file:line``
            跳转精准落到这一行;删行无新侧行号,不设锚点。
    """
    if line.startswith("+"):
        css_class, body = "add", line[1:]
    elif line.startswith("-"):
        css_class, body = "del", line[1:]
    elif line.startswith("\\"):
        css_class, body = "meta", line
    elif line.startswith(" "):
        css_class, body = "ctx", line[1:]
    else:
        # 无前缀的正文（meta-only 块里的 "new file mode" 等元信息行）原样保留。
        css_class, body = "ctx", line
    anchor_attribute = f' id="{anchor}"' if anchor else ""
    return (
        f'<div class="line {css_class}"{anchor_attribute}>'
        f'<span class="lineno"><span>{old_show}</span><em></em><span>{new_show}</span></span>'
        f'<span class="txt">{esc(body) or "&nbsp;"}</span></div>'
    )


def iter_hunk_numbered_lines(hunk: dict[str, Any]) -> Iterator[tuple[str, str, str]]:
    """按 unified diff 规则推进行号，产出 ``(原始行, 旧侧行号, 新侧行号)``。

    ``-`` 行消耗旧侧号、``+`` 行消耗新侧号、上下文行两边同时消耗；``\\`` 行（如
    "No newline at end of file"）不属于任何一侧，两侧行号都是空串。渲染与「可锚定行号」
    统计共用这一处规则，避免两处各推一遍导致漂移。
    """
    old_number = int(hunk["old_start"])
    new_number = int(hunk["new_start"])
    for line in hunk["lines"]:
        if line.startswith("+"):
            yield line, "", str(new_number)
            new_number += 1
        elif line.startswith("-"):
            yield line, str(old_number), ""
            old_number += 1
        elif line.startswith("\\"):
            yield line, "", ""
        else:
            yield line, str(old_number), str(new_number)
            old_number += 1
            new_number += 1


def anchorable_line_numbers(file_entry: dict[str, Any]) -> set[int]:
    """返回该文件在报告里带**新侧行号锚点**的行号集合。

    ``file:line`` 跳转只对落在 hunk 里的行有效——diff 不展示的行没有锚点。掌握这个集合
    才能在引用指向 hunk 之外时降级到文件锚点，而不是给出一个点不开的死链。
    """
    numbers: set[int] = set()
    for hunk in file_entry["hunks"]:
        for _line, _old_show, new_show in iter_hunk_numbered_lines(hunk):
            if new_show:
                numbers.add(int(new_show))
    return numbers


def _render_numbered_row(file_index: int, numbered_row: tuple[str, str, str]) -> str:
    """渲染一行已编号的 diff 行，新侧行号拿得到就带行锚点。"""
    line, old_show, new_show = numbered_row
    anchor = f"f{file_index}-l{new_show}" if new_show else ""
    return render_line(line, old_show=old_show, new_show=new_show, anchor=anchor)


def _focus_label_for_row(
    numbered_row: tuple[str, str, str], focus_ranges: Sequence[FocusRange]
) -> str | None:
    """返回该行所属聚焦区间的标签；``None`` 表示不在任何区间内（可折叠）。

    没有新侧行号的行（删行、``\\ No newline``）一律返回空标签（= 聚焦但不带说明）：它们
    不在任何新侧区间里，若跟着折叠，读者会以为这段什么都没删。
    """
    _line, _old_show, new_show = numbered_row
    if not new_show:
        return ""
    line_number = int(new_show)
    for focus_range in focus_ranges:
        if focus_range.contains(line_number):
            return focus_range.label
    return None


def _render_folded_run(
    file_index: int, numbered_rows: Sequence[tuple[str, str, str]], run_start: int, run_end: int
) -> str:
    """渲染一段未聚焦行：够长就折成一行占位，够短就直接显示。

    占位行写明折叠了多少行、行号区间，点开即见原文——折叠只改默认可见性，不删内容。
    """
    run_length = run_end - run_start
    rows_html = "".join(
        _render_numbered_row(file_index, numbered_row)
        for numbered_row in numbered_rows[run_start:run_end]
    )
    if run_length < MIN_FOLD_RUN_LINES:
        return rows_html
    first_line = numbered_rows[run_start][2] or numbered_rows[run_start][1]
    last_line = numbered_rows[run_end - 1][2] or numbered_rows[run_end - 1][1]
    return (
        '<details class="fold">'
        f'<summary class="fold-row">\u22ef 折叠 {run_length} 行'
        f"（{first_line}\u2013{last_line}）· 点击展开</summary>"
        f'<div class="fold-body">{rows_html}</div></details>'
    )


def render_hunk_rows(
    hunk: dict[str, Any],
    file_index: int,
    focus_ranges: Sequence[FocusRange] = (),
) -> str:
    """渲染一个 hunk 的全部行，可选地把未聚焦区间折起来。

    Args:
        hunk (dict[str, Any]): 单个 hunk。
        file_index (int): 该文件在报告里的序号,用于拼行级锚点。
        focus_ranges (Sequence[FocusRange]): 要展开的新侧行号区间。为空(默认)时整段展开;
            给定时区间外折成可点开的占位,但要满足两个门槛——该 hunk 行数够长、且这段
            未聚焦行够长——短于门槛的一律照常显示,不为两三行折一次。

    Returns:
        str: hunk 内全部行的 HTML;有**新侧行号**的行带 ``id="f<i>-l<新侧行号>"``,
        供 ``file:line`` 跳转精准落到这一行。
    """
    numbered_rows = list(iter_hunk_numbered_lines(hunk))
    if not focus_ranges or len(numbered_rows) < FOCUS_MIN_HUNK_LINES:
        return "".join(_render_numbered_row(file_index, row) for row in numbered_rows)

    blocks: list[str] = []
    row_index = 0
    active_label: str | None = None
    while row_index < len(numbered_rows):
        row_label = _focus_label_for_row(numbered_rows[row_index], focus_ranges)
        if row_label is None:
            run_end = row_index
            while run_end < len(numbered_rows) and (
                _focus_label_for_row(numbered_rows[run_end], focus_ranges) is None
            ):
                run_end += 1
            blocks.append(_render_folded_run(file_index, numbered_rows, row_index, run_end))
            row_index = run_end
            active_label = None
            continue
        # 每次进入新区间打一条说明，读者才知道这一段的看点是什么。
        if row_label and row_label != active_label:
            blocks.append(f'<div class="focus-caption">{esc(row_label)}</div>')
        active_label = row_label
        blocks.append(_render_numbered_row(file_index, numbered_rows[row_index]))
        row_index += 1
    return "".join(blocks)


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


def render_moves_card(files: Sequence[dict[str, Any]], display_indexes: Sequence[int]) -> str:
    """渲染左侧栏顶部的「文件移动」汇总卡；没有移动时返回空串。

    ``display_indexes`` 是树中可见顺序下的文件索引（``render_tree`` 的返回值）。
    锚点 ``#f<N>`` 用的是文件在 ``files`` 里的原始索引，因此必须取
    ``display_indexes`` 里的真实索引，而不是显示位置 ``enumerate`` 出来的序号——
    两者在显示顺序不同于原始顺序时并不相等，用错会跳到别的文件。
    """
    moved_entries = [
        (file_index, files[file_index])
        for file_index in display_indexes
        if moved_from_path(files[file_index])
    ]
    if not moved_entries:
        return ""
    items: list[str] = []
    for file_index, file_entry in moved_entries:
        added, removed = count_changes(file_entry)
        detail = "内容未变更" if added + removed == 0 else f"另有 {added + removed} 行改动"
        similarity = file_entry.get("similarity")
        detail_text = f"相似度 {esc(str(similarity))} · {detail}" if similarity else detail
        items.append(
            f'<li><a href="#f{file_index}">'
            f"{move_lines_html(moved_from_path(file_entry), str(file_entry['path']))}"
            f'<span class="mv-sim">{detail_text}</span></a></li>'
        )
    return (
        '<div class="moves-card">'
        f'<div class="moves-title">文件移动<span class="move-badge">'
        f"{len(moved_entries)} 个文件换了路径</span></div>"
        f'<ol class="moves-list">{"".join(items)}</ol></div>'
    )


#: hunk 数达到该值才启用「默认只展开关键 hunk」；低于该值的文件全部展开。
FOLD_HUNK_MIN_COUNT = 3

#: hunk 行数达到该值才启用「hunk 内聚焦折叠」；短 hunk 整段看就好，折起来反而更难读。
FOCUS_MIN_HUNK_LINES = 60

#: hunk 内一段未聚焦行少于该值时不折：为两三行折一次只会增加噪声。
MIN_FOLD_RUN_LINES = 6


def render_hunk_block(
    *,
    file_index: int,
    hunk: dict[str, Any],
    note: str,
    is_open: bool,
    focus_ranges: Sequence[FocusRange] = (),
) -> str:
    """渲染一个 hunk：``summary`` 是可点击的 hunk 头，默认展开态由 ``is_open`` 决定。

    折叠只改**默认展开态**，不删除内容：非关键 hunk 收成一行可点开的摘要（仍显示该
    hunk 的 ``+N -M`` 与说明），避免长文件里的大量噪声把重点淹掉。
    """
    added_lines = sum(1 for line in hunk["lines"] if line.startswith("+"))
    removed_lines = sum(1 for line in hunk["lines"] if line.startswith("-"))
    note_html = f'<span class="hunk-note">{esc(note)}</span>' if note else ""
    return (
        f'<details class="hunk"{" open" if is_open else ""}>'
        '<summary class="hunk-head"><span class="hunk-chevron" aria-hidden="true">\u25b8</span>'
        f'<span class="hunk-range">@@ -{hunk["old_start"]} +{hunk["new_start"]} @@ '
        f'{esc(hunk["label"])}</span>'
        f"{note_html}"
        f'<span class="hunk-hit"><span class="add-stat">+{added_lines}</span>'
        f'<span class="del-stat">-{removed_lines}</span></span></summary>'
        f'<div class="hunk-body">{render_hunk_rows(hunk, file_index, focus_ranges)}</div>'
        "</details>"
    )


def render_section(index: int, file_entry: dict[str, Any], summaries: dict[str, Any]) -> str:
    """渲染右侧单个文件的完整 diff 区块。"""
    path = file_entry["path"]
    added, removed = count_changes(file_entry)
    blocks: list[str] = []

    if file_entry["meta"]:
        meta_html = "".join(render_line(line) for line in file_entry["meta"])
        blocks.append(f'<div class="hunk-body meta-only">{meta_html}</div>')

    moved_from = moved_from_path(file_entry)
    if moved_from:
        blocks.append(render_move_banner(file_entry, moved_from))

    hunk_entries = file_entry["hunks"]
    # 只有「hunk 多到会淹没重点」的文件才折叠；短文件全部展开，避免多此一举。
    should_fold_unkeyed = len(hunk_entries) >= FOLD_HUNK_MIN_COUNT
    key_hunk_indexes = resolve_key_hunks(summaries, path, len(hunk_entries))
    focus_ranges = authored_focus_ranges(summaries, path)
    for hunk_index, hunk in enumerate(hunk_entries):
        blocks.append(
            render_hunk_block(
                file_index=index,
                hunk=hunk,
                note=hunk_note(summaries, path, hunk_index),
                is_open=(not should_fold_unkeyed) or hunk_index in key_hunk_indexes,
                focus_ranges=focus_ranges,
            )
        )

    if not hunk_entries:
        if moved_from:
            blocks.append('<p class="empty-hunk">纯移动：文件内容未变更，没有可展示的 hunk。</p>')
        else:
            blocks.append('<p class="empty-hunk">无内容变更（模式变更或二进制文件）。</p>')

    summary = file_summary(summaries, path)
    must_read_badge = (
        '<span class="role-badge must">必读</span>' if is_must_read(summaries, path) else ""
    )
    summary_html = f'<p class="summary">{esc(summary)}</p>' if summary else ""
    return (
        f'<section class="file" id="f{index}">'
        f'<button class="file-head" type="button" aria-expanded="true" '
        f'aria-controls="content-f{index}"><h2>{esc(path)}</h2>{must_read_badge}'
        f'<span class="stats"><span class="add-stat">+{added}</span>'
        f'<span class="del-stat">-{removed}</span></span>'
        '<span class="file-chevron" aria-hidden="true">▾</span></button>'
        f'<div class="file-content" id="content-f{index}">'
        f"{summary_html}{''.join(blocks)}</div></section>"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 页面骨架
# ─────────────────────────────────────────────────────────────────────────────

STYLE = """
  /* 设计令牌与 just view（scripts/shared/view/assets/viewer.css）同源，观感保持一致。 */
  :root {
    /* 报告是自包含文件，可能被任意 webview 打开：钉死浅色 color-scheme，
       防止深色系统下 UA 用深色画布 + 白字兜底（不支持 oklch/color-mix 的旧内核）。 */
    color-scheme: light;
    --radius: 0.625rem;
    --background: oklch(1 0 0);
    --foreground: oklch(0.129 0.042 264.695);
    --card: oklch(1 0 0);
    --primary: oklch(0.208 0.042 265.755);
    --primary-foreground: oklch(0.984 0.003 247.858);
    --secondary: oklch(0.968 0.007 247.896);
    --muted-foreground: oklch(0.554 0.046 257.417);
    --destructive: oklch(0.577 0.245 27.325);
    --border: oklch(0.929 0.013 255.508);
    --ring: oklch(0.704 0.04 256.788);
    --add: oklch(0.72 0.14 152 / 22%);
    --del: oklch(0.62 0.2 25 / 16%);
    --add-mark: oklch(0.5 0.13 152);
    --del-mark: oklch(0.52 0.2 25);
    --rename: oklch(0.62 0.11 256 / 18%);
    --rename-mark: oklch(0.48 0.13 256);
    --code-bg: oklch(0.995 0.002 250);
    --mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Microsoft YaHei", sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 10px; height: 100svh;
    background: color-mix(in oklab, var(--secondary) 60%, var(--background));
    color: var(--foreground);
    font-family: var(--sans);
    font-size: 13.5px; line-height: 1.5;
  }
  button { font: inherit; color: inherit; }

  /* ── 应用骨架：顶栏 + 左树/右 diff 两个独立滚动面 ─────── */
  .app { display: grid; height: 100%; grid-template-rows: auto minmax(0, 1fr); gap: 8px; }
  /* 有改动总览时多一行；总览自身是 auto 行，由 .overview-body 的 max-height 兜住高度。 */
  .app.has-overview { grid-template-rows: auto auto minmax(0, 1fr); }
  .body-grid {
    display: grid; min-height: 0; gap: 8px;
    grid-template-columns: minmax(320px, 440px) minmax(0, 1fr);
  }
  .surface {
    overflow: hidden; border: 1px solid var(--border);
    border-radius: calc(var(--radius) + 2px); background: var(--card);
  }

  /* ── 顶栏 ─────────────────────────────────────────────── */
  .topbar { display: flex; align-items: center; gap: 10px; padding: 9px 14px; }
  .repo-mark {
    display: grid; width: 24px; height: 24px; flex: none; place-items: center;
    border-radius: 7px; background: var(--primary); color: var(--primary-foreground);
    font-family: var(--mono); font-size: 12px; font-weight: 700;
  }
  .title-block { min-width: 0; }
  .topbar h1 {
    margin: 0; font-size: 15px; font-weight: 650;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .meta-line {
    color: var(--muted-foreground); font-size: 12px;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .spacer { flex: 1; }
  .totals {
    flex: none; color: var(--muted-foreground); font-family: var(--mono);
    font-size: 12px; font-variant-numeric: tabular-nums;
  }

  /* ── 改动总览（可选摘要）───────────────────────────────── */
  .overview { padding: 0; }
  .overview > summary.overview-head {
    display: flex; align-items: center; gap: 8px; padding: 9px 14px;
    list-style: none; cursor: pointer;
  }
  .overview > summary.overview-head::-webkit-details-marker { display: none; }
  .overview > summary.overview-head::before {
    content: "\25B8"; color: var(--muted-foreground); font-size: 10px;
    transition: transform .12s ease;
  }
  .overview[open] > summary.overview-head::before { transform: rotate(90deg); }
  .overview-badge { font-size: 13px; font-weight: 650; }
  .overview-hint { margin-left: auto; color: var(--muted-foreground); font-size: 11px; }
  .overview-body {
    border-top: 1px solid var(--border); padding: 4px 16px 14px;
  }
  .overview[open] .overview-body {
    overflow-y: auto; overscroll-behavior: contain; max-height: min(52vh, 620px);
  }
  .overview-body h2, .overview-body h3, .overview-body h4 {
    margin: 14px 0 6px; font-size: 13.5px; font-weight: 650;
  }
  .overview-body > :first-child { margin-top: 10px; }
  .overview-body p { margin: 6px 0; }
  .overview-body ul, .overview-body ol { margin: 6px 0; padding-left: 22px; }
  .overview-body li { margin: 3px 0; }
  .overview-body code {
    font-family: var(--mono); font-size: 12px; background: var(--secondary);
    border: 1px solid var(--border); border-radius: 5px; padding: 0 4px;
  }

  /* 总览里的「建议阅读顺序」与「重点文件清单」 */
  .ov-section + .ov-section { margin-top: 16px; }
  .ov-title {
    display: flex; align-items: baseline; gap: 8px; margin: 0 0 8px;
    font-size: 13.5px; font-weight: 650;
  }
  .ov-sub { color: var(--muted-foreground); font-size: 11px; font-weight: 400; }
  .ov-ref {
    color: var(--rename-mark); text-decoration: none;
    border-bottom: 1px dashed color-mix(in oklab, var(--rename-mark) 45%, transparent);
  }
  .ov-ref:hover { background: var(--rename); }
  .ov-steps { margin: 0; padding-left: 22px; }
  .ov-steps li { margin: 5px 0; }
  .ov-step-label { display: block; }
  .ov-step-refs { display: inline-flex; flex-wrap: wrap; gap: 8px; margin-top: 2px; }
  .ov-step-refs .ov-ref code { background: transparent; border: 0; padding: 0; }
  .ov-role { margin-top: 8px; }
  .ov-role-name {
    display: flex; align-items: center; gap: 6px; margin-bottom: 3px;
    font-size: 11.5px; font-weight: 600; color: var(--muted-foreground);
  }
  .ov-role-count {
    background: var(--secondary); border-radius: 8px; padding: 0 6px; font-weight: 400;
  }
  .ov-files { list-style: none; margin: 0 0 4px; padding: 0; }
  .ov-file a {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0 8px;
    align-items: baseline; padding: 4px 8px; border-radius: 6px;
    color: var(--foreground); text-decoration: none;
  }
  .ov-file a:hover { background: var(--secondary); }
  .ov-file-left { display: flex; align-items: baseline; gap: 6px; min-width: 0; }
  .ov-file-path { font-family: var(--mono); font-size: 12px; overflow-wrap: anywhere; }
  .ov-hit {
    display: flex; gap: 5px; font-family: var(--mono); font-size: 11px;
    font-variant-numeric: tabular-nums;
  }
  .ov-file-summary { grid-column: 1 / -1; color: var(--muted-foreground); font-size: 11.5px; }

  /* ── 左侧改动树 ───────────────────────────────────────── */
  aside.surface {
    display: flex; min-height: 0; flex-direction: column;
    padding: 10px 8px 12px; gap: 10px;
  }
  .tree { flex: 1; min-height: 0; overflow-y: auto; padding: 0 2px; overscroll-behavior: contain; }

  details.dir { margin: 0; }
  details.dir > summary {
    list-style: none; cursor: pointer; display: flex; align-items: center;
    gap: 6px; padding: 5px 8px; border-radius: 6px; font-size: 13px;
    font-weight: 600; color: var(--foreground);
  }
  details.dir > summary::-webkit-details-marker { display: none; }
  details.dir > summary:hover { background: var(--secondary); }
  details.dir > summary::before {
    content: "\25B8"; color: var(--muted-foreground); font-size: 10px; width: 10px;
    transition: transform .12s ease;
  }
  details.dir[open] > summary::before { transform: rotate(90deg); }
  .dir-row { padding-left: 8px; }
  .dir-name { font-family: var(--mono); }
  .dir-count {
    margin-left: auto; color: var(--muted-foreground); font-size: 11px; font-weight: 400;
    background: var(--secondary); border-radius: 8px; padding: 0 6px;
  }
  .children { border-left: 1px dashed var(--border); margin-left: 8px; }

  .file-row {
    display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px;
    text-decoration: none; color: var(--foreground); padding: 6px 8px;
    border-radius: 6px; border-left: 2px solid transparent; padding-left: 8px;
  }
  .file-row:hover { background: var(--secondary); }
  .file-row.active {
    background: color-mix(in oklab, var(--primary) 10%, transparent);
    border-left-color: var(--primary); color: var(--primary); font-weight: 620;
  }
  .file-name {
    font-family: var(--mono); font-size: 12.5px;
    overflow-wrap: anywhere; white-space: normal; min-width: 0;
  }
  .file-hit {
    font-variant-numeric: tabular-nums; font-size: 11px; white-space: nowrap;
    display: flex; gap: 5px; font-family: var(--mono);
  }
  .file-summary {
    grid-column: 1 / -1; color: var(--muted-foreground); font-size: 12px; line-height: 1.5;
    overflow: hidden; display: -webkit-box; -webkit-line-clamp: 4;
    -webkit-box-orient: vertical;
  }
  .file-row.active .file-summary { color: var(--foreground); opacity: .8; }

  /* ── 文件移动（重命名）───────────────────────────────── */
  .moves-card {
    flex: none; margin: 0 2px; padding: 9px 11px; background: var(--secondary);
    border: 1px solid var(--border); border-radius: 8px;
  }
  .moves-title {
    display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
    font-size: 12px; font-weight: 600; color: var(--foreground);
  }
  .moves-list {
    list-style: none; margin: 0; padding: 0;
    display: flex; flex-direction: column; gap: 9px;
  }
  .moves-list a {
    text-decoration: none; display: block; color: inherit;
    border-radius: 5px; padding: 2px 3px;
  }
  .moves-list a:hover { background: var(--card); }
  .moves-list a:hover .mv-new { color: var(--primary); }
  .mv-line {
    display: flex; gap: 6px; align-items: baseline;
    font-family: var(--mono); font-size: 10.5px; line-height: 1.45; overflow-wrap: anywhere;
  }
  .mv-glyph { flex: 0 0 9px; color: var(--muted-foreground); font-weight: 700; }
  .mv-old { color: var(--muted-foreground); text-decoration: line-through; }
  .mv-new { color: var(--rename-mark); }
  .mv-sim { display: block; margin-left: 15px; color: var(--muted-foreground); font-size: 10px; }

  .move-badge {
    font-size: 10px; font-weight: 600; letter-spacing: .3px;
    background: var(--rename); color: var(--rename-mark);
    border: 1px solid color-mix(in oklab, var(--rename-mark) 25%, transparent);
    border-radius: 4px; padding: 0 5px; white-space: nowrap;
  }
  .file-move-path {
    grid-column: 1 / -1; color: var(--muted-foreground); font-size: 10.5px;
    font-family: var(--mono); overflow-wrap: anywhere;
  }
  .move-banner {
    display: flex; flex-wrap: wrap; gap: 8px; align-items: baseline;
    background: var(--rename);
    border: 1px solid color-mix(in oklab, var(--rename-mark) 25%, transparent);
    border-radius: 8px; padding: 10px 12px; margin-bottom: 8px;
  }

  /* ── 右侧全部文件 ─────────────────────────────────────── */
  main.surface { display: flex; min-height: 0; flex-direction: column; }
  .viewer-body {
    flex: 1; min-height: 0; overflow-y: auto; background: var(--code-bg);
    padding: 14px 16px 60px; scroll-behavior: smooth;
  }
  .file {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    margin-bottom: 14px; scroll-margin-top: 12px;
  }
  .file-head {
    position: sticky; top: 0; z-index: 3;
    display: flex; width: 100%; justify-content: space-between;
    align-items: baseline; gap: 12px; margin: 0; padding: 10px 14px;
    border: 0; border-bottom: 1px solid var(--border); border-radius: 10px 10px 0 0;
    color: var(--foreground); background: var(--card); text-align: left; cursor: pointer;
  }
  .file-head:hover { background: var(--secondary); }
  .file-head:focus-visible { outline: 2px solid var(--ring); outline-offset: -3px; }
  .file-chevron {
    flex: 0 0 auto; color: var(--muted-foreground); font-size: 13px;
    transition: transform .12s ease;
  }
  .file.is-collapsed .file-chevron { transform: rotate(-90deg); }
  .file.is-collapsed .file-head { border-radius: 10px; border-bottom-color: transparent; }
  .file.is-collapsed .file-content { display: none; }
  .file-content { min-width: 0; padding: 12px 14px 14px; }
  .file h2 {
    flex: 1 1 auto; font-size: 13.5px; margin: 0; min-width: 0; overflow-wrap: anywhere;
    font-family: var(--mono); font-weight: 600;
  }
  .role-badge {
    flex: none; font-size: 10px; font-weight: 600; letter-spacing: .3px;
    border-radius: 4px; padding: 0 5px; white-space: nowrap; border: 1px solid transparent;
  }
  .role-badge.must {
    background: var(--add); color: var(--add-mark);
    border-color: color-mix(in oklab, var(--add-mark) 30%, transparent);
  }
  .role-badge.skim {
    background: var(--secondary); color: var(--muted-foreground);
    border-color: var(--border);
  }
  .stats span {
    font-variant-numeric: tabular-nums; font-size: 12px; margin-left: 8px;
    font-family: var(--mono);
  }
  .add-stat { color: var(--add-mark); }
  .del-stat { color: var(--del-mark); }
  .summary {
    color: var(--foreground); background: var(--secondary); border-left: 3px solid var(--primary);
    padding: 9px 12px; border-radius: 0 6px 6px 0; margin: 0 0 12px; font-size: 13px;
  }
  .empty-hunk { color: var(--muted-foreground); font-size: 12px; margin: 8px 0 0; }
  .hunk { margin-bottom: 14px; }
  /* hunk 头是 <summary>：折叠/展开整段，折叠时只剩一行摘要（含 +/- 与说明）。 */
  details.hunk > summary.hunk-head {
    display: flex; align-items: baseline; gap: 8px; cursor: pointer; list-style: none;
    font-family: var(--mono); font-size: 11.5px;
    color: var(--muted-foreground); background: var(--secondary); padding: 4px 14px;
    border: 1px solid var(--border); border-bottom: none;
    border-radius: 8px 8px 0 0;
  }
  details.hunk > summary.hunk-head::-webkit-details-marker { display: none; }
  details.hunk > summary.hunk-head:hover { background: var(--border); }
  details.hunk:not([open]) > summary.hunk-head {
    border-bottom: 1px solid var(--border); border-radius: 8px;
  }
  .hunk-chevron { flex: none; font-size: 10px; transition: transform .12s ease; }
  details.hunk[open] > summary.hunk-head .hunk-chevron { transform: rotate(90deg); }
  .hunk-range { min-width: 0; overflow-wrap: anywhere; }
  .hunk-note { flex: none; font-family: var(--sans); font-size: 11px; }
  .hunk-hit {
    margin-left: auto; flex: none; display: flex; gap: 6px;
    font-family: var(--mono); font-variant-numeric: tabular-nums;
  }
  .hunk-body {
    font-family: var(--mono); font-size: 12.5px; line-height: 1.65;
    border: 1px solid var(--border); border-radius: 0 0 8px 8px;
    background: var(--code-bg); padding: 4px 0;
  }
  /* hunk 内聚焦折叠：未聚焦区间收成一行占位，点开即见原文。 */
  details.fold > summary.fold-row {
    list-style: none; cursor: pointer; text-align: center;
    font-family: var(--mono); font-size: 11px; color: var(--muted-foreground);
    background: var(--secondary); padding: 2px 14px;
    border-top: 1px dashed var(--border); border-bottom: 1px dashed var(--border);
  }
  details.fold > summary.fold-row::-webkit-details-marker { display: none; }
  details.fold > summary.fold-row:hover { background: var(--border); color: var(--foreground); }
  details.fold[open] > summary.fold-row { border-bottom-style: solid; }
  /* 聚焦区间的小标题：说明这一段在看什么，只在区间起点出现一次。 */
  .focus-caption {
    font-family: var(--sans); font-size: 11px; font-weight: 600;
    color: var(--rename-mark); background: var(--rename);
    padding: 2px 14px; border-top: 1px solid var(--border);
  }
  .hunk-body.meta-only { border-radius: 8px; margin-bottom: 8px; }
  /* 行号双列 + 正文：正文折行而不横向滚动，口径同 just view 的改动视图。 */
  .line { display: grid; grid-template-columns: 78px minmax(0, 1fr); }
  .line .lineno {
    display: flex; justify-content: flex-end; align-items: baseline;
    padding-right: 12px; user-select: none;
    color: color-mix(in oklab, var(--muted-foreground) 75%, transparent);
  }
  .line .lineno em {
    font-style: normal; width: 8px;
    color: color-mix(in oklab, var(--muted-foreground) 48%, transparent);
  }
  .line .txt {
    min-width: 0; padding-right: 18px;
    white-space: pre-wrap; word-break: break-word;
  }
  .line.add { background: var(--add); }
  .line.add .txt::before { color: var(--add-mark); content: '+'; margin-right: 6px; }
  .line.del { background: var(--del); }
  .line.del .txt::before { color: var(--del-mark); content: "\2212"; margin-right: 6px; }
  .line.ctx .txt::before { content: ' '; margin-right: 6px; }
  .line.meta .txt { color: var(--muted-foreground); }
  /* 行级锚点：file:line 跳转落点。sticky 文件头约 40px，滚动时留出余量。 */
  .line { scroll-margin-top: 54px; }
  /* 放在 .line.add/.del 之后，同特异度靠后者胜出，跳转落点才能盖过增删底色。 */
  .line.flash { background: color-mix(in oklab, var(--ring) 42%, transparent); }
  .line.flash .lineno { color: var(--foreground); }
  .empty { padding: 40px; color: var(--muted-foreground); }

  @media (max-width: 900px) {
    .body-grid { grid-template-columns: minmax(0, 1fr); grid-template-rows: 240px minmax(0, 1fr); }
  }
"""

SCRIPT = """
  // 缩进交给 .children 的层级 margin，这里只负责滚动高亮。
  // 左右两栏各自独立滚动：右侧滚动容器是 .viewer-body，联动高亮挂它的 scroll 事件。
  var rows = Array.prototype.slice.call(document.querySelectorAll('.file-row'));
  var sections = Array.prototype.slice.call(document.querySelectorAll('.file'));
  var fileToggles = Array.prototype.slice.call(document.querySelectorAll('.file-head'));
  var aside = document.querySelector('aside');
  var scroller = document.querySelector('.viewer-body');
  // 侧栏的滚动面是内层 .tree，而不是 aside 本身（aside 只是 flex 外壳，overflow: hidden）。
  var treeScroller = document.querySelector('.tree');
  var byIndex = {};
  rows.forEach(function (row) { byIndex[row.dataset.index] = row; });

  fileToggles.forEach(function (toggle) {
    toggle.addEventListener('click', function () {
      var section = toggle.closest('.file');
      var expanded = toggle.getAttribute('aria-expanded') === 'true';
      toggle.setAttribute('aria-expanded', String(!expanded));
      section.classList.toggle('is-collapsed', expanded);
      if (expanded) {
        // 折叠后把后续文件放到查看区顶部，避免浏览器滚动锚定将其留在视口上方。
        var nextSection = section.nextElementSibling;
        while (nextSection && !nextSection.classList.contains('file')) {
          nextSection = nextSection.nextElementSibling;
        }
        if (nextSection) {
          window.requestAnimationFrame(function () {
            var top = nextSection.getBoundingClientRect().top;
            var base = scroller.getBoundingClientRect().top;
            scroller.scrollTo({ top: scroller.scrollTop + top - base - 12, behavior: 'instant' });
          });
        }
      }
    });
  });

  rows.forEach(function (row) {
    row.addEventListener('click', function () {
      var target = document.querySelector(row.getAttribute('href'));
      if (!target) { return; }
      target.classList.remove('is-collapsed');
      var toggle = target.querySelector('.file-head');
      if (toggle) { toggle.setAttribute('aria-expanded', 'true'); }
    });
  });

  // 跳转落点（含 file:line）可能落在折叠的文件、折叠的 hunk 或 hunk 内折叠的区间里：
  // 先把所有祖先展开，再滚动过去，并给目标行一次短暂高亮。原生 fragment 滚动对
  // display:none 里的目标无效，所以自己滚。
  function revealHashTarget() {
    var rawHash = location.hash || '';
    if (rawHash.indexOf('#f') !== 0) { return; }
    var target = document.getElementById(rawHash.slice(1));
    if (!target) { return; }
    var section = target.closest('.file');
    if (section) {
      section.classList.remove('is-collapsed');
      var head = section.querySelector('.file-head');
      if (head) { head.setAttribute('aria-expanded', 'true'); }
    }
    // 一路向上开掉所有 <details>：hunk 折叠与 hunk 内聚焦折叠用的是同一套祖先链。
    var ancestor = target.parentElement;
    while (ancestor) {
      if (ancestor.tagName === 'DETAILS') { ancestor.open = true; }
      ancestor = ancestor.parentElement;
    }
    if (target.classList.contains('line')) {
      target.classList.add('flash');
      window.setTimeout(function () { target.classList.remove('flash'); }, 1600);
    }
    window.requestAnimationFrame(function () {
      var targetBox = target.getBoundingClientRect();
      var viewBox = scroller.getBoundingClientRect();
      if (targetBox.top < viewBox.top + 8 || targetBox.bottom > viewBox.bottom - 8) {
        scroller.scrollTop += targetBox.top - viewBox.top - (viewBox.height / 2)
          + (targetBox.height / 2);
      }
    });
  }
  window.addEventListener('hashchange', revealHashTarget);
  window.addEventListener('load', revealHashTarget);

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
    // 锚点取滚动容器自身顶部下方 16px，而不是视口顶部：右栏在页面里也有偏移。
    var anchor = scroller.getBoundingClientRect().top + 16;
    sections.forEach(function (sec) {
      var delta = Math.abs(sec.getBoundingClientRect().top - anchor);
      // 右侧按文件树顺序渲染，但文件索引仍是原始 diff 索引；必须从 section id 取原始索引。
      if (delta < bestDelta) { bestDelta = delta; bestId = sec.id.slice(1); }
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

    var rowBox = active.getBoundingClientRect();
    var treeBox = treeScroller.getBoundingClientRect();
    if (rowBox.top < treeBox.top + 8) {
      treeScroller.scrollTop -= treeBox.top + 8 - rowBox.top;
    } else if (rowBox.bottom > treeBox.bottom - 8) {
      treeScroller.scrollTop += rowBox.bottom - (treeBox.bottom - 8);
    }
  }
  scroller.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; window.requestAnimationFrame(syncActive); }
  }, { passive: true });
  window.addEventListener('load', syncActive);
  syncActive();
"""


#: ``overview`` 字段支持的极简 Markdown 语法：标题、无序/有序列表、行内加粗与代码。
_OVERVIEW_HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)$")
_OVERVIEW_BULLET_RE = re.compile(r"^[-*]\s+(.*)$")
_OVERVIEW_ORDERED_RE = re.compile(r"^\d+\.\s+(.*)$")
_OVERVIEW_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_OVERVIEW_CODE_RE = re.compile(r"`([^`]+)`")


@dataclass(frozen=True)
class LinkTarget:
    """一个可跳转目标：文件在报告里的序号 + 该文件带行锚点的行号集合。

    ``line`` 只有落在 ``lines`` 里才拼行锚点——diff 不展示的行没有锚点，硬拼会得到
    点不开的死链。引用写偏或文件在生成间隙被改动时，自动降级为文件级跳转。
    """

    file_index: int
    lines: frozenset[int]

    def href(self, line_number: int | None) -> str:
        """返回跳转地址；行号不可锚定时降级为文件锚点。"""
        if line_number is not None and line_number in self.lines:
            return f"#f{self.file_index}-l{line_number}"
        return f"#f{self.file_index}"


def build_link_targets(files: Sequence[dict[str, Any]]) -> dict[str, LinkTarget]:
    """建立「改动文件路径 → 跳转目标」映射，供总览里的链接使用。"""
    return {
        str(file_entry["path"]): LinkTarget(
            file_index=file_index,
            lines=frozenset(anchorable_line_numbers(file_entry)),
        )
        for file_index, file_entry in enumerate(files)
    }


def _linkify_overview_paths(html_text: str, link_targets: dict[str, LinkTarget]) -> str:
    """把正文里出现的改动文件路径（可带 ``:行号``）包成指到对应文件/行的链接。

    单趟正则 + 长路径优先：替换出来的 ``href`` 不会被二次扫描，避免把链接套进链接；
    只有本次确实改动的文件才会变成链接，别处提到的路径原样保留。
    """
    if not link_targets or not html_text:
        return html_text
    escaped_targets = {esc(path): target for path, target in link_targets.items()}
    path_alternation = "|".join(
        re.escape(esc(path)) for path in sorted(link_targets, key=len, reverse=True)
    )
    link_pattern = re.compile(rf"(?P<path>{path_alternation})(?::(?P<line>\d+))?")

    def replace_match(match: re.Match[str]) -> str:
        target = escaped_targets.get(match.group("path"))
        if target is None:
            return match.group(0)
        raw_line = match.group("line")
        line_number = int(raw_line) if raw_line else None
        href = target.href(line_number)
        # 行号被降级掉时，显示文本也要跟着去掉 ``:行号``，否则链接与落点对不上。
        display_text = match.group(0) if href.endswith(f"-l{raw_line}") else match.group("path")
        return f'<a class="ov-ref" href="{href}">{display_text}</a>'

    return link_pattern.sub(replace_match, html_text)


def _render_overview_inline(text: str, link_targets: dict[str, LinkTarget]) -> str:
    """先转义、再套行内 ``**加粗**`` / `` `代码` ``、最后把文件路径变跳转链接。

    报告是要转发给他人的自包含文件，overview 文本也当不可信输入：转义在最前，保证它
    只能产生 ``strong`` / ``code`` / ``a``，不能注入任意标签。
    """
    escaped_text = esc(text)
    escaped_text = _OVERVIEW_BOLD_RE.sub(r"<strong>\1</strong>", escaped_text)
    escaped_text = _OVERVIEW_CODE_RE.sub(r"<code>\1</code>", escaped_text)
    return _linkify_overview_paths(escaped_text, link_targets)


def _resolve_reference(
    link_targets: dict[str, LinkTarget], reference: str
) -> tuple[str, str] | None:
    """把 ``path`` 或 ``path:line`` 解析成 ``(href, 短标签)``；非本次改动文件时返回 ``None``。

    短标签只留文件名（可选带 ``:行号``），完整路径放进 ``title``，避免阅读顺序里一长串
    绝对路径把版面撑爆。行号不可锚定时，短标签同样不显示行号。
    """
    raw_reference = reference.strip()
    if not raw_reference:
        return None
    path_part, separator, line_part = raw_reference.rpartition(":")
    if not path_part or not separator or not line_part.isdigit():
        path_part, line_part = raw_reference, ""
    target = link_targets.get(path_part)
    if target is None:
        return None
    line_number = int(line_part) if line_part else None
    href = target.href(line_number)
    short_name = path_part.rsplit("/", 1)[-1]
    anchored = line_number is not None and href.endswith(f"-l{line_number}")
    return href, f"{short_name}:{line_number}" if anchored else short_name


def _render_reading_path(summaries: dict[str, Any], link_targets: dict[str, LinkTarget]) -> str:
    """渲染可选 ``reading_path``：一条可点击的最短理解路径。"""
    raw_steps = summaries.get("reading_path")
    if not isinstance(raw_steps, list) or not raw_steps:
        return ""
    step_items: list[str] = []
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict):
            continue
        raw_label = raw_step.get("label")
        label_text = str(raw_label).strip() if raw_label else ""
        raw_refs = raw_step.get("refs")
        refs = raw_refs if isinstance(raw_refs, list) else []
        ref_links: list[str] = []
        for raw_ref in refs:
            resolved_reference = _resolve_reference(link_targets, str(raw_ref))
            if resolved_reference is None:
                continue
            href, short_label = resolved_reference
            title_attribute = f' title="{esc(str(raw_ref))}"'
            ref_links.append(
                f'<a class="ov-ref" href="{href}"{title_attribute}>'
                f"<code>{esc(short_label)}</code></a>"
            )
        if not label_text and not ref_links:
            continue
        label_html = f'<span class="ov-step-label">{esc(label_text)}</span>' if label_text else ""
        refs_html = f'<span class="ov-step-refs">{"".join(ref_links)}</span>' if ref_links else ""
        step_items.append(f"<li>{label_html}{refs_html}</li>")
    if not step_items:
        return ""
    return (
        '<div class="ov-section">'
        '<h4 class="ov-title">建议阅读顺序'
        f'<span class="ov-sub">{len(step_items)} 步看懂这次改动 · 点击直达</span></h4>'
        f'<ol class="ov-steps">{"".join(step_items)}</ol></div>'
    )


def _render_file_index(summaries: dict[str, Any], files: Sequence[dict[str, Any]]) -> str:
    """渲染「重点文件清单」：本次改动按角色分组，逐行可点，标出必读与扫一眼即可。"""
    if not files:
        return ""
    indexes_by_role: dict[str, list[int]] = {}
    for file_index, file_entry in enumerate(files):
        role = file_role(summaries, str(file_entry["path"]))
        indexes_by_role.setdefault(role, []).append(file_index)
    ordered_roles = [role for role in FILE_ROLE_ORDER if role in indexes_by_role]
    ordered_roles.extend(sorted(role for role in indexes_by_role if role not in FILE_ROLE_ORDER))

    must_read_count = sum(
        1 for file_entry in files if is_must_read(summaries, str(file_entry["path"]))
    )
    blocks = [
        '<div class="ov-section">'
        '<h4 class="ov-title">重点文件清单'
        f'<span class="ov-sub">{len(files)} 个文件 · {must_read_count} 个必读 · '
        "其余扫一眼即可 · 点击跳转</span></h4>"
    ]
    for role in ordered_roles:
        rows: list[str] = []
        for file_index in indexes_by_role[role]:
            file_entry = files[file_index]
            path = str(file_entry["path"])
            added, removed = count_changes(file_entry)
            badge_html = (
                '<span class="role-badge must">必读</span>'
                if is_must_read(summaries, path)
                else '<span class="role-badge skim">扫一眼</span>'
            )
            rows.append(
                f'<li class="ov-file"><a href="#f{file_index}" title="{esc(path)}">'
                f'<span class="ov-file-left"><span class="ov-file-path">{esc(path)}</span>'
                f"{badge_html}</span>"
                f'<span class="ov-hit"><span class="add-stat">+{added}</span>'
                f'<span class="del-stat">-{removed}</span></span>'
                f'<span class="ov-file-summary">{esc(file_summary(summaries, path))}</span>'
                "</a></li>"
            )
        blocks.append(
            f'<div class="ov-role"><div class="ov-role-name">{esc(role)}'
            f'<span class="ov-role-count">{len(indexes_by_role[role])}</span></div>'
            f'<ul class="ov-files">{"".join(rows)}</ul></div>'
        )
    blocks.append("</div>")
    return "".join(blocks)


def _render_overview_prose(summaries: dict[str, Any], link_targets: dict[str, LinkTarget]) -> str:
    """渲染 ``overview`` 正文：极简 Markdown → HTML，并把文件路径链接化。"""
    raw_overview = summaries.get("overview")
    if isinstance(raw_overview, list):
        overview_text = "\n".join(str(line) for line in raw_overview)
    elif isinstance(raw_overview, str):
        overview_text = raw_overview
    else:
        return ""
    if not overview_text.strip():
        return ""

    blocks: list[str] = []
    paragraph_lines: list[str] = []
    list_tag: str | None = None
    list_items: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            blocks.append("<p>" + " ".join(paragraph_lines) + "</p>")
            paragraph_lines.clear()

    def flush_list() -> None:
        nonlocal list_tag
        if list_tag is not None and list_items:
            blocks.append(
                f"<{list_tag}>"
                + "".join(f"<li>{list_item}</li>" for list_item in list_items)
                + f"</{list_tag}>"
            )
        list_items.clear()
        list_tag = None

    for raw_line in overview_text.splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            # 空行同时结束段落与列表，避免跨空行续接同一个列表。
            flush_paragraph()
            flush_list()
            continue
        heading_match = _OVERVIEW_HEADING_RE.match(stripped_line)
        if heading_match:
            flush_paragraph()
            flush_list()
            heading_level = len(heading_match.group(1))
            heading_text = _render_overview_inline(heading_match.group(2), link_targets)
            blocks.append(f"<h{heading_level}>{heading_text}</h{heading_level}>")
            continue
        bullet_match = _OVERVIEW_BULLET_RE.match(stripped_line)
        ordered_match = _OVERVIEW_ORDERED_RE.match(stripped_line)
        if bullet_match or ordered_match:
            flush_paragraph()
            wanted_tag = "ul" if bullet_match else "ol"
            if list_tag != wanted_tag:
                flush_list()
                list_tag = wanted_tag
            item_match = bullet_match or ordered_match
            list_items.append(_render_overview_inline(item_match.group(1), link_targets))
            continue
        flush_list()
        paragraph_lines.append(_render_overview_inline(stripped_line, link_targets))

    flush_paragraph()
    flush_list()
    return "".join(blocks)


def render_overview(summaries: dict[str, Any], files: Sequence[dict[str, Any]]) -> str:
    """渲染顶部可折叠的「改动总览」卡；作者未提供 overview/reading_path 时返回空串。

    卡片由三块组成，都是**可选**的：正文（``overview``）、建议阅读顺序
    （``reading_path``）、重点文件清单（按 ``files`` 自动生成，不需手写）。只要正文或
    阅读顺序有一项存在就出卡——文件清单本来就是本次改动的镜像，单独为它出卡会平白
    多占版面。

    Args:
        summaries (dict[str, Any]): 摘要 JSON（见 ``load_summaries``）。
        files (Sequence[dict[str, Any]]): 本次改动的文件，用于生成文件清单与链接目标。

    Returns:
        str: 「改动总览」卡的 HTML；作者未提供总览内容时为空串。
    """
    link_targets = build_link_targets(files)
    prose_html = _render_overview_prose(summaries, link_targets)
    reading_html = _render_reading_path(summaries, link_targets)
    if not prose_html and not reading_html:
        return ""
    index_html = _render_file_index(summaries, files)
    return (
        '<details class="overview surface" open>'
        '<summary class="overview-head"><span class="overview-badge">改动总览</span>'
        '<span class="overview-hint">点此行折叠 / 展开</span></summary>'
        f'<div class="overview-body">{prose_html}{reading_html}{index_html}</div></details>'
    )


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
    tree_html, display_indexes = render_tree(build_tree(files), summaries, files)
    moves_html = render_moves_card(files, display_indexes)
    sections = "".join(
        render_section(file_index, files[file_index], summaries) for file_index in display_indexes
    )
    if not files:
        sections = '<p class="empty">没有匹配的改动。</p>'
    overview_html = render_overview(summaries, files)
    app_class = "app has-overview" if overview_html else "app"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<div class="{app_class}">
  <header class="topbar surface">
    <span class="repo-mark">±</span>
    <div class="title-block">
      <h1>{esc(title)}</h1>
      <div class="meta-line">{esc(meta_line)}</div>
    </div>
    <span class="spacer"></span>
    <span class="totals">{len(files)} 个文件 ·
      <span class="add-stat">+{total_added}</span>
      <span class="del-stat">-{total_removed}</span></span>
  </header>
  {overview_html}
  <div class="body-grid">
    <aside class="surface">
      {moves_html}
      <div class="tree">{tree_html}</div>
    </aside>
    <main class="surface"><div class="viewer-body">{sections}</div></main>
  </div>
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
