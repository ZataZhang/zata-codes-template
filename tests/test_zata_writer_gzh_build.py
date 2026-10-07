"""``skills/zata-writer/assets/gzh_build`` 公众号转换脚本的行为测试。

覆盖公众号发布两条路径（``to_clipboard.py`` 手动粘贴、``push_draft.py`` API 推送）
共用的转换链：``decorate.py`` 的外链收口编号、列表降级、残留外链收口、剪贴板版
产物、``copy.sh`` 一键入口，以及 ``build.sh`` 中途失败后的临时文件清理。凡是会走到
剪贴板的用例，都在 PATH 最前面放了假的 ``osascript``，只记录调用参数，不碰真实剪贴板。

**本文件是模板内部测试**：被测对象 ``skills/`` 不同步进派生项目（见
``scripts/shared/template/sync_template.sh`` 的排除清单），因此本文件也已列入
该清单，不会随同步外流。
"""

from __future__ import annotations

import base64
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

GZH_BUILD_DIR = (
    Path(__file__).resolve().parents[1] / "skills" / "zata-writer" / "assets" / "gzh_build"
)
ARTICLE_NAME = "测试文章"
THEME_STYLE_BLOCK = (GZH_BUILD_DIR / "style.html").read_text(encoding="utf-8")

PARAGRAPH_RE = re.compile(r"<p\b([^>]*)>(.*?)</p>", re.S)
STYLE_ATTR_RE = re.compile(r'style="([^"]*)"')
TAG_RE = re.compile(r"<[^>]+>")


