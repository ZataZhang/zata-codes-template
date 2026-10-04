"""PRD Machine Contract 的解析原语 —— PRD 格式的**唯一实现**。

背景：`SKILL.md` 的 ``## Machine Contract (vN)`` 章节定义了 PRD 里若干**被机器
解析**的格式（Change Log 条目、验收清单复选框、验收状态横幅、rv-id 命名、证据
目录布局）。在引入本模块之前，这些格式各有各的实现（skill 的 checker 一套、各
执行工具再各写一套），于是**契约文本与真正执行的实现会漂移**——已经发生过：契约
模板里写的分组标题形式被某个解析器以"精确相等"拒掉。本模块把这些解析收敛到一处，
让消费方（含外部 agent runner）**调用**而不是**重写**。

约定：

- 本模块只做**解析**，不做门禁裁决。哪些未勾项该拦、哪些该放行（例如
  ``Human-Confirmed`` 组内的空框属于人属项，不拦归档）由契约规定、由消费方按契约
  取用，本模块只保证把结构如实报出来。
- **只依赖标准库**；可被 ``--json`` 子进程调用，也可直接 import。
- 需要 **Python >= 3.10**（同目录的 ``check_prd_acceptance_checklist.py`` 亦然）。
- 验收状态横幅与 Human-Confirmed 分组的解析，另有无法 import 本模块的消费方（跨
  同步边界的状态看板与 pre-commit hook）各持一份轻量实现；它们与本模块的等价性由
  仓库的守卫测试钉死，改本模块的这两处解析时必须同步改那几份。

版本：:data:`CONTRACT_VERSION` 必须与 ``SKILL.md`` 里的
``Machine-Contract-Version`` 标记一致；契约章节任何改动都要同步 bump。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# 版本
# ---------------------------------------------------------------------------

CONTRACT_VERSION = 5
"""本模块实现的 Machine Contract 版本；与 SKILL.md 的标记必须一致。"""

# ---------------------------------------------------------------------------
# 验收清单：章节、分组、复选框
# ---------------------------------------------------------------------------

ACCEPTANCE_CHECKLIST_HEADING_RE = re.compile(
    r"^##\s+(?:\d+\.\s+)?(?:Acceptance Checklist\b.*|验收清单.*)\s*$"
)
"""``## Acceptance Checklist`` / ``## 验收清单``（允许编号前缀与双语后缀）。"""

TOP_LEVEL_HEADING_RE = re.compile(r"^##\s+")
"""顶级标题；清单章节止于下一个它。"""

CHECKBOX_RE = re.compile(r"^\s*[-*+]\s+\[(?P<mark>[ xX])\]\s*(?P<label>.*)$")
"""只认 ``- [ ]`` / ``- [x]`` / ``- [X]``；``[~]`` 刻意**不是**复选框。"""

RESOLVED_MARK = "~"
"""``- [~] <原文> — runner-owned gate: <gate>`` 的标记；表示"等 runner 门禁，
不计未勾"，绝不是"已完成"。"""

CODE_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")

GROUP_HEADING_RE = re.compile(r"^(#{3,6})\s+(.+?)\s*$")
"""分组标题：三级及以下标题。清单章节内用标题表达分组。"""

BOLD_GROUP_LABEL_RE = re.compile(r"^\s*(?:\*\*|__)\s*(?P<label>.+?)\s*(?:\*\*|__)\s*$")
"""整行加粗的分组标签（如 ``**Human-Confirmed**``）。

契约规定的分组形式是标题；整行加粗属于**兼容**存量 PRD 的宽容输入，不在契约
里宣扬。要求整行只有加粗内容，因此行内强调（``**X：** 正文``）不会命中。
"""

BOLD_GROUP_DEPTH = 3
"""粗体分组标签没有层级，按三级处理，复用"遇同级或更高级分组即关闭"的规则。"""

HUMAN_CONFIRMED_GROUP_PREFIX = "human-confirmed"
"""``Human-Confirmed`` 分组标签的匹配前缀（大小写不敏感）。

用前缀而非精确相等：允许 ``Human-Confirmed (来自 Part A 风险地图)`` 这类带说明
后缀的写法。
"""

