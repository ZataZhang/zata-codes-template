"""仓库工作区的只读快照：文件树、文件正文、改动列表、单文件 diff 与两种预览。

查看器的全部内容都从这里出，而且**只读**：所有 ``git`` 调用都是查询
（``ls-files`` / ``diff`` / ``rev-parse``），所有文件访问都是读取。这里不存在任何写
路径——只读是硬边界，不是「本期先不做」。特别地，未跟踪文件的改动不靠 ``git add -N``
取得：那一条会写索引。

改动视图按 `git status` 的三段口径划分，每段的数据源都是真实 ``git``，且与终端逐项一致：

- 已暂存：``git diff --cached``（HEAD ↔ 索引）。
- 未暂存：``git diff``（索引 ↔ 工作区）。
- 未跟踪：``git ls-files --others --exclude-standard`` 列出文件；点开某个文件时才用
  ``git diff --no-index -- /dev/null <文件>`` 求它的逐行 diff。

界面显示的文件集合与增删统计不做二次推断，必须与同参数的终端输出逐项一致。唯一**不向界面
提供**的是未跟踪文件的 ``+N -M``：``git`` 的列表类命令都不报这个数，逐文件取一次在未跟踪
文件多时会让页面卡住（实测 800 个文件约 7 秒）。界面上那两列留空，并在分区上标出
``stats_available=false``；不提供与二进制是两件事，不共用同一个空值。

未跟踪一段沿用文件树的目录剪枝（见 :data:`_PRUNED_DIRECTORY_NAMES`）：派生项目忘了把
依赖目录写进 ``.gitignore`` 时，整棵依赖树既不该进文件树，也不该淹没改动列表。

重命名是这条口径上唯一的例外，而且必须例外：``git diff <rev> -- <新路径>`` 会把旧路径
排除出候选，配对随即失效，同一个文件被降级成「新增」且正文整篇算成新增行。所以单文件
diff 先在不带 pathspec 的完整 diff 上查出旧路径，再把新旧两条路径一起交给 ``git``
（见 :func:`_lookup_rename_source`）。界面上显示的仍是新路径，与终端 ``--name-only``
一致；旧路径只作为「重命名自何处」的出处。

预览有两条独立的路，都**默认不生效**，只在界面上被显式要求时才出力：

- Markdown：:func:`build_markdown_payload` 按需渲染成 HTML 片段（``/api/markdown``），
  文件视图打开 ``.md`` 先看到的仍是源码。
- HTML：:func:`build_raw_file_payload` 把文件字节原样供出（``/raw/``），由界面在新标签页
  里打开——查看器不做 HTML 内联渲染。

``/api/file`` 的应答里，``preview`` 说明**文本文件**支持哪种预览（由
:func:`resolve_preview_descriptor` 按后缀判定），``kind: "image"`` 加 ``url`` 则直接告诉界面
「这个文件是图片，去这个地址取」。后缀判定只写在服务端这一处，界面不复制任何后缀表。

所有对外路径参数先经 :func:`resolve_repository_path` 解析成绝对路径并断言仍在仓库根
之下，越界一律拒绝，且拒绝信息不回声任何绝对路径。改动分区取值是封闭枚举，任何取值都
不会作为参数流进 ``git``。
"""

from __future__ import annotations

import html
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

#: 改动视图的三个分区。字典的插入顺序即界面上的展示顺序：先看已暂存，再看未暂存，
#: 最后是未跟踪——未跟踪恒为「新增」，排在最后不打断前两段之间的对照。
_SECTION_LABELS: dict[str, str] = {
    "staged": "已暂存",
    "unstaged": "未暂存",
    "untracked": "未跟踪",
}

#: 前两个分区的 ``git diff`` 参数前缀；未跟踪那一段走 ``--no-index``，不在表里。
_SECTION_DIFF_ARGUMENT_PREFIXES: dict[str, tuple[str, ...]] = {
    "staged": ("diff", "--cached"),
    "unstaged": ("diff",),
}

#: 未跟踪文件的路径与 ``/dev/null`` 相比，因此它整篇都是新增行。
_UNTRACKED_DIFF_LEFT_PATH = "/dev/null"

#: ``git diff --no-index`` 在「两边有差异」时退出码为 ``1``（同 ``diff`` 语义），而那正是
#: 我们要的正常结果；``0`` 表示两边一致，``>1`` 才是真的出错。把它按成功接纳，否则每个
#: 有内容的未跟踪文件都会让 :func:`_run_git` 抛错。
_DIFF_NO_INDEX_EXIT_CODES = frozenset({0, 1})

#: 文件正文的渲染上限；超过即返回明确标记而不是正文。
MAX_FILE_BYTES = 256 * 1024
MAX_FILE_BYTES_LABEL = "256 KiB"

#: 单文件 diff 的行数上限，避免超大改动把响应撑爆。
MAX_DIFF_ROWS = 4000

_BINARY_SNIFF_BYTES = 8192

