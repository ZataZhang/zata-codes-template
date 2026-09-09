# 发布文章到公众号

把 Markdown 长文转成可直接粘贴进公众号后台编辑器的 HTML，并保证排版有视觉重点。

## 何时使用

用户要求「发公众号」「出公众号版」「排版成公众号文章」时使用。本流程只做排版与转换，不改动文章正文内容。

## 前置条件

- `pandoc`（macOS：`brew install pandoc`）
- 视觉验证（可选但推荐）：本机装有 Chrome，用无头模式截图检查排版

## 工作流程

1. **准备构建目录**。把 `assets/gzh_build/` 复制到文章所在文件夹（与文章 md 同级），得到：

   ```
   文章文件夹/
   ├── 文章.md
   └── gzh_build/
       ├── build.sh      # 构建脚本
       ├── decorate.py   # 后处理：装饰实体化 + 外链转纯文本
       └── style.html    # 排版主题（微信绿风格）
   ```

2. **配置关键句高亮（可选）**。公众号文章需要视觉重点。挑选 8～15 处金句（核心判断、转折句、结论句），在 `gzh_build/` 下新建 `<文章名>.highlights.sed`，每行一条规则：

   ```
   s/要高亮的原句/==&==/
   s/^独占一行的短句。$/==&==/
   ```

   `==文字==` 是 pandoc 的 mark 语法，会渲染成荧光笔高亮。注意长句优先于短句放前面，避免子串误伤；独占一行的短句用 `^$` 锚定，防止匹配到长句内部。

3. **构建**。在文章文件夹执行：

   ```bash
   ./gzh_build/build.sh 文章文件名（不带 .md）
   ```

   生成 `文章文件名_公众号版.html`。脚本自动取 md 首行 H1 作为标题（并从正文剔除，避免重复），应用高亮规则，用 pandoc（`-f markdown+mark`）转换并注入样式，最后由 `decorate.py` 做后处理：把标题装饰（h1 渐变线、h2 两侧菱形、h3 小方块）从 CSS 伪元素实体化为真实节点；整段都是链接的资料来源列表逐条拆成独立左对齐段落（微信阅读器默认两端对齐，短行会被拉成稀疏大字）；正文内联链接转成「锚文本 + 绿色上标编号」，URL 收口到文末「参考资料」。伪元素和 href 在「浏览器复制 → 粘贴进公众号编辑器」时都会丢，实体化后手动粘贴和 API 推送两条路径结果一致。

4. **视觉验证**。用无头 Chrome 截图检查，重点看标题装饰线、二级标题荧光底色、高亮句、表格表头、图片图注是否正常：

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless=new --disable-gpu --hide-scrollbars \
     --window-size=800,13000 --screenshot=/tmp/gzh_preview.png \
     "file://$PWD/文章文件名_公众号版.html"
   ```

   页面被登录弹窗或推广弹窗遮挡时，可用 Chrome DevTools Protocol 加载页面后先执行 JS 移除遮罩元素（fixed 定位 + 高 z-index + 全屏尺寸）再截图。

## 主题说明

`style.html` 的当前风格：正文 677px / 16px / 1.9 倍行距；标题带绿色渐变装饰线；二级标题居中加粗绿字、两侧绿色菱形；三级标题带绿色小方块；`<mark>` 黄色荧光高亮；引用为绿色左边条卡片；表格绿色表头白字 + 圆角 + 斑马纹；图片圆角带阴影；资料来源逐条左对齐灰色小字；正文内联链接为微信蓝锚文本 + 绿色上标编号，URL 收口到文末「参考资料」。

改风格只动 `style.html`，不动脚本。

## 动图素材：多张截图合成 GIF

演示类文章（如 Agent 跑完一个完整任务）适合把几张过程截图合成一张循环 GIF，比并排贴静态图省版面、叙事感更强。用 `make_demo_gif.py`：

```bash
python3 gzh_build/make_demo_gif.py image/xx/示例_主题.gif \
  截图1.png "① 首页选入口，交代任务" \
  截图2.png "② 它先确认方向再开工" \
  截图3.png "③ 交付飞书文档和本地文件"
