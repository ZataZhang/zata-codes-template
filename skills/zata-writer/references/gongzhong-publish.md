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
       ├── decorate.py   # 后处理：装饰实体化 + 外链转纯文本 + 插品牌动画
       ├── style.html    # 排版主题（微信绿风格）
       ├── copy.sh       # 手动粘贴：重建 + 生成剪贴板版并复制
       └── publish.sh    # API 推送草稿（需开发者凭证）
   ```

   同时把 `assets/brand/开头动画.gif` 复制到文章图片目录（`assets/` 或 `image/`，跟正文其他图放一起）。这是文章开头的品牌动画，**不要在 md 里手写引用**——公众号版的 `decorate.py` 会自动把它插到标题块下面，网页版则完全不插（网页版封面已有 kicker 和落款，正文里再来一遍是重复）。没放 GIF 时脚本会跳过并打印提示，不会产出坏图。

2. **构建前检查源 md**。两条路径（手动粘贴 / API 推送）都不会渲染 mermaid，来源组织也有约定，构建前先处理好：

   - **源 md 里不残留 mermaid 代码块**。粘贴路径下 pandoc 只会把它输出成普通代码块，读者看到的是源码；API 路径下脚本被剥、直接变纯文本。构建前先画成 PNG 流程图，在 md 里替换为图片引用 + 图注，保证 md 和 HTML 渲染一致。画法参考下文「流程图 / 架构图在公众号中的兼容写法」里的 PIL 脚本模板；各文章实际使用的定制脚本（`make_flow_02.py`、`make_flow_04.py` 这类）沉淀在文章项目自己的 `gzh_build/` 里，不在本 skill 的 assets 中。
   - **来源链接内联在正文，不在文末手写列表**。引用一律写成 `[锚文本](url)` 放在对应事实处，`decorate.py` 会自动转成「锚文本 + 上标编号」并把 URL 收口到文末唯一的「参考资料」。锚文本要能脱离正文独立读懂——它就是参考资料列表的条目名，写「标准模式生成速度同比提升约 100%」，不要只写「100%」。文末手写「资料来源」列表在粘贴路径不会被去重，会和自动追加的「参考资料」并存成两套（2026-09-09 实测踩坑）。

3. **配置关键句高亮（可选）**。公众号文章需要视觉重点。挑选 8～15 处金句（核心判断、转折句、结论句），在 `gzh_build/` 下新建 `<文章名>.highlights.sed`，每行一条规则：

   ```
   s/要高亮的原句/==&==/
   s/^独占一行的短句。$/==&==/
   ```

   `==文字==` 是 pandoc 的 mark 语法，会渲染成荧光笔高亮。注意长句优先于短句放前面，避免子串误伤；独占一行的短句用 `^$` 锚定，防止匹配到长句内部。

4. **构建**。在文章文件夹执行：

   ```bash
   ./gzh_build/build.sh 文章文件名（不带 .md）
   ```

   生成 `文章文件名_公众号版.html`。脚本自动取 md 首行 H1 作为标题（并从正文剔除，避免重复），应用高亮规则，用 pandoc（`-f markdown+mark`）转换并注入样式，最后由 `decorate.py` 做后处理：把标题装饰（h1 渐变线、h2 两侧菱形、h3 小方块）从 CSS 伪元素实体化为真实节点；整段都是链接的资料来源列表逐条拆成独立左对齐段落（微信阅读器默认两端对齐，短行会被拉成稀疏大字）；正文内联的 http(s) 链接（含 `<https://…>` 自动链接和带标题的链接）转成「锚文本 + 绿色上标编号」，URL 收口到文末「参考资料」；在标题块下面插入品牌动画 GIF。伪元素和 href 在「浏览器复制 → 粘贴进公众号编辑器」时都会丢，实体化后手动粘贴和 API 推送两条路径结果一致。

   注意：`_公众号版.html` 是构建中间产物，里面仍保留原生 `<ol>`/`<ul>`。**列表降级为「文字序号 + 普通段落」发生在发布阶段**：手动粘贴（`copy.sh`）和 API 推送（`publish.sh`）都经过 `push_draft.py` 的 `build_wechat_body()`，真正进编辑器的是这一步的产物（手动粘贴路径留档为 `_剪贴板版.html`）。浏览器里看 `_公众号版.html` 带原生列表，不代表发布效果；也不要从浏览器直接复制它去粘贴，那条路不经过列表降级，列表会被公众号打散。

