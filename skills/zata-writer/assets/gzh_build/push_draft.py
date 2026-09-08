#!/usr/bin/env python3
"""把公众号版 HTML 推送为公众号草稿：样式内联 + 正文图片上传 + draft/add。

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
from pathlib import Path

BASE = "https://api.weixin.qq.com/cgi-bin"
VOID_TAGS = {"img", "br", "hr", "meta", "link", "input"}

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


def parse_css(css_text):
    """把样式表解析为 (选择器, 声明) 规则列表，跳过伪元素规则（内联样式表达不了）。"""
    # 先去掉注释和 @media 等嵌套块，否则 @media print 里的 orphans/widows 会被当成普通规则内联
    css_text = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
    css_text = re.sub(r"@[^{}]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", css_text)
    rules = []
    for m in re.finditer(r"([^{}]+)\{([^}]+)\}", css_text):
        for sel in m.group(1).split(","):
            sel = sel.strip()
            if sel and "::" not in sel and not sel.startswith("@"):
                rules.append((sel, m.group(2).strip().rstrip(";")))
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
            existing = node.attrs.get("style", "").rstrip(";")
            node.attrs["style"] = ";".join([existing] + matched if existing else matched)
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
                img_p.children.append(img)
                img.parent = img_p
            new_children.append(img_p)
            if cap is not None:
                cap_p = El(
                    "p", [("style", "text-align:center;font-size:13px;color:#999;margin-top:6px;")]
                )
                cap_p.children = cap.children
                for c in cap_p.children:
                    if isinstance(c, El):
                        c.parent = cap_p
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
        existing = node.attrs.get("style", "").rstrip(";")
        node.attrs["style"] = (
            ((existing + ";") if existing else "")
            + "text-align:center;font-size:13px;color:#999;line-height:1.6;"
            "margin:6px 0 1.4em;letter-spacing:0;"
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
    LINKS.clear()
    LINK_INDEX.clear()
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
    # 页面里有两份 <style>（pandoc 默认样式 + 注入的主题），都要参与内联，后面的覆盖前面的
    css_text = "\n".join(re.findall(r"<style>(.*?)</style>", html_text, re.S))
    rules = parse_css(css_text)

    builder = TreeBuilder()
    builder.feed(html_text)
    body = collect_elements(builder.root, "body")[0]

    # 标题走草稿字段，正文里去掉 pandoc 生成的 header
    body.children = [c for c in body.children if not (isinstance(c, El) and c.tag == "header")]

    inline_styles(body, rules)
    wechat_compat(body)
    flatten_figures(body)

    # 正文外链统一收口到文末「参考资料」
    if LINKS:
        sep = El(
            "p", [("style", "margin:2em 0 0.8em;font-size:15px;font-weight:700;color:#1a1a1a;")]
        )
        sep.children.append("参考资料")
        body.children.append(sep)
        for i, (label, href) in enumerate(LINKS, 1):
            item = El(
                "p",
                [
                    (
                        "style",
                        "font-size:13px;color:#8a97a5;line-height:1.8;"
                        "word-break:break-all;margin:0 0 4px;text-align:left;",
                    )
                ],
            )
            item.children.append(f"[{i}] {label}：{href}")
            body.children.append(item)

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
    first_p = collect_elements(body, "p")
    digest = re.sub(r"\s+", " ", text_of(first_p[0])).strip()[:110] if first_p else title

    content = "".join(serialize(c) for c in body.children)
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
