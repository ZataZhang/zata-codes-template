import { appendFileSync, mkdirSync } from 'node:fs'
import { randomUUID } from 'node:crypto'
import { resolve } from 'node:path'
import {
  expect,
  request,
  type Browser,
  type BrowserContext,
  type Page,
} from '@playwright/test'
import { humanPause } from '../../support/demo-helpers'
import {
  getAdminBaseUrl,
  getAdminCredentials,
  getApiBaseUrl,
  getBaseUrl,
} from '../../support/env'

export type AgentScenario = {
  organizationId: string
  organizationName: string
  adminIdentifier: string
  adminPassword: string
  memberEmail: string
  memberPassword: string
  memberId: string
  dispose: () => Promise<void>
}

/** 通过正式 API 准备两域账号；Agent、Skill 与 Run 仍必须从真实页面创建。 */
export async function createAgentScenario(label: string): Promise<AgentScenario> {
  const suffix = `${label}-${Date.now()}-${Math.floor(Math.random() * 1000)}`
  const platformContext = await request.newContext({ baseURL: getApiBaseUrl() })
  const platformCredentials = getAdminCredentials()
  const loginResponse = await platformContext.post('/admin/auth/login', {
    data: platformCredentials,
  })
  expect(loginResponse.ok()).toBeTruthy()

  const organizationName = `RV ${suffix}`
  const organizationResponse = await platformContext.post('/admin/organizations', {
    data: { name: organizationName },
  })
  expect(organizationResponse.ok()).toBeTruthy()
  const organization = (await organizationResponse.json()) as { id: string }

  const adminIdentifier = `rv-admin-${suffix}`
  const adminPassword = `RvAdmin-${suffix}-pass`
  const adminResponse = await platformContext.post('/admin/admins', {
    data: {
      username: adminIdentifier,
      email: `${adminIdentifier}@example.test`,
      role: 'org',
      organization_id: organization.id,
      password: adminPassword,
    },
  })
  expect(adminResponse.ok()).toBeTruthy()

  const memberEmail = `rv-member-${suffix}@example.test`
  const memberPassword = `RvMember-${suffix}-pass`
  const memberResponse = await platformContext.post('/auth/register', {
    data: {
      display_name: `RV ${label}`,
      email: memberEmail,
      password: memberPassword,
    },
  })
  expect(memberResponse.ok()).toBeTruthy()
  const member = (await memberResponse.json()) as { user_id: string }
  const membershipResponse = await platformContext.patch(
    `/admin/users/${member.user_id}/organization`,
    { data: { organization_id: organization.id } },
  )
  expect(membershipResponse.ok()).toBeTruthy()

  return {
    organizationId: organization.id,
    organizationName,
    adminIdentifier,
    adminPassword,
    memberEmail,
    memberPassword,
    memberId: member.user_id,
    dispose: async () => platformContext.dispose(),
  }
}

/** 经管理前端的同源代理登录组织管理员。 */
export async function signInOrganizationAdmin(
  browser: Browser,
  scenario: AgentScenario,
): Promise<BrowserContext> {
  const context = await browser.newContext({
    baseURL: getAdminBaseUrl(),
    viewport: { width: 1440, height: 1200 },
    ...(process.env.PLAYWRIGHT_RECORD_VIDEO === '1'
      ? { recordVideo: { dir: evidencePath('videos') } }
      : {}),
  })
  const page = await context.newPage()
  await page.goto('/sign-in', { waitUntil: 'commit' })
  let sessionStatus = 0
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const loginStatus = await page.evaluate(async (credentials) => {
      const response = await fetch('/api/admin/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
        credentials: 'include',
      })
      return response.status
    }, { identifier: scenario.adminIdentifier, password: scenario.adminPassword })
    expect(loginStatus).toBe(200)
    sessionStatus = await page.evaluate(async () => {
      const response = await fetch('/api/admin/auth/me', {
        credentials: 'include',
        cache: 'no-store',
      })
      return response.status
    })
    if (sessionStatus === 200) {
      if (process.env.PLAYWRIGHT_RECORD_VIDEO !== '1') await page.close()
      return context
    }
    await page.waitForTimeout(250)
  }
  throw new Error(`admin login did not persist a session; /api/admin/auth/me returned ${sessionStatus}`)
}