```

每张截图一帧：统一缩放到 `--width`（默认 1400px），底部加深色说明条（白字，手动用「①②③」编号标步骤，不需要说明则该帧 caption 传 `""`），普通帧停 `--duration`（默认 2500ms），末帧停 `--last`（默认 4200ms，让读者看清交付结果），无限循环。3 帧 1400px 截图约 0.5MB，远低于公众号 10MB 动图限制。依赖本机 PIL 和中文字体（macOS 自动回退 Hiragino Sans GB / PingFang / STHeiti）。生成脚本调用示例见 `gzh_build/make_demo_gif_02.py` 式的单文章专用脚本——文章内容变化大时，把具体帧和说明文字固化成单独脚本，方便重跑。

合成用的原始帧截图先归档到图片目录的 `raw/` 子文件夹（规范见 web-images.md「原始素材归档」），专用脚本直接引用 `raw/` 路径；涉及手机号等隐私的遮蔽也写在脚本里，每次从原图重做（参考 `make_demo_gif_03.py`）。桌面横图和手机竖图混排时不能各帧统一铺满宽度——GIF 各帧共享一张画布，要按「等比缩放、居中放入固定画布」处理，参考 `make_demo_gif_03.py`。

## 公众号平台的硬限制（必须告知用户）

- **图片不会随粘贴带过去**。HTML 里的本地图片粘贴后是空位，需在公众号编辑器里逐张重新上传。
- **正文外链不可点**。订阅号正文里的外部链接会被剥成纯文字，唯一可点的外链位置是「阅读原文」。`decorate.py` 已在构建期处理：资料来源列表逐条拆成「标题（URL）」纯文本段落，正文内联链接转成上标编号并在文末附上 URL，读者可以复制地址。
- **高级 CSS 可能部分被剥**。荧光渐变、阴影等效果粘贴后多数保留，个别会丢，属正常现象。标题装饰（菱形、小方块、渐变线）已在构建期实体化为真实节点，粘贴后保留；列表序号的绿色（`::marker`）会丢，属可接受的损失。
- **发布前必须预览**。粘贴完成后用公众号后台「预览」发到自己微信，确认图片位置和表格显示无误再群发。

### 草稿 API 推送的额外限制（2026-09-08 实测）

手动粘贴进编辑器时，大部分 CSS 效果能保留；但通过 `draft/add` API 推送时，微信服务端会对 HTML 做更激进的过滤。以下问题均已在实际推送中复现：

- **CSS 自定义属性（`var(--xxx)`）会被完全丢弃**。元素引用 `color: var(--red)` 会变成无色（继承父元素默认值）。解决方案：推送前把所有 `var(--xxx)` 替换为硬编码颜色值，或者在 HTML 中完全不使用 CSS 变量。一条命令批量替换：

  ```python
  replacements = {
      'var(--red)': '#e2483d',
      'var(--dark)': '#1f2228',
      # ... 按项目实际变量替换
  }
  for k, v in replacements.items():
      html = html.replace(k, v)
  ```

- **外部 `<script>` 会被剥离**。Mermaid.js、KaTeX.js 等所有 CDN 引入的脚本都会被移除，依赖 JS 渲染的图表（Mermaid 流程图、时序图、代码高亮）全部失效，变成纯文本。解决方案：推送前把 Mermaid div 替换为纯 HTML/CSS 示意图（用 div + border + flex 布局模拟节点和箭头），或用后端渲染成 SVG/PNG 图片再上传。
- **`<style>` 标签整体被忽略**。API 推送时微信不会解析 `<style>` 标签，所有样式必须通过 `push_draft.py` 的内联逻辑（把 CSS 规则合并到每个标签的 `style` 属性）才能生效。自定义 HTML（非 pandoc 生成）如果依赖 `<style>` 里的类选择器，推送后样式全丢。解决方案：自定义 HTML 的每个元素都直接写内联 `style`，或确保 `push_draft.py` 能正确解析并内联。
- **深色/渐变背景可能被过滤**。`background-color: #1f2228` 等深色背景在内联样式中多数能保留，但渐变 `linear-gradient` 会被降级为纯色或丢失。卡片式深色代码块（用 `background-color` 而非渐变）可以正常显示。
- **HTML 末尾的「资料来源」区块**。如果源 HTML 已有手写的资料来源列表，`push_draft.py` 会把正文中的 `<a>` 标签收口为上标编号 + 文末列表，但源 HTML 里的手写资料来源区会和自动追加的「参考资料」标题重复。`push_draft.py` 已修复：检测到已有「资料来源」或「参考资料」标题时，只追加编号列表不再重复标题。
- **角标标注**。正文内联链接会被替换为「锚文本 + 绿色上标角标 `[编号]`」，角标样式为 13px 粗体绿色 `#07c160`，`vertical-align:super`。角标紧跟在对应句末，读者点正文无法跳转，只能看文末 URL 复制。这是微信平台限制，不是工具 bug。
- **推送前建议先用小号或文件传输助手预览**。草稿箱里的 HTML 和实际群发效果可能有差异，以手机端预览为准。

