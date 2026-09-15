/**
 * 公开站语言切换端到端用例（no-auth）。
 *
 * 覆盖 PRD `P2-FEAT-20260707-150000-frontend-i18n-bilingual` 的 oracle：
 * - rv-1：无 cookie / 无语言偏好时首屏呈现默认 locale（`en`）。
 * - rv-2：核心页面文案随语言变化（营销首页 + `/about` + `/features` + `/pricing` + 登录页）。
 * - rv-3：`NEXT_LOCALE` cookie 持久化，刷新后仍保持所选语言。
 * - rv-6：语言切换器可见可操作，点击后整页立即切换。
 *
 * 未登录状态下只有 `(marketing)` 分组挂载了 `SiteHeader`（切换器所在处），
 * 因此切换操作在营销首页执行；`/login` 属于 `(auth)` 分组、没有切换器，
 * 只用于断言"核心页面文案跟随已持久化的语言"。
 */
import { expect, test, type BrowserContext, type Page } from '@playwright/test'

/** 挂载语言切换器的公开页面（营销首页）。 */
const SWITCHER_PAGE_PATH = '/'
/** 核心页面：登录页（未登录可访问）。 */
const LOGIN_PAGE_PATH = '/login'
/** 公开站持久化语言选择的 cookie 名，与 `i18n/constants.ts` 的 LOCALE_COOKIE 一致。 */
const LOCALE_COOKIE_NAME = 'NEXT_LOCALE'

/** 营销首页 hero 主标题首行（`marketing.hero.titleLine1`）。 */
const ENGLISH_HERO_TITLE = 'A clean skeleton,'
const CHINESE_HERO_TITLE = '干净的骨架，'
/** 登录页标题（`auth.loginTitle`）。 */
const ENGLISH_LOGIN_TITLE = 'Welcome back'
const CHINESE_LOGIN_TITLE = '欢迎回来'

/**
 * 其余营销页的标题文案，用于验证它们同样走 i18n 而不是保留中文硬编码。
 *
 * 这三页是导航里可直接点到的可达页面，若漏迁会让英文访客在核心路径上撞到中文。
 */
const MARKETING_PAGE_TITLES = [
  {
    path: '/about',
    english: 'About this template',
    chinese: '关于本模板',
  },
  {
    path: '/features',
    english: 'Template capabilities',
    chinese: '模板能力',
  },
  {
    path: '/pricing',
    english: 'Open-source license',
    chinese: '开源授权',
  },
] as const

test.describe('public frontend locale', () => {
  /**
   * 清空 cookie，模拟"首次访问"的访客。
   *
   * @param context - 当前测试的浏览器上下文。
   */
  async function resetVisitorState(context: BrowserContext): Promise<void> {
    await context.clearCookies()
  }

  /**
   * 在营销首页把语言切成中文，并断言整页立即切换（无需手动刷新）。
   *
   * @param page - 当前页面对象。
   */
  async function switchToChinese(page: Page): Promise<void> {
    await page.goto(SWITCHER_PAGE_PATH)
    await expect(page.getByTestId('language-switcher')).toBeVisible()

    await page.getByTestId('language-option-zh').click()

    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
    await expect(page.getByText(CHINESE_HERO_TITLE, { exact: false })).toBeVisible()
  }

  test('default UI is English with html[lang=en]', async ({ page, context }) => {
    await resetVisitorState(context)
    await page.goto(SWITCHER_PAGE_PATH)

    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByText(ENGLISH_HERO_TITLE, { exact: false })).toBeVisible()
  })

  test('switching the language updates the page without a manual refresh', async ({
    page,
    context,
  }) => {
    await resetVisitorState(context)
    await page.goto(SWITCHER_PAGE_PATH)
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')

    await page.getByTestId('language-option-zh').click()

    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
    await expect(page.getByText(CHINESE_HERO_TITLE, { exact: false })).toBeVisible()
    // 英文文案应已被替换，而不是与中文并存。
    await expect(page.getByText(ENGLISH_HERO_TITLE, { exact: false })).toHaveCount(0)
  })

  test('the chosen language persists across reloads', async ({ page, context }) => {
    await resetVisitorState(context)
    await switchToChinese(page)

    // 切换器写入的 cookie 必须与服务端读取的名字一致。
    await expect
      .poll(async () => {
        const cookies = await context.cookies()
        return cookies.find((cookie) => cookie.name === LOCALE_COOKIE_NAME)?.value
      })
      .toBe('zh')

    await page.reload()

    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
    await expect(page.getByText(CHINESE_HERO_TITLE, { exact: false })).toBeVisible()
  })

  test('core pages follow the chosen language', async ({ page, context }) => {
    await resetVisitorState(context)
    await switchToChinese(page)

    await page.goto(LOGIN_PAGE_PATH)

    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
    await expect(page.getByText(CHINESE_LOGIN_TITLE, { exact: true })).toBeVisible()
    await expect(page.getByText(ENGLISH_LOGIN_TITLE, { exact: true })).toHaveCount(0)
  })

  test('remaining marketing pages are translated, not left in Chinese', async ({ page, context }) => {
    await resetVisitorState(context)

    // 英文（默认）：三页都不应出现中文标题。
    for (const marketingPage of MARKETING_PAGE_TITLES) {
      await page.goto(marketingPage.path)

      await expect(page.locator('html')).toHaveAttribute('lang', 'en')
      await expect(page.getByRole('heading', { name: marketingPage.english })).toBeVisible()
      await expect(page.getByText(marketingPage.chinese, { exact: true })).toHaveCount(0)
    }

    // 切到中文后：三页都应呈现中文标题。
    await switchToChinese(page)

    for (const marketingPage of MARKETING_PAGE_TITLES) {
      await page.goto(marketingPage.path)

      await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
      await expect(page.getByRole('heading', { name: marketingPage.chinese })).toBeVisible()
      await expect(page.getByText(marketingPage.english, { exact: true })).toHaveCount(0)
    }
  })

  test.describe('unsupported browser language', () => {
    // fr-FR 同时设置 Accept-Language 请求头与 navigator.language，
    // 用来验证协商失败时回退到 DEFAULT_LOCALE 而不是输出空白文案。
    test.use({ locale: 'fr-FR' })

    test('falls back to the default locale', async ({ page, context }) => {
      await resetVisitorState(context)
      await page.goto(SWITCHER_PAGE_PATH)

      await expect(page.locator('html')).toHaveAttribute('lang', 'en')
      await expect(page.getByText(ENGLISH_HERO_TITLE, { exact: false })).toBeVisible()
    })
  })
})
