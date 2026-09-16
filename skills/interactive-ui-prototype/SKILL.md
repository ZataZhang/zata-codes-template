---
name: interactive-ui-prototype
description: "[Updated 2026-09-16] Create or revise a connected, clickable, high-fidelity UI prototype grounded in the current repository's real pages, components, routes, and design system. Use when a user wants a 交互原型, 可点击草图, code prototype, multiple UI mockup states connected as a demo, or a visual design that can be reviewed before implementation. Do not use for implementing the production feature itself."
---

# Interactive UI Prototype

把“看起来接近最终产品”和“可以点击演示”放在同一个原型里。先读真实项目，再选择代码原型、图片状态原型或两者混合；不要凭空设计一个与现有产品脱节的新应用。

## Ground the Design in the Repository

1. 找到仓库根目录，读取 `AGENTS.md` 及其要求的相关规范。
2. 检查目标页面、路由、父级布局、现有组件、样式变量、图标和数据契约。若有正在运行的页面，优先从真实入口查看当前界面。
3. 用简短清单锁定要解决的问题、保留的现有结构、需要演示的关键状态，以及原型不承诺实现的部分。
4. 检查目标目录的 `git status` 和已有原型，保留用户改动。盘点能够与新原型衔接的现有页面、状态和入口。默认把产物放在仓库既有原型目录；没有约定时使用 `docs/prototypes/<feature-slug>/`。

不要把图片生成模型对通用后台界面的猜测当成产品事实。页面结构、文案、导航和可用动作应尽量来自真实代码；新设计决策需要能从用户目标解释。

## Choose the Prototype Form

根据主要风险选择形式：

- **Code-native**：交互、布局响应和真实组件关系最重要时，用项目现有前端栈实现。表单、筛选、开关、抽屉、弹窗和状态反馈通常适合这种方式。
- **Image-state**：视觉方向最重要、用户接受多张图时，为每个关键状态准备一张高保真图，用透明热点连接状态。
- **Hybrid**：视觉和交互都重要时，以高保真图片呈现复杂静态区域，以 HTML/CSS 控件、浮层或局部组件实现关键交互。默认优先考虑这种方式。

图片状态不应只是幻灯片。点击必须对应真实用户意图，并产生清楚的状态变化、反馈或导航结果。需要选择具体结构时，读取 [references/prototype-patterns.md](references/prototype-patterns.md)。

## Define the State Model Before Drawing

先列出最少但完整的状态集合。例如：

```text
overview
→ item-selected
→ evidence-open
→ start-confirmation
→ running
→ success | failure
```

为每个状态记录：进入动作、视觉变化、可继续点击的目标和返回路径。合并视觉相同的状态，不为每一次微小 hover 单独生成图片。关键分支必须可回退，演示不能走进死路。

若使用生成图片，保持同一画布尺寸、导航、布局网格、字体层级和稳定区域；提示词应明确“只改变哪些区域”。每张最终使用的 AI 生成或编辑图片必须配有同名提示词旁车文件，例如 `detail.png` 对应 `detail.prompt.md`，两者放在同一资源目录。旁车文件保存完整提示词、参考图片、保持不变区域、预期变化、画布尺寸、生成工具与日期，使下一次能够同时基于图片和原提示词继续编辑。用户要求只留最终稿时，成对清理被淘汰的图片与提示词文件。

先完成并确认全部最终状态图，再测量热点坐标。AI 编辑即使要求保持布局，也可能让按钮、抽屉或弹窗发生轻微位移；每个状态必须根据自己的最终图片单独校准热点，不直接复制上一状态的坐标。任何图片重新生成后，都将其热点视为需要重新验证。

浏览器截图、设计工具导出图或人工制作图不编造生成提示词；改为同名 `*.source.md`，记录代码入口、状态准备步骤、截图命令或源设计文件。详细格式见 [references/prototype-patterns.md](references/prototype-patterns.md) 的 Image provenance sidecars。

## Build a Reviewable Prototype

