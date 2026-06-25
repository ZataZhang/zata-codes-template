/**
 * Workflow canvas smoke test — verifies the new workflow page loads
 * without React maximum update depth errors.
 */
import { expect, test } from '../../fixtures/session.fixture'

test.describe('workflow canvas', () => {
  test('new workflow page renders the canvas without runtime errors', async ({ page }) => {
    const pageErrors: Error[] = []
    const consoleErrors: string[] = []
    const allConsoleMessages: string[] = []

    page.on('pageerror', (error) => pageErrors.push(error))
    page.on('console', (message) => {
      const text = `[${message.type()}] ${message.text()}`
      allConsoleMessages.push(text)
      if (message.type() === 'error') {
        consoleErrors.push(message.text())
      }
    })

    const cookies = await page.context().cookies()
    console.log('[e2e debug] cookies:', JSON.stringify(cookies))

    page.on('response', (response) => {
      if (response.url().includes('/auth/me')) {
        console.log('[e2e debug] /auth/me status:', response.status(), response.url())
      }
    })

    await page.goto('/app/workflows/new')
    await page.waitForLoadState('networkidle')
    console.log('[e2e debug] networkidle reached')

    // Give React a moment to hydrate and run effects.
    await page.waitForTimeout(3000)
    console.log('[e2e debug] console messages:', allConsoleMessages.join('\n'))
    await expect(page.getByText('加载中…')).not.toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('main')).toBeVisible()
    await expect(page.locator('.react-flow')).toBeVisible()

    // Give React a moment to trigger any potential update-loop errors.
    await page.waitForTimeout(1000)

    expect(pageErrors).toHaveLength(0)
    expect(consoleErrors).toHaveLength(0)
  })
})
