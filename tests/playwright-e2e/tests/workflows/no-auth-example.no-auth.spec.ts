/**
 * No-auth test pattern.
 *
 * Use this template for tests that target a surface that does NOT require
 * a logged-in session — e.g.:
 *   - A public-facing UI
 *   - A health / status endpoint
 *   - A login page
 *
 * Naming convention: *.no-auth.spec.ts
 * These files are picked up by the 'no-auth' project in playwright.config.ts
 * and are excluded from the 'chromium' project (which requires auth.setup.ts).
 *
 * Run with:
 *   playwright test --project=no-auth
 *
 * Point at a remote env (no local stack needed):
 *   PLAYWRIGHT_SKIP_STACK_BOOT=1 \
 *   PLAYWRIGHT_BASE_URL=https://your-staging-url \
 *   PLAYWRIGHT_HEALTH_URL=https://your-staging-url \
 *   playwright test --project=no-auth
 */
import { expect, test } from '@playwright/test'

test.describe('public surface smoke test', () => {
  test('login page loads and shows the login form', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByTestId('login-identifier-input')).toBeVisible()
    await expect(page.getByTestId('login-password-input')).toBeVisible()
    await expect(page.getByTestId('login-submit-button')).toBeVisible()
  })

  test('captures a screenshot artifact', async ({ page }, testInfo) => {
    await page.goto('/login')
    await expect(page.getByTestId('login-submit-button')).toBeVisible()

    const screenshotPath = testInfo.outputPath('login-page.png')
    await page.screenshot({ path: screenshotPath, fullPage: true, animations: 'disabled' })
    await testInfo.attach('login-page', { path: screenshotPath, contentType: 'image/png' })
  })
})