- 尽量复用项目依赖和设计令牌，不为原型引入庞大新框架。
- 原型应从一个明确入口启动，不要求评审者手动修改 URL 或源码切换状态。
- 图片热点使用相对坐标或百分比定位，并提供可见 focus、键盘触发和可读的 `aria-label`。
- 热点覆盖范围应与视觉控件一致。可交互元素必须具备按钮形态、指针光标、hover/focus 反馈中的至少两项；不能只依赖用户猜测图片里的哪一块能点。
- 原型提供常驻的“显示可点击区域”开关。开启后，用统一但不遮挡内容的描边或光晕标出所有交互目标；图片热点还应显示简短动作标签。首次进入时用一次性提示说明这个开关。
- 看起来像按钮但尚未实现的控件应明确禁用或改为静态元素。不要留下有 hover 效果却点击无响应的假按钮。
- 弹窗、抽屉、菜单等浮层需要正确的层级、关闭方式和遮罩行为。关键确认操作需展示 loading、success 和 failure 中实际相关的状态。
- 对同一对象的文字、状态、按钮可用性在所有画面中保持一致。
- 若真实数据不可用，使用清楚、稳定、贴近业务的数据样例；不要暗示原型已经接入生产 API。

## Connect Existing Prototypes

当仓库中已经有其他原型时，不让新原型成为孤立文件：

- 同一功能的多个画面放进同一个状态模型，通过真实按钮、热点或导航直接切换；不要只把截图并排陈列。
- 同一用户流程跨越多个原型时，在上一步的真实动作位置链接下一步，并提供返回路径。需要保留上下文时使用查询参数或 hash，例如 `?user=usr_8K2F#detail`。
- 不同主题、无法组成单一业务流程的原型统一登记到可点击的 prototype hub。Hub 应能直接打开或嵌入原型，并显示原型类型、验证层级和主要流程。
- 每个独立原型提供返回 Hub 的入口。遇到失效、空文件或缺少依赖的旧原型时，在 Hub 中标记不可用或暂不登记，不伪造可点击入口。
- 更新仓库已有的原型索引和文档导航；不要建立第二份互相漂移的清单。

具体连接方式见 [references/prototype-patterns.md](references/prototype-patterns.md) 的 Connected prototype system。

## Preserve the Artifact

原型目录至少保留：

```text
<feature-slug>/
├── index.html 或项目栈入口
├── assets/                 # 最终使用的图片和必要资源
└── prototype.md            # 目的、启动方式、状态图、提示词、限制
```

当仓库已有不同约定时服从仓库。`prototype.md` 应区分：

- 已可点击演示的流程；
- 图片或模拟数据表达的行为；
- 仍需生产实现确认的接口、权限和异常路径；
- 图片生成提示词及源代码依据。

`prototype.md` 负责总览并链接旁车文件；旁车文件才是每张图片可继续编辑的权威记录。不要只把多个提示词集中粘贴在无法对应具体图片的段落里。

将原型标为 **interactive prototype** 或 **component preview**。除非它确实经过生产入口和真实后端验证，不要称其为 E2E 或功能验收证据。

## Validate Through the Browser

1. 用仓库现有命令启动原型；没有现成命令时使用最小静态服务器。
2. 在浏览器中逐条走完状态模型，验证点击、返回、关闭、键盘操作和窗口尺寸变化。
3. 对图片状态原型，在桌面宽度和至少一个缩窄宽度下逐状态点击真实热点，确认每次点击发生在图片所画按钮内，并到达预期下一状态。不要只通过脚本直接调用状态切换函数。
4. 截取至少一个默认态和关键结果态，检查文字、裁切、热点偏移、浮层层级和图片加载。
5. 运行仓库要求的格式、构建或文档检查，以及 `git diff --check`。
6. 用 `git status --short` 确认只触及授权范围。除非用户明确要求，不执行 `git add`、`git commit` 或 `git push`。

交付时说明原型入口、覆盖的交互、采用哪种形式、图片与代码各自承担什么，以及尚未验证的生产行为。