#: ``/raw/`` 路由前缀。服务端据此分发，本模块据此拼 URL——同一个常量，两处引用，
#: 拼出来的地址不可能与服务端的匹配口径分岔。
RAW_ROUTE_PREFIX = "/raw/"

#: 路径越界时的拒绝文案。三个读取入口（正文、diff、预览）共用一份：分别各写一句时
#: 任何一处漏更新都会让「越界」在不同接口上说法不一。
_OUTSIDE_REPOSITORY_REFUSAL_MESSAGE = "拒绝：该路径越出仓库范围，只读查看器不读取仓库外的文件。"

#: 后缀 → 预览形态。**只看后缀，不做内容嗅探**：让「这个文件预览成什么」随正文漂移，
#: 排障时无从解释（与词法器解析同一口径）。
_MARKDOWN_SUFFIXES = frozenset({".md", ".markdown"})
_HTML_SUFFIXES = frozenset({".html", ".htm"})

#: 后缀 → 位图图片。命中即 ``kind: "image"``，由浏览器自己去 ``/raw/`` 取字节渲染。
#:
#: 只收 :data:`_RAW_CONTENT_TYPES_BY_SUFFIX` 里以 ``image/`` 开头的位图，**刻意不含
#: ``.svg``**：SVG 是可编辑的文本，源码视图对它更有用；它在 ``/raw/`` 里仍带
#: ``image/svg+xml``，供 HTML 文档按原样引用。两份表必须对得上——图片预览拿到的
#: Content-Type 不是 ``image/*`` 时浏览器会拒渲染，守卫测试里有一条专门钉这个。
_IMAGE_SUFFIXES = frozenset({".gif", ".ico", ".jpeg", ".jpg", ".png", ".webp"})

#: ``/raw/`` 应答的 Content-Type。只收 HTML 文档自己能引到的资源类型：样式、脚本、
#: 图片、字体、JSON。表外一律 :data:`_DEFAULT_RAW_CONTENT_TYPE`，配合服务端发回的
#: ``X-Content-Type-Options: nosniff``，浏览器不会把表外文件按内容嗅探成 HTML。
_RAW_CONTENT_TYPES_BY_SUFFIX: dict[str, str] = {
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".htm": "text/html; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".ico": "image/vnd.microsoft.icon",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}
_DEFAULT_RAW_CONTENT_TYPE = "application/octet-stream"

#: Markdown 预览启用的扩展：围栏代码、表格、以及列表缩进不按 4 空格误判为代码块。
#: 刻意不启用 ``codehilite``——那会引入第二套 Pygments 产出，与 :func:`highlight_source_lines`
#: 的行级高亮 CSS 抢同一批短类名。
_MARKDOWN_EXTENSIONS = ("fenced_code", "tables", "sane_lists")

#: 文件树不展示的目录名，只作用于**未跟踪**文件。`git ls-files` 已经不吃被 gitignore
#: 的目录，这里再挡一层是为了派生项目没把依赖目录写进 `.gitignore` 时不至于把整棵依赖
#: 树搬进文件树。
#:
#: 刻意不收 `build` / `dist` / `site` 这类既可能是构建产物、也可能是真实源码目录的名字
#: ——本仓库的 `scripts/build/` 就是源码。构建产物由 `.gitignore` 负责，那是「这不是源码」
#: 的权威信号。
_PRUNED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "__pycache__",
        "coverage",
        "node_modules",
        "site-packages",
        "venv",
    }
)

_HUNK_HEADER_PATTERN = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

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

_BINARY_DIFF_PREFIX = "Binary files "

_DIFF_METADATA_PREFIXES = (
    "diff --git ",
    "index ",
    "--- ",
    "+++ ",
    "new file mode ",
    "deleted file mode ",
    "old mode ",
    "new mode ",
    "similarity index ",
    "rename from ",
    "rename to ",
    _BINARY_DIFF_PREFIX,
    "\\ No newline at end of file",
)
_SPAN_TAG_PATTERN = re.compile(r"</?span[^>]*>")
_SPAN_CLASS_PATTERN = re.compile(r'class="([^"]*)"')


class WorkspaceReadError(RuntimeError):
    """读取仓库工作区失败，例如 ``git`` 调用非零退出。"""


@dataclass(frozen=True)
class WorkspacePayload:
    """一个只读接口的应答：HTTP 状态码加 JSON 载荷。

    Attributes:
        status_code (int): 应答的 HTTP 状态码。
        payload (dict[str, object]): 应答正文，会被序列化成 JSON。
    """

    status_code: int
    payload: dict[str, object]


