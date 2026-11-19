import { writeFile } from 'node:fs/promises'
import { chromium } from '/Users/zata/code/zata_code_template/tests/playwright-e2e/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs'

const browserEndpoint = process.env.PLAYWRIGHT_REMOTE_BROWSER_WS
const adminBaseUrl = process.env.RV7_ADMIN_BASE_URL
const outputPath = process.env.RV7_ADMIN_UI_OUTPUT
const organizationUsername = process.env.RV7_ORG_ADMIN_USERNAME
const organizationPassword = process.env.RV7_ORG_ADMIN_PASSWORD
const platformUsername = process.env.RV7_PLATFORM_ADMIN_USERNAME
const platformPassword = process.env.RV7_PLATFORM_ADMIN_PASSWORD
const externalEndpoint = process.env.RV7_OFFICIAL_A2A_ENDPOINT
const credentialAlias = process.env.RV7_PEER_CREDENTIAL_ALIAS

for (const [name, value] of Object.entries({
  adminBaseUrl,
  outputPath,
  organizationUsername,
  organizationPassword,
  platformUsername,
  platformPassword,
  externalEndpoint,
  credentialAlias,
})) {
  if (!value) throw new Error(`missing required RV-7 UI input: ${name}`)
}

const browser = browserEndpoint
  ? await chromium.connect(browserEndpoint, { timeout: 15_000 })
  : await chromium.launch({ headless: true })
const result = {}

async function signIn(page, username, password) {
  const response = await page.goto(`${adminBaseUrl}/sign-in`, { waitUntil: 'domcontentloaded' })
  const identifierInput = page.getByTestId('admin-login-identifier-input')
  try {
    await identifierInput.fill(username)
  } catch (error) {
    console.log('Admin sign-in page diagnostic:', {
      status: response?.status(),
      url: page.url(),
      title: await page.title(),
      body: (await page.locator('body').innerText()).slice(0, 500),
    })
    throw error
  }
  await page.getByTestId('admin-login-password-input').fill(password)
  const loginResponsePromise = page.waitForResponse((response) =>
    new URL(response.url()).pathname === '/api/admin/auth/login' &&
    response.request().method() === 'POST',
  )
  await page.getByTestId('admin-login-submit-button').click({ noWaitAfter: true })
  const loginResponse = await loginResponsePromise
  if (loginResponse.status() !== 200) {
    throw new Error(`admin login returned HTTP ${loginResponse.status()}`)
  }
  await page.waitForURL((url) => !url.pathname.endsWith('/sign-in'), { timeout: 15_000 })
  try {
    await page.waitForFunction(async () => {
      const response = await fetch('/api/admin/auth/me', { credentials: 'include' })
      return response.status === 200
    }, null, { polling: 250, timeout: 15_000 })
  } catch (error) {
    const sessionStatus = await page.evaluate(async () => {
      const response = await fetch('/api/admin/auth/me', { credentials: 'include' })
      return response.status
    }).catch(() => 0)
    console.log('Admin session readiness diagnostic:', {
      url: page.url(),
      loginStatus: loginResponse.status(),
      sessionStatus,
    })
    throw error
  }
}