HUMAN_CONFIRMED_MENTION_RE = re.compile(r"human[-\s_]?confirmed", re.IGNORECASE)
"""清单章节内是否**提到过** Human-Confirmed（不限书写形式），用于诊断"分组没被
识别出来"这一类写法问题。"""

RESOLVED_ITEM_RE = re.compile(r"^\s*[-*+]\s+\[~\]")


# ---------------------------------------------------------------------------
# Machine Contract §6 / §8：验收状态横幅
# ---------------------------------------------------------------------------

ACCEPTANCE_STATUS_BANNER_RE = re.compile(
    r"^\s*>\s*.*?(?:验收状态|Acceptance Status)", re.IGNORECASE
)
"""验收状态横幅所在行：引用块（``>`` 开头），且带可 grep 的字面量 ``验收状态``
（或 ``Acceptance Status``）。只在引用块行里找，避免把正文或决策日志里对横幅的
讨论误当成状态声明。"""

ACCEPTANCE_STATUS_NOT_STARTED = "not_started"
ACCEPTANCE_STATUS_AWAITING_HUMAN = "awaiting_human"
ACCEPTANCE_STATUS_ACCEPTED = "accepted"

ACCEPTANCE_STATUS_TOKENS: tuple[tuple[str, str], ...] = (
    (ACCEPTANCE_STATUS_NOT_STARTED, "未开工"),
    (ACCEPTANCE_STATUS_AWAITING_HUMAN, "待人工验收"),
    (ACCEPTANCE_STATUS_ACCEPTED, "已验收"),
    (ACCEPTANCE_STATUS_ACCEPTED, "可归档"),
)
"""状态词到状态值的映射。``可归档`` 是 v4 及以前 ``已验收`` 的旧称：存量 PRD 里的
``✅ 可归档`` 一律按已验收读，不要求回头改文件。"""


# ---------------------------------------------------------------------------
# Machine Contract §1：Change Log
# ---------------------------------------------------------------------------

CHANGE_LOG_HEADING_RE = re.compile(
    r"^##\s+(?:\d+\.\s+)?(?:Change Log\b.*|变更记录.*)\s*$",
    re.IGNORECASE,
)
"""``## Change Log`` / ``## 变更记录``（允许编号前缀）。"""

CHANGE_ENTRY_HEADING_RE = re.compile(r"^###\s+.+")
"""每条变更记录是一个 ``###`` 标题。"""

CHANGE_LOG_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "类型": re.compile(r"^\s*[-*+]\s+(?:类型|Type)\s*[:：]", re.IGNORECASE),
    "原文": re.compile(r"^\s*[-*+]\s+(?:原文|Before)\s*[:：]", re.IGNORECASE),
    "变更后": re.compile(r"^\s*[-*+]\s+(?:变更后|After)\s*[:：]", re.IGNORECASE),
    "原因": re.compile(r"^\s*[-*+]\s+(?:原因|Reason)\s*[:：]", re.IGNORECASE),
    "影响": re.compile(r"^\s*[-*+]\s+(?:影响|Impact)\s*[:：]", re.IGNORECASE),
    "审核": re.compile(r"^\s*[-*+]\s+(?:审核|Review)\s*[:：]", re.IGNORECASE),
}
"""契约 §1 规定的六个字段；缺任一即视为不完整条目。"""


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChecklistItem:
    """验收清单里的一条复选框。

    Attributes:
        line: 1-based 行号。
        text: 原始行文本（右侧空白已去除）。
        mark: ``" "`` 未勾 / ``"x"`` 已勾 / ``"~"`` runner-owned 豁免。
        group: 最近一层分组标签；不在任何分组内时为 ``None``。
        in_human_group: 本条是否处于 Human-Confirmed 分组的**作用范围内**。
            分组可以嵌套，因此这里记录的是"包含它的任一层分组是 Human-Confirmed"，
            而不是"它的直接分组标签叫 Human-Confirmed"。
    """

    line: int
    text: str
    mark: str
    group: str | None = None
    in_human_group: bool = False