def resolve_repository_path(repository_root: Path, requested_path: str) -> Path | None:
    """把请求路径解析成仓库内的绝对路径，越界时返回 ``None``。

    先 ``resolve()`` 再断言：符号链接指向仓库外时只有解析后才会暴露，这一步是路径
    逃逸防护的关键顺序，不能颠倒成「先断言再解析」。

    Args:
        repository_root (Path): 仓库根绝对路径。
        requested_path (str): 界面传来的仓库相对路径；空串表示仓库根。

    Returns:
        Path | None: 位于仓库内的绝对路径；越界、绝对路径或解析失败时为 ``None``。
    """
    if not requested_path:
        return repository_root
    requested_relative_path = Path(requested_path)
    if requested_relative_path.is_absolute():
        return None
    try:
        resolved_path = (repository_root / requested_relative_path).resolve()
    except (OSError, ValueError):
        # 路径里带 NUL 字节时 resolve() 抛的是 ValueError 而不是 OSError；漏掉它会让
        # 异常穿透到 HTTP 层，畸形请求变成「连接被丢弃 + 日志 traceback」而不是拒绝应答。
        return None
    if resolved_path == repository_root or resolved_path.is_relative_to(repository_root):
        return resolved_path
    return None


def build_refusal_payload(status_code: int, message: str) -> WorkspacePayload:
    """构造一条拒绝应答。

    拒绝信息里绝不带绝对路径，否则「路径越界被拒绝」本身就成了仓库外路径的探测口
    与信息泄漏面。

    Args:
        status_code (int): 应答的 HTTP 状态码。
        message (str): 面向使用者的中文说明。

    Returns:
        WorkspacePayload: 拒绝应答。
    """
    return WorkspacePayload(status_code=status_code, payload={"error": message})


def build_info_payload(repository_root: Path) -> WorkspacePayload:
    """给出界面启动所需的仓库元信息。

    Args:
        repository_root (Path): 仓库根绝对路径。

    Returns:
        WorkspacePayload: 含仓库名、当前分支与渲染上限的应答。
    """
    return WorkspacePayload(
        status_code=200,
        payload={
            "repo_name": repository_root.name,
            "branch": _read_current_branch_name(repository_root),
            "limits": {
                "max_file_bytes": MAX_FILE_BYTES,
                "max_file_label": MAX_FILE_BYTES_LABEL,
            },
        },
    )


def build_tree_payload(repository_root: Path) -> WorkspacePayload:
    """列出文件树要展示的全部仓库内路径。

    Returns:
        WorkspacePayload: 含扁平路径列表与文件数的应答；前端据此自行组装成树。
    """
    file_paths = collect_viewable_file_paths(repository_root)
    return WorkspacePayload(
        status_code=200, payload={"paths": file_paths, "count": len(file_paths)}
    )


def collect_viewable_file_paths(repository_root: Path) -> list[str]:
    """列出受版本控制与未跟踪（且未被忽略）的全部文件路径。

    受控文件一律照收：被提交进版本库的就是有意的源码，哪怕它的目录名看起来像构建产物
    ——本仓库的 ``scripts/build/`` 正是这种情形，按目录名剪枝会把它整棵藏掉。目录名剪枝
    只作用在**未跟踪**文件上，挡的是派生项目忘了把依赖目录写进 ``.gitignore`` 时把整棵
    依赖树搬进文件树。

    Args:
        repository_root (Path): 仓库根绝对路径。

    Returns:
        list[str]: 已排序的仓库相对路径（POSIX 分隔符）。
    """
    tracked_paths = {
        candidate_path
        for candidate_path in _run_git(repository_root, "ls-files", "-z", "--cached").split("\0")
        if candidate_path
    }
    return sorted(tracked_paths | set(_collect_untracked_file_paths(repository_root)))


def _collect_untracked_file_paths(repository_root: Path) -> list[str]:
    """列出未跟踪、未被忽略且不落在剪枝目录下的文件路径。

    文件树与改动视图的「未跟踪」一段共用这一份口径：两处若各列各的，同一个文件会在
    文件树里被剪掉、却在改动列表里冒出来。

    Args:
        repository_root (Path): 仓库根绝对路径。

    Returns:
        list[str]: 已排序的仓库相对路径。
    """
    return sorted(
        candidate_path
        for candidate_path in _run_git(
            repository_root, "ls-files", "-z", "--others", "--exclude-standard"
        ).split("\0")
        if candidate_path and not _is_pruned_path(candidate_path)
    )