/** 经成员前台的同源代理登录组织成员。 */
export async function signInMember(
  browser: Browser,
  scenario: AgentScenario,
): Promise<BrowserContext> {
  const context = await browser.newContext({
    baseURL: getBaseUrl(),
    viewport: { width: 1440, height: 1200 },
    ...(process.env.PLAYWRIGHT_RECORD_VIDEO === '1'
      ? { recordVideo: { dir: evidencePath('videos') } }
      : {}),
  })
  const page = await context.newPage()
  await page.goto('/login', { waitUntil: 'commit' })
  let sessionStatus = 0
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const loginStatus = await page.evaluate(async (credentials) => {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials),
        credentials: 'include',
      })
      return response.status
    }, { identifier: scenario.memberEmail, password: scenario.memberPassword })
    expect(loginStatus).toBe(200)
    sessionStatus = await page.evaluate(async () => {
      const response = await fetch('/api/auth/me', {
        credentials: 'include',
        cache: 'no-store',
      })
      return response.status
    })
    if (sessionStatus === 200) {
      if (process.env.PLAYWRIGHT_RECORD_VIDEO !== '1') await page.close()
      return context
    }
    await page.waitForTimeout(250)
  }
  throw new Error(`member login did not persist a session; /api/auth/me returned ${sessionStatus}`)
}

/** 在全新浏览器上下文中通过正式同源 API 登录成员。 */
export async function signInMemberInFreshContext(
  browser: Browser,
  scenario: AgentScenario,
): Promise<BrowserContext> {
  const context = await browser.newContext({
    baseURL: getBaseUrl(),
    viewport: { width: 1440, height: 1200 },
  })
  const page = await context.newPage()
  try {
    await page.goto('/login', { waitUntil: 'commit' })
    let sessionStatus = 0
    for (let attempt = 0; attempt < 2; attempt += 1) {
      const loginStatus = await page.evaluate(async (credentials) => {
        const response = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(credentials),
          credentials: 'include',
        })
        return response.status
      }, { identifier: scenario.memberEmail, password: scenario.memberPassword })
      expect(loginStatus).toBe(200)
      sessionStatus = await page.evaluate(async () => {
        const response = await fetch('/api/auth/me', {
          credentials: 'include',
          cache: 'no-store',
        })
        return response.status
      })
      if (sessionStatus === 200) {
        await page.close()
        return context
      }
      await page.waitForTimeout(250)
    }
    throw new Error(`fresh member login did not persist; /api/auth/me returned ${sessionStatus}`)
  } catch (error) {
    await context.close()
    throw error
  }
}

/** 保存指定 Playwright 页面的录屏到对应 RV 证据文件名。 */
export async function savePageVideo(page: Page, fileName: string): Promise<void> {
  const video = page.video()
  if (!video) return
  if (!page.isClosed()) await page.close()
  await video.saveAs(evidencePath(fileName))
}

/** 从真实管理页创建声明式 Skill。 */
export async function createSkillThroughUi(
  page: Page,
  input: { name: string; body: string; onProgress?: (checkpoint: string) => void },
): Promise<string> {
  const initialSkillListPromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname === '/api/admin/skills',
    { timeout: 60_000 },
  )
  await page.goto('/agents', { waitUntil: 'commit' })
  expect((await initialSkillListPromise).status()).toBe(200)
  input.onProgress?.('admin Skill page navigation and list response completed')
  const form = page.locator('form').filter({
    has: page.getByRole('button', { name: 'Create Skill' }),
  })
  await form.getByLabel('Skill name').fill(input.name)
  input.onProgress?.('admin Skill name field accepted input')
  await form.getByLabel('Description').fill('Versioned reference for realistic validation')
  await form.getByLabel('Declarative Skill content').fill(input.body)
  const createSkillResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/admin/skills',
    { timeout: 30_000 },
  )
  await form.getByRole('button', { name: 'Create Skill' }).click()
  const createSkillResponse = await createSkillResponsePromise
  expect(createSkillResponse.status()).toBe(201)
  const createdSkill = (await createSkillResponse.json()) as {
    id: string
    name: string
    current_version: number
  }
  expect(createdSkill.name).toBe(input.name)
  expect(createdSkill.current_version).toBe(1)
  await expect(form.getByLabel('Skill name')).toHaveValue('', { timeout: 30_000 })

  // Wait for the actual page refresh triggered by the successful form submit.
  const skillHistoryPicker = page.getByLabel('Select Skill').nth(1)
  await expect(
    skillHistoryPicker.getByRole('option', { name: `${input.name} · v1` }),
  ).toHaveText(`${input.name} · v1`, { timeout: 60_000 })
  return createdSkill.id
}

