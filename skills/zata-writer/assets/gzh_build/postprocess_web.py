#!/usr/bin/env python3
"""网页版 HTML 后处理：把 pandoc 输出组装成 hero 封面 + 目录 + 正文 + 资料来源 + 页脚。

用法: python3 postprocess_web.py 文章_网页版.html "kicker" "副标题"
"""

import base64
import re
import sys
from datetime import date
from pathlib import Path

html_path = Path(sys.argv[1])
kicker = sys.argv[2] if len(sys.argv) > 2 else ""
subtitle = sys.argv[3] if len(sys.argv) > 3 else ""

html = html_path.read_text(encoding="utf-8")

# pandoc 头部的标题/副题
title_m = re.search(r"<h1 class=\"title\">(.*?)</h1>", html, re.S)
title = title_m.group(1) if title_m else html_path.stem

# 文章专属封面图（gzh_build/hero.html，SVG 或任意 HTML）
hero_file = html_path.parent / "gzh_build" / "hero.html"
hero = hero_file.read_text(encoding="utf-8").strip() if hero_file.exists() else ""

# 摘出 pandoc 生成的 TOC
toc_m = re.search(r"<nav id=\"TOC\"[^>]*>(.*?)</nav>", html, re.S)
toc_inner = toc_m.group(1) if toc_m else ""

# 摘出 pandoc 头（隐藏样式兜底，直接移除）
header_m = re.search(r"<header id=\"title-block-header\">.*?</header>", html, re.S)
header_html = header_m.group(0) if header_m else ""

sub_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
cover = (
    '<section class="cover">'
    f'<p class="kicker">{kicker}</p>'
    f"<h1>{title}</h1>"
    '<div class="rule"></div>'
    f"{sub_html}" + (f'<div class="hero">{hero}</div>' if hero else "") + "</section>"
)
toc = (
    f'<section class="toc"><div class="label">目录</div><nav>{toc_inner}</nav></section>'
    if toc_inner
    else ""
)
toc_side = (
    f'<aside class="toc-side"><div class="label">目录</div><nav>{toc_inner}</nav></aside>'
    if toc_inner
    else ""
)

# 滚动高亮：视口顶缘之上最后一条标题即当前节，点亮侧边栏对应条目
spy = """<script>
(function () {
  var links = [].slice.call(document.querySelectorAll('.toc-side a'));
  if (!links.length) return;
  var map = {};
  links.forEach(function (a) { map[a.getAttribute('href').slice(1)] = a; });
  var hs = [].slice.call(document.querySelectorAll('h2[id]'));
  function update() {
    var cur = null;
    hs.forEach(function (h) {
      if (h.getBoundingClientRect().top <= 160) cur = h;
    });
    links.forEach(function (a) { a.classList.remove('active'); });
    if (cur) {
      var a = map[cur.id];
      if (a) a.classList.add('active');
    }
  }
  window.addEventListener('scroll', update, { passive: true });
  window.addEventListener('resize', update);
  update();
})();
</script>"""

body_m = re.search(r"<body>(.*)</body>", html, re.S)
body = body_m.group(1)
body = body.replace(header_html, "", 1)
if toc_m:
    body = body.replace(toc_m.group(0), "", 1)

# 正文包进 <main class="content">，资料来源单独包块
src_h2 = re.search(r"<h2 id=\"[^\"]*\">资料来源</h2>", body)
if src_h2:
    head, tail = body[: src_h2.start()], body[src_h2.start() :]
    tail = tail.replace(src_h2.group(0), src_h2.group(0), 1)
    body = f'<main class="content">{head}</main><section class="sources">{tail}</section>'
else:
    body = f'<main class="content">{body}</main>'

body = (
    cover
    + toc_side
    + toc
    + body
    + spy
    + f'<footer class="colophon"><span>Zata 山外志</span><span>{date.today().year}</span></footer>'
)

html = html[: body_m.start(1)] + body + html[body_m.end(1) :]


# 本地图片转 base64 内联，做成可单独分享的单文件
def inline(m):
    """把匹配到的本地图片 src 替换为 base64 data URI；图片不存在时原样返回。"""
    src = m.group(1)
    local = html_path.parent / src
    if not local.exists():
        return m.group(0)
    data = base64.b64encode(local.read_bytes()).decode()
    return f'src="data:image/{local.suffix.lstrip(".")};base64,{data}"'


html = re.sub(r'src="(?!https?:)([^"]+)"', inline, html)

html_path.write_text(html, encoding="utf-8")
print(f"后处理完成: {html_path.name}")
