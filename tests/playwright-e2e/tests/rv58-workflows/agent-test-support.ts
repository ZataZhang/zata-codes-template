import { appendFileSync, mkdirSync } from 'node:fs'
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
  await page.goto('/sign-in')
  const status = await page.evaluate(async (credentials) => {
    const response = await fetch('/api/admin/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
      credentials: 'include',
    })
    return response.status
  }, { identifier: scenario.adminIdentifier, password: scenario.adminPassword })
  expect(status).toBe(200)
  return context
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
  await page.goto('/login')
  const status = await page.evaluate(async (credentials) => {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(credentials),
      credentials: 'include',
    })
    return response.status
  }, { identifier: scenario.memberEmail, password: scenario.memberPassword })
  expect(status).toBe(200)
  return context
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
  input: { name: string; body: string },
): Promise<string> {
  await page.goto('/agents')
  const form = page.locator('form').filter({
    has: page.getByRole('button', { name: 'Create Skill' }),
  })
  await form.getByLabel('Skill name').fill(input.name)
  await form.getByLabel('Description').fill('Versioned reference for realistic validation')
  await form.getByLabel('Declarative Skill content').fill(input.body)
  await form.getByRole('button', { name: 'Create Skill' }).click()
  await expect(page.getByRole('option', { name: `${input.name} · v1` }).first()).toHaveText(
    `${input.name} · v1`,
  )
  return page.evaluate(async (skillName) => {
    const response = await fetch('/api/admin/skills', { credentials: 'include' })
    if (!response.ok) throw new Error(`Skill list failed with HTTP ${response.status}`)
    const skillList = (await response.json()) as {
      items: Array<{ id: string; name: string }>
    }
    const createdSkill = skillList.items.find((skill) => skill.name === skillName)
    if (!createdSkill) throw new Error('Created Skill was not returned by the API')
    return createdSkill.id
  }, input.name)
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

/** 从真实成员页提交消息，核对增量回复，并等待持久终态。 */
export async function runAgentThroughUi(
  page: Page,
  input: {
    agentName: string
    message: string
    onIncrementalReply?: (partialReply: string) => Promise<void>
  },
): Promise<string> {
  await page.goto('/app/agents')
  await page.locator('button[aria-pressed]').filter({ hasText: input.agentName }).click()
  await page.getByLabel('Write a message…').fill(input.message)
  const canonicalRequests: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/')) canonicalRequests.push(`${request.method()} ${request.url()}`)
  })
  await page.getByRole('button', { name: 'Send message' }).click()
  const runDetail = page.getByTestId('agent-run-detail')
  const replyParagraph = page.getByTestId('agent-run-reply')
  if (process.env.RV2_NEGATIVE_CONTROL === '1') {
    await expect(runDetail).toContainText('failed', { timeout: 60_000 })
    await expect(runDetail).toContainText('succeeded', { timeout: 10_000 })
  } else {
    // 增量可见：运行仍在进行时，回复正文已经随 message.delta 事件增长。
    // `agent-run-live-reply` 只在收到流式片段后出现，避免把占位文案当成回复。
    await expect(page.getByTestId('agent-run-live-reply')).toBeVisible({ timeout: 60_000 })
    await expect(runDetail).toContainText('Status: running')
    const partialReply = (await replyParagraph.innerText()).trim()
    expect(partialReply.length).toBeGreaterThan(0)
    if (input.onIncrementalReply) await input.onIncrementalReply(partialReply)
    await expect(runDetail).toContainText('succeeded', { timeout: 60_000 })
    const finalReply = (await replyParagraph.innerText()).trim()
    expect(
      finalReply.startsWith(partialReply),
      `partial reply ${JSON.stringify(partialReply)} is not a prefix of final reply ${JSON.stringify(finalReply)}`,
    ).toBeTruthy()
    expect(finalReply.length).toBeGreaterThan(partialReply.length)
    expect(canonicalRequests.some((entry) => entry.includes('/api/agent-runs/') && entry.includes('/events'))).toBeTruthy()
  }
  await expect(runDetail).toContainText('stub-reply')
  expect(canonicalRequests.some((entry) => entry.startsWith('POST ') && entry.includes('/api/agent-runs'))).toBeTruthy()
  expect(canonicalRequests.every((entry) => !entry.includes('/api/api/'))).toBeTruthy()
  const runIdText = await page.getByTestId('agent-run-id').innerText()
  return runIdText.replace(/^Run ID:\s*/, '').trim()
}

/** 证据目录只由 RV 运行器指定，不把原始图片或录屏写入代码 diff。 */
export function evidencePath(fileName: string): string {
  const directory = process.env.PLAYWRIGHT_EVIDENCE_DIR
  if (!directory) throw new Error('PLAYWRIGHT_EVIDENCE_DIR is required for Agent RV flows')
  mkdirSync(directory, { recursive: true })
  return resolve(directory, fileName)
}

/** 为主演示录屏增加明确步骤字幕；页面、API 与数据仍来自生产入口。 */
export async function showDemoCaption(page: Page, caption: string): Promise<void> {
  await page.evaluate((text) => {
    document.getElementById('rv-demo-caption')?.remove()
    const overlay = document.createElement('div')
    overlay.id = 'rv-demo-caption'
    overlay.textContent = text
    overlay.style.cssText =
      'position:fixed;left:24px;bottom:24px;z-index:9999;max-width:720px;padding:12px 18px;' +
      'border-radius:8px;background:#111827;color:white;font:600 15px system-ui;box-shadow:0 4px 20px #0004'
    document.body.appendChild(overlay)
  }, caption)
  const captionOverlay = page.locator('#rv-demo-caption')
  await expect(captionOverlay).toBeVisible()
  const captionBox = await captionOverlay.boundingBox()
  const viewport = page.viewportSize()
  appendFileSync(
    evidencePath('rv-2-caption-trace.txt'),
    `${new Date().toISOString()} ${JSON.stringify(viewport)} ${JSON.stringify(captionBox)} ${caption}\n`,
    'utf8',
  )
  await humanPause(page, 900)
}
