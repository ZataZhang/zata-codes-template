# Prototype Patterns

只在需要选择或实现具体原型结构时读取本页。

## 1. Code-native prototype

适合交互逻辑和响应式布局是主要未知量的场景。

- 优先复用真实页面 shell、导航、组件库和设计令牌。
- 用本地状态和固定 fixture 驱动，不让原型依赖未实现的 API。
- 若直接修改生产页面会污染功能代码，建立独立的 prototype route 或静态入口。

## 2. Image-state prototype

适合视觉稿已经很好、需要用最短路径补上点击演示的场景。

```html
<main class="prototype" data-state="overview">
  <img src="assets/overview.png" alt="路线图总览" />
  <button class="hotspot evidence" aria-label="查看完成证据"></button>
</main>
```

推荐用一个状态表管理切换，而不是在多个事件处理器里散落路径：

```js
const screens = {
  overview: { image: "assets/overview.png", actions: { evidence: "evidence-open" } },
  "evidence-open": { image: "assets/evidence-open.png", actions: { close: "overview" } },
};
```

热点坐标使用百分比，从同一设计画布计算。图片以 `width: 100%` 缩放并保持原始宽高比，热点才能同步缩放。若需要手机和桌面两套布局，为各断点提供独立状态图和坐标表。

## 3. Hybrid prototype

这是高保真和真实交互兼顾时的首选。

常见组合：

- 背景图保留完整页面视觉，真实按钮覆盖在关键动作上；
- 背景图展示页面主体，真实 HTML 抽屉或 Dialog 覆盖其上；
- 静态图用于图表或复杂画布，筛选器、状态条和表单使用真实控件；
- 一张基础画面加多个局部状态图层，减少整屏图片数量。

真实控件应覆盖并遮住图片里对应的伪控件，避免出现两个开关或两套文字。控件颜色、圆角、阴影和字号从图片或现有设计令牌中对齐。

## State-image production

生成多张状态图时，先确定基础图，再以它作为编辑输入逐张派生：

1. 基础页面；
2. 选中或展开态；
3. 确认态；
4. 处理中；
5. 成功和必要的失败态。

每次提示词明确：保持不变的区域、唯一变化的区域、画布尺寸和文字。能用真实 DOM 覆盖的动态文字、计数和状态不要反复烘焙进图片。

推荐先生成基础状态，再以最接近的稳定状态为编辑输入逐张派生。成功态不一定要从确认弹窗态继续编辑；若成功态需要移除弹窗并恢复详情抽屉，从详情态派生通常更稳定，并在旁车文件中准确记录真实参考图。

热点坐标属于对应最终图片，不属于抽象状态。图片生成完成并通过视觉检查后再测量百分比坐标；若某张图重新生成，只重新校准受影响状态。验证时让自动化点击热点元素本身，并检查实际切换后的图片路径或状态标识。

## Image provenance sidecars

AI 生成或编辑图片使用同名 `.prompt.md`：

```text
assets/detail.png
assets/detail.prompt.md
```

旁车文件至少记录：

```markdown
# detail.png

- 生成工具：ImageGen
- 生成日期：YYYY-MM-DD
- 画布：1440 × 1000
- 参考图片：`overview.png`
- 上一状态：`overview`

## 保持不变

- 侧边栏、顶栏、表格列宽和页面留白

## 本次变化

- 打开右侧用户详情抽屉

## 完整提示词

<可直接复用的完整生成或编辑提示词>
```

若一次调用产生多个最终图片，为每张图片保存它实际使用的提示词或清楚标明共享提示词与各自变量。不要只保存一份概括性中文说明。

非 AI 生成图片使用同名 `.source.md`，例如 `detail.source.md`。记录源页面或设计文件、准备状态的操作、画布尺寸、截图或导出命令及日期。没有生成提示词时明确写“无：该图片为浏览器截图”，不要反向编造提示词。

移动、重命名或删除最终图片时同步处理其旁车文件，并更新 `prototype.md` 的链接。

## Connected prototype system

根据关系选择连接层级：

1. **同一页面状态**：一个入口、一个状态表；用按钮或热点改变状态。
2. **同一业务流程的多个页面**：使用真实链接或客户端路由，必要时用 URL 参数携带选中对象和步骤。
3. **互不相关的多个原型**：使用 prototype hub 统一登记。Hub 可以用卡片跳转，也可以在 iframe 中直接加载和操作原型。

Hub 的登记项至少包括标题、入口、原型形式和验证层级。可以维护一个小型 JSON/JavaScript registry 作为唯一清单，由界面动态渲染；不要在 HTML、Markdown 和脚本中分别手写三份状态数据。仓库文档索引只链接到 Hub 和正式说明页。

跨原型传递上下文时，优先使用可复制的 URL：

```text
prototype-hub.html?prototype=admin-users
admin-users.html?user=usr_8K2F#detail
```

原型读取参数后应有安全默认值。缺少对应对象或状态时回到起点，而不是显示空白页。

## Interaction quality checklist

- 不开启辅助模式时，主要动作也能从形状、颜色和 hover/focus 反馈识别；
- “显示可点击区域”能够完整标出当前画面的交互目标；
- 未实现的按钮已禁用或静态化，不会给出虚假可点击暗示；
- 首次进入时能看出哪些元素可以操作；
- 所有关键动作都有即时反馈；
- 每个浮层都能关闭；
- 每条主流程都能返回起点；
- loading 不会无限停留；
- failure 有恢复动作；
- 热点在常见缩放比例下没有偏移；
- 键盘焦点顺序与视觉顺序一致；
- 原型说明没有把模拟行为描述成生产能力。