@dataclass(frozen=True)
class ChecklistState:
    """验收清单章节的解析结果。

    Attributes:
        section_found: 是否找到清单章节。
        items: 章节内全部复选框条目（含已勾与 ``[~]``）。
        human_group_found: 是否识别出 Human-Confirmed 分组。
        human_confirmed_mentioned: 章节内是否出现过 ``Human-Confirmed`` 字样。
            ``mentioned`` 为真而 ``group_found`` 为假，说明分组写法没被识别——
            消费方据此给出可行动的诊断，而不是让 agent 自己猜。
    """

    section_found: bool
    items: tuple[ChecklistItem, ...] = ()
    human_group_found: bool = False
    human_confirmed_mentioned: bool = False

    @property
    def unchecked_items(self) -> tuple[ChecklistItem, ...]:
        """全部未勾条目（``- [ ]``），**不排除**人属分组。"""
        return tuple(item for item in self.items if item.mark == " ")

    @property
    def checked_items(self) -> tuple[ChecklistItem, ...]:
        """已勾条目（``- [x]``）。"""
        return tuple(item for item in self.items if item.mark == "x")

    @property
    def resolved_items(self) -> tuple[ChecklistItem, ...]:
        """``[~]`` 条目。"""
        return tuple(item for item in self.items if item.mark == RESOLVED_MARK)

    @property
    def human_items(self) -> tuple[ChecklistItem, ...]:
        """位于 Human-Confirmed 分组作用范围内的条目（含 ``[~]`` 后置门禁）。"""
        return tuple(item for item in self.items if item.in_human_group)

    @property
    def execution_unchecked_items(self) -> tuple[ChecklistItem, ...]:
        """未勾且**不在**人属分组内的条目——执行侧真正要处理的那些。

        契约规定 Human-Confirmed 组内的空框由人填写，执行工具不得代勾，因此它们
        从"执行项"里排除；``[~]`` 本就不算未勾。归档门禁只看这一组：执行侧交付
        完整即可归档，人属项留着等人填。
        """
        return tuple(item for item in self.unchecked_items if not item.in_human_group)

    @property
    def human_unchecked_items(self) -> tuple[ChecklistItem, ...]:
        """未勾且**位于**人属分组内的条目——还在等人确认的那些。

        与 :attr:`execution_unchecked_items` 互补：两者合起来恰好是
        :attr:`unchecked_items`。横幅是 ``待人工验收`` 还是 ``已验收``，取决于这一组
        是否为空。
        """
        return tuple(item for item in self.unchecked_items if item.in_human_group)


@dataclass(frozen=True)
class AcceptanceBanner:
    """验收状态横幅的解析结果。

    Attributes:
        line: 横幅首行的 1-based 行号。
        status: ``"not_started"`` / ``"awaiting_human"`` / ``"accepted"``；横幅在但
            状态词无法识别时为空串。
    """

    line: int
    status: str


@dataclass(frozen=True)
class ChangeLogEntry:
    """一条 Change Log 记录。

    Attributes:
        line: ``###`` 标题所在行号（1-based）。
        title: 标题文本。
        missing_fields: 缺失的字段名（取自 :data:`CHANGE_LOG_FIELD_PATTERNS`）。
    """

    line: int
    title: str
    missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChangeLogState:
    """Change Log 章节的解析结果。

    Attributes:
        section_found: 是否存在 ``## Change Log`` / ``## 变更记录`` 章节。
        entries: 按出现顺序的条目。
    """

    section_found: bool
    entries: tuple[ChangeLogEntry, ...] = ()

    @property
    def entry_count(self) -> int:
        """条目数。消费方用"条目数是否增加"判断改过 PRD 有没有留痕。"""
        return len(self.entries)

    @property
    def is_complete(self) -> bool:
        """章节存在、至少一条记录，且没有缺字段的条目。"""
        return (
            self.section_found
            and bool(self.entries)
            and not any(entry.missing_fields for entry in self.entries)
        )


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------