5. **视觉验证**。截图要看真正进编辑器的 `_剪贴板版.html`，而不是 `_公众号版.html`。先只生成文件（`--no-copy` 不动剪贴板）：

   ```bash
   ./gzh_build/copy.sh 文章文件名 --no-copy
   ```

   再用无头 Chrome 截图，重点看正文开头的品牌动画、二级标题装饰、高亮句、列表序号与缩进（含列表后的段距）、表格表头、图片图注是否正常，流程图必须是渲染后的图片而非代码块，文末「参考资料」只有一份且与正文上标编号一一对应。文章标题走编辑器的标题栏、不在正文里，截图里没有标题块是正常的：

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless=new --disable-gpu --hide-scrollbars \
     --window-size=800,13000 --screenshot=/tmp/gzh_preview.png \
     "file://$PWD/文章文件名_剪贴板版.html"
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

合成用的原始帧截图先完成隐私打码、再归档到图片目录的 `raw/` 子文件夹（打码规范见 web-images.md「隐私打码」——raw/ 会随仓库留存，别把未打码原图留在里面），专用脚本直接引用 `raw/` 路径。桌面横图和手机竖图混排时不能各帧统一铺满宽度——GIF 各帧共享一张画布，要按「等比缩放、居中放入固定画布」处理，参考 `make_demo_gif_03.py`。

专用脚本的价值在迭代：用户会往已成稿的 GIF 里插帧、改 raw/ 里的标注文字、换个别帧——脚本每次从 `raw/` 重读重跑，这些改动零成本。注意两点：

- **插入中间帧要全序列重新编号**：说明条里的「①②③」是手动写的，在第 2 帧后插入新帧，后面所有帧的编号、`DUR` 数组都要跟着改；
- **抽帧验证的坑**：从一个 GIF 里导出多帧核对时，只能 `Image.open` 一次然后循环 `seek(i)`——在循环里重新打开文件会永远停在第 0 帧。

## 卡通插画封面：AI 底图 + PIL 叠字（2026-09-10 实测）

想要人物出镜、风格轻松的封面时，走「AI 生成卡通底图 + PIL 叠加文字」两步路线，脚本 `make_cover_cartoon.py`。不让生图模型直接画字：中文渲染极不可靠（错字、乱码），底图必须无字，标题由 PIL 画出，字号、颜色、位置全部可控。

**人物设定**：品牌人物参考图在 `assets/brand/人物设定.png`（动漫风年轻男性：黑色蓬松卷发、黑框眼镜、白衬衫挽袖、托腮思考或抱笔记本）。生图工具只接受文字提示词、不能传参考图，人物一致性靠把设定写成英文描述放进 prompt，可直接复用：

> young man with messy fluffy dark wavy hair and black rectangular glasses, wearing a white button-up shirt with rolled-up sleeves, calm friendly smile, thinking pose with hand on chin or holding a slim laptop, modern anime-influenced flat cartoon illustration, clean lines, soft cel shading

**流程**：

1. **生成底图**（2560×1080，约 2.35:1）。prompt 模板，`<角色描述>` 用上面的片段，场景按文章主题替换：

   ```text
   Flat vector cartoon illustration, wide horizontal banner. Right two-thirds:
   <角色描述> at a desk, <场景：人物在做什么、周围漂浮/摆放什么元素>, connected by
   thin curved lines. The left third of the image is calm and almost empty with
   only very subtle soft shapes, reserved as clear space for text overlay. Soft
   pastel background, warm cream fading to light sky blue, light green (#07C160)
   accents, soft rounded shapes, gentle shadows. Absolutely no text, no letters,
   no numbers, no logos, no watermark.
   ```

   「左侧三分之一留白」和「无文字」两条必须保留：前者给标题区，后者规避中文渲染翻车。生成后记下右下角「AI 生成」水印的像素坐标（看图工具量）。

