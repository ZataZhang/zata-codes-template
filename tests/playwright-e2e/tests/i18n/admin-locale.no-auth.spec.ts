/**
 * 后台语言切换端到端用例（no-auth）。
 *
 * 覆盖 PRD `P2-FEAT-20260707-150000-frontend-i18n-bilingual` 的 oracle：
 * - rv-1：清空 localStorage 后首屏 `<html lang>` 为默认 locale（`en`）。
 * - rv-5：`react-i18next` 接入 + `localStorage` 持久化（刷新后仍保持）。
 * - rv-6：语言切换器可见可操作，点击后整页立即切换。
 *
 * 本文件落在 Playwright 的 `no-auth` project（baseURL 指向公开站），而后台是
 * 另一个域，因此所有导航都使用 `getAdminBaseUrl()` 拼出的绝对地址。
 * 通过 `just e2e` 运行时，`scripts/shared/e2e/run-with-just-stack.sh` 会导出
 * `PLAYWRIGHT_ADMIN_BASE_URL`，指向 `just run` 实际使用的后台端口。
 */
import { expect, test, type Page } from '@playwright/test'
import { getAdminBaseUrl } from '../../support/env'

const ADMIN_BASE_URL = getAdminBaseUrl()
const SIGN_IN_PATH = '/sign-in'

/** 后台持久化语言选择的 localStorage 键，与 `src/i18n/init.ts` 的 LOCALE_STORAGE_KEY 一致。 */
const LOCALE_STORAGE_KEY = 'i18nextLng'

/** 登录页标题（`auth.signInTitle`）。 */
const ENGLISH_SIGN_IN_TITLE = 'Welcome back'
const CHINESE_SIGN_IN_TITLE = '欢迎回来'

/**
 * 品牌面板底部版权文案（`auth.copyright`）的稳定片段。
 *
 * 该 key 带 `{{year}}` 插值，是本仓库最容易踩坑的一处：i18next 只认 `{{var}}`，
 * 写成 ICU 的 `{var}` 不会报错，而是把占位符原样渲染成 `© {year} Zata.`。
 * 因此这里既断言年份已代入，也断言不再残留花括号。
 */
const COPYRIGHT_MARKER_ENGLISH = 'Zata. All rights reserved.'
const COPYRIGHT_MARKER_CHINESE = 'Zata. 保留所有权利。'

test.describe('admin frontend locale', () => {
  /**
   * 打开后台登录页并清掉已保存的语言选择，回到"首次访问"状态。
   *
   * @param page - 当前页面对象。
   */
  async function clearSavedLocale(page: Page): Promise<void> {
    await page.goto(`${ADMIN_BASE_URL}${SIGN_IN_PATH}`)
    await page.evaluate((storageKey) => {
      window.localStorage.removeItem(storageKey)
    }, LOCALE_STORAGE_KEY)
    await page.reload()
  }

  /**
   * 在登录页点切换器切到中文，并断言整页立即切换。
   *
   * @param page - 当前页面对象。
   */
  async function switchToChinese(page: Page): Promise<void> {
    await expect(page.getByTestId('language-switcher')).toBeVisible()

    await page.getByTestId('language-option-zh').click()

    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
    await expect(page.getByTestId('admin-sign-in-heading')).toHaveText(CHINESE_SIGN_IN_TITLE)
  }

  test('default admin UI is English with html[lang=en]', async ({ page }) => {
    await clearSavedLocale(page)

    await expect(page.getByTestId('admin-sign-in-heading')).toHaveText(ENGLISH_SIGN_IN_TITLE)
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  })

  test('switching the language updates the page without a manual refresh', async ({ page }) => {
    await clearSavedLocale(page)
    await expect(page.getByTestId('admin-sign-in-heading')).toHaveText(ENGLISH_SIGN_IN_TITLE)

    await switchToChinese(page)

    await expect(page.getByTestId('admin-sign-in-heading')).not.toHaveText(ENGLISH_SIGN_IN_TITLE)
  })

  test('the chosen language persists in localStorage', async ({ page }) => {
    await clearSavedLocale(page)
    await switchToChinese(page)

    await expect
      .poll(() =>
        page.evaluate((storageKey) => window.localStorage.getItem(storageKey), LOCALE_STORAGE_KEY),
      )
      .toBe('zh')
  })

  test('the chosen language survives reload', async ({ page }) => {
    await clearSavedLocale(page)
    await switchToChinese(page)

    await page.reload()

    await expect(page.getByTestId('admin-sign-in-heading')).toHaveText(CHINESE_SIGN_IN_TITLE)
    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
  })

  test('interpolated copy resolves the placeholder instead of rendering it literally', async ({
    page,
  }) => {
    await clearSavedLocale(page)

    const currentYear = new Date().getFullYear().toString()
    const copyright = page.getByTestId('admin-auth-copyright')

    // 英文：年份已代入，且不残留 `{year}` 这类未解析占位符。
    await expect(copyright).toContainText(currentYear)
    await expect(copyright).toContainText(COPYRIGHT_MARKER_ENGLISH)
    await expect(copyright).not.toContainText('{year}')

    // 中文：换语言后年份同样代入，中文版权串生效。
    await switchToChinese(page)

    await expect(copyright).toContainText(currentYear)
    await expect(copyright).toContainText(COPYRIGHT_MARKER_CHINESE)
    await expect(copyright).not.toContainText('{year}')
  })
})