/** 从真实管理页创建并发布绑定 Skill 的 Agent，返回页面展示的 Agent ID。 */
export async function createAgentThroughUi(
  page: Page,
  input: { name: string; skillName: string },
): Promise<string> {
  const form = page.locator('form').filter({
    has: page.getByRole('button', { name: 'Create draft Agent' }),
  })
  await form.getByLabel('Name', { exact: true }).fill(input.name)
  await form.getByLabel('Description').fill('Real user flow Agent')
  await form.getByLabel('Select Skill').selectOption({ label: `${input.skillName} · v1` })
  await form.getByLabel('Agent instructions').fill('Answer briefly and use the supplied Skill reference.')
  await form.getByRole('button', { name: 'Create draft Agent' }).click()

  const agentCard = page.locator('div[data-testid^="managed-agent-"]').filter({ hasText: input.name })
  await expect(agentCard).toBeVisible()
  const agentId = (await agentCard.locator('p.font-mono').innerText()).trim()
  expect(agentId).not.toBe('')
  await agentCard.getByRole('button', { name: 'Publish', exact: true }).click()
  await expect(agentCard).toContainText('Published')
  await expect(agentCard.getByRole('link', { name: /A2A Agent Card:/ })).toBeVisible()
  return agentId
}

/** 通过已认证的组织管理页正式 API 准备快照验证所需 Agent。 */
export async function createPublishedAgentThroughApi(
  page: Page,
  input: { name: string; skillId: string },
): Promise<string> {
  return page.evaluate(async (agentInput) => {
    const createResponse = await fetch('/api/admin/agents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        name: agentInput.name,
        description: 'Real Skill version snapshot validation',
        instructions: 'Answer briefly using the assigned Skill reference.',
        model_name: null,
        skill_id: agentInput.skillId,
        peer_ids: [],
      }),
    })
    if (createResponse.status !== 201) {
      throw new Error(`Agent creation returned HTTP ${createResponse.status}`)
    }
    const createdAgent = (await createResponse.json()) as { id: string }
    const publishResponse = await fetch(`/api/admin/agents/${createdAgent.id}/publish`, {
      method: 'POST',
      credentials: 'include',
    })
    if (publishResponse.status !== 200) {
      throw new Error(`Agent publish returned HTTP ${publishResponse.status}`)
    }
    return createdAgent.id
  }, input)
}

