# 用户管理图片热点原型截图

- 来源：`../admin-users-interactive.html` 的 Chromium 浏览器截图
- 更新时间：2026-11-17
- 状态与画布：1536 × 1024；列表、详情、确认和完成四个状态
- 用途：供 `../admin-users-image-hotspot.html` 叠加透明热点并切换状态

## 复现步骤

使用 Playwright Chromium 打开 `admin-users-interactive.html`，等待页面与字体加载后隐藏 `.prototype-note`、`.interaction-legend` 和热点描边，并把 `.app-shell` 最小高度设为 `100vh`。截图列表后，依次点击首行“查看详情”、详情抽屉的“禁用用户”和确认框的“确认禁用”，每次等待过渡完成再截图。

```text
users-list-state.png      初始列表
users-detail-state.png    打开首位用户详情
users-confirm-state.png   打开禁用确认框
users-success-state.png   确认禁用并等待 Toast 显示
```

列表与详情状态也复用于 `admin-users-interactive.md` 的文档预览；该预览保留页面工具栏与热点提示。
