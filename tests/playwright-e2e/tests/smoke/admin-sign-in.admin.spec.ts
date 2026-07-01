import { expect, test } from '@playwright/test'
import { getAdminBaseUrl, getAdminCredentials } from '../../support/env'

test.use({
  baseURL: getAdminBaseUrl(),
  // This test exercises the sign-in flow from an unauthenticated state, so
  // clear any storage state inherited from the surrounding admin project.
  storageState: { cookies: [], origins: [] },
})

test.describe('admin sign-in smoke', () => {
  test('admin sign-in form logs in and redirects to dashboard', async ({ page }) => {
    const credentials = getAdminCredentials()

    await page.goto('/sign-in')
    await expect(page.getByTestId('admin-login-identifier-input')).toBeVisible()

    await page.getByTestId('admin-login-identifier-input').fill(credentials.identifier)
    await page.getByTestId('admin-login-password-input').fill(credentials.password)
    await page.getByTestId('admin-login-submit-button').click()

    await expect(page).not.toHaveURL(/\/sign-in/)
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible()
  })
})
