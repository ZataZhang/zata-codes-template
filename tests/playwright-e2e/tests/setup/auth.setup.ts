import { expect, test as setup } from '@playwright/test'
import { ensureAuthDirectory, getAuthStorageStatePath, getCredentials } from '../../support/env'

/**
 * Auth setup step — logs in via the frontend API proxy using fetch and persists
 * cookies to .auth/session.json so tests don't need to re-authenticate.
 *
 * We call /api/auth/login from the frontend origin so the session cookie is set
 * on the same domain the browser tests will use.
 */
setup('authenticate and persist storage state', async ({ page }) => {
  ensureAuthDirectory()

  const credentials = getCredentials()

  await page.goto('/login')
  await page.waitForLoadState('networkidle')

  const response = await page.evaluate(
    async (creds) => {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(creds),
        credentials: 'include',
      })
      return { status: res.status, statusText: res.statusText }
    },
    credentials,
  )

  expect(response.status).toBe(200)

  await page.goto('/app/dashboard')
  await expect(page).toHaveURL(/\/app\/dashboard/)

  await page.context().storageState({ path: getAuthStorageStatePath() })
})