def build_file_payload(repository_root: Path, requested_path: str) -> WorkspacePayload:
    """读取单个文件并按图片、可渲染、二进制、超限四种形态给出应答。

    Args:
        repository_root (Path): 仓库根绝对路径。
        requested_path (str): 界面传来的仓库相对路径。

    Returns:
        WorkspacePayload: 图片应答（``kind: "image"`` + ``url``）、正文应答（带行号渲染
            所需的逐行 HTML，另带 ``preview`` 说明该文本文件支持哪种预览）或明确的形态
            标记（二进制 / 超限）。
    """
    resolved_path = resolve_repository_path(repository_root, requested_path)
    if resolved_path is None:
        return build_refusal_payload(403, _OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)

    normalized_relative_path = Path(requested_path).as_posix() if requested_path else ""
    if resolved_path.is_dir():
        return build_refusal_payload(
            400, f"拒绝：{normalized_relative_path or '.'} 是一个目录，请选择一个文件。"
        )
    if not resolved_path.is_file():
        return build_refusal_payload(404, f"未找到文件：{normalized_relative_path}")

    file_byte_count = resolved_path.stat().st_size
    # 图片在读字节之前就返回，因此**不受** 256 KiB 那条上限约束：字节是浏览器拿 URL 自己去
    # 取的，服务端不读、也就没有可省的开销。截图动辄超过 256 KiB，而超限的图片恰恰是最该
    # 能预览的那一类。
    if Path(normalized_relative_path).suffix.lower() in _IMAGE_SUFFIXES:
        return WorkspacePayload(
            status_code=200,
            payload={
                "path": normalized_relative_path,
                "kind": "image",
                "url": build_raw_file_url(normalized_relative_path),
                "size": file_byte_count,
                "size_label": format_size_label(file_byte_count),
            },
        )
    if file_byte_count > MAX_FILE_BYTES:
        return WorkspacePayload(
            status_code=200,
            payload={
                "path": normalized_relative_path,
                "kind": "oversize",
                "size": file_byte_count,
                "size_label": format_size_label(file_byte_count),
                "limit_label": MAX_FILE_BYTES_LABEL,
                "note": f"文件为 {format_size_label(file_byte_count)}，超过 "
                f"{MAX_FILE_BYTES_LABEL} 的渲染上限，未读取正文。",
            },
        )

    raw_file_bytes = resolved_path.read_bytes()
    if b"\0" in raw_file_bytes[:_BINARY_SNIFF_BYTES]:
        return WorkspacePayload(
            status_code=200,
            payload={
                "path": normalized_relative_path,
                "kind": "binary",
                "size": file_byte_count,
                "size_label": format_size_label(file_byte_count),
                "note": "二进制文件，不渲染正文。",
            },
        )

    source_text = raw_file_bytes.decode("utf-8", errors="replace")
    highlighted_source = highlight_source_lines(source_text, normalized_relative_path)
    return WorkspacePayload(
        status_code=200,
        payload={
            "path": normalized_relative_path,
            "kind": "text",
            "language": highlighted_source.language_label,
            "size": file_byte_count,
            "size_label": format_size_label(file_byte_count),
            "line_count": len(highlighted_source.rendered_lines),
            "highlighted": highlighted_source.is_highlighted,
            "lines": highlighted_source.rendered_lines,
            "preview": resolve_preview_descriptor(normalized_relative_path),
        },
    )


def resolve_preview_descriptor(relative_path: str) -> dict[str, str] | None:
    """给出某个文件支持的预览方式；不支持预览时为 ``None``。

    界面靠这一位决定在内容区头部摆什么控件，而不是自己按后缀判一遍：后缀表只写在
    这里，两处分头维护时新增一种可预览的格式必然漏掉其中一边。

    Args:
        relative_path (str): 仓库相对路径。

    Returns:
        dict[str, str] | None: ``{"mode": "markdown"}``、``{"mode": "external",
            "url": "/raw/..."}``，或 ``None``。
    """
    file_suffix = Path(relative_path).suffix.lower()
    if file_suffix in _MARKDOWN_SUFFIXES:
        return {"mode": "markdown"}
    if file_suffix in _HTML_SUFFIXES:
        return {"mode": "external", "url": build_raw_file_url(relative_path)}
    return None


def build_raw_file_url(relative_path: str) -> str:
    """把仓库相对路径拼成 ``/raw/`` 路由下的 URL。

    逐段编码而不是整串 ``quote``：路径分隔符必须保持字面 ``/``，否则 ``/raw/`` 之后
    会被当成一个巨大的文件名，而文件名里的 ``%2F`` 解码回来也不是目录层级。

    Args:
        relative_path (str): 仓库相对路径（POSIX 分隔符）。

    Returns:
        str: 编码后的 ``/raw/`` URL。
    """
    encoded_segments = [quote(path_segment, safe="") for path_segment in relative_path.split("/")]
    return f"{RAW_ROUTE_PREFIX}{'/'.join(encoded_segments)}"