try {
  const adminContext = await browser.newContext()
  let organizationPage = await adminContext.newPage()
  await signIn(organizationPage, organizationUsername, organizationPassword)
  await organizationPage.goto(`${adminBaseUrl}/agents/`, { waitUntil: 'domcontentloaded' })
  await organizationPage.getByRole('heading', { name: /Agents and Skills|Agent 与 Skill/ }).waitFor()

  const suffix = `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
  const peerName = `RV7-UI-Peer-${suffix}`
  const peerForm = organizationPage.locator('form:has(input[type="url"])')
  await peerForm.locator('input').nth(0).fill(peerName)
  await peerForm.locator('input').nth(1).fill(externalEndpoint)
  await peerForm.locator('input').nth(2).fill(externalEndpoint)
  await peerForm.locator('input').nth(3).fill(credentialAlias)
  const registeredPeerResponse = organizationPage.waitForResponse((response) =>
    response.url().includes('/api/admin/a2a-peers') && response.request().method() === 'POST' && response.status() === 201,
  )
  await peerForm.locator('button[type="submit"]').click()
  const registeredPeer = await (await registeredPeerResponse).json()
  result.peerId = registeredPeer.id
  await organizationPage.getByText(peerName, { exact: true }).waitFor()
  console.log('Organization administrator UI: external peer submitted for approval.')
  await adminContext.clearCookies()
  console.log('Organization admin session cleared before platform approval.')

  const platformPage = organizationPage
  await signIn(platformPage, platformUsername, platformPassword)
  const platformResponse = await platformPage.goto(`${adminBaseUrl}/a2a-approvals/`, {
    waitUntil: 'domcontentloaded',
  })
  const platformHeading = platformPage.locator('h1').first()
  platformPage.on('pageerror', (error) => console.log('Platform page error:', error.message))
  platformPage.on('console', (message) => {
    if (message.type() === 'error') console.log('Platform console error:', message.text())
  })
  try {
    await platformHeading.waitFor({ timeout: 15_000 })
  } catch (error) {
    const pageText = (await platformPage.locator('body').innerText()).slice(0, 600)
    const pageState = await platformPage.evaluate(() => ({
      readyState: document.readyState,
      bodyHtml: document.body.innerHTML.slice(0, 1000),
    }))
    console.log('Platform review page diagnostic:', {
      url: platformPage.url(),
      title: await platformPage.title(),
      responseStatus: platformResponse?.status(),
      pageText,
      pageState,
    })
    throw error
  }
  const approvalTitle = await platformHeading.innerText()
  if (!approvalTitle.toLowerCase().includes('a2a')) {
    throw new Error(`unexpected platform review page title: ${approvalTitle}`)
  }
  await platformPage.getByText(peerName, { exact: true }).waitFor({ timeout: 15_000 })
  const approvedPeerResponse = platformPage.waitForResponse((response) =>
    response.url().includes(`/api/admin/a2a-peers/${result.peerId}/approve`) &&
    response.request().method() === 'POST' &&
    response.status() === 200,
  )
  await platformPage
    .getByRole('button', { name: /Approve destination|批准目标/ })
    .first()
    .click({ noWaitAfter: true })
  await approvedPeerResponse
  await platformPage.getByText(/A2A destination approved|A2A 目标已批准/).waitFor({ timeout: 10_000 })
  console.log('Platform administrator UI: registered peer approved through the review page.')

  await adminContext.clearCookies()
  await signIn(organizationPage, organizationUsername, organizationPassword)
  await organizationPage.goto(`${adminBaseUrl}/agents/`, { waitUntil: 'domcontentloaded' })
  await organizationPage
    .getByRole('heading', { name: /Agents and Skills|Agent 与 Skill/ })
    .waitFor({ timeout: 15_000 })
  const approvedPeer = organizationPage.locator('div.rounded.border').filter({ hasText: peerName })
  await approvedPeer.getByText(/Approved|已批准/).waitFor()

  const agentName = `RV7-UI-Agent-${suffix}`
  const agentForm = organizationPage.locator('form').first()
  await agentForm.locator('input').nth(0).fill(agentName)
  await agentForm.locator('input').nth(1).fill('RV-7 real admin interface validation')
  await agentForm.locator('input').nth(2).fill('rv58-stub-model')
  await agentForm.locator('textarea').fill('Respond concisely for protocol validation.')
  await organizationPage.getByRole('checkbox', { name: peerName }).check()
  const createdAgentResponse = organizationPage.waitForResponse((response) =>
    response.url().includes('/api/admin/agents') && response.request().method() === 'POST' && response.status() === 201,
  )
  await agentForm.locator('button[type="submit"]').click()
  const createdAgentHttpResponse = await createdAgentResponse
  const createdAgentRequest = createdAgentHttpResponse.request().postDataJSON()
  const createdAgent = await createdAgentHttpResponse.json()
  result.agentId = createdAgent.id
  if (!createdAgentRequest.peer_ids?.includes(registeredPeer.id)) {
    throw new Error('Agent creation request omitted the selected approved A2A peer.')
  }
  if (!createdAgent.allowed_peer_ids?.includes(registeredPeer.id)) {
    throw new Error('Agent creation did not persist the selected approved A2A peer.')
  }
  console.log('Created Agent selected peer ID:', registeredPeer.id)

  const agentCard = organizationPage.locator(`[data-testid="managed-agent-${result.agentId}"]`)
  await agentCard.waitFor()
  const agentCardText = await agentCard.innerText()
  if (!agentCardText.includes(peerName)) {
    throw new Error(`Agent card omitted its selected peer name: ${agentCardText}`)
  }
  await Promise.all([
    organizationPage.waitForResponse((response) =>
      response.url().includes(`/api/admin/agents/${result.agentId}/publish`) && response.status() === 200,
    ),
    agentCard.locator('button').nth(0).click(),
  ])
  await agentCard.getByText(/Published|已发布/).waitFor()

  const credentialResponse = organizationPage.waitForResponse((response) =>
    response.url().includes(`/api/admin/agents/${result.agentId}/a2a-credentials`) && response.status() === 201,
  )
  await agentCard.locator('button').nth(2).click()
  const credential = await (await credentialResponse).json()
  result.inboundToken = credential.token
  const tokenPanel = organizationPage.locator('div.rounded-md.border').filter({ hasText: /Copy this token now|现在复制此令牌/ })
  await tokenPanel.waitFor()
  await organizationPage.getByRole('button', { name: /Dismiss|关闭/ }).click()

  await organizationPage.screenshot({
    path: `${process.env.RV7_EVIDENCE_DIR}/rv-7-a2a-admin.png`,
    fullPage: true,
  })
  result.agentName = agentName
  result.peerName = peerName
  await writeFile(outputPath, `${JSON.stringify(result)}\n`, { encoding: 'utf8', mode: 0o600 })
  await adminContext.close()
  console.log('RV-7 admin UI evidence: rv-7-a2a-admin.png')
} finally {
  await browser.close()
}
