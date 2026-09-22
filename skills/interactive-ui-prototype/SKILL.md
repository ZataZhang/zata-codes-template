---
name: interactive-ui-prototype
description: "[Updated 2026-09-22] Create or revise a connected, clickable, high-fidelity UI prototype grounded in the current repository's real pages, components, routes, and design system. Use when a user wants a 交互原型, 可点击草图, code prototype, multiple UI mockup states connected as a demo, or a visual design that can be reviewed before implementation. Do not use for implementing the production feature itself."
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
- **原型评审控件与产品画布必须分层。** 返回 Hub、原型说明、热点开关、重置等属于 prototype chrome，不属于产品 UI；不得为它们在产品页面顶部或侧边栏内新增横向工具条、导航项或占位高度，也不得因此移动、压缩真实产品布局。默认复用 `assets/prototype-system-template/prototype-chrome.css/js` 的底部毛玻璃 Dock，四个操作常驻可见；鼠标离开后自动淡化并收缩为可找回的“原型”胶囊，悬停或键盘聚焦恢复。如果真实产品已有合适的开发者菜单，也可以复用。
- prototype chrome 应使用独立容器和稳定标识（例如 `data-prototype-chrome`），方便截图时按证据目的选择保留或隐藏。评审原型交互时保留；需要对照真实产品视觉或生成 Hub 缩略图时默认隐藏，并在截图旁车中记录。
- **共享 chrome 的变更会连带让所有引用它的截图过期。** 把某块产品外壳（侧栏、顶栏）或评审 Dock 抽象成共享文件、或修改已有的共享文件，都属于对全部相关画面的视觉变更：必须在同一次改动里重截所有引用它的预览图，并把共享文件名写进每张图旁车的失效条件。只改折线以下或不进画面的文案不算重截触发器。
- 图片热点使用相对坐标或百分比定位，并提供可见 focus、键盘触发和可读的 `aria-label`。
- 热点覆盖范围应与视觉控件一致。可交互元素必须具备按钮形态、指针光标、hover/focus 反馈中的至少两项；不能只依赖用户猜测图片里的哪一块能点。
- 原型提供常驻的“显示可点击区域”开关，默认开启，重置后也恢复为开启。开启后，用统一但不遮挡内容的描边或光晕标出所有交互目标；图片热点还应显示简短动作标签。
- 看起来像按钮但尚未实现的控件应明确禁用或改为静态元素。不要留下有 hover 效果却点击无响应的假按钮。
- 列表行、卡片、缩略图这类可点击对象要同时给出两条路径：**直开入口**（缩略图和名称本身就是打开目标的链接）与**详情入口**（点行内其他区域打开预览与元数据浮层）。两条路径的点击结果必须写进页面文案和 `prototype.md`，不要让评审者逐个试点才知道点哪里会发生什么；Hub 的具体点击语义见 [references/prototype-hub-contract.md](references/prototype-hub-contract.md)。
- 弹窗、抽屉、菜单等浮层需要正确的层级、关闭方式和遮罩行为。关键确认操作需展示 loading、success 和 failure 中实际相关的状态。
- 对同一对象的文字、状态、按钮可用性在所有画面中保持一致。
- 若真实数据不可用，使用清楚、稳定、贴近业务的数据样例；不要暗示原型已经接入生产 API。

## Connect Existing Prototypes

当仓库中已经有其他原型时，不让新原型成为孤立文件：