def build_markdown_payload(repository_root: Path, requested_path: str) -> WorkspacePayload:
    """把单个 Markdown 文件渲染成 HTML 片段，供界面的「预览」开关按需取回。

    按需而不是随 :func:`build_file_payload` 一起返回：文件视图打开 ``.md`` 先看到的是
    源码，每次打开都顺带渲染会让正文应答白白胖一倍，而多数时候那份 HTML 没人看。

    Args:
        repository_root (Path): 仓库根绝对路径。
        requested_path (str): 界面传来的仓库相对路径。

    Returns:
        WorkspacePayload: ``{"format": "markdown", "html": ...}``；路径越界、不是
            Markdown 文件、文件缺失、超出渲染上限或渲染依赖缺失时为拒绝应答。
    """
    resolved_path = resolve_repository_path(repository_root, requested_path)
    if resolved_path is None:
        return build_refusal_payload(403, _OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)

    normalized_relative_path = Path(requested_path).as_posix() if requested_path else ""
    if Path(normalized_relative_path).suffix.lower() not in _MARKDOWN_SUFFIXES:
        return build_refusal_payload(
            400,
            f"拒绝：{normalized_relative_path or '.'} 不是 Markdown 文件，没有可渲染的预览。",
        )
    if not resolved_path.is_file():
        return build_refusal_payload(404, f"未找到文件：{normalized_relative_path}")
    # 上限与正文渲染同一口径：超限文件在正文侧本来就走 oversize 分支，预览侧再放一次
    # 就等于绕开了那条上限。
    if resolved_path.stat().st_size > MAX_FILE_BYTES:
        return build_refusal_payload(
            400,
            f"拒绝：文件超过 {MAX_FILE_BYTES_LABEL} 的渲染上限，请用本地编辑器打开。",
        )

    rendered_html = render_markdown_document(
        resolved_path.read_bytes().decode("utf-8", errors="replace")
    )
    if rendered_html is None:
        return build_refusal_payload(
            503, "服务端未安装 Markdown 渲染依赖，无法生成预览，请阅读源码。"
        )
    return WorkspacePayload(status_code=200, payload={"format": "markdown", "html": rendered_html})