def load_gzh_script(file_name: str) -> ModuleType:
    """按文件路径加载 gzh_build 下的脚本（它们是独立脚本，不是可导入的包）。"""
    spec = importlib.util.spec_from_file_location(
        f"gzh_{Path(file_name).stem}_under_test", GZH_BUILD_DIR / file_name
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


decorate = load_gzh_script("decorate.py")
push_draft = load_gzh_script("push_draft.py")


def paragraph_styles(html_text: str) -> dict[str, str]:
    """返回 {段落纯文本: style 属性}；降级后的段落互不嵌套，非贪婪匹配足够。"""
    styles_by_text = {}
    for paragraph_match in PARAGRAPH_RE.finditer(html_text):
        style_match = STYLE_ATTR_RE.search(paragraph_match.group(1))
        paragraph_text = TAG_RE.sub("", paragraph_match.group(2)).strip()
        styles_by_text[paragraph_text] = style_match.group(1) if style_match else ""
    return styles_by_text


def margin_bottom_of(style_text: str) -> str:
    """按层叠顺序求内联样式最终生效的下边距：后写的声明覆盖先写的。"""
    margin_bottom = ""
    for declaration in style_text.split(";"):
        property_name, _, property_value = declaration.partition(":")
        property_name, property_value = property_name.strip(), property_value.strip()
        if property_name == "margin-bottom":
            margin_bottom = property_value
        elif property_name == "margin":
            margin_parts = property_value.split()
            margin_bottom = margin_parts[2] if len(margin_parts) >= 3 else margin_parts[0]
    return margin_bottom


@pytest.fixture
def article_dir(tmp_path: Path) -> Path:
    """模拟真实文章目录：文章文件夹里带一份 gzh_build/ 脚本副本，与实际用法一致。"""
    article_path = tmp_path / "article"
    shutil.copytree(
        GZH_BUILD_DIR,
        article_path / "gzh_build",
        ignore=shutil.ignore_patterns("__pycache__", ".env"),
    )
    return article_path


def write_fake_command(fake_bin_dir: Path, command_name: str, script_body: str) -> None:
    """在 fake_bin_dir 里写一个可执行的 /bin/sh 假命令。"""
    fake_bin_dir.mkdir(exist_ok=True)
    fake_command_path = fake_bin_dir / command_name
    fake_command_path.write_text(f"#!/bin/sh\n{script_body}\n", encoding="utf-8")
    fake_command_path.chmod(0o755)


def env_with_fake_bin(fake_bin_dir: Path) -> dict[str, str]:
    """子进程环境：fake_bin_dir 排在 PATH 最前面，里面的假命令顶替同名真命令。"""
    return {**os.environ, "PATH": f"{fake_bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"}


@pytest.fixture
def clipboard_env(tmp_path: Path) -> tuple[dict[str, str], Path]:
    """PATH 最前面放一个假 osascript：只把参数追加进日志，不碰真实剪贴板。"""
    fake_bin_dir = tmp_path / "fake_bin"
    call_log_path = tmp_path / "osascript_calls.log"
    write_fake_command(fake_bin_dir, "osascript", f'printf \'%s\\n\' "$*" >> "{call_log_path}"')
    return env_with_fake_bin(fake_bin_dir), call_log_path


def write_article_html(article_path: Path, body_html: str) -> str:
    """按 build.sh 的产出形态（pandoc 标题块 + 注入的主题样式）写出公众号版，返回页面文本。"""
    page_html = (
        '<!DOCTYPE html>\n<html lang="">\n<head>\n<meta charset="utf-8" />\n'
        f"<title>{ARTICLE_NAME}</title>\n{THEME_STYLE_BLOCK}\n</head>\n<body>\n"
        f'<header id="title-block-header">\n<h1 class="title">{ARTICLE_NAME}</h1>\n'
        '<div class="title-bar"></div></header>\n'
        f"{body_html}\n</body>\n</html>\n"
    )
    (article_path / f"{ARTICLE_NAME}_公众号版.html").write_text(page_html, encoding="utf-8")
    return page_html


def run_in_article(
    article_path: Path, child_env: dict[str, str], command: list[str]
) -> subprocess.CompletedProcess[str]:
    """在文章目录里运行真实入口命令并捕获输出；退出码交给断言判断。"""
    return subprocess.run(
        command,
        cwd=article_path,
        env=child_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def run_to_clipboard(
    article_path: Path, child_env: dict[str, str], *cli_args: str
) -> subprocess.CompletedProcess[str]:
    """以真实入口方式运行文章目录里的 gzh_build/to_clipboard.py。"""
    script_path = article_path / "gzh_build" / "to_clipboard.py"
    return run_in_article(article_path, child_env, [sys.executable, str(script_path), *cli_args])


def run_gzh_shell(
    article_path: Path, child_env: dict[str, str], script_name: str, *cli_args: str
) -> subprocess.CompletedProcess[str]:
    """直接执行文章目录里的 gzh_build/*.sh，可执行位也在验证范围内。"""
    script_path = article_path / "gzh_build" / script_name
    return run_in_article(article_path, child_env, [str(script_path), *cli_args])


def read_clipboard_html(article_path: Path) -> str:
    """读取 to_clipboard.py 写出的剪贴板版 HTML。"""
    return (article_path / f"{ARTICLE_NAME}_剪贴板版.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# decorate.py：构建期外链收口
# ---------------------------------------------------------------------------

LINK_VARIANTS_BODY = """\
<body>
<p>自动链接 <a href="https://example.com/auto"
class="uri">https://example.com/auto</a>，带标题 <a
href="https://example.com/t" title="提示">标题链接</a>，原始 HTML
<a target="_blank" href="https://example.com/raw">原始链接</a>，再引一次 <a
href="https://example.com/t">同一地址</a>，脚注<a href="#fn1"
class="footnote-ref" id="fnref1"
role="doc-noteref"><sup>1</sup></a>，相对 <a href="other.md">本地文件</a>。</p>
</body>"""


class TestDecorateLinks:
    """pandoc 产出的各类 http(s) 外链都在构建期统一编号，只留一份「参考资料」。"""

    def test_inline_refs_numbers_every_http_link_variant_once(self) -> None:
        """自动链接、带标题链接、属性在前的原始 HTML 链接都编号；同一 URL 复用编号。"""
        decorated_html = decorate.inline_refs(LINK_VARIANTS_BODY)

        sup_numbers = re.findall(r'<span class="ref-sup">\[(\d+)\]</span>', decorated_html)
        assert sup_numbers == ["1", "2", "3", "2"]
        assert decorated_html.count("参考资料") == 1
        assert re.findall(r'<p class="srcline">(.*?)</p>', decorated_html) == [
            "[1] https://example.com/auto",
            "[2] 标题链接：https://example.com/t",
            "[3] 原始链接：https://example.com/raw",
        ]

    def test_inline_refs_leaves_footnote_and_relative_links(self) -> None:
        """脚注锚点和相对路径不是外链，不进「参考资料」。"""
        decorated_html = decorate.inline_refs(LINK_VARIANTS_BODY)

        assert 'href="#fn1"' in decorated_html
        assert '<a href="other.md">本地文件</a>' in decorated_html

    def test_source_list_splits_autolinks_and_titled_links(self) -> None:
        """整段都是链接的来源列表逐条拆段；自动链接只写一遍 URL。"""
        source_list_html = (
            '<p><a href="https://example.com/a"\nclass="uri">https://example.com/a</a><br />\n'
            '<a href="https://example.com/b" title="提示">B 站</a></p>'
        )

        split_html = decorate.split_source_list(source_list_html)

        assert re.findall(r'<p class="srcline">(.*?)</p>', split_html) == [
            "https://example.com/a",
            "B 站（https://example.com/b）",
        ]


# ---------------------------------------------------------------------------
# to_clipboard.py：剪贴板版产物（真实入口，假 osascript）
# ---------------------------------------------------------------------------

LIST_BODY = """\
<ul>
<li>第一项
<ul>
<li>子项</li>
</ul></li>
<li>第二项</li>
</ul>
<p>列表后的段落。</p>
<ol start="3" type="1">
<li><p>第三步</p></li>
<li><p>第四步</p>
<p>第四步的第二段。</p></li>
</ol>
<ul>
<li><p>带引用的项</p>
<blockquote>
<p>引用内容</p>
</blockquote></li>
</ul>"""

RESIDUAL_LINK_BODY = '<p>手写 HTML 里的<a href="https://example.com/custom">外链</a>。</p>'


class TestClipboardLists:
    """列表降级成「文字序号 + 段落」后，层级、续段和段距都要保留。"""

    @pytest.fixture
    def clipboard_html(self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]) -> str:
        """以 --no-copy 跑一遍列表夹具，返回剪贴板版 HTML。"""
        child_env, _ = clipboard_env
        write_article_html(article_dir, LIST_BODY)
        completed = run_to_clipboard(article_dir, child_env, ARTICLE_NAME, "--no-copy")
        assert completed.returncode == 0, completed.stderr
        return read_clipboard_html(article_dir)

    def test_output_has_single_body_and_no_native_lists(self, clipboard_html: str) -> None:
        """产物只有一层 <body>，原生列表全部降级。"""
        assert clipboard_html.count("<body") == 1
        assert not re.search(r"<(ol|ul|li)\b", clipboard_html)

    def test_nested_items_indent_one_level_deeper(self, clipboard_html: str) -> None:
        """嵌套列表多缩进一级。"""
        styles_by_text = paragraph_styles(clipboard_html)

        assert "padding-left:1.4em" in styles_by_text["• 第一项"]
        assert "padding-left:2.8em" in styles_by_text["• 子项"]

    def test_only_last_block_of_top_level_list_gets_paragraph_gap(
        self, clipboard_html: str
    ) -> None:
        """只有顶层列表的最后一块补回段距，列表后的段落不会贴上来。"""
        styles_by_text = paragraph_styles(clipboard_html)

        assert margin_bottom_of(styles_by_text["• 第一项"]) == "0.55em"
        assert margin_bottom_of(styles_by_text["• 子项"]) == "0.55em"
        assert margin_bottom_of(styles_by_text["• 第二项"]) == "1.3em"
        assert margin_bottom_of(styles_by_text["列表后的段落。"]) == "1.3em"

    def test_multi_paragraph_item_keeps_continuation_paragraph(self, clipboard_html: str) -> None:
        """一项里的第二段单独成段，与正文对齐、不带序号。"""
        styles_by_text = paragraph_styles(clipboard_html)

        assert "3. 第三步" in styles_by_text
        assert margin_bottom_of(styles_by_text["4. 第四步"]) == "0.55em"
        continuation_style = styles_by_text["第四步的第二段。"]
        assert "padding-left:1.4em" in continuation_style
        assert "text-indent:-" not in continuation_style
        assert margin_bottom_of(continuation_style) == "1.3em"

    def test_block_inside_item_stays_outside_paragraph(self, clipboard_html: str) -> None:
        """列表项里的引用块不塞进段落，按正文缩进对齐。"""
        styles_by_text = paragraph_styles(clipboard_html)
        quote_match = re.search(r'<section style="([^"]*)">(.*?)</section>', clipboard_html, re.S)

        assert "• 带引用的项" in styles_by_text
        assert quote_match is not None
        assert "引用内容" in quote_match.group(2)
        assert "margin-left:1.4em" in quote_match.group(1)


class TestClipboardOutput:
    """剪贴板版的图片内嵌、外链收口、参数形式与剪贴板开关。"""

    def test_local_images_embedded_and_remote_images_kept(
        self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
    ) -> None:
        """本地图片按真实类型转 data URI，远程图片原样保留。"""
        child_env, _ = clipboard_env
        image_dir = article_dir / "image" / ARTICLE_NAME
        image_dir.mkdir(parents=True)
        png_bytes = b"\x89PNG\r\n\x1a\nfake-png"
        (image_dir / "示意图.png").write_bytes(png_bytes)
        (image_dir / "动图.webp").write_bytes(b"RIFF0000WEBPfake")
        write_article_html(
            article_dir,
            f'<p><img src="image/{ARTICLE_NAME}/示意图.png" alt="示意图" /></p>\n'
            f'<p><img src="image/{ARTICLE_NAME}/动图.webp" alt="动图" /></p>\n'
            '<p><img src="https://example.com/remote.png" alt="远程图" /></p>',
        )

        completed = run_to_clipboard(article_dir, child_env, ARTICLE_NAME, "--no-copy")

        assert completed.returncode == 0, completed.stderr
        clipboard_html = read_clipboard_html(article_dir)
        expected_png_src = f"data:image/png;base64,{base64.b64encode(png_bytes).decode()}"
        assert f'src="{expected_png_src}"' in clipboard_html
        assert 'src="data:image/webp;base64,' in clipboard_html
        assert 'src="https://example.com/remote.png"' in clipboard_html

    def test_figure_becomes_centered_image_and_caption_paragraphs(
        self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
    ) -> None:
        """figure/figcaption 降级成居中图片段 + 图注段，alt 清空避免和图注重复。"""
        child_env, _ = clipboard_env
        write_article_html(
            article_dir,
            '<figure>\n<img src="https://example.com/chart.png" alt="份额对比" />\n'
            '<figcaption aria-hidden="true">份额对比</figcaption>\n</figure>',
        )

        completed = run_to_clipboard(article_dir, child_env, ARTICLE_NAME, "--no-copy")

        assert completed.returncode == 0, completed.stderr
        clipboard_html = read_clipboard_html(article_dir)
        assert "<figure" not in clipboard_html
        assert '<img src="https://example.com/chart.png" alt=""' in clipboard_html
        assert "text-align:center;font-size:13px" in paragraph_styles(clipboard_html)["份额对比"]

    def test_residual_links_get_one_reference_list(
        self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
    ) -> None:
        """构建期没收口的外链由共用转换链补一份「参考资料」，上标都有着落。"""
        child_env, _ = clipboard_env
        write_article_html(article_dir, RESIDUAL_LINK_BODY)

        completed = run_to_clipboard(article_dir, child_env, ARTICLE_NAME, "--no-copy")

        assert completed.returncode == 0, completed.stderr
        clipboard_html = read_clipboard_html(article_dir)
        assert re.findall(r"\[(\d+)\]</span>", clipboard_html) == ["1"]
        assert clipboard_html.count("参考资料") == 1
        assert "[1] 外链：https://example.com/custom" in clipboard_html

    def test_clipboard_body_matches_api_draft_content(
        self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
    ) -> None:
        """剪贴板版正文与草稿接口的 content 完全一致（两条路径共用一条转换链）。"""
        child_env, _ = clipboard_env
        page_html = write_article_html(article_dir, LIST_BODY + "\n" + RESIDUAL_LINK_BODY)

        completed = run_to_clipboard(article_dir, child_env, ARTICLE_NAME, "--no-copy")

        assert completed.returncode == 0, completed.stderr
        body_match = re.search(r"<body[^>]*>(.*)</body>", read_clipboard_html(article_dir), re.S)
        assert body_match is not None
        api_content = push_draft.serialize_content(push_draft.build_wechat_body(page_html))
        assert body_match.group(1) == api_content

    @pytest.mark.parametrize(
        "article_arg", [ARTICLE_NAME, f"{ARTICLE_NAME}.md", f"{ARTICLE_NAME}_公众号版.html"]
    )
    def test_no_copy_accepts_name_forms_and_skips_clipboard(
        self,
        article_dir: Path,
        clipboard_env: tuple[dict[str, str], Path],
        article_arg: str,
    ) -> None:
        """三种文章名写法都能找到公众号版；--no-copy 不调用 osascript。"""
        child_env, call_log_path = clipboard_env
        write_article_html(article_dir, "<p>正文。</p>")

        completed = run_to_clipboard(article_dir, child_env, article_arg, "--no-copy")

        assert completed.returncode == 0, completed.stderr
        assert (article_dir / f"{ARTICLE_NAME}_剪贴板版.html").exists()
        assert not call_log_path.exists()

    def test_default_mode_sends_output_file_to_clipboard(
        self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
    ) -> None:
        """默认模式把写出的剪贴板版文件交给 osascript。"""
        child_env, call_log_path = clipboard_env
        write_article_html(article_dir, "<p>正文。</p>")

        completed = run_to_clipboard(article_dir, child_env, ARTICLE_NAME)

        assert completed.returncode == 0, completed.stderr
        output_path = (article_dir / f"{ARTICLE_NAME}_剪贴板版.html").resolve()
        osascript_calls = call_log_path.read_text(encoding="utf-8")
        assert f'read (POSIX file "{output_path}") as «class HTML»' in osascript_calls

    def test_missing_article_html_explains_how_to_build(
        self, article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
    ) -> None:
        """公众号版不存在时给出可执行的提示，不抛 traceback。"""
        child_env, call_log_path = clipboard_env

        completed = run_to_clipboard(article_dir, child_env, "不存在的文章", "--no-copy")

        assert completed.returncode != 0
        assert "Traceback" not in completed.stderr
        assert "copy.sh" in completed.stderr
        assert not call_log_path.exists()


# ---------------------------------------------------------------------------
# copy.sh：先重建公众号版，再生成剪贴板版
# ---------------------------------------------------------------------------

ARTICLE_MARKDOWN = """\
# 测试文章

自动链接 <https://example.com/auto>，带标题的 [标题链接](https://example.com/t "提示")，\
普通的 [普通链接](https://example.com/plain)。

- 第一项
- 第二项
"""


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="copy.sh 依赖本机 pandoc")
def test_copy_sh_rebuilds_then_writes_clipboard_file(
    article_dir: Path, clipboard_env: tuple[dict[str, str], Path]
) -> None:
    """copy.sh 先重建公众号版再写剪贴板版，链接编号与参考资料一一对应。"""
    child_env, call_log_path = clipboard_env
    (article_dir / f"{ARTICLE_NAME}.md").write_text(ARTICLE_MARKDOWN, encoding="utf-8")
    gongzhong_html_path = article_dir / f"{ARTICLE_NAME}_公众号版.html"
    gongzhong_html_path.write_text("<html><body><p>过期内容</p></body></html>", encoding="utf-8")

    completed = run_gzh_shell(article_dir, child_env, "copy.sh", f"{ARTICLE_NAME}.md", "--no-copy")

    assert completed.returncode == 0, completed.stderr
    assert "过期内容" not in gongzhong_html_path.read_text(encoding="utf-8")
    clipboard_html = read_clipboard_html(article_dir)
    assert not re.search(r"<(ol|ul|li)\b", clipboard_html)
    assert clipboard_html.count("参考资料") == 1
    assert re.findall(r"\[(\d+)\]</span>", clipboard_html) == ["1", "2", "3"]
    assert re.findall(r">\[(\d+)\] ", clipboard_html) == ["1", "2", "3"]
    assert not call_log_path.exists()


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="build.sh 依赖本机 pandoc")
def test_failed_build_cleans_temp_file_and_next_build_succeeds(
    article_dir: Path, tmp_path: Path
) -> None:
    """构建在 pandoc 这步失败时临时文件被清理，下一次构建不受影响。"""
    (article_dir / f"{ARTICLE_NAME}.md").write_text(ARTICLE_MARKDOWN, encoding="utf-8")
    failing_bin_dir = tmp_path / "failing_bin"
    pandoc_input_log_path = tmp_path / "pandoc_input.log"
    # 假 pandoc 记下 build.sh 交给它的临时文件路径，然后报错退出
    write_fake_command(
        failing_bin_dir, "pandoc", f'printf \'%s\\n\' "$1" >> "{pandoc_input_log_path}"\nexit 1'
    )

    failed_build = run_gzh_shell(
        article_dir, env_with_fake_bin(failing_bin_dir), "build.sh", ARTICLE_NAME
    )

    assert failed_build.returncode != 0
    build_temp_path = Path(pandoc_input_log_path.read_text(encoding="utf-8").splitlines()[0])
    assert not build_temp_path.exists()

    rebuilt = run_gzh_shell(article_dir, dict(os.environ), "build.sh", ARTICLE_NAME)

    assert rebuilt.returncode == 0, rebuilt.stderr
    assert (article_dir / f"{ARTICLE_NAME}_公众号版.html").exists()
