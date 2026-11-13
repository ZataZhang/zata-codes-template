import { expect, test, type Page } from '@playwright/test'
import { getBaseUrl } from '../../support/env'
import {
  beginOidcAuthorization,
  createRecordedContext,
  fillTestIdentity,
  readApiResponseFromPage,
  requireOidcTestEnvironment,
  saveEvidenceScreenshot,
  saveEvidenceVideo,
  waitForCanonicalRequest,
  waitForCanonicalResponse,
} from '../../support/oidc-test-helpers'

const registrationPrdStem =
  'P1-FEAT-20261112-134527-registration-policy-and-user-oidc'

type RegistrationPolicy = {
  registration_mode: 'both' | 'oidc_only' | 'closed'
  allowed_email_domains: string[]
}

async function saveRegistrationPolicy(
  page: Page,
  registrationPolicy: RegistrationPolicy
): Promise<void> {
  const registrationModeId = registrationPolicy.registration_mode.replace('_', '-')
  await page.locator(`#registration-${registrationModeId}`).click()
  await page
    .getByTestId('registration-policy-domains')
    .fill(registrationPolicy.allowed_email_domains.join('\n'))
  const saveResponsePromise = waitForCanonicalResponse(
    page,
    'PUT',
    '/api/admin/settings/registration-policy'
  )
  await page.getByTestId('registration-policy-save').click()
  const saveResponse = await saveResponsePromise
  expect(saveResponse.status()).toBe(200)
  expect(saveResponse.request().postDataJSON()).toEqual(registrationPolicy)
}

