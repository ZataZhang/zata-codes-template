# login-demo.png

- 来源类型：浏览器截图，无 AI 生成提示词
- 日期：2026-09-20
- 画布：1440 × 1000
- 页面：`../login-demo.html`
- 状态：默认态（idle），未提交表单
- 工具：Playwright Chromium `page.screenshot()`

截图前给 `body` 加了 `capture-product-only` 类隐藏底部 prototype chrome（Dock），
避免把评审工具误当成产品设计。

## 复现

```js
await page.goto('http://localhost:8898/login-demo.html')
await page.waitForTimeout(700)
await page.evaluate(() => document.body.classList.add('capture-product-only'))
await page.screenshot({ path: 'docs/prototypes/assets/login-demo.png' })
```

## 说明

画面为本地 fixture，未接入生产 API。验证层级为 interactive prototype / component preview，
不构成功能验收或 E2E 证据。