2. **合成封面**：

   ```bash
   python3 gzh_build/make_cover_cartoon.py 底图.png assets/封面.png \
     "标题行1|标题行2" "副标题" "角标" --watermark X0,Y0,X1,Y1
   ```

   脚本自动完成：水印修补（用水印左侧同行背景平移覆盖 + 高斯模糊抹匀）→ 中心裁切 2.35:1 → 缩放 900×383 → 左侧叠角标、最多两行标题、副标题、品牌落款。底图整体偏深时加 `--light` 换浅色文字。副标题、角标、水印参数都可省略。生成后目检：水印是否抹净、文字有没有压到底图主体。

3. **投入使用**：输出命名为 `封面.png` 放进文章图片目录，`push_draft.py` 会优先用它做封面。底图原图留在文章的 `gzh_build/` 里，改标题文案时直接重跑第 2 步，不用重新生图。

## 数据对比图：SVG 作者稿 → PNG

正文里出现对比性数据（份额、金额、倍数、排名）时，默认出一张数据图，并在**提纲阶段**就规划好——图和正文同步产出，不要正文写完再补。做法与流程图一致：**SVG 只当源文件，入稿一律用 PNG**，因为微信会剥掉内联 `<svg>`。

流程：

1. **脚本化生成 SVG**。数据驱动，用 Python 写入 `assets/图N_*.svg`（1600×900，与文章其他自绘图同风格：白底、`PingFang SC`、标题 32px 居中、脚注注明数据来源）。脚本沉淀在文章的 `gzh_build/make_*.py`，改数据或配色重跑即可，不手工改 SVG。
2. **光栅化到 2×**：

   ```bash
   "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
     --headless=new --disable-gpu --hide-scrollbars \
     --force-device-scale-factor=2 --window-size=1600,900 \
     --default-background-color=FFFFFFFF \
     --screenshot=assets/图N_*.png "file://$PWD/assets/图N_*.svg"
   ```

   产出 3200 宽 PNG，手机上不糊。画布不是 1600×900 时同步改 `--window-size`。
3. **在 md 里按配图格式插入**：短 alt + 独立一行 `*▲ …*` 图注，图注写明数据来源和「图：本文绘制」。

取向与实测坑（2026-10-06）：

- **优先构成条、直接标注**。对比「份额转移」用两期堆叠条（同一套配色、同一根尺子，一眼看出谁涨谁跌）；对比两三个数值用直接标注的柱（值写在柱上，不靠坐标轴估读）。**不要交默认的交叉折线图**——三条线加网格线是「Excel 味」，信息密度和观感都差，会被直接打回。
- 标签会和图例/刻度抢位：年份、图例、数值标签落在同一水平线上会叠字。画之前先把它们分层（如年份放条上方、图例另起一行）。
- 横向柱的绘制函数如果复用固定的 `y`，多条柱会画在同一位置互相覆盖；每条柱必须独立传 `y`。
- 画布高度要贴合内容，底部留白会把图片撑高，在手机文章里白占一屏。
- 堆叠条两端要用 `clipPath` 收圆角，否则只能得到直角。
- 脚本里的数值要和正文口径一致；改正文数字时同步改脚本重跑，别只改一处。

## 公众号平台的硬限制（必须告知用户）

- **本地图片要转存到微信**，做法按发布路径不同：
  - `copy.sh` 手动粘贴：剪贴板版把本地图片转成 base64 内嵌，粘贴后由编辑器转存。逐张确认图片都已显示、开头的品牌动画 GIF 仍在动，没转存成功的再手动补传。
  - `publish.sh` API 推送：正文图片已由接口逐张上传到微信图床并替换地址，不用补传。
  - 从浏览器直接复制 `_公众号版.html`（不推荐）：本地图片粘贴后是空位，只能在编辑器里逐张重新上传。