### 流程图 / 架构图在公众号中的兼容写法

Mermaid、Draw.io、SVG 图片（部分公众号编辑器）在 API 推送时都不可靠。最稳的做法是用纯 HTML + 内联样式模拟流程图。经过多轮实测，以下是**微信草稿 API 唯一可靠的写法**：

**外层容器：单个 `<div>` + 纯色 `background`**（不要用 `<table>`）

- `<table>` 的多行布局会被微信编辑器在行与行之间插入白缝（`border-collapse` 被忽略），视觉上碎裂成一条条。
- `<div>` + `background:#1f2228` + `padding` + `text-align:center` 是最安全的容器。
- 不要用 `border-radius`（会被剥），也不要用 `flex` / `gap`（会被剥）。

**行内节点：`<span>` + `display:inline-block` + 纯色背景**

- 多个节点横排用 `<span style="display:inline-block;background:#2d3038;padding:6px 12px;margin:2px">节点文字</span>`，中间用空格分隔。
- `display:inline-block` 在微信中稳定支持，`float` 和 `flex` 不行。
- 背景色用十六进制 `#2d3038`，不要用 `rgba()`（部分客户端会丢）。

**箭头：纯文字 `↓` 或 `→` + 红色 `color:#e2483d`**

- 不要用 SVG 箭头或图片，直接文字箭头即可。

**完整模板**：

```html
<div style="background:#1f2228;margin:26px 0 30px;font-size:14px;color:#e7e9ee;line-height:2.2;padding:20px 16px;text-align:center">
  <div style="color:#8f95a3;font-size:12px;letter-spacing:2px;margin-bottom:8px">WORKFLOW</div>
  <div>起点</div>
  <div style="color:#e2483d;font-size:16px;line-height:1.4">↓</div>
  <div>中间步骤</div>
  <div style="color:#e2483d;font-size:16px;line-height:1.4">↓</div>
  <div>
    <span style="background:#2d3038;padding:6px 12px;font-size:13px;margin:2px;display:inline-block">节点 A</span>
    <span style="background:#2d3038;padding:6px 12px;font-size:13px;margin:2px;display:inline-block">节点 B</span>
    <span style="background:#2d3038;padding:6px 12px;font-size:13px;margin:2px;display:inline-block">节点 C</span>
  </div>
  <div style="color:#e2483d;font-size:16px;line-height:1.4">↓</div>
  <div>终点</div>
</div>
```

**禁止使用的属性**（会被微信 API 剥掉或渲染异常）：`display:flex`、`gap`、`border-radius`、`rgba()` 颜色、`<table>` 多行流程图布局、`float`、`position`。