- 同一功能的多个画面放进同一个状态模型，通过真实按钮、热点或导航直接切换；不要只把截图并排陈列。
- 同一用户流程跨越多个原型时，在上一步的真实动作位置链接下一步，并提供返回路径。需要保留上下文时使用查询参数或 hash，例如 `?user=usr_8K2F#detail`。
- **同一产品外壳只允许存在一份。** 属于同一产品画布（同一条侧栏、同一顶栏）的多个原型，必须引用共享外壳文件（`assets/prototype-system-template/app-shell.css/js`，或仓库已有的等价外壳），不得每个原型复制一份侧栏。侧栏项只声明它在产品里的名字和指向的 registry 条目，文件路径、是否可点全部由 registry 推导：同条目内的视图渲染成按钮，跨条目渲染成真实链接（带 `↗` 一类的跨页标记），既无条目也未登记的渲染成带原因说明的静态项。禁止把跨模块入口做成点不动的假链接。窄屏把侧栏收成图标列，而不是整条隐藏，否则移动端就断了跨原型跳转。
- 不同主题、无法组成单一业务流程的原型统一登记到可点击的 prototype hub。Hub 只管理原型资产及其入口，不承担 PRD、Issue、CI/CD、任务调度或运行监控职责。
- 每个独立原型提供返回 Hub 的入口。遇到失效、空文件或缺少依赖的旧原型时，在 Hub 中标记不可用或暂不登记，不伪造可点击入口。
- 更新仓库已有的原型索引和文档导航；不要建立第二份互相漂移的清单。

具体连接方式见 [references/prototype-patterns.md](references/prototype-patterns.md) 的 Connected prototype system。

需要实际创建或重构 Hub 时，读取 [references/prototype-hub-contract.md](references/prototype-hub-contract.md)；图片状态需要可点击热点时，读取 [references/image-hotspot-contract.md](references/image-hotspot-contract.md)；需要组件库时，读取 [references/component-library-contract.md](references/component-library-contract.md)。这些模式可从 `assets/prototype-system-template/` 复制最小骨架——它已包含共享产品外壳（`app-shell.css/js`）、唯一事实源（`registry.js`）与评审 Dock（`prototype-chrome.css/js`）三部分，脚本按 registry → 外壳 → 页面脚本的顺序引入——但必须替换示例 registry、路径、文案和视觉变量，并服从目标仓库现有设计系统。

### Prototype Hub Delivery Gate

当仓库已经有两个或以上互不属于同一业务流程的原型，或已有 prototype hub / 原型总览入口时，Hub 登记是交付的一部分，不是可选文档整理：

1. 先定位现有 Hub、registry、原型索引和文档导航，确认哪个文件是原型清单的唯一事实源；不得因为现有 Hub 不在 `docs/prototypes/index.md` 就另建第二套。
2. 每个新增或实质修改的独立原型都必须同步登记 Hub。registry 至少包含标题、入口、所属项目、所属模块、所属原型系统（同一产品外壳下的一组原型共享一个系统名，独立原型留空）、原型形式（code-native / image-state / hybrid）、版本、更新时间、验证层级、主要流程、可用状态和 provenance sidecar；列表只展示便于扫描的字段，其余信息放到详情抽屉。**registry 是“有哪些原型、能不能点”的唯一事实源**：Hub 目录和共享外壳的导航都是它的一个视图，不要在 HTML、Markdown 或外壳脚本里再手写第二份条目清单——三份数据必然漂移。外壳导航从 registry 推导，registry 条目标为不可用时，侧栏对应项必须跟着降级成静态项。
3. 每个独立原型必须通过低干扰的 prototype chrome 提供返回 Hub 的可见入口；不得用横跨产品画布的顶部工具条实现。纯图片资产由 Hub 卡片同时提供原图和说明页入口。
4. AI 生成/编辑图片登记到 Hub 前，必须存在对应的 `.prompt.md`；浏览器截图或设计导出图必须存在 `.source.md`。缺少 provenance sidecar 的图片不得标成可继续维护的最终原型。
5. 旧原型入口失效、文件为空或依赖缺失时，Hub 明确标记不可用，不能保留一个看似可点击但实际失败的卡片。
6. 交付前从 Hub 真实入口打开新卡片，在桌面和至少一个窄屏宽度验证：缩略图加载、缩略图/名称直开、行内其他位置的详情抽屉、返回 Hub、验证层级标签和无横向溢出。只验证目标原型文件本身不算完成。

若仓库还没有 Hub，但本次交付会形成两个或以上独立原型，创建最小 Hub 并把 registry 作为唯一清单；文档索引只链接 Hub 和正式说明页，不重复手写卡片清单。

