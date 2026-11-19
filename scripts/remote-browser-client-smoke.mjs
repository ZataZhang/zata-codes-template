import { chromium } from '/Users/zata/code/zata_code_template/tests/playwright-e2e/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs'

const endpoint = process.env.PLAYWRIGHT_REMOTE_BROWSER_WS
if (!endpoint) throw new Error('PLAYWRIGHT_REMOTE_BROWSER_WS is required')
const browser = await chromium.connect(endpoint, { timeout: 10_000 })
const page = await browser.newPage()
await page.goto('about:blank')
console.log(`Remote Playwright handshake: PASS; browser=${browser.browserType().name()}`)
await browser.close()