def render_markdown_document(source_text: str) -> str | None:
    """把 Markdown 正文渲染成 HTML 片段。

    ``markdown`` 按 :func:`highlight_source_lines` 里 pygments 同一条口径处理：显式声明
    的 dev 依赖，但缺失即降级——派生项目做 ``uv sync --no-dev`` 时预览入口不出现，源码
    高亮照旧。import 必须留在函数里：``launch.py`` 的 import 闭包只能含标准库加同目录
    兄弟模块（见 ``tests/guards/shared/test_view_launch_entry.py``），提到模块顶层会让
    ``just view`` 在 ``-S`` 下直接起不来。

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


@dataclass(frozen=True)
class RawFilePayload:
    """一个原始文件字节应答，供 ``/raw/`` 路由原样返回。

    Attributes:
        status_code (int): 应答的 HTTP 状态码。
        content_type (str): 应答的 ``Content-Type``。
        body_bytes (bytes): 应答正文。
    """

    status_code: int
    content_type: str
    body_bytes: bytes


def build_raw_file_payload(
    repository_root: Path, requested_path: str
) -> RawFilePayload | WorkspacePayload:
    """按仓库相对路径原样返回文件字节，供 HTML 文件在自己的标签页里打开。

    ``/raw/`` 是唯一一条**保持路径原样**的路由，而且必须保持：HTML 文档里的相对引用
    （``./a.css``、``../img/i.png``）要能解析回同一路由、真的加载出来。替代的防护是
    照旧走 :func:`resolve_repository_path` 的解析与越界断言——保持原样指的是 URL，
    不是边界。

    Args:
        repository_root (Path): 仓库根绝对路径。
        requested_path (str): 已解码的仓库相对路径。

    Returns:
        RawFilePayload | WorkspacePayload: 命中时为原始字节应答；路径越界、指向目录或
            文件缺失时为 JSON 拒绝应答。
    """
    resolved_path = resolve_repository_path(repository_root, requested_path)
    if resolved_path is None:
        return build_refusal_payload(403, _OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)

    normalized_relative_path = Path(requested_path).as_posix() if requested_path else ""
    if resolved_path.is_dir():
        return build_refusal_payload(
            400, f"拒绝：{normalized_relative_path or '.'} 是一个目录，请选择一个文件。"
        )
    if not resolved_path.is_file():
        return build_refusal_payload(404, f"未找到文件：{normalized_relative_path}")

    return RawFilePayload(
        status_code=200,
        content_type=_resolve_raw_content_type(normalized_relative_path),
        body_bytes=resolved_path.read_bytes(),
    )


def _resolve_raw_content_type(relative_path: str) -> str:
    """按后缀给出 ``/raw/`` 应答的 Content-Type，表外一律二进制流。"""
    return _RAW_CONTENT_TYPES_BY_SUFFIX.get(
        Path(relative_path).suffix.lower(), _DEFAULT_RAW_CONTENT_TYPE
    )


def build_changes_payload(repository_root: Path) -> WorkspacePayload:
    """给出三个分区各自的改动文件集合与增删统计。

    Args:
        repository_root (Path): 仓库根绝对路径。

    Returns:
        WorkspacePayload: 三个分区（已暂存 / 未暂存 / 未跟踪）的文件列表、分区合计与
            三区合计。空分区同样返回，界面据此显示「已暂存 0」。
    """
    sections: list[dict[str, object]] = []
    for section_name, section_label in _SECTION_LABELS.items():
        if section_name in _SECTION_DIFF_ARGUMENT_PREFIXES:
            changed_files = _collect_index_section_files(repository_root, section_name)
            has_stats = True
        else:
            # 未跟踪那一段只列文件、不给 +N -M。git 的列表类命令都不为未跟踪文件报统计，
            # 唯一口径是逐个文件跑一次 ``--no-index --numstat``；本机实测每个文件约 8ms，
            # 800 个未跟踪文件要 7 秒左右（并发跑到 8 路也只降到 4 秒，瓶颈在进程创建），
            # 页面会像卡死。逐行 diff 仍由 ``--no-index`` 在点击时才取一次。
            #
            # ``add`` / ``del`` 留 ``None`` 表示「本轮不提供」，由 ``has_stats`` 与另外两段
            # 区分开——**不提供**与**二进制**在界面上是两件事，不能共用同一个 ``None``。
            changed_files = [
                {"path": untracked_path, "status": "A", "add": None, "del": None}
                for untracked_path in _collect_untracked_file_paths(repository_root)
            ]
            has_stats = False
        sections.append(
            {
                "section": section_name,
                "label": section_label,
                "stats_available": has_stats,
                "files": changed_files,
                "totals": _total_changed_files(changed_files),
            }
        )

    all_files = [entry for section in sections for entry in section["files"]]
    return WorkspacePayload(
        status_code=200,
        payload={
            "sections": sections,
            "totals": _total_changed_files(all_files),
        },
    )


def _collect_index_section_files(
    repository_root: Path, section_name: str
) -> list[dict[str, object]]:
    """列出「已暂存」或「未暂存」分区下的改动文件。

    两个分区只差一个 ``--cached``，因此共用这条实现：分别各写一份会让口径悄悄分岔。

    Args:
        repository_root (Path): 仓库根绝对路径。
        section_name (str): ``staged`` 或 ``unstaged``。

    Returns:
        list[dict[str, object]]: 已按路径排序的改动文件条目。
    """
    section_arguments = _SECTION_DIFF_ARGUMENT_PREFIXES[section_name]
    status_entry_by_path = _parse_status_entries(
        _run_git(repository_root, *section_arguments, "--name-status", "-z")
    )
    numstat_by_path = _parse_numstat_entries(
        _run_git(repository_root, *section_arguments, "--numstat", "-z")
    )

    changed_files: list[dict[str, object]] = []
    for changed_path in sorted(status_entry_by_path):
        added_count, deleted_count = numstat_by_path.get(changed_path, (None, None))
        changed_files.append(
            {
                "path": changed_path,
                "status": status_entry_by_path[changed_path][0],
                "add": added_count,
                "del": deleted_count,
            }
        )
    return changed_files


def _total_changed_files(
    changed_files: list[dict[str, object]],
) -> dict[str, int]:
    """把一组改动文件条目汇总成文件数与增删合计。"""
    return {
        "files": len(changed_files),
        "add": sum(entry["add"] or 0 for entry in changed_files),
        "del": sum(entry["del"] or 0 for entry in changed_files),
    }


def build_diff_payload(
    repository_root: Path, requested_path: str, section_name: str
) -> WorkspacePayload:
    """给出单个文件在某个改动分区下的逐行改动。

    Args:
        repository_root (Path): 仓库根绝对路径。
        requested_path (str): 界面传来的仓库相对路径。
        section_name (str): 改动分区取值，必须是 :data:`_SECTION_LABELS` 的键之一。

    Returns:
        WorkspacePayload: 逐行 diff 应答；路径越界、文件不存在或分区取值不可用时为
            拒绝应答。正文含 ``rename_from``：该文件是重命名而来时给出旧路径，否则为
            ``None``。
    """
    section_label = _SECTION_LABELS.get(section_name)
    if section_label is None:
        return build_refusal_payload(
            400,
            f"拒绝：{section_name} 不是可用的改动分区，"
            f"请选择「{'」「'.join(_SECTION_LABELS.values())}」。",
        )

    resolved_path = resolve_repository_path(repository_root, requested_path)
    if resolved_path is None:
        return build_refusal_payload(403, _OUTSIDE_REPOSITORY_REFUSAL_MESSAGE)

    normalized_relative_path = Path(requested_path).as_posix()
    if section_name == "untracked":
        # 未跟踪文件没有可配对的旧路径，也没有索引侧可以比较；它整篇对着 /dev/null 求
        # diff。文件已被删除时提前拒绝，否则 git 的非零退出会变成 500 而不是明确应答。
        if not resolved_path.is_file():
            return build_refusal_payload(404, f"未找到文件：{normalized_relative_path}")
        rename_source = None
        diff_text = _run_git(
            repository_root,
            "diff",
            "--no-index",
            "--",
            _UNTRACKED_DIFF_LEFT_PATH,
            normalized_relative_path,
            allowed_exit_codes=_DIFF_NO_INDEX_EXIT_CODES,
        )
    else:
        section_arguments = _SECTION_DIFF_ARGUMENT_PREFIXES[section_name]
        rename_source = _lookup_rename_source(
            repository_root, section_arguments, normalized_relative_path
        )
        # 重命名必须连旧路径一起作为 pathspec 交给 git，配对才成立；只给新路径会让同一个
        # 文件降级成「新增」，正文整篇算成新增行。
        diff_pathspecs = (
            [rename_source, normalized_relative_path]
            if rename_source
            else [normalized_relative_path]
        )
        diff_text = _run_git(repository_root, *section_arguments, "-M", "--", *diff_pathspecs)

    parsed_diff = _parse_unified_diff_rows(diff_text)
    return WorkspacePayload(
        status_code=200,
        payload={
            "path": normalized_relative_path,
            "section": section_name,
            "section_label": section_label,
            "rename_from": rename_source,
            "rows": parsed_diff.rows,
            "truncated": parsed_diff.is_truncated,
            "binary": parsed_diff.is_binary,
            "empty": not parsed_diff.rows,
        },
    )


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


def prewarm_highlighting() -> None:
    """在后台预热 Pygments 的导入与词法解析，使首屏不为这段导入付费。

    典型耗时 100–150ms，正好落在冷启动预算里；预热失败不影响功能，只是首个文件
    请求会自己付这段开销。
    """
    highlight_source_lines("prewarm = True\n", "view_prewarm.py")


def format_size_label(byte_count: int) -> str:
    """把字节数渲染成人类可读的大小标签。

    Args:
        byte_count (int): 字节数。

    Returns:
        str: 形如 ``512 B`` / ``1.5 KB`` / ``2.3 MB`` 的标签。
    """
    if byte_count < 1024:
        return f"{byte_count} B"
    if byte_count < 1024 * 1024:
        return f"{byte_count / 1024:.1f} KB"
    return f"{byte_count / (1024 * 1024):.1f} MB"


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


def _is_pruned_path(relative_path: str) -> bool:
    """判断路径是否位于文件树不展示的目录下。"""
    return any(
        path_segment in _PRUNED_DIRECTORY_NAMES for path_segment in relative_path.split("/")[:-1]
    )


def _read_current_branch_name(repository_root: Path) -> str:
    """读取当前检出的分支名；分离头指针时回退为短提交号。"""
    branch_output = _run_git(repository_root, "rev-parse", "--abbrev-ref", "HEAD").strip()
    if branch_output and branch_output != "HEAD":
        return branch_output
    return _run_git(repository_root, "rev-parse", "--short", "HEAD").strip()


def _parse_status_entries(status_output: str) -> dict[str, tuple[str, str | None]]:
    """解析 ``git diff --name-status -z``，返回 新路径 -> (状态字母, 重命名来源)。

    重命名与复制条目带两个路径（旧、新）。键取新路径——终端 ``--name-only`` 在同一次
    diff 上也只列新路径，两边必须逐项一致。旧路径单独留在值里，是因为单文件 diff 需要
    它才能把配对还原（见 :func:`_lookup_rename_source`）；非重命名条目该位为 ``None``。
    """
    output_tokens = status_output.split("\0")
    status_entry_by_path: dict[str, tuple[str, str | None]] = {}
    token_index = 0
    while token_index < len(output_tokens):
        status_token = output_tokens[token_index]
        token_index += 1
        if not status_token:
            continue
        is_rename_or_copy = status_token[0] in {"R", "C"}
        source_path = (
            output_tokens[token_index]
            if is_rename_or_copy and token_index < len(output_tokens) and output_tokens[token_index]
            else None
        )
        path_token_index = token_index + 1 if is_rename_or_copy else token_index
        token_index = path_token_index + 1
        if path_token_index < len(output_tokens) and output_tokens[path_token_index]:
            status_entry_by_path[output_tokens[path_token_index]] = (
                status_token[0],
                source_path,
            )
    return status_entry_by_path


def _lookup_rename_source(
    repository_root: Path, section_arguments: tuple[str, ...], changed_path: str
) -> str | None:
    """查出 ``changed_path`` 是否由某条旧路径重命名而来，是则返回该旧路径。

    必须在**不带 pathspec 的完整 diff** 上查：``git diff <rev> -- <新路径>`` 把旧路径
    排除出候选，同一个文件会被降级成「新增」，查不到任何配对。

    Args:
        repository_root (Path): 仓库根绝对路径。
        section_arguments (tuple[str, ...]): 该分区的 ``git diff`` 参数前缀。
        changed_path (str): 仓库相对的新路径。

    Returns:
        str | None: 重命名来源的仓库相对路径；不是重命名时为 ``None``。
    """
    status_entry_by_path = _parse_status_entries(
        _run_git(repository_root, *section_arguments, "--name-status", "-z")
    )
    status_entry = status_entry_by_path.get(changed_path)
    return status_entry[1] if status_entry else None


def _parse_numstat_entries(numstat_output: str) -> dict[str, tuple[int | None, int | None]]:
    """解析 ``git diff --numstat -z``，返回 新路径 -> (新增行数, 删除行数)。

    二进制文件的计数字段是 ``-``，按 ``None`` 保留：界面据此显示「二进制」而不是
    假装有 0 行改动。
    """
    output_tokens = numstat_output.split("\0")
    counts_by_path: dict[str, tuple[int | None, int | None]] = {}
    token_index = 0
    while token_index < len(output_tokens):
        statistics_token = output_tokens[token_index]
        token_index += 1
        if not statistics_token:
            continue
        added_field, _, remainder_field = statistics_token.partition("\t")
        deleted_field, _, path_field = remainder_field.partition("\t")
        if path_field:
            # 普通条目：统计字段与路径同占一个 token。
            changed_path = path_field
        elif token_index + 1 < len(output_tokens):
            # 重命名条目：统计字段自成一个 token，其后的旧路径与新路径各占一个；与
            # ``--name-status -z`` 一样只取新路径，才能和终端 ``--name-only`` 对齐。
            changed_path = output_tokens[token_index + 1]
            token_index += 2
        else:
            continue
        counts_by_path[changed_path] = (
            _parse_count_field(added_field),
            _parse_count_field(deleted_field),
        )
    return counts_by_path


def _parse_count_field(raw_count_field: str) -> int | None:
    """把 numstat 的计数字段转成整数；二进制文件的 ``-`` 返回 ``None``。"""
    return int(raw_count_field) if raw_count_field.isdigit() else None


@dataclass(frozen=True)
class _ParsedDiff:
    """一份 unified diff 解析后的结果。

    Attributes:
        rows (list[dict[str, object]]): 逐行结构。
        is_truncated (bool): 是否因超出行数上限被截断。
        is_binary (bool): git 是否判定为二进制。二进制 diff 没有任何逐行内容，只留一行
            ``Binary files ... differ``；不单独记这一位，「没有改动」与「改动是二进制的」
            就会被界面说成同一件事。
    """

    rows: list[dict[str, object]]
    is_truncated: bool
    is_binary: bool


def _parse_unified_diff_rows(diff_text: str) -> _ParsedDiff:
    """把 unified diff 文本解析成带新旧行号的逐行结构。

    Args:
        diff_text (str): ``git diff`` 的原始输出。

    Returns:
        _ParsedDiff: 逐行结构、截断标记与二进制标记。
    """
    diff_rows: list[dict[str, object]] = []
    old_line_number = 0
    new_line_number = 0
    is_truncated = False
    is_binary = False
    for diff_line in diff_text.splitlines():
        if len(diff_rows) >= MAX_DIFF_ROWS:
            is_truncated = True
            break
        if diff_line.startswith(_BINARY_DIFF_PREFIX):
            is_binary = True
            continue
        hunk_match = _HUNK_HEADER_PATTERN.match(diff_line)
        if hunk_match:
            old_line_number = int(hunk_match.group(1))
            new_line_number = int(hunk_match.group(2))
            diff_rows.append(
                {
                    "kind": "hunk",
                    "old_no": None,
                    "new_no": None,
                    "text": diff_line,
                }
            )
            continue
        if any(diff_line.startswith(prefix) for prefix in _DIFF_METADATA_PREFIXES):
            continue
        if diff_line.startswith("+"):
            diff_rows.append(
                {"kind": "add", "old_no": None, "new_no": new_line_number, "text": diff_line[1:]}
            )
            new_line_number += 1
        elif diff_line.startswith("-"):
            diff_rows.append(
                {"kind": "del", "old_no": old_line_number, "new_no": None, "text": diff_line[1:]}
            )
            old_line_number += 1
        elif diff_line.startswith(" "):
            diff_rows.append(
                {
                    "kind": "ctx",
                    "old_no": old_line_number,
                    "new_no": new_line_number,
                    "text": diff_line[1:],
                }
            )
            old_line_number += 1
            new_line_number += 1
    return _ParsedDiff(rows=diff_rows, is_truncated=is_truncated, is_binary=is_binary)


def _run_git(
    repository_root: Path,
    *git_arguments: str,
    allowed_exit_codes: frozenset[int] = frozenset({0}),
) -> str:
    """在仓库根执行一次只读 ``git`` 查询并返回标准输出。

    Args:
        repository_root (Path): 仓库根绝对路径。
        *git_arguments (str): 传给 ``git`` 的参数（不含 ``git`` 本身）。
        allowed_exit_codes (frozenset[int]): 视为成功的退出码。默认只认 ``0``；``git
            diff --no-index`` 这类「有差异即退出 1」的子命令由调用方显式放宽。

    Returns:
        str: 命令的标准输出。

    Raises:
        WorkspaceReadError: ``git`` 的退出码不在 ``allowed_exit_codes`` 里。
    """
    completed_process = subprocess.run(
        ["git", "--no-pager", *git_arguments],
        cwd=repository_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if completed_process.returncode not in allowed_exit_codes:
        raise WorkspaceReadError(
            f"git {' '.join(git_arguments)} 执行失败：{completed_process.stderr.strip()}"
        )
    return completed_process.stdout