### Prototype Hub Default Information Architecture

没有既有产品规范或用户另选风格时，Hub 默认采用“高密度目录 + 右侧预览详情”结构，视觉参考见 `assets/prototype-hub-catalog-reference.png`：

- 左侧仅提供原型资产维度的导航，例如全部原型、按项目、按模块、按原型系统、按原型形式、按可用状态；不要复制主产品的业务导航。
- 主区顶部提供搜索，以及项目、模块、原型系统、原型形式、可用状态筛选。列表列优先使用预览、原型名称、项目、模块、原型形式、版本、更新时间和可用状态。
- 一个原型系统下的多个原型共享同一产品外壳，评审者常常分不清它们其实是一套界面。按原型系统分组时，分组行除了计数还要写明这层关系（例如“共享同一个产品外壳，打开任意一个都能用左侧侧栏点到其余模块”），让目录本身解释入口结构，而不是让评审者逐个打开才发现。
- 选中列表项后打开右侧详情抽屉，展示较大预览、原型描述、验证层级、主要流程、来源/旁车、版本历史，以及“打开原型”和“返回目录”。
- 默认保持目录高密度、可扫描；缩略图用于识别，不把每个条目做成占据大量空间的运营卡片。
- Hub 只回答“有哪些原型、属于哪里、是什么形式、当前是否可打开、如何进入和追溯来源”。CI/CD、PRD 执行状态、Issue、仓库健康、Daemon、任务依赖、审核队列、运行监控和自动修复策略均不得进入 Hub。
- 某个原型画面本身可以包含上述业务内容，但 Hub 只把它当作缩略图和原型入口，不抽取这些内容成为 Hub 字段或公共控制项。
- Hub 的主导航只放原型资产分类。组件库和原型规范属于辅助入口，应独立分组；组件库不得作为普通原型写入 prototype registry。

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
- 关键可点击对象的点击结果：哪些是直开目标、哪些打开详情浮层、哪些切换演示分支，以及页面文案里如何向评审者说明；
- 图片或模拟数据表达的行为；
- 仍需生产实现确认的接口、权限和异常路径；
- 图片生成提示词及源代码依据。

`prototype.md` 负责总览并链接旁车文件；旁车文件才是每张图片可继续编辑的权威记录。不要只把多个提示词集中粘贴在无法对应具体图片的段落里。

将原型标为 **interactive prototype** 或 **component preview**。除非它确实经过生产入口和真实后端验证，不要称其为 E2E 或功能验收证据。

## Validate Through the Browser

1. 用仓库现有命令启动原型；没有现成命令时使用最小静态服务器。
2. 在浏览器中逐条走完状态模型，验证点击、返回、关闭、键盘操作和窗口尺寸变化。
3. 对图片状态原型，在桌面宽度和至少一个缩窄宽度下逐状态点击真实热点，确认每次点击发生在图片所画按钮内，并到达预期下一状态。不要只通过脚本直接调用状态切换函数。
4. 截取至少一个默认态和关键结果态，检查文字、裁切、热点偏移、浮层层级和图片加载；用于评审产品视觉或 Hub 缩略图的截图默认隐藏 prototype chrome。若本次改动落在共享外壳或共享 chrome 上，逐个核对所有引用它的预览图是否已重截、旁车失效条件是否已登记该共享文件。
5. 从 Prototype Hub 打开本次原型并走到关键状态，再验证返回 Hub；在窄屏复查 Hub 卡片与原型入口。存在共享外壳时，另需从外壳真实点击一次跨原型入口，确认落到对应页面而不是无响应。
6. 运行仓库要求的格式、构建或文档检查，以及 `git diff --check`。
7. 用 `git status --short` 确认只触及授权范围。除非用户明确要求，不执行 `git add`、`git commit` 或 `git push`。

交付时说明 Hub 入口、原型入口、覆盖的交互、采用哪种形式、图片与代码各自承担什么、provenance sidecar，以及尚未验证的生产行为。没有完成适用的 Hub 登记、返回入口或旁车文件时，不得声称原型交付完成。
