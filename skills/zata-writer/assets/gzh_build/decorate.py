#!/usr/bin/env python3
"""公众号版 HTML 后处理：把伪元素装饰和外链转换成真实节点。

伪元素（::before/::after/::marker）在「浏览器复制 → 粘贴进公众号编辑器」的路径
上会丢，因为粘贴只带 DOM 里的真实节点；外链的 href 也会被订阅号剥掉。这里在
构建期把它们实体化，让手动粘贴和 push_draft.py 的 API 路径得到一致的结果：

- h1 渐变线、h2 菱形、h3 小方块：伪元素 -> 真实节点
- 资料来源列表（同一个 <p> 里全是 <a> + <br>）：逐条拆成独立左对齐小字段落，
  避免微信阅读器两端对齐把短行拉成稀疏大字
- 正文内联链接：锚文本 + 绿色上标编号，URL 收口到文末「参考资料」

用法: python3 decorate.py 文章_公众号版.html（原地修改）
"""

import re
import sys
from pathlib import Path

# 注意 pandoc 会把长行折行，<a 和 href 之间可能是换行
LINK_RE = re.compile(r'<a\s+href="([^"]+)">(.*?)</a>', re.S)


def decorate_headings(html):
    """把 h1/h2/h3 的伪元素装饰实体化为真实节点，粘贴进编辑器才不会丢。

    Args:
        html (str): 公众号版 HTML 全文。

    Returns:
        str: 替换后的 HTML。
    """
    # h1 标题下的渐变装饰线：伪元素 -> 真实 div
    html = re.sub(
        r'(<h1 class="title">.*?</h1>)',
        r'\1<div class="title-bar"></div>',
        html,
        flags=re.S,
    )
    # 二级标题两侧的绿色菱形：伪元素 -> 真实 span
    html = re.sub(
        r"(<h2[^>]*>)(.*?)(</h2>)",
        r'\1<span class="h2-deco">◆ </span>\2<span class="h2-deco"> ◆</span>\3',
        html,
        flags=re.S,
    )
    # 三级标题前的绿色小方块：伪元素 -> 文本符号（空 span 容易被编辑器剥掉）
    html = re.sub(
        r"(<h3[^>]*>)",
        r'\1<span class="h3-deco">■</span>',
        html,
    )
    return html


def split_source_list(html):
    """整段都是链接（<br> 分隔）的 <p> 视为资料来源列表，逐条拆成独立段落。"""

    def repl(m):
        items = LINK_RE.findall(m.group(1))
        return "\n".join(
            f'<p class="srcline">{label.strip()}（{href}）</p>' for href, label in items
        )

    return re.sub(
        r'<p>((?:\s*<a\s+href="[^"]+">.*?</a>(?:<br\s*/?>)?)+)\s*</p>',
        repl,
        html,
        flags=re.S,
    )


def inline_refs(html):
    """剩余的内联链接改成 锚文本+绿色上标编号，URL 收口到文末「参考资料」。"""
    links, index = [], {}

    def repl(m):
        href, label = m.group(1), m.group(2).strip()
        if href not in index:
            index[href] = len(links) + 1
            links.append((label, href))
        return f'{label}<span class="ref-sup">[{index[href]}]</span>'

    html = LINK_RE.sub(repl, html)
    if links:
        refs = ['<p class="refs-title">参考资料</p>']
        refs += [
            f'<p class="srcline">[{i}] {label}：{href}</p>'
            for i, (label, href) in enumerate(links, 1)
        ]
        html = html.replace("</body>", "\n".join(refs) + "\n</body>")
    return html


def main():
    """入口：标题装饰 → 来源拆分 → 内链收口，顺序原地改写 HTML 文件。"""
    path = Path(sys.argv[1])
    html = path.read_text(encoding="utf-8")
    html = decorate_headings(html)
    html = split_source_list(html)
    html = inline_refs(html)
    path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()