/** 从已认证成员会话正式创建 Run 并以独立请求读取终态快照。 */
export async function createAgentRunThroughApi(
  context: BrowserContext,
  input: { agentId: string; message: string },
): Promise<{
  id: string
  status: string
  assistant_message: string | null
  skill_version: number | null
}> {
  const createResponse = await context.request.post(`${getBaseUrl()}/api/agent-runs`, {
    headers: { 'Idempotency-Key': randomUUID() },
    data: {
      agent_id: input.agentId,
      message: input.message,
    },
    timeout: 60_000,
  })
  expect(
    createResponse.status(),
    `Run creation returned HTTP ${createResponse.status()}: ${await createResponse.text()}`,
  ).toBe(202)
  const createdRun = (await createResponse.json()) as { id: string }
  const deadline = Date.now() + 60_000
  let agentRun: {
    id: string
    status: string
    assistant_message: string | null
    skill_version: number | null
  } | null = null
  while (Date.now() < deadline) {
    const readResponse = await context.request.get(
      `${getBaseUrl()}/api/agent-runs/${createdRun.id}`,
      { timeout: 60_000 },
    )
    expect(readResponse.status()).toBe(200)
    const runDetail = (await readResponse.json()) as NonNullable<typeof agentRun>
    if (runDetail.status === 'succeeded' || runDetail.status === 'failed') {
      agentRun = runDetail
      break
    }
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
  if (!agentRun) throw new Error('Run did not reach a terminal state within 60 seconds')
  expect(agentRun.status).toBe('succeeded')
  return agentRun
}

/** 从真实成员页提交消息，核对增量回复，并等待持久终态。 */
export async function runAgentThroughUi(
  page: Page,
  input: {
    agentName: string
    message: string
    requireIncrementalReply?: boolean
    expectedTerminalStatus?: 'succeeded' | 'failed'
    onIncrementalReply?: (partialReply: string) => Promise<void>
    onProgress?: (checkpoint: string) => void
  },
): Promise<string> {
  const agentDirectoryResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'GET' &&
      new URL(response.url()).pathname === '/api/agents',
    { timeout: 30_000 },
  )
  await page.goto('/app/agents', { waitUntil: 'commit' })
  input.onProgress?.('member Agent page navigation committed')
  const agentDirectoryResponse = await agentDirectoryResponsePromise
  input.onProgress?.('member Agent directory response received')
  const agentDirectoryStatus = agentDirectoryResponse.status()
  expect(
    agentDirectoryStatus,
    `member Agent directory returned HTTP ${agentDirectoryStatus}`,
  ).toBe(200)
  const agentDirectory = (await agentDirectoryResponse.json()) as {
    items: Array<{ name: string }>
  }
  const visibleAgentNames = agentDirectory.items.map((agent) => agent.name)
  expect(
    visibleAgentNames,
    `member Agent directory did not contain ${input.agentName}; returned ${JSON.stringify(visibleAgentNames)}`,
  ).toContain(input.agentName)
  const agentButton = page
    .locator('button[aria-pressed]')
    .filter({ hasText: input.agentName })
  await expect(agentButton).toBeVisible({ timeout: 30_000 })
  await agentButton.click()
  await page.getByLabel('Write a message…').fill(input.message)
  input.onProgress?.('member selected the published Agent and filled the prompt')
  const canonicalRequests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/')) canonicalRequests.push(`${request.method()} ${request.url()}`)
  })
  const runCreationResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname === '/api/agent-runs',
    { timeout: 30_000 },
  )
  await page.getByRole('button', { name: 'Send message' }).click()
  const runCreationResponse = await runCreationResponsePromise
  input.onProgress?.('member Run creation returned from the API')
  expect(runCreationResponse.status()).toBe(202)
  const createdRun = (await runCreationResponse.json()) as { id: string }
  expect(createdRun.id).not.toBe('')
  const runDetail = page.getByTestId('agent-run-detail')
  const replyParagraph = page.getByTestId('agent-run-reply')
  if (input.expectedTerminalStatus) {
    const readPersistedStatus = () =>
      page.evaluate(async (runId) => {
        const response = await fetch(`/api/agent-runs/${encodeURIComponent(runId)}`, {
          credentials: 'include',
          cache: 'no-store',
        })
        if (!response.ok) throw new Error(`Run detail failed with HTTP ${response.status}`)
        return (await response.json()) as {
          status: string
          assistant_message: string | null
        }
      }, createdRun.id)
    await expect.poll(async () => (await readPersistedStatus()).status, { timeout: 30_000 })
      .toBe(input.expectedTerminalStatus)
    const persistedRun = await readPersistedStatus()
    if (process.env.RV2_TERMINAL_MUTANT === '1') {
      appendFileSync(
        evidencePath('rv-2-negative-terminal-probe.txt'),
        [
          `run_id=${createdRun.id}`,
          `persisted_status=${persistedRun.status}`,
          `expected_ui_status=Status: ${input.expectedTerminalStatus}`,
          `ui_before_assertion=${(await runDetail.innerText()).replace(/\s+/g, ' ').trim()}`,
          '',
        ].join('\n'),
        'utf8',
      )
    }
    try {
      await expect(runDetail).toContainText(
        `Status: ${input.expectedTerminalStatus}`,
        { timeout: 30_000 },
      )
    } catch (error) {
      if (process.env.RV2_TERMINAL_MUTANT === '1') {
        appendFileSync(
          evidencePath('rv-2-negative-terminal-probe.txt'),
          `ui_after_assertion_timeout=${(await runDetail.innerText()).replace(/\s+/g, ' ').trim()}\n`,
          'utf8',
        )
      }
      throw error
    }
    if (input.expectedTerminalStatus === 'succeeded') {
      await expect(replyParagraph).toContainText('stub-reply')
    }
    expect(persistedRun.status).toBe(input.expectedTerminalStatus)
  } else if (input.requireIncrementalReply !== false) {
    // 增量可见：运行仍在进行时，回复正文已经随 message.delta 事件增长。
    // `agent-run-live-reply` 只在收到流式片段后出现，避免把占位文案当成回复。
    await expect(page.getByTestId('agent-run-live-reply')).toBeVisible({ timeout: 60_000 })
    input.onProgress?.('member UI displayed an incremental reply while running')
    await expect(runDetail).toContainText('Status: running')
    const partialReply = (await replyParagraph.innerText()).trim()
    expect(partialReply.length).toBeGreaterThan(0)
    if (input.onIncrementalReply) await input.onIncrementalReply(partialReply)
    await expect(runDetail).toContainText('succeeded', { timeout: 60_000 })
    input.onProgress?.('member Run reached a successful terminal state')
    const finalReply = (await replyParagraph.innerText()).trim()
    expect(
      finalReply.startsWith(partialReply),
      `partial reply ${JSON.stringify(partialReply)} is not a prefix of final reply ${JSON.stringify(finalReply)}`,
    ).toBeTruthy()
    expect(finalReply.length).toBeGreaterThan(partialReply.length)
  } else {
    await expect
      .poll(
        async () =>
          page.evaluate(async (runId) => {
            const response = await fetch(`/api/agent-runs/${encodeURIComponent(runId)}`, {
              credentials: 'include',
              cache: 'no-store',
            })
            if (!response.ok) throw new Error(`Run detail failed with HTTP ${response.status}`)
            const persistedRun = (await response.json()) as { status: string }
            return persistedRun.status
          }, createdRun.id),
        { timeout: 60_000 },
      )
      .toBe('succeeded')
    const runHistoryItem = page.getByTestId(`agent-run-history-${createdRun.id}`)
    await expect(runHistoryItem).toBeVisible({ timeout: 30_000 })
    await runHistoryItem.click()
    await expect(runDetail).toContainText('succeeded', { timeout: 15_000 })
  }
  if (input.expectedTerminalStatus !== 'failed') {
    await expect(runDetail).toContainText('stub-reply')
  }
  expect(canonicalRequests.some((entry) => entry.startsWith('POST ') && entry.includes('/api/agent-runs'))).toBeTruthy()
  expect(canonicalRequests.some((entry) => entry.includes('/api/agent-runs/') && entry.includes('/events'))).toBeTruthy()
  expect(canonicalRequests.every((entry) => !entry.includes('/api/api/'))).toBeTruthy()
  const runIdText = await page.getByTestId('agent-run-id').innerText()
  const displayedRunId = runIdText.replace(/^Run ID:\s*/, '').trim()
  expect(displayedRunId).toBe(createdRun.id)
  return displayedRunId
}