**推荐做法：流程图用图片，不用 HTML**。

HTML 模拟流程图在草稿 API 中即使通过 `push_draft.py` 的内联处理，微信服务端仍可能剥掉 `<div>` 的 `background` 属性，导致流程图变成无色纯文字。最可靠的做法是用 PIL 生成 PNG 流程图，通过 `<img>` 上传——微信对图片的兼容性最好，颜色、圆角、间距全部保留。

流程图生成脚本参考（PIL，深色主题，卡片式布局）：

```python
from PIL import Image, ImageDraw, ImageFont

W = 1400
bg = (28, 30, 36)       # 深色底
card = (52, 56, 66)     # 卡片色
border = (68, 72, 84)   # 卡片描边
text = (235, 236, 240)
muted = (120, 126, 140)
red = (232, 76, 61)     # 箭头色

img = Image.new('RGB', (W, 580), bg)
d = ImageDraw.Draw(img)

def font(size, bold=False):
    for p in ['/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc']:
        try:
            return ImageFont.truetype(p, size, index=1 if bold else 0)
        except: pass
    return ImageFont.load_default()

f_step = font(30, bold=True)   # 步骤文字
f_card = font(26, bold=True)   # 节点卡片
f_label = font(14)             # WORKFLOW 小标签

def draw_step(text, y):
    tw = d.textlength(text, font=f_step)
    x = (W - tw - 48) / 2
    d.rounded_rectangle([x, y, x+tw+48, y+64], radius=16, fill=card, outline=border, width=1)
    d.text(((W-tw)/2, y+14), text, fill=text, font=f_step)

def draw_arrow(y):
    cx = W // 2
    d.line([(cx, y), (cx, y+26)], fill=red, width=3)
    d.polygon([(cx-8, y+24), (cx+8, y+24), (cx, y+38)], fill=red)

# 画法和尺寸根据实际内容调整
```

生成后放在文章 `image/` 目录下，HTML 里用 `<img src="image/xx/workflow.png" alt="...">` 引用，`push_draft.py` 会自动上传到微信图床。PIL 生成流程图时不要用 emoji（macOS 系统字体在 PIL 中显示为方框）。

## 自动化：直接推送草稿（可选）

配置好公众号开发者凭证后，可以跳过手动粘贴，一条命令把文章送进草稿箱。

### 配置

凭证二选一，推荐环境变量（一次配置，所有文章的 `gzh_build/` 副本通用）：

```bash
# 写进 ~/.zshrc，GZH_ 前缀辨识度高
export GZH_APPID=公众号的AppID
export GZH_APPSECRET=公众号的AppSecret
```

或者在 `gzh_build/.env` 中填写（`.env` 不进 git）：

```
APPID=公众号的AppID
APPSECRET=公众号的AppSecret
```

脚本读取顺序：`GZH_APPID`/`GZH_APPSECRET` 环境变量 → `.env` 的 `APPID`/`APPSECRET`。

- AppSecret 在公众号后台「设置与开发 → 基本配置」点「重置」获取，只显示一次，仅管理员可操作
- 同一页面配置 IP 白名单，要填**微信实际看到的出口 IP**：本地有代理分流时，微信 API 通常走直连，出口 IP 和浏览器查到的可能不同；以接口报错 `40164 invalid ip <真实IP>` 里的地址为准
- 动态 IP 变化后接口会报 40164，重新查并更新白名单

### 使用

```bash
./gzh_build/publish.sh 文章文件名
```

串联两步：先跑 build.sh 生成公众号版 HTML，再由 `push_draft.py` 完成样式内联（`<style>` 里的规则合并到每个标签的 `style` 属性，因为草稿接口不接受样式表）、正文图片逐张上传微信图床并替换 src、首图上传为封面素材，最后调 `draft/add` 创建草稿。草稿出现在公众号后台草稿箱，手机预览确认后手动发布。

