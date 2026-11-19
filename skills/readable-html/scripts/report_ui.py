"""图文汇报的内嵌图片与渐进增强组件，复用 svg_kit 的主题令牌。"""

import base64
import mimetypes
import re
from html import escape
from pathlib import Path

_KIND_LABELS = {
    "diagram": "能力示意图",
    "prototype": "设计原型",
    "screenshot": "实际页面截图",
}


def evidence_figure(
    image_path: Path,
    *,
    title: str,
    description: str = "",
    kind: str = "screenshot",
) -> str:
    """将本地图片内嵌为有说明、可键盘放大的证据图。

    Args:
        image_path: 实际图片文件路径。
        title: 图片标题，同时用作替代文本。
        description: 图片依据、环境或原型边界说明。
        kind: diagram、prototype 或 screenshot。

    Returns:
        可插入页面的 figure HTML。

    Raises:
        ValueError: 图片类型或图片语义不受支持。
        OSError: 图片文件无法读取。
    """
    if kind not in _KIND_LABELS:
        raise ValueError(f"不支持的图片语义：{kind}")
    image_path = Path(image_path)
    mime_type = mimetypes.guess_type(image_path.name)[0]
    if mime_type not in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
        raise ValueError(f"不支持的图片类型：{image_path.suffix}")
    encoded_image = base64.b64encode(image_path.read_bytes()).decode("ascii")
    image_uri = f"data:{mime_type};base64,{encoded_image}"
    safe_title = escape(title, quote=True)
    return (
        '<figure class="report-evidence">'
        f'<span class="report-kind">{_KIND_LABELS[kind]}</span>'
        f'<button type="button" class="report-zoom" aria-haspopup="dialog" '
        f'aria-label="放大查看：{safe_title}"><img src="{image_uri}" '
        f'alt="{safe_title}" loading="lazy"></button>'
        f"<figcaption><b>{safe_title}</b><p>{escape(description)}</p>"
        '<small class="report-zoom-hint" hidden>点击图片放大</small></figcaption></figure>'
    )


_REPORT_STYLE = """
.report-story{display:grid;
grid-template-columns:1fr 1.1fr;
gap:32px;
align-items:center}

.report-gallery{display:grid;
grid-template-columns:1fr 1fr;
gap:24px}

.report-evidence{margin:0;
min-width:0}

.report-kind{display:block;
color:var(--muted);
font-size:12px;
margin-bottom:8px}

.report-zoom{display:block;
width:100%;
padding:0;
background:var(--soft);
border:1px solid var(--line);
border-radius:12px;
overflow:hidden;
color:inherit;
cursor:zoom-in}

.report-zoom:focus-visible{outline:3px solid var(--accent);
outline-offset:4px}

.report-zoom img{display:block;
width:100%;
height:auto;
max-height:520px;
object-fit:contain}

.report-evidence figcaption{margin-top:12px;
font-size:14px}

.report-evidence figcaption p{font-size:13px;
color:var(--muted);
margin:4px 0}

.report-evidence small{color:var(--accent);
font-size:12px}

.report-detail{border-top:1px solid var(--line);
margin-top:24px}

.report-detail summary{padding:16px 0;
cursor:pointer;
font-weight:600}

.report-detail-body{padding:0 0 20px;
overflow-x:auto}

.report-lightbox{padding:0;
border:1px solid var(--line);
border-radius:12px;
max-width:96vw;
max-height:94vh;
background:var(--surface);
color:var(--fg)}

.report-lightbox::backdrop{background:var(--gate);
opacity:.9}

.report-lightbox img{display:block;
max-width:91vw;
max-height:80vh;
object-fit:contain;
margin:auto}

.report-lightbox-bar{display:flex;
align-items:center;
justify-content:space-between;
gap:20px;
padding:12px 18px;
font-size:14px}

.report-lightbox button{font:inherit;
border:1px solid var(--line);
border-radius:6px;
padding:5px 14px;
background:var(--surface);
color:var(--fg);
cursor:pointer}

@media(max-width:820px){.report-story,.report-gallery{grid-template-columns:1fr;
gap:22px}
.report-zoom img{max-height:440px}
}

@media print{.report-lightbox,.report-zoom-hint,.report-print,nav.toc{display:none!important}
.report-zoom{border:0}
.report-story,.report-evidence{break-inside:avoid}
.report-zoom img{max-height:350px}
.report-detail-body{overflow:visible}
}

"""

_REPORT_SCRIPT = """
(()=>{
const dialog=document.querySelector('.report-lightbox');
if(!dialog||typeof dialog.showModal!=='function')return;
const preview=dialog.querySelector('img');
const caption=dialog.querySelector('.report-lightbox-title');
document.querySelectorAll('.report-zoom-hint').forEach(hint=>hint.hidden=false);
document.addEventListener('click',event=>{
  const trigger=event.target.closest('.report-zoom');
  if(!trigger)return;
  const source=trigger.querySelector('img');
  preview.src=source.src;preview.alt=source.alt;caption.textContent=source.alt;
  dialog.showModal();
});
dialog.querySelector('button').addEventListener('click',()=>dialog.close());
dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close()});
let collapsed=[];
window.addEventListener('beforeprint',()=>{
  collapsed=[...document.querySelectorAll('details')].filter(detail=>!detail.open);
  collapsed.forEach(detail=>detail.open=true);
});
window.addEventListener('afterprint',()=>{
  collapsed.forEach(detail=>detail.open=false);collapsed=[];
});
})();
"""


def report_enhancements(document: str) -> str:
    """为完整汇报 HTML 加入离线样式、大图和打印增强。

    Args:
        document: 由 page() 或项目生成器产生的完整 HTML。

    Returns:
        移除在线字体链接并注入一次交互组件的完整 HTML。

    Raises:
        ValueError: 输入缺少完整 HTML 的 head/body 结束标签。
    """
    if not re.search(r"</head\s*>", document, re.I) or not re.search(r"</body\s*>", document, re.I):
        raise ValueError("需要包含 head 和 body 的完整 HTML")
    if 'id="readable-report-enhancements"' in document:
        return document
    document = re.sub(
        r'<link\b[^>]*href=[\'"]https://fonts\.(?:googleapis|gstatic)\.com[^>]*>',
        "",
        document,
        flags=re.I,
    )
    document = re.sub(
        r"</head\s*>",
        lambda _: f'<style id="readable-report-enhancements">{_REPORT_STYLE}</style></head>',
        document,
        count=1,
        flags=re.I,
    )
    lightbox = (
        '<dialog class="report-lightbox" aria-label="图片大图">'
        '<div class="report-lightbox-bar"><span class="report-lightbox-title"></span>'
        '<button type="button" autofocus>关闭</button></div><img alt=""></dialog>'
    )
    return re.sub(
        r"</body\s*>",
        lambda _: f"{lightbox}<script>{_REPORT_SCRIPT}</script></body>",
        document,
        count=1,
        flags=re.I,
    )
