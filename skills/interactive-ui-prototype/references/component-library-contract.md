# Component Library Contract

仅在仓库需要原型组件库时读取。组件库是辅助设计资产，不登记为普通原型，也不进入原型类型筛选。

## 三级结构

1. Hub 中的独立“组件库”入口；
2. 组件目录：分类、搜索、目录行、快速预览；
3. 组件详情：变体、状态矩阵和组合示例。

目录展开只展示少量高频示例，并提供“查看完整组件”。不要把大量表单类型和状态全部堆在目录首页。

## Registry

Component registry 与 Prototype registry 分离，至少包含：`id`、`title`、`category`、`categoryLabel`、`contents`、`status`、`preview` 和详情入口。

## 详情最低内容

- 基础用法与主要变体；
- Default、Hover、Focus、Loading、Error、Disabled、Empty 中适用的状态；
- 长文本、空内容和大量选项等边界；
- 键盘操作与使用限制。

表单类进一步覆盖单选、多选、搜索、异步加载、级联、Checkbox、Radio、Switch、日期与校验状态。

可复制骨架：`assets/prototype-system-template/component-library.html`、`component-library.js`、`component-detail.html`、`component-detail.js`、`components.css`。
