import { expect, test as setup } from '@playwright/test'
import {
  ensureAuthDirectory,
  getAdminAuthStorageStatePath,
  getAdminCredentials,
} from '../../support/env'

/**
 * Admin auth setup — logs into the admin frontend via its `/api` proxy and
 * persists cookies to .auth/admin-session.json. Separate from the public auth
 * setup: admin uses the `/admin/auth/login` endpoint and the `admin_session_id`
 * cookie, so the two domains never share a stored session.
 */
setup('admin authenticate and persist storage state', async ({ page }) => {
  ensureAuthDirectory()

  const credentials = getAdminCredentials()

  await page.goto('/sign-in')
  await page.waitForLoadState('networkidle')

  const response = await page.evaluate(async (creds) => {
    const res = await fetch('/api/admin/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(creds),
      credentials: 'include',
    })
    return { status: res.status }
  }, credentials)

  expect(response.status).toBe(200)

  // Authenticated admin landing route must not bounce back to /sign-in.
  await page.goto('/')
  await expect(page).not.toHaveURL(/\/sign-in/)

  await page.context().storageState({ path: getAdminAuthStorageStatePath() })
})
