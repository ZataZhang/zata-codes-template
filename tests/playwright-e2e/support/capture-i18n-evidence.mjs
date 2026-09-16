/**
 * 采集 PRD §9.1 人读呈递区要求的 i18n 截图。
 *
 * 产出（落盘到 `tasks/evidence/P2-FEAT-20260707-150000-frontend-i18n-bilingual/`）：
 * - `s1-first-visit-default.png`  公开站首次访问（无 cookie）的默认语言首屏（rv-1）
 * - `s2-switch-before.png`        公开站切换语言前（rv-3 / rv-6）
 * - `s2-switch-after.png`         公开站点击切换器后整页变中文（rv-3 / rv-6）
 * - `s3-after-reload.png`         公开站切换后按 F5 仍为中文（rv-3）
 * - `s4-core-en.png`              登录后仪表盘（英文，rv-2）
 * - `s4-core-zh.png`              登录后仪表盘（中文，rv-2）
 * - `s4-settings-en.png`          设置页（英文，rv-2）
 * - `s4-settings-zh.png`          设置页（中文，rv-2）
 * - `s4-marketing-en.png`         `/features` 营销页（英文，rv-2）
 * - `s4-marketing-zh.png`         `/features` 营销页（中文，rv-2）
 * - `s5-admin-en.png`             后台登录页（英文，rv-5 / rv-6）
 * - `s5-admin-zh.png`             后台登录页（中文，rv-5 / rv-6）
 *
 * 这是真实入口流程：真实构建产物 / 真实 dev server、真实路由、真实语言切换器点击。
 * 唯一被脚本化的是"登录"这一步（用 `.env.local` 的 public 引导账号填真实登录表单），
 * 因为受保护页面必须先认证才能到达。
 *
 * 用法（需先启动公开站、后台与后端）：
 *   cd tests/playwright-e2e
 *   PLAYWRIGHT_BASE_URL=http://localhost:3929 \
 *   PLAYWRIGHT_ADMIN_BASE_URL=http://localhost:5842 \
 *   node support/capture-i18n-evidence.mjs
 */

