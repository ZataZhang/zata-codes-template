import { mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const worktree = resolve(scriptDirectory, '../../../..')
const evidenceDirectory = resolve(scriptDirectory, '..')
const require = createRequire(resolve(worktree, 'tests/playwright-e2e/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/package.json'))
const { chromium } = require('playwright')

mkdirSync(evidenceDirectory, { recursive: true })
const browser = await chromium.launch({ headless: true })
const page = await browser.newPage({ viewport: { width: 1440, height: 1200 } })
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(String(error)))
await page.goto(pathToFileURL(resolve(worktree, 'docs/prototypes/agent-online.html')).href)
await page.locator('button[data-view="member"]').click()
await page.evaluate(() => document.documentElement.classList.add('capture-product-only'))
await page.screenshot({ path: resolve(evidenceDirectory, 'rv-2-prototype.png'), fullPage: true })
await page.locator('button[data-view="skills"]').click()
await page.locator('.compareAction').click()
await page.locator('#confirmRestore').click()
await page.screenshot({ path: resolve(evidenceDirectory, 'rv-3-prototype.png'), fullPage: true })
if (pageErrors.length > 0) throw new Error(pageErrors.join('\n'))
await browser.close()
console.log('PROTOTYPE_CAPTURE PASS: rv-2 and rv-3 target states at 1440x1200')
