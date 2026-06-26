import { expect, test } from '@playwright/test'

/**
 * Admin user-management e2e (admin auth domain).
 *
 * Verifies the full browser path: admin session → admin frontend `users` page →
 * `/admin/users` API → real public_user data, plus the disable flow. Creates its
 * own throwaway public user as the disable target so it never affects other
 * fixtures (e.g. the public e2e login user).
 */
test.describe('admin user management', () => {
  test('lists real public users and disables a target user', async ({ page }) => {
    await page.goto('/users')

    // Admin is authenticated (storageState) and the users page renders.
    await expect(page.getByRole('heading', { name: '用户' })).toBeVisible()

    // Create a throwaway public user via the admin frontend's /api proxy.
    const targetEmail = `admin-e2e-${Date.now()}@example.com`
    const registerStatus = await page.evaluate(async (email) => {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          display_name: 'Admin E2E Target',
          email,
          password: 'secret123',
        }),
        credentials: 'omit',
      })
      return res.status
    }, targetEmail)
    expect([200, 201]).toContain(registerStatus)

    // Search for the new user and confirm it shows as active.
    await page.getByPlaceholder(/搜索/).fill(targetEmail)
    await page.getByRole('button', { name: '搜索' }).click()

    const targetRow = page.getByRole('row').filter({ hasText: targetEmail })
    await expect(targetRow).toBeVisible()
    await expect(targetRow.getByText('正常')).toBeVisible()

    // Disable it and confirm in the dialog.
    await targetRow.getByRole('button', { name: '禁用' }).click()
    await page.getByRole('button', { name: '确认' }).click()

    // Toast feedback plus the row status flipping to disabled.
    await expect(page.getByText(/已禁用/)).toBeVisible()
    await expect(targetRow.getByText('已禁用')).toBeVisible()
  })
})