def acceptance_section_bounds(lines: list[str]) -> tuple[int, int] | None:
    """返回 Acceptance Checklist 章节在 ``lines`` 中的半开区间。

    Args:
        lines: PRD 文本按行切分的结果。

    Returns:
        ``(start, end)`` 0-based 半开区间，``start`` 指向标题的**下一行**；
        找不到章节时返回 ``None``。
    """
    start_index: int | None = None
    for line_index, line in enumerate(lines):
        if ACCEPTANCE_CHECKLIST_HEADING_RE.match(line):
            start_index = line_index
            break

    if start_index is None:
        return None

    end_index = len(lines)
    for line_index in range(start_index + 1, len(lines)):
        if TOP_LEVEL_HEADING_RE.match(lines[line_index]):
            end_index = line_index
            break

    return start_index + 1, end_index


def _is_human_confirmed_group_label(label: str) -> bool:
    """判断分组标签是否指代 Human-Confirmed 分组（前缀匹配，大小写不敏感）。"""
    return label.strip().casefold().startswith(HUMAN_CONFIRMED_GROUP_PREFIX)


def parse_checklist(file_content: str) -> ChecklistState:
    """解析 PRD 的 Acceptance Checklist 章节。

    只统计章节内的复选框；围栏代码块内的内容忽略。分组由三级及以下标题表达
    （整行加粗标签作为兼容输入一并接受）；遇到同级或更高级的分组即关闭当前分组。

    Args:
        file_content: PRD 全文。

    Returns:
        :class:`ChecklistState`；找不到章节时 ``section_found`` 为 ``False``。
    """
    lines = file_content.splitlines()
    bounds = acceptance_section_bounds(lines)
    if bounds is None:
        return ChecklistState(section_found=False)

    start_index, end_index = bounds
    items: list[ChecklistItem] = []
    in_code_block = False
    # 分组栈：元素是 (层级, 标签, 是否人属组)。条目归属"包含它的所有分组"，
    # 因此人属判定看整条栈，而不是只看最近一层——嵌套子标题不该把人属项踢出去。
    group_stack: list[tuple[int, str, bool]] = []
    human_group_found = False
    human_confirmed_mentioned = False

    def _record(line_index: int, line: str, mark: str) -> None:
        innermost = group_stack[-1][1] if group_stack else None
        items.append(
            ChecklistItem(
                line=line_index + 1,
                text=line.rstrip(),
                mark=mark,
                group=innermost,
                in_human_group=any(entry[2] for entry in group_stack),
            )
        )

    for line_index in range(start_index, end_index):
        line = lines[line_index]
        if CODE_FENCE_RE.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if HUMAN_CONFIRMED_MENTION_RE.search(line):
            human_confirmed_mentioned = True

        heading_match = GROUP_HEADING_RE.match(line)
        if heading_match:
            depth = len(heading_match.group(1))
            label = heading_match.group(2).strip()
            while group_stack and depth <= group_stack[-1][0]:
                group_stack.pop()
            is_human = _is_human_confirmed_group_label(label)
            group_stack.append((depth, label, is_human))
            human_group_found = human_group_found or is_human
            continue

        bold_group_match = BOLD_GROUP_LABEL_RE.match(line)
        if bold_group_match:
            label = bold_group_match.group("label").strip()
            while group_stack and BOLD_GROUP_DEPTH <= group_stack[-1][0]:
                group_stack.pop()
            is_human = _is_human_confirmed_group_label(label)
            group_stack.append((BOLD_GROUP_DEPTH, label, is_human))
            human_group_found = human_group_found or is_human
            continue

        checkbox_match = CHECKBOX_RE.match(line)
        if checkbox_match:
            _record(line_index, line, checkbox_match.group("mark").lower())
            continue

        if RESOLVED_ITEM_RE.match(line):
            _record(line_index, line, RESOLVED_MARK)

    return ChecklistState(
        section_found=True,
        items=tuple(items),
        human_group_found=human_group_found,
        human_confirmed_mentioned=human_confirmed_mentioned,
    )