- **正文外链不可点**。订阅号正文里的外部链接会被剥成纯文字，唯一可点的外链位置是「阅读原文」。`decorate.py` 已在构建期处理：资料来源列表逐条拆成「标题（URL）」纯文本段落，正文内联链接转成上标编号并在文末附上 URL，读者可以复制地址。
- **高级 CSS 可能部分被剥**。荧光渐变、阴影等效果粘贴后多数保留，个别会丢，属正常现象。标题装饰（菱形、小方块）已在构建期实体化为真实节点，粘贴后保留。
- **原生列表（`<ol>`/`<ul>`）会被打散**。公众号编辑器和草稿接口都不认原生有序/无序列表：粘贴或推送后，`<li>` 的序号会和内容被拆成两行、空行处还会多出空序号。两条发布路径共用的 `build_wechat_body()`（`push_draft.py`）已在转换期用 `flatten_lists()` 把列表降级为**「文字序号 + 普通段落」**：有序用绿色粗体 `1. `，无序用绿色 `•`，`text-indent` 做悬挂缩进；嵌套列表逐级加深缩进，一项里的续段和引用块与正文对齐，列表结束处补回正常段距。微信只当普通段落处理。md 里照常写 `1.` / `-` 列表即可，不需要手工改；但不要从浏览器直接复制 `_公众号版.html`，那条路不经过降级。
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
- **HTML 末尾的「资料来源」区块**。`build_wechat_body()` 会把所有 http(s) `<a>` 收口为上标编号 + 文末「参考资料」，但不识别手写的资料来源区：自定义 HTML 末尾手写的来源列表如果也用 `<a>`，这些链接会被再编号一遍，和自动追加的「参考资料」重复。自定义 HTML 只在正文里写 `<a>`，不手写来源区；确实要保留手写来源区时，URL 写成纯文本，不包 `<a>`。
- **角标标注**。正文内联链接会被替换为「锚文本 + 绿色上标角标 `[编号]`」，角标样式为 11px 绿色 `#07c160`，`vertical-align:super`。角标紧跟在对应句末，读者点正文无法跳转，只能看文末 URL 复制。这是微信平台限制，不是工具 bug。
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

串联两步：先跑 build.sh 生成公众号版 HTML，再由 `push_draft.py` 的 `build_wechat_body()` 完成样式内联（`<style>` 里的规则合并到每个标签的 `style` 属性，因为草稿接口不接受样式表）、标签兼容转换、列表与 figure 降级、残留外链收口（这条转换链与手动粘贴路径共用），然后把正文图片逐张上传微信图床并替换 src、首图上传为封面素材，最后调 `draft/add` 创建草稿。草稿出现在公众号后台草稿箱，手机预览确认后手动发布。

### 手动粘贴：一键复制到剪贴板（无需凭证）

没有开发者凭证、或想手动排版时，在文章文件夹执行：

```bash
./gzh_build/copy.sh 文章文件名
```

它先跑 build.sh 重建公众号版（避免用到过期的 HTML），再由 `to_clipboard.py` 处理并放进系统剪贴板（osascript，仅 macOS），然后去公众号后台编辑器 `Cmd+V`。处理走的是和 API 路径同一个 `build_wechat_body()`，所以粘出来的排版和草稿箱一致；额外把本地图片转成 base64 内嵌，粘贴后由编辑器转存，要逐张确认（见「公众号平台的硬限制」的图片一条）。处理结果留档为 `文章名_剪贴板版.html`，脚本会打印剪贴板内容类型。

加 `--no-copy` 只写 `_剪贴板版.html`、不动剪贴板：截图验证（工作流程第 5 步）和改稿后重建派生文件时都用它，免得覆盖用户剪贴板里的内容。

### 自定义 HTML（非 pandoc 生成）

如果文章需要精细排版（杂志风、卡片式布局），可以手写 HTML 而不是走 pandoc 流程。此时 `_公众号版.html` 就是实际推送源，必须和源 HTML 完全一致：

1. 手写的 HTML 直接命名为 `文章名.html`，确认内容、样式和流程图都通过微信兼容检查（见上文限制清单）。
2. 把手写的 HTML 复制为 `文章名_公众号版.html`，作为 `push_draft.py` 的输入文件。浏览器打开这个文件看到的排版，就是推送后在手机上看到的效果（因为所有样式都是内联的，没有 `<style>` 和 `<script>`）。
3. 推送命令：`python3 gzh_build/push_draft.py 文章名_公众号版.html 文章名.md`
4. 手动粘贴直接运行 `python3 gzh_build/to_clipboard.py 文章名`。不要用 `copy.sh` 或 `publish.sh`：它们会先跑 build.sh 从 md 重建，覆盖手写的 `_公众号版.html`；没有 md 时则直接报错。

**核心原则**：`_公众号版.html` 必须忠实反映推送后的效果。用户在浏览器预览这个文件，看到的颜色、卡片、流程图就是草稿箱里的样子。如果预览和实际推送不一致，说明 HTML 里有微信不兼容的属性（var、flex、border-radius 等），需要修。唯一的预期差异是原生列表：推送时会被降级成文字序号段落（见「公众号平台的硬限制」）。