### 自定义 HTML（非 pandoc 生成）

如果文章需要精细排版（杂志风、卡片式布局），可以手写 HTML 而不是走 pandoc 流程。此时 `_公众号版.html` 就是实际推送源，必须和源 HTML 完全一致：

1. 手写的 HTML 直接命名为 `文章名.html`，确认内容、样式和流程图都通过微信兼容检查（见上文限制清单）。
2. 把手写的 HTML 复制为 `文章名_公众号版.html`，作为 `push_draft.py` 的输入文件。浏览器打开这个文件看到的排版，就是推送后在手机上看到的效果（因为所有样式都是内联的，没有 `<style>` 和 `<script>`）。
3. 推送命令：`python3 gzh_build/push_draft.py 文章名_公众号版.html 文章名.md`

**核心原则**：`_公众号版.html` 必须忠实反映推送后的效果。用户在浏览器预览这个文件，看到的颜色、卡片、流程图就是草稿箱里的样子。如果预览和实际推送不一致，说明 HTML 里有微信不兼容的属性（var、flex、border-radius 等），需要修。

### API 版本与手动粘贴版的差异

- 草稿接口的标签白名单比编辑器粘贴更严格：`<mark>` 和 `<blockquote>` 会被剥掉，`push_draft.py` 已做适配（mark 转 span + 纯色背景，blockquote 转 section 卡片）；渐变背景也会被过滤，统一降级为纯色
- 标题装饰（h2 菱形、h3 小方块、h1 渐变线）已由 `decorate.py` 在构建期实体化为真实节点，API 版本和手动粘贴一致保留；只有列表序号的 `::marker` 变色无法内联会丢。`push_draft.py` 会检测 h2 里是否已有菱形，避免重复添加
- 标题风格：二级标题居中、19px 加粗绿字、两侧绿色菱形点缀（参考新智元的居中标题路线，比左对齐更醒目）；装饰用文本符号「◆」而非图片，草稿接口友好
- 文章开头加品牌 GIF：现成的品牌动画在 `assets/brand/开头动画.gif`（「Zata山外志」，打字机逐字出现 + 光标闪烁，右侧节点网络漂移），直接复制到文章图片目录、在 H1 标题下一行引用即可，不用每次重新生成；需要改文字或样式时才用 `make_brand_gif.py 输出.gif [左文字] [右文字]` 生成变体（依赖本机 PIL 和中文字体）。封面自动取第一张**非 GIF** 的静态图，避免 GIF 首帧空白
- 封面用 `make_cover.py 输出.png 标题 [副标题] [角标]` 生成排版式封面（900×383）：深色渐变底 + 左侧标题区 + 右侧把文章核心概念图形化（对比类文章画「多个产品节点连向中心『你』」，节点用品牌色，在 PRODUCTS 列表里改）；命名为 `封面.png` 放到文章图片目录后，`push_draft.py` 会优先用它做封面
- figure/figcaption 会被转换成居中段 + 图注段，兼容性更好
- 外链会被剥成纯文字（订阅号正文不支持外链）；`push_draft.py` 把正文 `[文字](url)` 转成「锚文本 + 绿色小上标编号」，所有 URL 按出现顺序收口到文末「参考资料」编号列表（正文不再出现小字 URL）。如需一个可点击入口，可通过草稿的 `content_source_url` 字段设置「阅读原文」链接（只能放一个）
- 图注约定：图片下一行单独写 `*▲ 说明文字。图：来源*`，API 版由 `push_draft.py` 识别 ▲ 前缀渲染为 13px 灰色居中小字；粘贴版靠 `p:has(> em:only-child)` 样式实现同样效果
- 发布动作（`freepublish/submit`）刻意不自动化，保留人工确认环节

## 交付时说明

交付 HTML 后，向用户简要说明：文件位置、粘贴步骤（浏览器打开 → 全选复制 → 粘贴进编辑器）、需要手动补传哪些图片、以及建议的标题/摘要/封面。
