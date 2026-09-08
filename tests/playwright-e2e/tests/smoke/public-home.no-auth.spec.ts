import { expect, test } from '@playwright/test'

test.describe('public home smoke', () => {
  test('public home page loads and shows hero heading', async ({ page }) => {
    await page.goto('/')

    // 只断言 hero 结构渲染成功，不断言营销文案。文案属于随时会改的产品内容，
    // 把它写进 smoke 断言会让每次改标题都误报一次 CI（历史上已发生：业务域摘除
    // 时首页标题从「让 Agent」改成「干净的骨架」，本用例红了一个多月）。
    const heroHeading = page.getByTestId('public-hero-heading')
    await expect(heroHeading).toBeVisible()
    await expect(heroHeading).not.toBeEmpty()
  })
})