### API 版本与手动粘贴版的差异

- 草稿接口的标签白名单比编辑器粘贴更严格：`<mark>` 和 `<blockquote>` 会被剥掉，`push_draft.py` 已做适配（mark 转 span + 纯色背景，blockquote 转 section 卡片）；渐变背景也会被过滤，统一降级为纯色
- 标题装饰（h2 菱形、h3 小方块）已由 `decorate.py` 在构建期实体化为真实节点，API 版本和手动粘贴一致保留。`push_draft.py` 会检测 h2 里是否已有菱形，避免重复添加。h1 标题块（含渐变线）不进正文，两条路径的标题都走草稿字段或编辑器的标题栏
- 原生有序/无序列表（`<ol>`/`<ul>`）会被公众号打散（序号与内容分行、空行多出空序号），两条路径共用的 `build_wechat_body()` 在转换期用 `flatten_lists()` 把它们降级为「文字序号 + 普通段落」，序号沿用主题绿 `#07c160`（有序加粗），排版稳定
- 标题风格：二级标题居中、19px 加粗绿字、两侧绿色菱形点缀（参考新智元的居中标题路线，比左对齐更醒目）；装饰用文本符号「◆」而非图片，草稿接口友好
- 文章开头加品牌 GIF：现成的品牌动画在 `assets/brand/开头动画.gif`（「Zata山外志」，打字机逐字出现 + 光标闪烁，右侧节点网络漂移）。**公众号版由 `decorate.py` 在构建期自动插到标题块下面，作者只需要把 GIF 复制到文章图片目录**；需要改文字或样式时才用 `make_brand_gif.py 输出.gif [左文字] [右文字]` 生成变体（依赖本机 PIL 和中文字体），换掉图片目录里那个文件即可。网页版不要这个 GIF（见 web-publish.md）。封面自动取第一张**非 GIF** 的静态图，避免 GIF 首帧空白
- 封面用 `make_cover.py 输出.png 标题 [副标题] [角标]` 生成排版式封面（900×383）：深色渐变底 + 左侧标题区 + 右侧把文章核心概念图形化（对比类文章画「多个产品节点连向中心『你』」，节点用品牌色，在 PRODUCTS 列表里改）；想要人物出镜的轻松风格改走「卡通插画封面」路线（见上文专节，`make_cover_cartoon.py`）；命名为 `封面.png` 放到文章图片目录后，`push_draft.py` 会优先用它做封面
- figure/figcaption 会被转换成居中段 + 图注段，兼容性更好
- 外链会被剥成纯文字（订阅号正文不支持外链）；`decorate.py` 在构建期把正文 http(s) 链接转成「锚文本 + 绿色小上标编号」，所有 URL 按出现顺序收口到文末「参考资料」编号列表（正文不再出现小字 URL）。没经过 `decorate.py` 的链接（如手写 HTML）由 `build_wechat_body()` 兜底做同样的收口，两条发布路径结果一致。如需一个可点击入口，可通过草稿的 `content_source_url` 字段设置「阅读原文」链接（只能放一个）
- 图注约定：图片下一行单独写 `*▲ 说明文字。图：来源*`，两条发布路径都由 `build_wechat_body()` 识别 ▲ 前缀渲染为 13px 灰色居中小字；浏览器预览 `_公众号版.html` 时靠 `p:has(> em:only-child)` 样式实现同样效果
- 摘要由 `push_draft.py` 自动取正文第一段**有文字**的段落（截 110 字）。开头是品牌动画和配图时，前几个 `<p>` 里只有 `<img>`，所以是按「有文字的段」而不是「第一个 `<p>`」取的——不要改回取 `paras[0]`
- 发布动作（`freepublish/submit`）刻意不自动化，保留人工确认环节

## 交付时说明

交付 HTML 后，向用户简要说明：文件位置、粘贴步骤（`./gzh_build/copy.sh 文章文件名` 重建并复制，再到编辑器 `Cmd+V`）、粘贴后逐张确认图片已转存（含开头的品牌动画 GIF，没转存的手动补传；走 `publish.sh` 时图片已由接口上传）、以及建议的标题/摘要/封面。
