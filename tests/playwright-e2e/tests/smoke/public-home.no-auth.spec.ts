import { expect, test } from '@playwright/test'

test.describe('public home smoke', () => {
  test('public home page loads and shows hero heading', async ({ page }) => {
    await page.goto('/')

    const heroHeading = page.getByTestId('public-hero-heading')
    await expect(heroHeading).toBeVisible()
    await expect(heroHeading).toContainText('让 Agent')
  })
})
