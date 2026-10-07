#!/usr/bin/env python3
"""把公众号版 HTML 做成可直接粘贴进微信编辑器的剪贴板内容。

流程：push_draft.build_wechat_body()（与 API 推送草稿共用的转换链：样式内联、标签
兼容转换、列表与 figure 降级、残留外链收口）→ 本地图片转 base64 内嵌 → 写出
文章名_剪贴板版.html → osascript 以 «class HTML» 放进系统剪贴板（仅 macOS）。

内嵌图片粘贴后是否被编辑器转存、GIF 是否还会动，以编辑器里的实际显示为准，
粘贴后要逐张确认。

用法（一般直接用 copy.sh：先重新构建公众号版，再调用本脚本）:
    python3 gzh_build/to_clipboard.py 文章名 [--no-copy]
文章名可带 .md 或 _公众号版.html 后缀；--no-copy 只写文件、不动剪贴板，截图验证时用。
"""

import argparse
import base64
import mimetypes
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from push_draft import build_wechat_body, collect_elements, serialize_content  # noqa: E402

ARTICLE_DIR = Path(__file__).resolve().parent.parent
NAME_SUFFIXES = ("_公众号版.html", ".md")
FONT_FAMILY = (
    "-apple-system-font,BlinkMacSystemFont,Helvetica Neue,PingFang SC,"
    "Microsoft YaHei,Body,segoe ui,Roboto,Arial,miui,Hiragino Sans GB,sans-serif"
)


def embed_local_images(body, article_dir):
    """把本地图片的 src 换成 base64 data URI；远程图片和已内嵌的保持原样。"""
    for img in collect_elements(body, "img"):
        src = img.attrs.get("src", "")
        if not src or src.startswith(("http://", "https://", "data:")):
            continue
        image_path = article_dir / src
        if not image_path.is_file():
            sys.exit(f"找不到图片 {src}（相对文章目录 {article_dir}）")
        mime_type = mimetypes.guess_type(image_path.name)[0] or ""
        if not mime_type.startswith("image/"):
            sys.exit(f"无法识别图片类型：{src}")
        image_base64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        img.attrs["src"] = f"data:{mime_type};base64,{image_base64}"


def main():
    """读取公众号版 HTML，写出剪贴板版文件，并按需放进系统剪贴板。"""
    parser = argparse.ArgumentParser(description="生成可直接粘贴进公众号编辑器的剪贴板版 HTML")
    parser.add_argument("article", help="文章名，可带 .md 或 _公众号版.html 后缀")
    parser.add_argument(
        "--no-copy", action="store_true", help="只写出 _剪贴板版.html，不动系统剪贴板"
    )
    cli_args = parser.parse_args()

    # 文章名去掉目录和 .md / _公众号版.html 后缀，与 build.sh 的处理一致
    name = Path(cli_args.article).name
    for suffix in NAME_SUFFIXES:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    html_path = ARTICLE_DIR / f"{name}_公众号版.html"
    if not html_path.is_file():
        sys.exit(
            f"找不到 {html_path.name}：先运行 ./gzh_build/build.sh {name}，"
            f"或直接用 ./gzh_build/copy.sh {name}（构建 + 复制一步完成）"
        )

    body = build_wechat_body(html_path.read_text(encoding="utf-8"))
    embed_local_images(body, ARTICLE_DIR)
    clipboard_html = (
        '<html><head><meta charset="utf-8"></head>'
        f'<body style="font-family:{FONT_FAMILY}">{serialize_content(body)}</body></html>'
    )
    out_path = ARTICLE_DIR / f"{name}_剪贴板版.html"
    out_path.write_text(clipboard_html, encoding="utf-8")
    print(f"已写出 {out_path.name}（{out_path.stat().st_size // 1024} KB）")
    if cli_args.no_copy:
        return

    # osascript 以 «class HTML» 读入文件，编辑器粘贴时按富文本处理
    copy_script = f'set the clipboard to (read (POSIX file "{out_path}") as «class HTML»)'
    subprocess.run(["osascript", "-e", copy_script], check=True)
    clipboard_info = subprocess.run(
        ["osascript", "-e", "clipboard info"], capture_output=True, text=True
    ).stdout.strip()
    print(f"已复制到剪贴板，内容类型: {clipboard_info}")


if __name__ == "__main__":
    main()
