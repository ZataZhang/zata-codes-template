#!/usr/bin/env python3
"""把公众号版 HTML 推送为公众号草稿：样式内联 + 正文图片上传 + draft/add。

正文转换统一走 build_wechat_body()，to_clipboard.py 的手动粘贴路径也调用它，
两条发布路径的排版因此一致。

用法: python3 push_draft.py 文章_公众号版.html 文章.md
凭证优先读系统环境变量 GZH_APPID / GZH_APPSECRET，
未设置时回退到脚本同目录的 .env（APPID / APPSECRET）。
输出不打印密钥和 token。
"""

import json
import os
import re
import subprocess
import sys
from html import escape
from html.parser import HTMLParser
from itertools import groupby
from pathlib import Path

BASE = "https://api.weixin.qq.com/cgi-bin"
VOID_TAGS = {"img", "br", "hr", "meta", "link", "input"}

# 列表降级版式：序号悬挂宽度、项间距；顶层列表结束处补回的段距与 style.html 里
# p / ol, ul 的 margin-bottom 一致，否则列表后的段落会贴上来，像列表的延续
LIST_MARKER_WIDTH_EM = 1.4
LIST_ITEM_GAP = "0.55em"
LIST_END_GAP = "1.3em"
LIST_MARKER_COLOR = "#07c160"
# <li> 里的这些子元素按块处理：各自成段或保持块级，不和文字揉进同一个 <p>
LIST_BLOCK_TAGS = {
    "p", "ol", "ul", "div", "section", "blockquote", "pre", "table", "figure", "hr", "dl",
    "h1", "h2", "h3", "h4", "h5", "h6",
}  # fmt: skip

# 正文外链收口：anchor 文本留在正文，URL 进文末「参考资料」
LINKS = []  # [(label, url)]，按正文出现顺序编号
LINK_INDEX = {}  # url -> 编号（去重）


class El:
    """轻量 DOM 节点，保存标签、属性和子节点。"""

    def __init__(self, tag, attrs):
        """初始化标签、属性映射和空的子节点列表。"""
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []
        self.parent = None


class TreeBuilder(HTMLParser):
    """把标准 HTML 解析成树结构。"""

    def __init__(self):
        """创建根节点并从根节点开始维护解析栈。"""
        super().__init__(convert_charrefs=True)
        self.root = El("root", [])
        self.stack = [self.root]

    def _append(self, node):
        """把节点挂到当前栈顶元素下。"""
        node.parent = self.stack[-1]
        self.stack[-1].children.append(node)

    def handle_starttag(self, tag, attrs):
        """记录起始标签；非 void 标签继续压入解析栈。"""
        el = El(tag, attrs)
        self._append(el)
        if tag not in VOID_TAGS:
            self.stack.append(el)

    def handle_endtag(self, tag):
        """遇到闭合标签时弹出对应的解析栈节点。"""
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        """把文本内容追加到当前栈顶元素。"""
        self.stack[-1].children.append(data)


def append_children(parent, nodes):
    """把节点依次挂到 parent 下，元素节点同步更新 parent 指针。"""
    for node in nodes:
        if isinstance(node, El):
            node.parent = parent
        parent.children.append(node)


def append_style(node, declarations):
    """在节点现有内联样式后追加声明；同名属性后写的覆盖先写的。"""
    existing = node.attrs.get("style", "").rstrip(";")
    node.attrs["style"] = f"{existing};{declarations}" if existing else declarations