test('saved OIDC-only registration policy opens an allowed user through the real login flow', async ({
  browser,
  page,
}) => {
  test.setTimeout(180_000)
  const issuerUrl = requireOidcTestEnvironment()
  const currentPolicyResponsePromise = waitForCanonicalResponse(
    page,
    'GET',
    '/api/admin/settings/registration-policy'
  )
  await page.goto('/registration')
  const currentPolicyResponse = await currentPolicyResponsePromise
  expect(currentPolicyResponse.status()).toBe(200)
  const previousPolicy = (await currentPolicyResponse.json()) as RegistrationPolicy

  const uniqueSuffix = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const userEmail = `registration-${uniqueSuffix}@example.com`
  const identitySubject = `playwright-public-${uniqueSuffix}`
  const publicContext = await createRecordedContext(browser, getBaseUrl())
  const publicPage = await publicContext.newPage()

  try {
    await saveRegistrationPolicy(page, {
      registration_mode: 'oidc_only',
      allowed_email_domains: ['example.com'],
    })
    await expect(page.locator('#registration-oidc-only')).toHaveAttribute(
      'aria-checked',
      'true'
    )
    await expect(page.getByTestId('registration-policy-domains')).toHaveValue(
      'example.com'
    )
    await saveEvidenceScreenshot(
      page,
      registrationPrdStem,
      'rv-1-registration-settings.png'
    )

    const deniedIdentityContext = await createRecordedContext(browser, getBaseUrl())
    const deniedIdentityPage = await deniedIdentityContext.newPage()
    try {
      await deniedIdentityPage.goto('/register')
      await expect(
        deniedIdentityPage.getByTestId('registration-oidc-only-state')
      ).toBeVisible()
      const deniedAuthorizationUrl = await beginOidcAuthorization(
        deniedIdentityPage,
        {
          buttonTestId: 'public-oidc-sign-in',
          startApiPath: '/api/auth/oidc/start',
          issuerUrl,
        }
      )
      const deniedState = deniedAuthorizationUrl.searchParams.get('state')
      expect(deniedState).toBeTruthy()
      expect(deniedAuthorizationUrl.searchParams.get('code_challenge_method')).toBe(
        'S256'
      )
      await fillTestIdentity(deniedIdentityPage, {
        email: `x-${uniqueSuffix}@other.test`,
        subject: `playwright-public-denied-${uniqueSuffix}`,
        emailVerified: true,
      })
      const deniedCallbackRequestPromise = waitForCanonicalRequest(
        deniedIdentityPage,
        'GET',
        '/api/auth/oidc/callback'
      )
      const deniedCallbackResponsePromise = waitForCanonicalResponse(
        deniedIdentityPage,
        'GET',
        '/api/auth/oidc/callback'
      )
      await deniedIdentityPage.getByTestId('oidc-test-submit').click()
      const [deniedCallbackRequest, deniedCallbackResponse] = await Promise.all([
        deniedCallbackRequestPromise,
        deniedCallbackResponsePromise,
      ])
      expect(new URL(deniedCallbackRequest.url()).searchParams.get('state')).toBe(
        deniedState
      )
      expect(new URL(deniedCallbackRequest.url()).searchParams.get('code')).toBeTruthy()
      expect(deniedCallbackResponse.status()).toBe(302)
      await expect(deniedIdentityPage).toHaveURL(/\/login\?sso_error=1/)
      await expect(
        deniedIdentityPage.getByText(
          'Organization sign-in failed. Please contact your administrator.',
          { exact: true }
        )
      ).toBeVisible()
      const deniedUserSession = await readApiResponseFromPage<{
        user_id: string
        email: string
      }>(deniedIdentityPage, '/api/auth/me')
      expect(deniedUserSession.status).toBe(401)
      expect(
        (await deniedIdentityContext.cookies(getBaseUrl())).some(
          (cookie) => cookie.name === 'session_id'
        )
      ).toBe(false)
      await saveEvidenceScreenshot(
        deniedIdentityPage,
        registrationPrdStem,
        'rv-1-user-oidc-domain-rejection.png'
      )
      await saveEvidenceVideo(
        deniedIdentityPage,
        registrationPrdStem,
        'rv-1-user-oidc-domain-rejection.webm'
      )
    } finally {
      await deniedIdentityContext.close()
    }

    await publicPage.goto('/register')
    await expect(publicPage.getByTestId('registration-oidc-only-state')).toBeVisible()
    await expect(publicPage.getByTestId('public-registration-password-form')).toHaveCount(0)
    await expect(publicPage.locator('input[type="password"]')).toHaveCount(0)
    await saveEvidenceScreenshot(
      publicPage,
      registrationPrdStem,
      'rv-1-register-oidc-only.png'
    )

    const startResponsePromise = waitForCanonicalResponse(
      publicPage,
      'GET',
      '/api/auth/oidc/start'
    )
    const startRequestPromise = waitForCanonicalRequest(
      publicPage,
      'GET',
      '/api/auth/oidc/start'
    )
    await publicPage.getByTestId('public-oidc-sign-in').click()
    const [startResponse, startRequest] = await Promise.all([
      startResponsePromise,
      startRequestPromise,
    ])
    expect(startRequest.url()).toContain('/api/auth/oidc/start')
    expect(startResponse.status()).toBe(302)
    const authorizationUrl = new URL(startResponse.headers().location ?? '')
    expect(authorizationUrl.origin).toBe(issuerUrl)
    expect(authorizationUrl.searchParams.get('code_challenge_method')).toBe('S256')
    const authorizationState = authorizationUrl.searchParams.get('state')
    expect(authorizationState).toBeTruthy()
    expect(authorizationUrl.searchParams.get('nonce')).toBeTruthy()
    expect(authorizationUrl.searchParams.get('code_challenge')).toBeTruthy()

    await fillTestIdentity(publicPage, {
      email: userEmail,
      subject: identitySubject,
      emailVerified: true,
    })
    const callbackRequestPromise = waitForCanonicalRequest(
      publicPage,
      'GET',
      '/api/auth/oidc/callback'
    )
    const callbackResponsePromise = waitForCanonicalResponse(
      publicPage,
      'GET',
      '/api/auth/oidc/callback'
    )
    await publicPage.getByTestId('oidc-test-submit').click()
    const [callbackRequest, callbackResponse] = await Promise.all([
      callbackRequestPromise,
      callbackResponsePromise,
    ])
    expect(new URL(callbackRequest.url()).searchParams.get('state')).toBe(
      authorizationState
    )
    expect(new URL(callbackRequest.url()).searchParams.get('code')).toBeTruthy()
    expect(callbackResponse.status()).toBe(302)

    await expect(publicPage).toHaveURL(/\/app\/dashboard/)
    const authenticatedUser = await readApiResponseFromPage<{
      user_id: string
      email: string
      display_name: string
    }>(publicPage, '/api/auth/me')
    expect(authenticatedUser.status).toBe(200)
    expect(authenticatedUser.body?.email).toBe(userEmail)

    const freshPublicContext = await browser.newContext({
      baseURL: getBaseUrl(),
      storageState: await publicContext.storageState(),
    })
    const freshPublicPage = await freshPublicContext.newPage()
    await freshPublicPage.goto('/login')
    const freshUserSession = await readApiResponseFromPage<{
      user_id: string
      email: string
    }>(freshPublicPage, '/api/auth/me')
    expect(freshUserSession.status).toBe(200)
    expect(freshUserSession.body?.user_id).toBe(authenticatedUser.body?.user_id)
    await freshPublicContext.close()
    await saveEvidenceScreenshot(
      publicPage,
      registrationPrdStem,
      'rv-1-user-oidc-dashboard.png'
    )
    await saveEvidenceVideo(
      publicPage,
      registrationPrdStem,
      'rv-1-user-oidc-sign-in.webm'
    )
  } finally {
    if (!publicContext.pages().every((contextPage) => contextPage.isClosed())) {
      await publicContext.close()
    }
    await saveRegistrationPolicy(page, previousPolicy)
  }
})
