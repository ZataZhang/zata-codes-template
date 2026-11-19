import { chromium } from '/Users/zata/code/zata_code_template/tests/playwright-e2e/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs'

const endpoint = process.env.PLAYWRIGHT_REMOTE_BROWSER_WS
if (!endpoint) throw new Error('PLAYWRIGHT_REMOTE_BROWSER_WS is required')
const browser = await chromium.connect(endpoint, { timeout: 10_000 })
const page = await browser.newPage()
const errors = []
page.on('pageerror', (error) => errors.push(String(error)))
await page.goto('file:///work/tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/human-review-checklist.html')
if (!(await page.locator('.card').first().isVisible())) throw new Error('first decision card is not visible')
await page.locator('#next').click()
if (!(await page.locator('video').isVisible())) throw new Error('primary demo video is not visible')
for (let index = 0; index < 4; index += 1) await page.locator('#next').click()
const markdown = await page.locator('#result').textContent()
if (!markdown.includes('第 5 项') || !markdown.includes('（未选择）')) throw new Error('review result does not list all five unanswered decisions')
if (errors.length > 0) throw new Error(errors.join('\n'))
console.log('HUMAN_REVIEW_HTML PASS: zero pageerror, first decision card and primary demo visible, five decisions navigate')
await browser.close()