def parse_css(css_text):
    """把样式表解析为 (选择器, 声明) 规则列表，跳过伪元素规则（内联样式表达不了）。"""
    # 先去掉注释和 @media 等嵌套块，否则 @media print 里的 orphans/widows 会被当成普通规则内联
    css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
    css_text = re.sub(r"@[^{}]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css_text)
    rules = []
    for m in re.finditer(r"([^{}]+)\{([^}]+)\}", css_text):
        # 跨行的声明要压成单行：内联进 style 属性时保留换行会产出畸形属性值
        decls = re.sub(r"\s+", " ", m.group(2)).strip().rstrip(";")
        for sel in m.group(1).split(","):
            sel = sel.strip()
            if sel and "::" not in sel and not sel.startswith("@"):
                rules.append((sel, decls))
    return rules


def match_simple(el, simple):
    """判断单个简单选择器是否命中元素。"""
    pseudo = None
    m = re.search(r":(last-child|nth-child\(even\))", simple)
    if m:
        pseudo = m.group(1)
        simple = simple[: m.start()]
    tag, _, cls = simple.partition(".")
    if tag and el.tag != tag:
        return False
    if cls and cls not in el.attrs.get("class", "").split():
        return False
    if pseudo and el.parent is not None:
        sibs = [c for c in el.parent.children if isinstance(c, El)]
        if pseudo == "last-child" and (not sibs or sibs[-1] is not el):
            return False
        if pseudo == "nth-child(even)" and (sibs.index(el) + 1) % 2 != 0:
            return False
    return True


def match_selector(el, selector):
    """判断完整的后代选择器是否命中元素。"""
    parts = selector.split()
    if not match_simple(el, parts[-1]):
        return False
    anc = el.parent
    for part in reversed(parts[:-1]):
        while anc is not None and not match_simple(anc, part):
            anc = anc.parent
        if anc is None:
            return False
        anc = anc.parent
    return True


def inline_styles(node, rules):
    """把命中的 CSS 规则合并进节点的内联样式。"""
    if isinstance(node, El):
        matched = [decls for sel, decls in rules if match_selector(node, sel)]
        if matched:
            append_style(node, ";".join(matched))
        for child in node.children:
            inline_styles(child, rules)


def flatten_figures(node):
    """公众号草稿接口对 figure/figcaption 支持不稳，转成居中段 + 图注段。"""
    if not isinstance(node, El):
        return
    new_children = []
    for child in node.children:
        if isinstance(child, El) and child.tag == "figure":
            img = next((c for c in child.children if isinstance(c, El) and c.tag == "img"), None)
            cap = next(
                (c for c in child.children if isinstance(c, El) and c.tag == "figcaption"), None
            )
            img_p = El("p", [("style", "text-align:center;")])
            if img is not None:
                img.attrs["alt"] = ""  # 避免编辑器同时显示 alt 和图注造成重复
                append_children(img_p, [img])
            new_children.append(img_p)
            if cap is not None:
                cap_p = El(
                    "p", [("style", "text-align:center;font-size:13px;color:#999;margin-top:6px;")]
                )
                append_children(cap_p, cap.children)
                new_children.append(cap_p)
        else:
            flatten_figures(child)
            new_children.append(child)
    node.children = new_children


def collect_elements(node, tag):
    """递归收集指定标签的所有元素节点。"""
    found = []
    if isinstance(node, El):
        if node.tag == tag:
            found.append(node)
        for child in node.children:
            found.extend(collect_elements(child, tag))
    return found


def serialize(node):
    """把节点序列化为微信可接受的 HTML 字符串。"""
    if isinstance(node, str):
        return escape(node)
    attrs = "".join(f' {k}="{escape(str(v), quote=True)}"' for k, v in node.attrs.items())
    if node.tag in VOID_TAGS:
        return f"<{node.tag}{attrs}>"
    return f"<{node.tag}{attrs}>" + "".join(serialize(c) for c in node.children) + f"</{node.tag}>"


def wechat_compat(node):
    """公众号草稿接口的标签白名单适配：mark/blockquote 会被剥掉，渐变背景会被过滤。

    在内联样式之后运行，用纯内联的稳妥样式替换这些元素。
    """
    if not isinstance(node, El):
        return
    if node.tag == "mark":
        node.tag = "span"
        node.attrs.pop("class", None)
        node.attrs["style"] = "background-color:#fff1a8;color:#1a1a1a;padding:0 1px;"
    elif node.tag == "blockquote":
        node.tag = "section"
        node.attrs.pop("class", None)
        node.attrs["style"] = (
            "margin:0 0 1.4em;padding:14px 18px;background-color:#f6f8f7;"
            "border-left:4px solid #07c160;color:#6b6b6b;font-size:14px;line-height:1.8;"
        )
    elif node.tag == "h2":
        # 参考新智元：居中标题 + 两侧绿色菱形装饰，比纯左对齐更醒目
        node.attrs.pop("class", None)
        node.attrs["style"] = (
            "text-align:center;font-size:19px;font-weight:800;color:#07c160;"
            "line-height:1.6;margin:2em 0 1.2em;"
        )
        # decorate.py 已在构建期注入过菱形的，不再重复添加
        if not text_of(node).strip().startswith("◆"):
            deco_l = El("span", [("style", "color:#07c160;font-size:15px;")])
            deco_l.children.append("◆ ")
            deco_r = El("span", [("style", "color:#07c160;font-size:15px;")])
            deco_r.children.append(" ◆")
            node.children.insert(0, deco_l)
            node.children.append(deco_r)
    elif node.tag == "h3":
        node.attrs["style"] = "font-size:16.5px;font-weight:700;color:#1a1a1a;margin:1.6em 0 0.9em;"
    elif node.tag == "p" and text_of(node).strip().startswith("▲"):
        # 图注约定：整段以 ▲ 开头 → 小字居中灰（md 里写在图片下一行的斜体段）
        append_style(
            node,
            "text-align:center;font-size:13px;color:#999;line-height:1.6;"
            "margin:6px 0 1.4em;letter-spacing:0;",
        )
    elif node.tag == "img":
        node.attrs["style"] = "max-width:100%;"
    new_children = []
    for child in node.children:
        if isinstance(child, El) and child.tag == "a":
            # 订阅号正文不支持外链：锚文本保留为正常正文，URL 收进文末「参考资料」，
            # 正文里只留一个绿色小上标编号
            href = child.attrs.get("href", "").strip()
            label = text_of(child).strip()
            span = El("span", [])
            span.children.append(label)
            if href.startswith("http"):
                if href not in LINK_INDEX:
                    LINK_INDEX[href] = len(LINKS) + 1
                    LINKS.append((label, href))
                sup = El("span", [("style", "font-size:11px;color:#07c160;vertical-align:super;")])
                sup.children.append(f"[{LINK_INDEX[href]}]")
                span.children.append(sup)
            new_children.append(span)
        else:
            wechat_compat(child)
            new_children.append(child)
    node.children = new_children


def text_of(node):
    """递归提取节点内所有纯文本内容。"""
    if isinstance(node, str):
        return node
    return "".join(text_of(c) for c in node.children)


def split_list_item(li):
    """把 <li> 的直接子节点按顺序切段：("text", 节点列表)、("list", 嵌套列表)、("block", 块元素)。

    连续的文字和内联元素合成一段；pandoc 松散列表给每段包的 <p> 各自成段，
    避免多段并成一行；引用、代码块等块元素单独成段，不塞进 <p>。只有空白的文字段丢弃。
    """
    segments = []
    for is_block, run in groupby(
        li.children, key=lambda child: isinstance(child, El) and child.tag in LIST_BLOCK_TAGS
    ):
        if not is_block:
            inline_nodes = list(run)
            if any(isinstance(node, El) or node.strip() for node in inline_nodes):
                segments.append(("text", inline_nodes))
            continue
        for block in run:
            if block.tag == "p":
                segments.append(("text", block.children))
            elif block.tag in ("ol", "ul"):
                segments.append(("list", block))
            else:
                segments.append(("block", block))
    return segments


def list_paragraph(indent_em, hanging):
    """列表降级用的段落：首段用负 text-indent 把序号悬挂在左侧，续段直接与正文对齐。"""
    style = f"margin:0 0 {LIST_ITEM_GAP};padding-left:{indent_em:g}em;"
    if hanging:
        style += f"text-indent:-{LIST_MARKER_WIDTH_EM:g}em;"
    return El("p", [("style", style)])


def list_paragraphs(list_el, depth):
    """把一个 <ol>/<ul> 展开成「文字序号 + 段落」的块序列。

    每项首段带序号；同一项的续段和块元素与首段正文对齐、不带序号；
    嵌套列表递归加深一级缩进。
    """
    ordered = list_el.tag == "ol"
    number = 1
    start_match = re.match(r"\d+", str(list_el.attrs.get("start", "")))
    if ordered and start_match:
        number = int(start_match.group())
    marker_weight = "700" if ordered else "400"
    indent_em = (depth + 1) * LIST_MARKER_WIDTH_EM
    blocks = []
    for li in list_el.children:
        if not (isinstance(li, El) and li.tag == "li"):
            continue
        segments = split_list_item(li)
        marker = El("span", [("style", f"color:{LIST_MARKER_COLOR};font-weight:{marker_weight};")])
        marker.children.append(f"{number}. " if ordered else "• ")
        lead = list_paragraph(indent_em, hanging=True)
        append_children(lead, [marker])
        # 首段是文字时并进序号段；以块或嵌套列表开头的项，序号单独占一段
        if segments and segments[0][0] == "text":
            append_children(lead, segments.pop(0)[1])
        blocks.append(lead)
        for kind, payload in segments:
            if kind == "text":
                continuation = list_paragraph(indent_em, hanging=False)
                append_children(continuation, payload)
                blocks.append(continuation)
            elif kind == "list":
                blocks.extend(list_paragraphs(payload, depth + 1))
            else:
                flatten_lists(payload)
                append_style(payload, f"margin-left:{indent_em:g}em;")
                blocks.append(payload)
        number += 1
    return blocks


def flatten_lists(node):
    """把 <ol>/<ul> 降级为「文字序号 + 普通段落」，规避公众号对原生列表的破坏。

    公众号编辑器与草稿接口都不认原生有序/无序列表：粘贴或推送后，<li> 的序号会
    与内容被拆成两行，空行处还会多出空序号。这里改用段落承载「1. / •」文字序号，
    微信只当普通段落处理，手动粘贴与 API 推送两条路径结果一致。

    在内联样式与 wechat_compat 之后运行（序号颜色/加粗在这里按主题补回）。
    """
    if not isinstance(node, El):
        return
    new_children = []
    for child in node.children:
        if isinstance(child, El) and child.tag in ("ol", "ul"):
            blocks = list_paragraphs(child, depth=0)
            if blocks:
                append_style(blocks[-1], f"margin-bottom:{LIST_END_GAP};")
            new_children.extend(blocks)
        else:
            flatten_lists(child)
            new_children.append(child)
    node.children = []
    append_children(node, new_children)


def append_reference_list(body):
    """把 wechat_compat 收集的残留外链追加为文末「参考资料」，编号与正文上标一一对应。

    pandoc 生成的外链已由 decorate.py 在构建期收口，这里兜底的是手写 HTML 等
    没经过 decorate.py 的链接。
    """
    if not LINKS:
        return
    title_p = El(
        "p", [("style", "margin:2em 0 0.8em;font-size:15px;font-weight:700;color:#1a1a1a;")]
    )
    title_p.children.append("参考资料")
    entry_paragraphs = [title_p]
    for i, (label, href) in enumerate(LINKS, 1):
        entry_p = El(
            "p",
            [
                (
                    "style",
                    "font-size:13px;color:#8a97a5;line-height:1.8;"
                    "word-break:break-all;margin:0 0 4px;text-align:left;",
                )
            ],
        )
        entry_p.children.append(f"[{i}] {label}：{href}")
        entry_paragraphs.append(entry_p)
    append_children(body, entry_paragraphs)


def build_wechat_body(html_text):
    """把公众号版 HTML 转成微信可接受的正文节点：手动粘贴与 API 推送共用这一条转换链。

    合并页面里全部 <style> 规则并内联 → 去掉 pandoc 标题块 → 标签兼容转换 →
    列表、figure 降级 → 残留外链收口到「参考资料」。返回 body 节点，
    序列化用 serialize_content()，不要把 <body> 标签本身带进正文。
    """
    LINKS.clear()
    LINK_INDEX.clear()
    # 页面里有两份 <style>（pandoc 默认样式 + 注入的主题），都要参与内联，后面的覆盖前面的
    css_text = "\n".join(re.findall(r"<style>(.*?)</style>", html_text, re.S))
    rules = parse_css(css_text)

    builder = TreeBuilder()
    builder.feed(html_text)
    body = collect_elements(builder.root, "body")[0]

    # 标题走草稿字段或编辑器的标题栏，正文里去掉 pandoc 生成的 header
    body.children = [c for c in body.children if not (isinstance(c, El) and c.tag == "header")]

    inline_styles(body, rules)
    wechat_compat(body)
    flatten_lists(body)
    flatten_figures(body)
    append_reference_list(body)
    return body


def serialize_content(body):
    """序列化正文：只拼接 body 的子节点，不带 <body> 标签本身。"""
    return "".join(serialize(c) for c in body.children)


def curl(args):
    """执行 curl 命令并返回 UTF-8 响应文本。"""
    return subprocess.run(
        ["curl", "-s", "--max-time", "60"] + args, capture_output=True, check=True
    ).stdout.decode("utf-8")


def get_token(appid, secret):
    """通过公众号接口获取访问 token。"""
    resp = json.loads(
        curl([f"{BASE}/token?grant_type=client_credential&appid={appid}&secret={secret}"])
    )
    if "access_token" not in resp:
        sys.exit(f"获取 token 失败: {resp.get('errcode')} {resp.get('errmsg')}")
    return resp["access_token"]


def upload_image(url, path):
    """上传图片到公众号接口并返回响应结果。"""
    resp = json.loads(curl(["-F", f"media=@{path}", url]))
    if "errcode" in resp and resp["errcode"] != 0:
        sys.exit(f"图片上传失败 {path}: {resp.get('errcode')} {resp.get('errmsg')}")
    return resp


def main():
    """读取文章与凭证，生成草稿并推送到公众号。"""
    html_path = Path(sys.argv[1]).resolve()
    md_path = Path(sys.argv[2]).resolve()
    article_dir = html_path.parent

    # 优先系统环境变量，回退到 .env 文件
    appid = os.environ.get("GZH_APPID", "").strip()
    appsecret = os.environ.get("GZH_APPSECRET", "").strip()
    if not (appid and appsecret):
        env_file = Path(__file__).parent / ".env"
        if env_file.exists():
            env = dict(
                line.split("=", 1)
                for line in env_file.read_text(encoding="utf-8").splitlines()
                if "=" in line and not line.startswith("#")
            )
            appid = appid or env.get("APPID", "").strip()
            appsecret = appsecret or env.get("APPSECRET", "").strip()
    if not (appid and appsecret):
        sys.exit(
            "缺少凭证：请设置环境变量 GZH_APPID / GZH_APPSECRET，"
            "或在 gzh_build/.env 中填写 APPID / APPSECRET"
        )

    html_text = html_path.read_text(encoding="utf-8")
    body = build_wechat_body(html_text)

    token = get_token(appid, appsecret)

    # 正文图片：本地文件上传到微信图床，替换 src
    images = collect_elements(body, "img")
    for img in images:
        src = img.attrs.get("src", "")
        if src.startswith("http"):
            continue
        local = article_dir / src
        resp = upload_image(f"{BASE}/media/uploadimg?access_token={token}", local)
        img.attrs["src"] = resp["url"]
        print(f"已上传正文图: {local.name}")
    # 上传后丢掉 class，减少草稿接口过滤噪音
    for img in images:
        img.attrs.pop("class", None)

    # 封面：图片目录里有「封面.png/jpg」就优先用它；否则取第一张非 GIF 的本地图
    # （GIF 开头动画首帧可能是空白，不适合做封面）
    covers = sorted(article_dir.glob("image/*/封面.*")) or sorted(article_dir.rglob("封面.*"))
    if covers:
        first_local = str(covers[0].relative_to(article_dir))
    else:
        local_srcs = [
            s
            for s in re.findall(r'<img[^>]+src="(?!http)([^"]+)"', html_text)
            if not s.lower().endswith(".gif")
        ]
        if not local_srcs:
            sys.exit("文章没有可用作封面的静态图片")
        first_local = local_srcs[0]
    cover_resp = upload_image(
        f"{BASE}/material/add_material?access_token={token}&type=image", article_dir / first_local
    )
    thumb_media_id = cover_resp["media_id"]
    print(f"已上传封面: {first_local}")

    title = re.sub(r"^#\s*", "", md_path.read_text(encoding="utf-8").splitlines()[0]).strip()
    # 摘要取第一段有文字的正文：正文开头的品牌动画（decorate.py 插的）和图片段落
    # 都是只有 <img> 的 <p>，取第一段会得到空摘要。
    paras = collect_elements(body, "p")
    digest = next(
        (re.sub(r"\s+", " ", text_of(p)).strip() for p in paras if text_of(p).strip()), ""
    )
    digest = digest[:110] or title

    content = serialize_content(body)
    print(f"正文 HTML 长度: {len(content)} 字符")

    payload = {
        "articles": [
            {
                "title": title,
                "author": "",
                "digest": digest,
                "content": content,
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }
    payload_file = Path("/tmp/gzh_draft_payload.json")
    payload_file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    resp = json.loads(
        curl(
            [
                "-X",
                "POST",
                "-H",
                "Content-Type: application/json; charset=utf-8",
                "--data-binary",
                f"@{payload_file}",
                f"{BASE}/draft/add?access_token={token}",
            ]
        )
    )
    if "media_id" in resp:
        print(f"草稿创建成功，media_id: {resp['media_id']}")
        print("去公众号后台「草稿箱」查看并预览确认。")
    else:
        sys.exit(f"草稿创建失败: {resp.get('errcode')} {resp.get('errmsg')}")


if __name__ == "__main__":
    main()
