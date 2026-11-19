import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const worktree = resolve(scriptDirectory, '../../../..')
const require = createRequire(resolve(worktree, 'tests/playwright-e2e/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/package.json'))
const { chromium } = require('playwright')
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1280, height: 1000 } })
const errors = []
page.on('pageerror', (error) => errors.push(String(error)))
await page.goto(pathToFileURL(resolve(scriptDirectory, '../human-review-checklist.html')).href)
if (!(await page.locator('.card').first().isVisible())) throw new Error('first card is not visible')
for (let index = 0; index < 5; index += 1) await page.locator('#next').click()
const markdown = await page.locator('#result').textContent()
if (!markdown.includes('第 5 项') || !markdown.includes('（未选择）')) throw new Error('markdown did not include all decisions')
if (errors.length > 0) throw new Error(errors.join('\n'))
console.log('HUMAN_REVIEW_HTML PASS: zero pageerror, first card visible, navigation and markdown work')
await browser.close()
