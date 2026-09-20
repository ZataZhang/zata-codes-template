# admin-users-interactive.png

- 来源类型：浏览器截图，无 AI 生成提示词
- 日期：2026-09-16（文件提交时间；原始截图命令未在仓库中记录）
- 画布：1440 × 1000
- 页面：`../admin-users-interactive.html`
- 工具：Playwright Chromium `page.screenshot()`

> 本文件为建立 Prototype Hub registry 时补记。上方的日期取自该图片进入版本库的时间，
> **原始截图命令、视口设置与状态准备步骤未在仓库中找到记录**；如已知原始命令，请在此补全，
> 不要把推测写成事实。

## 复现（建议口径）

```js
await page.goto('<static-server>/admin-users-interactive.html')
await page.waitForTimeout(700)
await page.screenshot({ path: 'docs/prototypes/assets/admin-users-interactive.png' })
```

## 说明

本图只作为 Hub 目录的缩略图使用；原型的可交互状态与边界见 `../admin-users-interactive.md`。