import { chromium } from '@playwright/test'
import { existsSync, mkdirSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const currentDirectoryPath = dirname(fileURLToPath(import.meta.url))
// support/ → playwright-e2e/ → tests/ → 仓库根
const repositoryRootPath = resolve(currentDirectoryPath, '../../..')
const evidenceDirectoryPath = resolve(
  repositoryRootPath,
  'tasks/evidence/P2-FEAT-20260707-150000-frontend-i18n-bilingual'
)

const publicBaseUrl = (
  process.env.PLAYWRIGHT_BASE_URL ?? `http://localhost:${process.env.FRONTEND_PUBLIC_PORT ?? '3000'}`
).replace(/\/$/, '')
const adminBaseUrl = (
  process.env.PLAYWRIGHT_ADMIN_BASE_URL ??
  `http://localhost:${process.env.FRONTEND_ADMIN_PORT ?? '5173'}`
).replace(/\/$/, '')

/** 视口与 Playwright 配置保持一致，便于与 e2e 截图对照。 */
const viewport = { width: 1440, height: 1200 }

/**
 * 读取仓库根 `.env.local` 里的键值对，用于取 public 引导账号。
 *
 * @returns {Record<string, string>} 键值映射；文件不存在时返回空对象。
 */
function readEnvLocal() {
  const envLocalPath = resolve(repositoryRootPath, '.env.local')
  if (!existsSync(envLocalPath)) return {}
  const result = {}
  for (const rawLine of readFileSync(envLocalPath, 'utf-8').split('\n')) {
    const line = rawLine.trim()
    if (!line || line.startsWith('#')) continue
    const separatorIndex = line.indexOf('=')
    if (separatorIndex <= 0) continue
    result[line.slice(0, separatorIndex).trim()] = line.slice(separatorIndex + 1).trim()
  }
  return result
}

const envLocal = readEnvLocal()
const publicIdentifier = process.env.APP_BOOTSTRAP_EMAIL ?? envLocal.APP_BOOTSTRAP_EMAIL
const publicPassword = process.env.APP_BOOTSTRAP_PASSWORD ?? envLocal.APP_BOOTSTRAP_PASSWORD

/**
 * 截图并落盘。
 *
 * @param {import('@playwright/test').Page} page - 页面对象。
 * @param {string} fileName - 目标文件名。
 */
async function capture(page, fileName) {
  const filePath = resolve(evidenceDirectoryPath, fileName)
  await page.screenshot({ path: filePath, fullPage: false })
  console.log(`  📸 ${fileName}`)
}

/**
 * 等待 `<html lang>` 变成期望值，确保截图落在切换完成之后。
 *
 * @param {import('@playwright/test').Page} page - 页面对象。
 * @param {string} expectedLocale - 期望的 locale。
 */
async function waitForLocale(page, expectedLocale) {
  await page.waitForFunction(
    (locale) => document.documentElement.lang === locale,
    expectedLocale,
    { timeout: 15_000 }
  )
}

/**
 * 等待某个 testid 元素的文本变成期望值。
 *
 * @param {import('@playwright/test').Page} page - 页面对象。
 * @param {string} testId - 目标元素的 data-testid。
 * @param {string} expectedText - 期望的完整文本。
 */
async function expectText(page, testId, expectedText) {
  await page.waitForFunction(
    ({ id, text }) => document.querySelector(`[data-testid="${id}"]`)?.textContent?.trim() === text,
    { id: testId, text: expectedText },
    { timeout: 15_000 }
  )
}

/** 采集公开站首屏与切换器截图（rv-1 / rv-3 / rv-6）。 */
async function capturePublicLocaleSwitching(browser) {
  const context = await browser.newContext({ viewport })
  const page = await context.newPage()

  // rv-1：全新上下文 = 无 NEXT_LOCALE cookie，且浏览器语言为默认 en-US。
  await page.goto(`${publicBaseUrl}/`)
  await waitForLocale(page, 'en')
  // 等 React 真正挂载切换器，避免截到尚未 hydrate 的空白帧。
  await page.getByTestId('language-switcher').waitFor({ state: 'visible' })
  await page.waitForTimeout(500)
  await capture(page, 's1-first-visit-default.png')

  // rv-6：切换前。
  await capture(page, 's2-switch-before.png')

  // rv-3 / rv-6：点击真实切换器。
  await page.getByTestId('language-option-zh').click()
  await waitForLocale(page, 'zh')
  await page.waitForTimeout(500)
  await capture(page, 's2-switch-after.png')

  // rv-3：刷新后仍保持中文。
  await page.reload()
  await waitForLocale(page, 'zh')
  await page.waitForTimeout(500)
  await capture(page, 's3-after-reload.png')

  await context.close()
}

/**
 * 用 public 引导账号登录，采集仪表盘与设置页的双语截图（rv-2）。
 *
 * @param {import('@playwright/test').Browser} browser - 浏览器实例。
 */
async function captureCorePages(browser) {
  if (!publicIdentifier || !publicPassword) {
    throw new Error('缺少 APP_BOOTSTRAP_EMAIL / APP_BOOTSTRAP_PASSWORD，无法登录采集核心页面截图。')
  }

  const context = await browser.newContext({ viewport, locale: 'en-US' })
  const page = await context.newPage()

  await page.goto(`${publicBaseUrl}/login`)
  await page.getByTestId('login-identifier-input').fill(publicIdentifier)
  await page.getByTestId('login-password-input').fill(publicPassword)
  await page.getByTestId('login-submit-button').click()
  await page.waitForURL(/\/app\//, { timeout: 20_000 })

  // 仪表盘：英文。
  await page.goto(`${publicBaseUrl}/app/dashboard`)
  await waitForLocale(page, 'en')
  await page.waitForTimeout(800)
  await capture(page, 's4-core-en.png')

  // 仪表盘：中文（用 cookie 直接设定，避免依赖侧栏切换器的位置）。
  await context.addCookies([
    { name: 'NEXT_LOCALE', value: 'zh', url: publicBaseUrl },
  ])
  await page.goto(`${publicBaseUrl}/app/dashboard`)
  await waitForLocale(page, 'zh')
  await page.waitForTimeout(800)
  await capture(page, 's4-core-zh.png')

  // 设置页：中文 + 英文。
  await page.goto(`${publicBaseUrl}/app/settings`)
  await waitForLocale(page, 'zh')
  await page.waitForTimeout(500)
  await capture(page, 's4-settings-zh.png')

  await context.addCookies([
    { name: 'NEXT_LOCALE', value: 'en', url: publicBaseUrl },
  ])
  await page.goto(`${publicBaseUrl}/app/settings`)
  await waitForLocale(page, 'en')
  await page.waitForTimeout(500)
  await capture(page, 's4-settings-en.png')

  await context.close()
}

/** 采集后台登录页的双语截图（rv-5 / rv-6）。 */
async function captureAdminLocaleSwitching(browser) {
  const context = await browser.newContext({ viewport, locale: 'en-US' })
  const page = await context.newPage()

  await page.goto(`${adminBaseUrl}/sign-in`)
  // 清掉可能残留的语言选择，回到"首次访问"状态。
  await page.evaluate(() => window.localStorage.removeItem('i18nextLng'))
  await page.reload()
  await waitForLocale(page, 'en')
  // 只等 <html lang> 会截到 React 尚未渲染的空白帧；等真实标题可见再截图。
  await page.getByTestId('admin-sign-in-heading').waitFor({ state: 'visible' })
  await expectText(page, 'admin-sign-in-heading', 'Welcome back')
  await capture(page, 's5-admin-en.png')

  await page.getByTestId('language-option-zh').click()
  await waitForLocale(page, 'zh')
  await expectText(page, 'admin-sign-in-heading', '欢迎回来')
  await capture(page, 's5-admin-zh.png')

  await context.close()
}

/** 采集其余营销页（/features）的双语截图（rv-2）。 */
async function captureMarketingPages(browser) {
  const context = await browser.newContext({ viewport, locale: 'en-US' })
  const page = await context.newPage()

  await context.addCookies([{ name: 'NEXT_LOCALE', value: 'en', url: publicBaseUrl }])
  await page.goto(`${publicBaseUrl}/features`)
  await waitForLocale(page, 'en')
  // 等真实标题渲染出来，避免截到 React 尚未绘制的空白帧。
  await page.getByRole('heading', { name: 'Template capabilities' }).waitFor({ state: 'visible' })
  await capture(page, 's4-marketing-en.png')

  await context.addCookies([{ name: 'NEXT_LOCALE', value: 'zh', url: publicBaseUrl }])
  await page.goto(`${publicBaseUrl}/features`)
  await waitForLocale(page, 'zh')
  await page.getByRole('heading', { name: '模板能力' }).waitFor({ state: 'visible' })
  await capture(page, 's4-marketing-zh.png')

  await context.close()
}

/** 入口：依次采集三组截图。 */
async function main() {
  mkdirSync(evidenceDirectoryPath, { recursive: true })
  console.log(`证据目录：${evidenceDirectoryPath}`)
  console.log(`公开站：${publicBaseUrl}　后台：${adminBaseUrl}`)

  const browser = await chromium.launch()
  try {
    console.log('▸ 公开站首屏与切换（rv-1 / rv-3 / rv-6）')
    await capturePublicLocaleSwitching(browser)
    console.log('▸ 后台登录页双语（rv-5 / rv-6）')
    await captureAdminLocaleSwitching(browser)
    console.log('▸ 核心页面双语（rv-2）')
    await captureCorePages(browser)
    console.log('▸ 营销页双语（rv-2）')
    await captureMarketingPages(browser)
  } finally {
    await browser.close()
  }

  console.log('✅ 截图采集完成。')
}

await main()
