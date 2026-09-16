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
- 点击缩略图或名称：直接打开原型。
- 链接点击不得同时触发行选择。
- 缩略图、名称及详情动作必须支持键盘焦点。

## 数据契约

Prototype registry 至少包含：`id`、`title`、`entry`、`project`、`module`、`form`、`version`、`updatedAt`、`availability`、`validationLevel`、`description`、`preview`、`source`。HTML 只从 registry 渲染，不重复维护条目。

可复制骨架：`assets/prototype-system-template/hub.html`、`hub.css`、`hub.js`。