def find_acceptance_banner(file_content: str) -> AcceptanceBanner | None:
    """定位 PRD 头部的验收状态横幅并解析其三态（Machine Contract §6 / §8）。

    横幅是 §9 验收清单的投影，只有 ``⬜ 未开工`` / ``🧍 待人工验收`` /
    ``✅ 已验收`` 三个状态（旧称 ``✅ 可归档`` 按 ``已验收`` 读）。命中首行横幅后取
    标记之后**最先出现**的状态词，模板自带的括号说明（``未开工（…改为 🧍 待人工
    验收…）``）因此不会把默认态误判成待人工。只认这一处显式声明，不按 §9 的未勾项
    结构反推——结构推断会把尚未完工的 PRD 误报成"等你验收"。

    Args:
        file_content: PRD 全文。

    Returns:
        :class:`AcceptanceBanner`；PRD 没有横幅行时为 ``None``。横幅在但状态词无法
        识别时，其 ``status`` 为空串。
    """
    for line_index, line in enumerate(file_content.splitlines()):
        banner_match = ACCEPTANCE_STATUS_BANNER_RE.match(line)
        if banner_match is None:
            continue
        remainder_text = line[banner_match.end() :]
        matched_status_offsets = [
            (remainder_text.find(token_text), status_value)
            for status_value, token_text in ACCEPTANCE_STATUS_TOKENS
            if token_text in remainder_text
        ]
        status_value = min(matched_status_offsets)[1] if matched_status_offsets else ""
        return AcceptanceBanner(line=line_index + 1, status=status_value)
    return None


def parse_acceptance_status(file_content: str) -> str:
    """返回验收状态横幅的状态值；没有横幅或状态词无法识别时返回空串。

    Args:
        file_content: PRD 全文。

    Returns:
        ``"not_started"`` / ``"awaiting_human"`` / ``"accepted"`` / ``""``。
    """
    banner = find_acceptance_banner(file_content)
    return banner.status if banner is not None else ""


def parse_change_log(file_content: str) -> ChangeLogState:
    """解析 PRD 的 Change Log 章节（Machine Contract §1）。

    章节止于下一个 ``##`` 标题；每条记录是一个 ``###`` 标题加六个 ``- 字段：``
    行。缺字段的条目照样返回（在 ``missing_fields`` 里点名），由消费方决定怎么用——
    "改了 PRD 没写完整 Change Log"是门禁问题，不是解析问题。

    Args:
        file_content: PRD 全文。

    Returns:
        :class:`ChangeLogState`；找不到章节时 ``section_found`` 为 ``False``。
    """
    lines = file_content.splitlines()

    start_index: int | None = None
    for line_index, line in enumerate(lines):
        if CHANGE_LOG_HEADING_RE.match(line):
            start_index = line_index
            break

    if start_index is None:
        return ChangeLogState(section_found=False)

    end_index = len(lines)
    for line_index in range(start_index + 1, len(lines)):
        if TOP_LEVEL_HEADING_RE.match(lines[line_index]):
            end_index = line_index
            break

    entries: list[ChangeLogEntry] = []
    current_title: str | None = None
    current_line = 0
    found_fields: set[str] = set()

    def flush() -> None:
        if current_title is None:
            return
        missing = tuple(field for field in CHANGE_LOG_FIELD_PATTERNS if field not in found_fields)
        entries.append(
            ChangeLogEntry(line=current_line, title=current_title, missing_fields=missing)
        )

    for line_index in range(start_index + 1, end_index):
        line = lines[line_index]
        entry_match = CHANGE_ENTRY_HEADING_RE.match(line)
        if entry_match:
            flush()
            current_title = line[4:].strip()
            current_line = line_index + 1
            found_fields = set()
            continue
        if current_title is None:
            continue
        for field_name, field_pattern in CHANGE_LOG_FIELD_PATTERNS.items():
            if field_pattern.match(line):
                found_fields.add(field_name)
                break

    flush()
    return ChangeLogState(section_found=True, entries=tuple(entries))