/** 证据目录只由 RV 运行器指定，不把原始图片或录屏写入代码 diff。 */
export function evidencePath(fileName: string): string {
  const directory = process.env.PLAYWRIGHT_EVIDENCE_DIR
  if (!directory) throw new Error('PLAYWRIGHT_EVIDENCE_DIR is required for Agent RV flows')
  mkdirSync(directory, { recursive: true })
  return resolve(directory, fileName)
}

/** 为主演示录屏增加明确步骤字幕；页面、API 与数据仍来自生产入口。 */
export async function showDemoCaption(
  page: Page,
  caption: string,
  traceFileName = 'rv-2-caption-trace.txt',
): Promise<void> {
  await page.evaluate((text) => {
    document.getElementById('rv-demo-caption')?.remove()
    const overlay = document.createElement('div')
    overlay.id = 'rv-demo-caption'
    overlay.textContent = text
    overlay.style.cssText =
      'position:fixed;left:24px;bottom:24px;z-index:9999;max-width:720px;padding:12px 18px;' +
      'border-radius:8px;background:#111827;color:white;font:600 15px system-ui;box-shadow:0 4px 20px #0004;' +
      'pointer-events:none'
    document.body.appendChild(overlay)
  }, caption)
  const captionOverlay = page.locator('#rv-demo-caption')
  await expect(captionOverlay).toBeVisible()
  const captionBox = await captionOverlay.boundingBox()
  const viewport = page.viewportSize()
  appendFileSync(
    evidencePath(traceFileName),
    `${new Date().toISOString()} ${JSON.stringify(viewport)} ${JSON.stringify(captionBox)} ${caption}\n`,
    'utf8',
  )
  await humanPause(page, 900)
}
