# 原型预览图来源

- 页面：`docs/prototypes/agent-online.html`
- 入口：Prototype Hub → 多组织 Agent 在线底座 → 默认 Agents 管理页
- 验证层级：`interactive prototype（component preview，非功能验收证据）`
- 浏览器：Chromium 156.0.8078.79（Alpine Linux），视口 `1440 × 1000`，设备缩放 `1`
- 截图：由 `tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/prototype-hub-check.mjs` 从 Hub 打开页面后生成；截图前移除热点描边并隐藏评审 Dock。
- Hub 桌面和窄屏入口、详情抽屉、原型打开与回链，以及 Agent、Skill、Run 交互均通过同一脚本验证。
- 重拍命令：在仓库根运行 `docker run --rm --mount type=bind,source="$PWD",target=/work -w /work node:22-alpine sh -c 'apk add --no-cache chromium font-noto-cjk >/dev/null && node tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/prototype-hub-check.mjs'`。

本截图是本地原型的组件预览图，不是 `frontend-admin` 或 `frontend-public` 真实功能验收证据。
