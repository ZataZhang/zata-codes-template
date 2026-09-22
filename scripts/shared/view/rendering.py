"""把正文渲染成界面能直接铺的行级 HTML：语法高亮与 Markdown 预览。

这里只做「正文 → HTML」这一件事，不碰文件系统、不调 ``git``：输入是已解码的字符串，
输出是逐行 HTML 或整段 HTML 片段。读文件、判二进制、按后缀决定用哪种渲染都在
:mod:`workspace` 里，所以本模块可以被单独测、也可以被换掉。

两个渲染器都按「缺失即降级」处理显式声明的 dev 依赖（``pygments`` / ``markdown``）：派生
项目做 ``uv sync --no-dev`` 时高亮与预览消失，查看器其余功能不缺失。import 必须留在函数
里——``launch.py`` 的 import 闭包只能含标准库加同目录兄弟模块（见
``tests/guards/shared/test_view_launch_entry.py``），提到模块顶层会让 ``just view`` 在
``-S`` 下直接起不来。
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

#: Markdown 预览启用的扩展：围栏代码、表格、以及列表缩进不按 4 空格误判为代码块。
#: 刻意不启用 ``codehilite``——那会引入第二套 Pygments 产出，与 :func:`highlight_source_lines`
#: 的行级高亮 CSS 抢同一批短类名。
_MARKDOWN_EXTENSIONS = ("fenced_code", "tables", "sane_lists")

#: Pygments 认不出来的仓库惯用文件名，映射到显式指定的词法器别名与展示标签。
#:
#: 只放「按扩展名判不出来、但语义有明确最近邻」的名字，不放任何仓库专属路径。标签
#: 刻意写明是近似匹配：``justfile.shared`` 用 Makefile 词法器高亮，界面若只写
#: 「Makefile」会让人以为渲染错了语言。
#:
#: - ``justfile`` / ``justfile.shared``：Pygments 2.x 没有 Just 词法器，而 just 的
#:   配方语法与 Make 同源（``target:`` 加缩进 recipe）。按 Make 渲染仍能正确着色
#:   注释、目标名与内嵌 shell，比整篇纯文本更接近真实语义。
#: - ``uv.lock``：内容就是 TOML，Pygments 只按 ``*.toml`` 匹配扩展名。
_FALLBACK_LEXERS_BY_FILENAME: dict[str, tuple[str, str]] = {
    "justfile": ("make", "Just（Makefile 词法器近似）"),
    "justfile.shared": ("make", "Just（Makefile 词法器近似）"),
    "uv.lock": ("toml", "TOML"),
}

_SPAN_TAG_PATTERN = re.compile(r"</?span[^>]*>")
_SPAN_CLASS_PATTERN = re.compile(r'class="([^"]*)"')


@dataclass(frozen=True)
class HighlightedSource:
    """文件正文的渲染结果。

    Attributes:
        rendered_lines (list[str]): 逐行 HTML；未高亮时是转义后的纯文本行。
        language_label (str): 语言标签，展示在内容区头部。
        is_highlighted (bool): 是否真的做了语法高亮。
    """

    rendered_lines: list[str]
    language_label: str
    is_highlighted: bool


@dataclass(frozen=True)
class _ResolvedSourceLexer:
    """按文件名解析出的词法器，附带展示给界面的语言标签。

    两个值总是一起出现：标签描述的是「用哪个词法器渲染的」，分开传会让调用方有机会
    拿词法器名字直接当标签用，而回退匹配时那个名字是错的。
    """

    lexer: object
    language_label: str


def highlight_source_lines(source_text: str, relative_path: str) -> HighlightedSource:
    """把源码渲染成逐行 HTML，可用时带语法高亮。

    Pygments 不保证 token span 在行边界闭合（多行字符串与注释会跨行），直接按换行
    切会把标签切坏，因此这里把整段源码渲染完再切行，并在每行末尾补上仍未闭合的
    ``</span>``、在下一行开头按栈里记录的 class 重新打开。

    Pygments 是显式声明的 dev 依赖，但这里仍按「缺失即降级」处理：派生项目做
    ``uv sync --no-dev`` 时高亮消失，查看器功能不缺失。

    Args:
        source_text (str): 已解码的文件正文。
        relative_path (str): 仓库相对路径，用于按文件名推断语言。

    Returns:
        HighlightedSource: 逐行 HTML 与语言标签。
    """
    try:
        from pygments import highlight as render_highlight
        from pygments.formatters import HtmlFormatter
    except ImportError:
        return _build_plain_text_source(source_text, "纯文本（未安装语法高亮依赖）")

    resolved_source = _resolve_lexer_for_relative_path(relative_path, source_text)
    if resolved_source is None:
        return _build_plain_text_source(source_text, "纯文本")

    highlighted_html = render_highlight(
        source_text, resolved_source.lexer, HtmlFormatter(nowrap=True)
    )
    return HighlightedSource(
        rendered_lines=_split_highlighted_lines(highlighted_html),
        language_label=resolved_source.language_label,
        is_highlighted=True,
    )


def render_markdown_document(source_text: str) -> str | None:
    """把 Markdown 正文渲染成 HTML 片段。

    ``markdown`` 按 :func:`highlight_source_lines` 里 pygments 同一条口径处理：显式声明
    的 dev 依赖，但缺失即降级——派生项目做 ``uv sync --no-dev`` 时预览入口不出现，源码
    高亮照旧。

    正文里的 raw HTML 不做清洗。查看器绑在回环上、只读，预览又是用户主动点开的一次；
    这一点写进了 ``docs/guides/file-viewer.md``，而不是靠这里默默替用户过滤内容。

    Args:
        source_text (str): 已解码的 Markdown 正文。

    Returns:
        str | None: 渲染后的 HTML 片段；依赖缺失时为 ``None``。
    """
    try:
        import markdown
    except ImportError:
        return None
    return markdown.markdown(source_text, extensions=list(_MARKDOWN_EXTENSIONS))


def prewarm_highlighting() -> None:
    """在后台预热 Pygments 的导入与词法解析，使首屏不为这段导入付费。

    典型耗时 100–150ms，正好落在冷启动预算里；预热失败不影响功能，只是首个文件
    请求会自己付这段开销。
    """
    highlight_source_lines("prewarm = True\n", "view_prewarm.py")


def _resolve_lexer_for_relative_path(
    relative_path: str, source_text: str
) -> _ResolvedSourceLexer | None:
    """按文件名解析词法器，认不出来时走显式的回退表。

    刻意不做基于内容的 ``guess_lexer``：那会让「这个文件渲染成什么语言」随正文内容
    漂移，排障时无法解释。

    Args:
        relative_path (str): 仓库相对路径。
        source_text (str): 已解码的文件正文，供 Pygments 消解同扩展名的歧义。

    Returns:
        _ResolvedSourceLexer | None: 词法器与展示标签；文件名与回退表都解析不出时为
            ``None``。
    """
    from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
    from pygments.util import ClassNotFound

    try:
        matched_lexer = get_lexer_for_filename(relative_path, source_text, stripnl=False)
    except ClassNotFound:
        fallback_lexer_alias, fallback_label = _FALLBACK_LEXERS_BY_FILENAME.get(
            Path(relative_path).name, (None, "")
        )
        if fallback_lexer_alias is None:
            return None
        try:
            matched_lexer = get_lexer_by_name(fallback_lexer_alias, stripnl=False)
        except ClassNotFound:
            return None
        return _ResolvedSourceLexer(lexer=matched_lexer, language_label=fallback_label)

    return _ResolvedSourceLexer(lexer=matched_lexer, language_label=matched_lexer.name)


def _build_plain_text_source(source_text: str, language_label: str) -> HighlightedSource:
    """无高亮时的降级渲染：转义后的纯文本行，行数与高亮路径保持一致。"""
    return HighlightedSource(
        rendered_lines=[
            _escape_source_line(source_line) for source_line in _split_source_lines(source_text)
        ],
        language_label=language_label,
        is_highlighted=False,
    )


def _split_source_lines(source_text: str) -> list[str]:
    """按 ``wc -l`` 语义切分正文，末尾换行不产生额外空行。"""
    source_lines = source_text.split("\n")
    if source_lines and source_lines[-1] == "":
        source_lines.pop()
    return source_lines


def _escape_source_line(source_line: str) -> str:
    """把一行源码转义成可直接放进 HTML 的纯文本。"""
    return html.escape(source_line, quote=True)


def _split_highlighted_lines(highlighted_html: str) -> list[str]:
    """把整段高亮 HTML 切成逐行 HTML，使每行自身标签平衡。

    Pygments 输出对换行敏感但不在行边界闭合 token span，因此逐行切分时要把跨行的
    span 在行尾闭合、在下一行行首按原 class 重开，行内既有标签的位置保持原样。

    Args:
        highlighted_html (str): ``HtmlFormatter(nowrap=True)`` 的整段输出。

    Returns:
        list[str]: 逐行 HTML，长度与 ``wc -l`` 语义一致。
    """
    rendered_lines: list[str] = []
    open_span_classes: list[str] = []
    for raw_html_line in highlighted_html.split("\n"):
        reopened_prefix = "".join(
            f'<span class="{span_class}">' for span_class in open_span_classes
        )
        scanned_parts: list[str] = []
        scan_cursor = 0
        for span_match in _SPAN_TAG_PATTERN.finditer(raw_html_line):
            scanned_parts.append(raw_html_line[scan_cursor : span_match.start()])
            scan_cursor = span_match.end()
            span_tag_text = span_match.group(0)
            if span_tag_text.startswith("</"):
                if open_span_classes:
                    open_span_classes.pop()
            else:
                class_match = _SPAN_CLASS_PATTERN.search(span_tag_text)
                open_span_classes.append(class_match.group(1) if class_match else "")
            scanned_parts.append(span_tag_text)
        scanned_parts.append(raw_html_line[scan_cursor:])
        closing_suffix = "</span>" * len(open_span_classes)
        rendered_lines.append(reopened_prefix + "".join(scanned_parts) + closing_suffix)

    if rendered_lines and rendered_lines[-1] == "":
        rendered_lines.pop()
    return rendered_lines
