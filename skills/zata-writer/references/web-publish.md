# 网页版文章：可分享的单文件 HTML

用户要求「出个网页版」「做一个可以分享的 HTML 长文」「网页文章」时使用本路线。它独立于公众号路线：外链保持可点、图片直接内嵌、整个文章是一个自包含的 HTML 文件，直接发给任何人用浏览器打开即可。2026-09-10 用「三种办公 Agent 怎么选」一文完整实测过。

## 前置条件

- `pandoc`（`brew install pandoc`）
- 无头 Chrome（验证用；macOS 上 `/Applications/Google Chrome.app/.../MacOS/Chrome` 即可，无需额外安装）

## 工作流程

1. 把 `assets/gzh_build/` 整个目录拷贝到文章所在目录（和公众号构建共用目录名，不冲突）。
2. 文章 Markdown 保持普通结构即可：一级标题作文章标题，二级标题进目录，图片用相对路径引用 `image/` 下的本地文件。
3. （可选）荧光高亮：写 `gzh_build/<文章名>.highlights.sed`，每行一条 `s/要高亮的句子/<mark>要高亮的句子<\/mark>/`。句子必须逐字匹配正文。
4. （可选）文章专属封面：写 `gzh_build/hero.html`，放一段内联 SVG（或其他 HTML）。后处理会把它装进封面区。SVG 建议用主题色系（米白底 #fbf7ee、锈红 #a6300e、灰线 #cfc8b6），画抽象示意而非复杂插画。
5. 构建：

   ```bash
   ./gzh_build/build_web.sh 文章名 "Zata 山外志 · 手记" "副标题，可省略"
   ```

   脚本内部：剥掉 H1（避免和封面重复）→ 应用 highlights → `pandoc -f markdown+mark -t html5 -s --toc --toc-depth=2 -H style_web.html` → `postprocess_web.py` 组装封面/目录/正文/资料来源/页脚 → 本地图片转 base64 内联。
6. 无头 Chrome 截图验证（封面、正文、表格、图注、资料来源），再测侧边栏目录（见下）。

## 主题行为（style_web.html + postprocess_web.py）

- 单栏 780px，米白纸感背景（#fbfaf6），衬线标题（Georgia/宋体），无圆角无阴影，媒体报道质感。
- 封面：kicker（顶部小字）+ 大标题 + 锈红短横线 + 可选副标题 + 可选 hero SVG，整体带细边框。
- 目录双形态：窗口 ≥1200px 时显示左侧固定侧边栏（180px，滚动到哪一节就点亮哪一条，当前节为锈红色）；窄窗口时显示正文内的编号目录。
- 编号：正文二级标题自动带 `01/02/…` 编号，图片图注自动带「图 N ·」编号，均由 CSS counter 驱动。
- 「资料来源」标题会自动识别并把该节包进独立的窄栏版式块。
- 所有本地图片转 base64 内联，产出真正的单文件（十张截图约 3MB 量级）。
- 页脚自动写「Zata 山外志 + 当前年份」。

## 实测踩坑（2026-09-10）

- **CSS counter-reset 必须合并成一条声明**。`body { counter-reset: sec; }` 和 `body { counter-reset: fig; }` 两条规则同时存在时，后者会整个覆盖前者（同名属性级覆盖），导致 `sec` 计数器不存在、资料来源节的标题编号从 01 重新数起。正确写法：`body { counter-reset: sec fig; }` 一条搞定。若新增计数器，永远改这一行。
- **侧边栏滚动高亮必须用滚动位置判断，不要用 IntersectionObserver + rootMargin 窄带**。点目录锚点跳转后标题会落在视口最顶端（y≈0），窄带（如 `-15% 0px -70% 0px`）永远罩不住它，高亮不会动。正确做法：监听 scroll/resize，取「`getBoundingClientRect().top <= 160` 的最后一个 h2」为当前节。postprocess_web.py 里的脚本已是这个实现。
- **无头 Chrome 完全不能滚动**（scrollY 恒为 0，scrollIntoView/scrollTo 无效），且滚动后的截图可能整页空白——这是合成器产物，不是页面 bug。验证滚动相关功能用「负 margin 平移 + 派发 resize」：把 `document.body.style.marginTop` 设为 `-(目标元素绝对Y - 目标值)px`，再 `dispatchEvent(new Event('resize'))` 触发高亮更新，然后用 `--dump-dom` grep `data-active`/`active` 和截图确认。
- 锚点 URL 直接打开后截图空白同样是无头环境产物；先确认 dump-dom 里内容完整再下结论。
- 截图命令模板：`"$CHROME" --headless=new --disable-gpu --screenshot=/tmp/x.png --window-size=1210,1800 "file://$PWD/文章_网页版.html"`（1210 宽可测到侧边栏档位，780 宽测窄档）。
