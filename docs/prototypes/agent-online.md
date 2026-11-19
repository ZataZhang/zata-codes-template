# 多组织 Agent 在线底座

这是 Issue #58 的交互原型，覆盖组织管理员管理 Agent、治理 Skill 版本，以及成员运行 Agent 和重开历史。页面使用本地示例状态，不连接 API；验证层级为 **interactive prototype（component preview，非功能验收证据）**。

## 入口

- [打开完整交互原型](agent-online.html)
- [返回 Prototype Hub](prototype-hub.html)
- PRD 路径：`tasks/pending/P1-FEAT-20260928-115856-multi-organization-online-agent-base.md`

## 可操作流程

- 在 Agent 列表打开「新建 Agent」，配置模型后发布；无模型的草稿显示不可运行状态。
- 在 Skill 管理里对比版本，并确认将旧内容恢复为一个新版本。
- 在成员工作台切换 Agent、提交消息、观察 Run 状态与最终回复，然后从历史重新打开会话。
- 使用右下角 Dock 重置状态，或切换可点击区域查看控件热点。

## 设计来源与限制

页面沿用 `frontend-public` 的工作台会话入口和 `frontend-admin` 的组织管理导航模式。模拟的 Run、模型结果和 Skill 记录仅用于评审交互顺序；正式验收须使用真实浏览器入口、API、数据库和 Run 事件链，并与本原型做同状态对照。

原型预览图由本地 Chromium 对页面直接截图生成，来源与命令见 [`agent-online.source.md`](assets/agent-online.source.md)。