# ---------------------------------------------------------------------------
# JSON 接口（供外部执行工具消费；不要在这里做门禁裁决）
# ---------------------------------------------------------------------------


def _item_payload(item: ChecklistItem) -> dict[str, object]:
    return {
        "line": item.line,
        "mark": item.mark,
        "group": item.group,
        "in_human_group": item.in_human_group,
        "text": item.text,
    }


def describe_prd(file_content: str, *, path: str) -> dict[str, object]:
    """把一份 PRD 的解析结果渲染成可序列化字典。

    Args:
        file_content: PRD 全文。
        path: 写进 payload 的来源标识（原样回显，便于消费方对账）。

    Returns:
        含 ``acceptance_status``、``checklist``、``change_log`` 的字典。
    """
    checklist = parse_checklist(file_content)
    change_log = parse_change_log(file_content)
    return {
        "path": path,
        "acceptance_status": parse_acceptance_status(file_content),
        "checklist": {
            "section_found": checklist.section_found,
            "human_group_found": checklist.human_group_found,
            "human_confirmed_mentioned": checklist.human_confirmed_mentioned,
            "items": [_item_payload(item) for item in checklist.items],
            "unchecked": [_item_payload(item) for item in checklist.unchecked_items],
            "checked": [_item_payload(item) for item in checklist.checked_items],
            "resolved": [_item_payload(item) for item in checklist.resolved_items],
            "human_items": [_item_payload(item) for item in checklist.human_items],
            "execution_unchecked": [
                _item_payload(item) for item in checklist.execution_unchecked_items
            ],
            "human_unchecked": [_item_payload(item) for item in checklist.human_unchecked_items],
        },
        "change_log": {
            "section_found": change_log.section_found,
            "entry_count": change_log.entry_count,
            "is_complete": change_log.is_complete,
            "entries": [
                {
                    "line": entry.line,
                    "title": entry.title,
                    "missing_fields": list(entry.missing_fields),
                }
                for entry in change_log.entries
            ],
        },
    }


def describe_paths(paths: list[Path]) -> dict[str, object]:
    """读取一批 PRD 并渲染成 ``--json`` 的完整 payload。

    Args:
        paths: PRD 文件路径。

    Returns:
        含 ``contract_version`` 与 ``prds`` 列表的字典；读取失败的文件进 ``errors``。
    """
    prds: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as read_error:
            errors.append({"path": str(path), "error": str(read_error)})
            continue
        prds.append(describe_prd(content, path=str(path)))
    return {"contract_version": CONTRACT_VERSION, "prds": prds, "errors": errors}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Parse PRD Machine Contract primitives (Acceptance Checklist, Acceptance Status "
            "Banner, Change Log). "
            "This is a parser, not a gate: it reports structure and leaves the "
            "accept/reject decision to the caller."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the machine-readable payload instead of a human summary.",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="PRD files to parse.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI 入口：``prd_contract.py [--json] <prd>...``"""
    args = _build_parser().parse_args(argv)
    payload = describe_paths(list(args.paths))

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"PRD Machine Contract v{CONTRACT_VERSION}\n")
    for prd in payload["prds"]:
        checklist = prd["checklist"]
        change_log = prd["change_log"]
        print(f"{prd['path']}")
        print(f"  acceptance status: {prd['acceptance_status'] or '-'}")
        print(
            f"  checklist: unchecked={len(checklist['unchecked'])} "
            f"human={len(checklist['human_items'])} "
            f"execution_unchecked={len(checklist['execution_unchecked'])} "
            f"human_unchecked={len(checklist['human_unchecked'])} "
            f"human_group_found={checklist['human_group_found']}"
        )
        print(
            f"  change log: entries={change_log['entry_count']} "
            f"complete={change_log['is_complete']}"
        )
    for error in payload["errors"]:
        print(f"{error['path']}: {error['error']}", file=sys.stderr)
    return 1 if payload["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
