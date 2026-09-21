# file-viewer-interactive.png / -diff.png / -disconnected.png

- 来源类型：浏览器截图，无 AI 生成提示词
- 日期：2026-09-21
- 画布：1440 × 900（`deviceScaleFactor: 2`，输出 2880 × 1800）
- 页面：`../file-viewer-interactive.html`
- 工具：Playwright Chromium `page.screenshot()`

三张图是同一个页面的三个状态，共用同一份截图脚本：

| 文件 | 状态 | 准备步骤 |
|---|---|---|
| `file-viewer-interactive.png` | 文件视图（默认） | 打开页面即可；默认选中 `docs/ai-standards/tooling.md` |
| `file-viewer-interactive-diff.png` | 改动视图 | 点顶部「改动」（基线为「工作区改动」，6 个改动文件） |
| `file-viewer-interactive-disconnected.png` | 服务已退出态 | 点 Dock「说明」→「模拟服务已退出」（等效于闲置回收） |

截图前给 `body` 加了 `capture-product-only` 类隐藏底部 prototype chrome（Dock），
避免把评审工具误当成产品设计。

## 复现

```js
await page.goto('http://localhost:8898/file-viewer-interactive.html')
await page.waitForTimeout(600)
await page.evaluate(() => document.body.classList.add('capture-product-only'))

await page.screenshot({ path: 'docs/prototypes/assets/file-viewer-interactive.png' })

await page.click('#tab-diff')
await page.waitForTimeout(300)
await page.screenshot({ path: 'docs/prototypes/assets/file-viewer-interactive-diff.png' })

await page.click('[data-info-toggle]')
await page.waitForTimeout(250)
await page.click('#simulate-exit')
await page.waitForTimeout(300)
await page.screenshot({ path: 'docs/prototypes/assets/file-viewer-interactive-disconnected.png' })
```

本地服务：`python3 -m http.server 8898 --directory docs/prototypes`

（截图脚本运行时 Dock 若已闲置收缩，点 Dock 内按钮前需先 `page.hover('[data-prototype-chrome]')` 唤醒。）

## 说明

画面为本地 fixture，未接入生产只读接口。验证层级为 interactive prototype / component preview，
不构成功能验收或 E2E 证据。
