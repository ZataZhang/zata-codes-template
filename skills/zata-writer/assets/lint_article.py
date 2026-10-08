#!/usr/bin/env python3
"""zata-writer 文章 lint：把能计数的写作问题确定性地拦下来。

用法：
    python3 lint_article.py 文章.md [更多文章.md ...] [--style 风格标识] [--warn-only]

ERROR（下列数字是默认 analytical 的额度，其他风格见 STYLE_LIMITS）：
  - 强调性加粗：每个二级标题下至多 1 处；段首不超过 16 字的短标签不计
  - 评判性最高级：「最关键」「最扎实」「真正」「才是」等，全文至多 3 处
  - 反转句：「不是 X，是 Y」「Y，而不是 X」「不在 X，在 Y」，全文至多 4 处
  - 感叹号：全文至多 3 个
  - 人设词：作者经历、感受、习惯类表述。编的就删；确认来自用户素材的，在行尾加 <!-- lint-ok -->
WARN（逐条判断）：
  - 表格超过 4 列或 10 行；一行里数字超过 10 个（数字墙）
  - 给原作者的解释打分超过 1 处；「我认为」类表态超过 5 处
  - 报告套话；连续 4 段以上单句段；图注里写裁图过程；开场用转述式钩子

含 lint-ok 的行跳过所有检查。
默认 analytical 保留原有阈值；explainer-video 使用 STYLE_LIMITS 对应额度。
阈值与 references/styles/ 对应文件保持一致，改一处要同步另一处。
人设词等真实性检查共用；表态频率、单句段和开场钩子提示按风格启用。
退出码：有 ERROR 时为 1；加 --warn-only 时恒为 0。
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StyleLimits:
    """所选风格的强调额度；成组阈值统一传递。"""

    bold_per_section: int
    superlatives: int
    reframes: int
    exclamations: int


STYLE_LIMITS = {
    "analytical": StyleLimits(1, 3, 4, 3),
    "explainer-video": StyleLimits(2, 4, 5, 4),
}
LABEL_MAX_CHARS = 16
NUMBERED_LABEL_MAX_CHARS = 30
MAX_TABLE_COLS = 4
MAX_TABLE_ROWS = 10
MAX_NUMBERS_PER_LINE = 10
MAX_JUDGE_AUTHOR = 1
MAX_I_THINK = 5
SINGLE_SENTENCE_STREAK = 4
MAX_LISTED = 30  # 每条规则最多列出的命中数

# 「最」后面跟这些字时是量或方位的描述（最后、最大、最新、最右……），不算评判
NEUTRAL_ZUI = re.compile(
    r"最(?:后|终|近|新|早|晚|初|优|好|先|小|大|多|少|高|低|长|短|快|慢|末|左|右|上|下|前|内|外|底|顶)"
)
# 但「最大的问题」「最好的例子」这类仍是评判
EVALUATIVE_ZUI = re.compile(
    r"最(?:大|高|多|好|小)的?(?:问题|风险|价值|意义|亮点|收获|贡献|启发|误区|坑|教训|看点|卖点|例子|证据|理由|优势|短板|破绽)"
)
INTENSIFIERS = re.compile(r"真正|才是")

REFRAME_PATTERNS = [
    # 不是 X，是 Y／不是 X，而是 Y／不在于 X，而在于 Y
    re.compile(
        r"(?<!是)不(?:是|在于?)[^。！？；\n]{1,40}?[，,；;—–]+\s*(?:而|它|这|那|却)?(?:是|在于?)"
    ),
    # 是 Y，不是 X
    re.compile(r"是[^。！？；\n]{1,40}?[，,]\s*(?:而)?不是"),
    # Y 而不是 X／Y 而非 X
    re.compile(r"而(?:不是|非)(?!\s*[\d.]+\b)"),
]

PERSONA_PATTERNS = [
    re.compile(p)
    for p in (
        r"盯着[^。！？\n]{0,8}?(?:很久|半天|好久|许久)",
        r"(?:看|读)了?(?:很久|半天|好久|好几遍)",
        r"我(?:最|很|特别|非常|挺)?喜欢",
        r"不敢相信",
        r"越来越(?:确定|相信|觉得|肯定)",
        r"以后凡是",
        r"我的动作是",
        r"愣住|愣了一下|心里一沉|倒吸一口|拍案|惊出一身|起鸡皮疙瘩|眼前一亮",
        r"我一直(?:以为|觉得|认为)",
        r"(?:读|看)完[^。！？\n]{0,10}最想",
        r"让我(?:震惊|意外|惊讶|兴奋|失望)",
    )
]
REPORT_SPEAK = re.compile(
    r"值得注意的是|综上所述|总而言之|不难发现|毋庸置疑|众所周知|不言而喻|显而易见"
)
JUDGE_AUTHOR = re.compile(
    r"(?:作者|论文)[^。！？\n]{0,30}?我(?:也)?(?:认同|接受|同意|赞同|买账|认为(?:是)?对)"
    r"|我(?:也)?(?:认同|接受|同意|赞同)(?:作者|这个|这一|这条|该)"
)
I_THINK = re.compile(r"我认为|我觉得|我的判断是|我的读法|在我看来|我倾向于")
OPENING_DEVICE = re.compile(r"有人说|评论区|讨论里|第一反应")
CAPTION_PROCESS = re.compile(r"裁(?:掉|切|图|剪)|切掉")
BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
NUMBERED_LABEL = re.compile(
    r"(?:[一二三四五六七八九十]+、|\d+[.、]|(?:选项|方案|路|步骤|第|阶段|层|定理|引理|Theorem|Lemma|Step)\s*[\d一二三四五六七八九十.]+)"
)
LEADING_MARKER = re.compile(r"\s*(?:>\s*)*(?:[-*+]\s+|\d+[.、)]\s*)?")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?%?")
CJK = re.compile(r"[一-鿿]")


@dataclass
class Block:
    """一段连续的 Markdown 块：类型、带行号的原文和标题层级。"""

    kind: str  # para / list / quote / caption / table / heading / image
    lines: list[tuple[int, str]] = field(default_factory=list)
    level: int = 0  # 标题层级

    @property
    def start(self) -> int:
        """块首行的行号。"""
        return self.lines[0][0]


@dataclass
class Report:
    """lint 结果：ERROR 和 WARN 各自是（规则说明，命中列表）。"""

    errors: list[tuple[str, list[str]]] = field(default_factory=list)
    warns: list[tuple[str, list[str]]] = field(default_factory=list)


def strip_inline(text: str) -> str:
    """行内代码和公式换成占位符，去掉注释、图片和网址，链接只留文字。"""
    text = re.sub(r"<!--.*?-->", "", text)
    text = re.sub(r"`[^`]*`", "X", text)  # 行内代码
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)  # 行内图片
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # 链接只留文字
    text = re.sub(r"\$[^$\n]+\$", "X", text)  # 行内公式
    text = re.sub(r"https?://\S+", "", text)
    return text


def classify(s: str) -> str:
    """按行首标记判断块类型。"""
    if s.startswith("#"):
        return "heading"
    if s.startswith("|"):
        return "table"
    if s.startswith("!["):
        return "image"
    if s.startswith(">"):
        return "quote"
    if re.match(r"[-*+]\s", s) or re.match(r"\d+[.、)]\s", s):
        return "list"
    if (s.startswith("*") and not s.startswith("**") and s.endswith("*")) or (
        s.startswith("_") and not s.startswith("__") and s.endswith("_")
    ):
        return "caption"
    return "para"


def parse(path: Path) -> list[Block]:
    """跳过 front matter、代码块、公式块和 HTML/短代码行，按空行把正文切成 Block。"""
    raw = path.read_text(encoding="utf-8").split("\n")
    start = 0
    if raw and raw[0].strip() == "---":
        for j in range(1, len(raw)):
            if raw[j].strip() == "---":
                start = j + 1
                break
    blocks: list[Block] = []
    cur: Block | None = None
    in_code = in_math = False

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            blocks.append(cur)
            cur = None

    for n in range(start, len(raw)):
        line, s, lineno = raw[n], raw[n].strip(), n + 1
        if in_code:
            if s.startswith(("```", "~~~")):
                in_code = False
            continue
        if s.startswith(("```", "~~~")):
            flush()
            in_code = True
            continue
        if in_math:
            if s.endswith("$$"):
                in_math = False
            continue
        if s.startswith("$$"):
            flush()
            if s == "$$" or not s.endswith("$$"):
                in_math = True
            continue
        if not s:
            flush()
            continue
        if s.startswith(("{{<", "{{%")) or (s.startswith("<") and not s.startswith("<!--")):
            flush()
            continue
        kind = classify(s)
        if kind == "heading":
            flush()
            level = len(s) - len(s.lstrip("#"))
            blocks.append(Block("heading", [(lineno, s.lstrip("#").strip())], level))
            continue
        if cur is not None and (cur.kind == "table") != (kind == "table"):
            flush()
        if cur is None:
            cur = Block(kind)
        cur.lines.append((lineno, line))
    flush()
    return blocks


def snippet(text: str, pos: int, before: int = 10, after: int = 16) -> str:
    """截取命中位置前后的一小段原文，放进报告。"""
    return text[max(0, pos - before) : pos + after].strip()


def listed(items: list[str]) -> list[str]:
    """命中太多时只列前 MAX_LISTED 条，并注明还剩多少。"""
    if len(items) <= MAX_LISTED:
        return items
    return items[:MAX_LISTED] + [f"……另有 {len(items) - MAX_LISTED} 处"]


def lint(path: Path, *, style: str = "analytical") -> tuple[Report, str]:
    """按风格检查文章，保留默认分析型的兼容行为。

    Args:
        path: 待检查的 Markdown 文章路径。
        style: STYLE_LIMITS 中的风格标识（analytical 或 explainer-video）。

    Returns:
        检查报告和一行统计摘要。

    Raises:
        KeyError: 风格标识不存在。
    """
    style_limits = STYLE_LIMITS[style]
    blocks = parse(path)
    rep = Report()
    prose_kinds = {"para", "list", "quote", "caption"}

    # 按二级标题切节
    sections: list[tuple[str, list[Block]]] = [("（开头）", [])]
    for b in blocks:
        if b.kind == "heading" and b.level == 2:
            sections.append((b.lines[0][1], []))
        else:
            sections[-1][1].append(b)

    def prose_lines(include_headings: bool = True):
        for b in blocks:
            if b.kind in prose_kinds or (include_headings and b.kind == "heading"):
                for lineno, line in b.lines:
                    if "lint-ok" not in line:
                        yield b, lineno, strip_inline(line)

    # 1. 强调性加粗
    over_sections, total_emph, total_label = [], 0, 0
    for name, sec_blocks in sections:
        emph = []
        for b in sec_blocks:
            if b.kind not in prose_kinds:
                continue
            for lineno, line in b.lines:
                if "lint-ok" in line:
                    continue
                text = strip_inline(line)
                prefix = LEADING_MARKER.match(text).end()
                for m in BOLD.finditer(text):
                    inner = m.group(1) or m.group(2) or ""
                    is_label = len(inner) <= LABEL_MAX_CHARS or (
                        NUMBERED_LABEL.match(inner) and len(inner) <= NUMBERED_LABEL_MAX_CHARS
                    )
                    if m.start() == prefix and is_label:
                        total_label += 1
                        continue
                    emph.append(f"L{lineno}「{inner[:24]}」")
        total_emph += len(emph)
        if len(emph) > style_limits.bold_per_section:
            over_sections.append(
                f"{name}：{len(emph)} 处　" + "　".join(emph[:6]) + ("……" if len(emph) > 6 else "")
            )
    if over_sections:
        rep.errors.append(
            (
                f"强调性加粗超额：{len(over_sections)} 节超过每节 "
                f"{style_limits.bold_per_section} 处"
                f"（全文 {total_emph} 处）",
                over_sections,
            )
        )

    # 2. 评判性最高级
    sup = []
    for _, lineno, text in prose_lines():
        hits = [
            m.start()
            for m in re.finditer("最", text)
            if EVALUATIVE_ZUI.match(text[m.start() :]) or not NEUTRAL_ZUI.match(text[m.start() :])
        ]
        hits += [m.start() for m in INTENSIFIERS.finditer(text)]
        seen_clauses = set()
        for pos in sorted(hits):
            clause = len(re.findall(r"[，,。；;：:！？!?、]", text[:pos]))  # 同一分句只算一处
            if clause not in seen_clauses:
                seen_clauses.add(clause)
                sup.append(f"L{lineno} …{snippet(text, pos)}…")
    if len(sup) > style_limits.superlatives:
        rep.errors.append(
            (f"评判性最高级 {len(sup)} 处（上限 {style_limits.superlatives}）", listed(sup))
        )

    # 3. 反转句
    ref = []
    for _, lineno, text in prose_lines():
        spans = sorted(m.span() for pat in REFRAME_PATTERNS for m in pat.finditer(text))
        merged: list[list[int]] = []
        for a, b in spans:
            if merged and a < merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        for a, b in merged:
            ref.append(f"L{lineno} …{text[max(0, a - 6) : b + 8].strip()}…")
    if len(ref) > style_limits.reframes:
        rep.errors.append(
            (f"反转句（不是 X，是 Y）{len(ref)} 处（上限 {style_limits.reframes}）", listed(ref))
        )

    # 4. 感叹号
    exc = [
        f"L{lineno} …{snippet(text, m.start())}…"
        for _, lineno, text in prose_lines()
        for m in re.finditer(r"[！!]", text)
    ]
    if len(exc) > style_limits.exclamations:
        rep.errors.append(
            (f"感叹号 {len(exc)} 个（上限 {style_limits.exclamations}）", listed(exc))
        )

    # 5. 人设词
    persona = []
    for _, lineno, text in prose_lines():
        spans = sorted(m.span() for pat in PERSONA_PATTERNS for m in pat.finditer(text))
        last_end = -1
        for a, b in spans:
            if a >= last_end:
                persona.append(f"L{lineno} …{snippet(text, a)}…")
            last_end = max(last_end, b)
    if persona:
        rep.errors.append(
            (f"人设词 {len(persona)} 处：确认来自用户素材，否则删除", listed(persona))
        )

    # 6. 表格尺寸
    tables = []
    for b in blocks:
        if b.kind != "table":
            continue
        cols = len(b.lines[0][1].strip().strip("|").split("|"))
        rows = len(b.lines) - (
            2 if len(b.lines) > 1 and re.match(r"^\|?[\s:|-]+\|?$", b.lines[1][1].strip()) else 1
        )
        if cols > MAX_TABLE_COLS or rows > MAX_TABLE_ROWS:
            tables.append(f"L{b.start} {cols} 列 × {rows} 行")
    if tables:
        rep.warns.append(
            (f"表格过大（上限 {MAX_TABLE_COLS} 列 / {MAX_TABLE_ROWS} 行，手机上读不了）", tables)
        )

    # 7. 数字墙
    walls = []
    for b, lineno, text in prose_lines(include_headings=False):
        k = len(NUMBER.findall(text))
        if k > MAX_NUMBERS_PER_LINE:
            walls.append(f"L{lineno} {k} 个数字")
    if walls:
        rep.warns.append((f"数字墙（一行超过 {MAX_NUMBERS_PER_LINE} 个数字，改表格或删减）", walls))

    # 8. 给作者打分、我认为
    judge = [
        f"L{lineno} …{snippet(text, m.start())}…"
        for _, lineno, text in prose_lines()
        for m in JUDGE_AUTHOR.finditer(text)
    ]
    if len(judge) > MAX_JUDGE_AUTHOR:
        rep.warns.append(
            (f"给原作者的解释打分 {len(judge)} 处（上限 {MAX_JUDGE_AUTHOR}）", listed(judge))
        )
    think = [
        f"L{lineno} …{snippet(text, m.start())}…"
        for _, lineno, text in prose_lines()
        for m in I_THINK.finditer(text)
    ]
    if len(think) > MAX_I_THINK:
        rep.warns.append((f"「我认为」类表态 {len(think)} 处（上限 {MAX_I_THINK}）", listed(think)))

    # 9. 报告套话
    speak = [
        f"L{lineno} …{snippet(text, m.start())}…"
        for _, lineno, text in prose_lines()
        for m in REPORT_SPEAK.finditer(text)
    ]
    if speak:
        rep.warns.append(("报告套话", listed(speak)))

    # 10. 连续单句段
    streaks, run = [], []
    for b in blocks:
        if b.kind == "para":
            text = strip_inline(" ".join(line for _, line in b.lines))
            if len(re.findall(r"[。！？!?]", text.rstrip("。！？!? "))) == 0:
                run.append(b.start)
                continue
        if len(run) >= SINGLE_SENTENCE_STREAK:
            streaks.append(f"L{run[0]} 起连续 {len(run)} 段")
        run = []
    if len(run) >= SINGLE_SENTENCE_STREAK:
        streaks.append(f"L{run[0]} 起连续 {len(run)} 段")
    if streaks and style != "explainer-video":
        rep.warns.append(("连续单句段（碎片流）", streaks))

    # 11. 图注里的处理过程
    cap = [
        f"L{lineno} …{snippet(text, m.start())}…"
        for b in blocks
        if b.kind == "caption"
        for lineno, line in b.lines
        for text in [strip_inline(line)]
        for m in CAPTION_PROCESS.finditer(text)
    ]
    if cap:
        rep.warns.append(("图注里写了处理过程（写进交付说明，图注只给读者需要的信息）", cap))

    # 12. 开场钩子
    first_paras = [b for b in blocks if b.kind == "para"][:3]
    hooks = [
        f"L{lineno} …{snippet(strip_inline(line), m.start())}…"
        for b in first_paras
        for lineno, line in b.lines
        for m in OPENING_DEVICE.finditer(strip_inline(line))
    ]
    if hooks and style == "analytical":
        rep.warns.append(("开场用了转述式钩子：确认上一篇没用过，且引语本身有信息量", hooks))

    cjk = sum(len(CJK.findall(text)) for _, _, text in prose_lines(include_headings=False))
    h2 = sum(1 for b in blocks if b.kind == "heading" and b.level == 2)
    paras = sum(1 for b in blocks if b.kind == "para")
    stats = (
        f"风格 {style}｜正文 {cjk} 字｜二级标题 {h2} 个｜段落 {paras}｜"
        f"强调性加粗 {total_emph}（另有段首标签 {total_label}，表格内不计）"
    )
    return rep, stats


def main() -> int:
    """命令行入口：逐篇检查，有 ERROR 时返回 1（--warn-only 时恒为 0）。"""
    ap = argparse.ArgumentParser(description="zata-writer 文章 lint")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--warn-only", action="store_true", help="只报告，不以非零退出码失败")
    ap.add_argument(
        "--style",
        choices=tuple(STYLE_LIMITS),
        default="analytical",
        help="文章风格，默认 analytical（同行拆解）",
    )
    args = ap.parse_args()

    failed = False
    for path in args.files:
        rep, stats = lint(path, style=args.style)
        print(f"== {path}")
        print(f"   {stats}")
        for title, items in rep.errors:
            print(f"ERROR {title}")
            for it in items:
                print(f"      {it}")
        for title, items in rep.warns:
            print(f"WARN  {title}")
            for it in items:
                print(f"      {it}")
        print(f"结果：{len(rep.errors)} 项 ERROR，{len(rep.warns)} 项 WARN\n")
        failed = failed or bool(rep.errors)
    return 1 if failed and not args.warn_only else 0


if __name__ == "__main__":
    sys.exit(main())
