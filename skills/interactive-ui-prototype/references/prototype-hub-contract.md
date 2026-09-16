# Prototype Hub Contract

仅在需要创建或修改 Prototype Hub 时读取。

## 职责边界

Hub 只回答：有哪些原型、属于哪个项目/模块、采用什么形式、是否可打开、如何进入及追溯说明。CI/CD、PRD 执行状态、Issue、仓库健康、任务调度和运行监控不能成为 Hub 的公共字段或控制项。

## 信息架构

- 主导航：全部原型、图片原型、交互原型、当前可用。
- 辅助入口：组件库、原型规范。放在独立区域，不混入原型类型筛选。
- 主区：搜索、项目/模块/形式筛选、高密度目录。
- 详情区：大图预览、描述、验证层级、版本、来源、打开入口。

## 点击语义

- 点击行的非链接区域：切换右侧详情。
- 点击缩略图或名称：直接打开原型，默认新标签页打开以保留 Hub 的搜索、筛选与滚动状态。
- 链接点击不得同时触发行选择。
- 缩略图、名称及详情动作必须支持键盘焦点。

## 原型内返回入口

- 返回 Hub、原型说明、热点开关和重置属于 prototype chrome，不属于被评审产品的界面。
- 禁止把这些动作做成横跨产品顶部的常驻工具条，或塞进产品业务侧边栏导致信息架构失真。
- 默认复用模板的底部毛玻璃 Dock，常驻 Hub、说明、热点和重置四个动作；闲置后淡化收缩为“原型”胶囊，悬停或键盘聚焦恢复。不得遮挡主操作、Dialog 确认按钮、Toast 或移动端安全区。
- Hub 缩略图默认隐藏 prototype chrome，避免目录预览把评审工具误当成产品设计。

## 数据契约

Prototype registry 至少包含：`id`、`title`、`entry`、`project`、`module`、`form`、`version`、`updatedAt`、`availability`、`validationLevel`、`description`、`preview`、`source`。HTML 只从 registry 渲染，不重复维护条目。

可复制骨架：`assets/prototype-system-template/hub.html`、`hub.css`、`hub.js`。
