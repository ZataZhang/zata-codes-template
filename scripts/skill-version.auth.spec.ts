import { expect, request, test } from '@playwright/test'
import {
  createAgentScenario,
  createAgentRunThroughApi,
  createPublishedAgentThroughApi,
  createSkillThroughUi,
  evidencePath,
  showDemoCaption,
  signInMember,
  signInOrganizationAdmin,
} from './agent-test-support'
import { getApiBaseUrl } from '../../support/env'

test.setTimeout(260_000)

/**
 * rv-3 真实 Skill 版本流程：更新、比较、恢复和两次 Run 的冻结版本。
 * 模型传输由 RV 运行器替换；其余页面、API、事务锁与持久化均为真实实现。
 * 当前产品无删除入口，RV 前缀数据留在专用 worktree 数据库并随一次性数据库清理。
 */
test('rv-3 restores old content as a new version and freezes each Run snapshot', async ({ browser }) => {
  const scenario = await createAgentScenario('rv3')
  const adminContext = await signInOrganizationAdmin(browser, scenario)
  const memberContext = await signInMember(browser, scenario)
  try {
    const adminPage = adminContext.pages()[0] ?? await adminContext.newPage()
    const skillId = await createSkillThroughUi(adminPage, {
      name: 'RV3 versioned policy',
      body: 'RV3 skill v1: use the original answer.',
    })
    const agentName = 'RV3 versioned helper'
    const agentId = await createPublishedAgentThroughApi(adminPage, {
      name: agentName,
      skillId,
    })

    const originalRun = await createAgentRunThroughApi(memberContext, {
      agentId,
      message: 'Run before Skill restore',
    })
    expect(originalRun.skill_version).toBe(1)
    expect(originalRun.assistant_message).toContain('RV3 skill v1')

    await showDemoCaption(
      adminPage,
      'real user flow · append v2 and compare it with v1',
      'rv-3-caption-trace.txt',
    )
    const skillPicker = adminPage.getByLabel('Select Skill').nth(1)
    await expect(skillPicker).toBeVisible({ timeout: 30_000 })
    await skillPicker.selectOption({ label: 'RV3 versioned policy · v1' })
    const revisionContent = adminPage.locator(
      'textarea[aria-label="New declarative version content"]',
    )
    await expect(revisionContent).toBeVisible({ timeout: 30_000 })
    await revisionContent.fill('RV3 skill v2: use the changed answer.')
    await adminPage.getByRole('button', { name: 'Append version' }).click()
    await expect(adminPage.getByTestId('skill-revision-2')).toBeVisible()
    await adminPage.getByTestId('skill-revision-1').getByRole('button', { name: 'Compare' }).click()
    await expect(adminPage.locator('pre').filter({ hasText: 'RV3 skill v1' })).toBeVisible()
    await expect(adminPage.locator('pre').filter({ hasText: 'RV3 skill v2' })).toBeVisible()

    const restoreResponsePromise = adminPage.waitForResponse(
      (response) =>
        response.url().includes(`/api/admin/skills/${skillId}/restore/1`) &&
        response.request().method() === 'POST',
      { timeout: 15_000 },
    )
    adminPage.once('dialog', async (dialog) => {
      await dialog.accept()
    })
    await adminPage.getByTestId('skill-revision-1').getByRole('button', { name: 'Restore as new version' }).click()
    expect((await restoreResponsePromise).status()).toBe(200)
    await expect(adminPage.getByTestId('skill-revision-3')).toBeVisible()
    await expect(adminPage.getByRole('option', { name: 'RV3 versioned policy · v3' }).first()).toHaveText(
      'RV3 versioned policy · v3',
    )
    await showDemoCaption(
      adminPage,
      'real user flow · restore appended v3; v1 and v2 remain immutable',
      'rv-3-caption-trace.txt',
    )
    await adminPage.screenshot({ path: evidencePath('rv-3-skill-version.png'), fullPage: true })

    if (process.env.RV3_MUTATE_OLD_VERSION === '1') {
      await adminPage.route(`**/api/admin/skills/${skillId}/versions`, async (route) => {
        const response = await route.fetch()
        const versionHistory = (await response.json()) as {
          items: Array<{ version: number; body: string }>
        }
        versionHistory.items[0].body = 'RV3 NEGATIVE CONTROL: old record was modified.'
        await route.fulfill({ response, body: JSON.stringify(versionHistory) })
      })
    }
    const revisionHistory = await adminPage.evaluate(async (selectedSkillId) => {
      const response = await fetch(`/api/admin/skills/${selectedSkillId}/versions`, {
        credentials: 'include',
      })
      if (!response.ok) throw new Error(`Version history failed with HTTP ${response.status}`)
      return (await response.json()) as {
        items: Array<{ version: number; body: string }>
      }
    }, skillId)
    expect(revisionHistory.items.map((revision) => revision.version)).toEqual([1, 2, 3])
    expect(revisionHistory.items.map((revision) => revision.body)).toEqual([
      'RV3 skill v1: use the original answer.',
      'RV3 skill v2: use the changed answer.',
      'RV3 skill v1: use the original answer.',
    ])

    await showDemoCaption(
      adminPage,
      'real user flow · the new Run freezes restored v3; old Run stays on v1',
      'rv-3-caption-trace.txt',
    )
    const restoredRun = await createAgentRunThroughApi(memberContext, {
      agentId,
      message: 'Run after Skill restore',
    })
    expect(restoredRun.id).not.toBe(originalRun.id)
    expect(restoredRun.skill_version).toBe(3)
    expect(restoredRun.assistant_message).toContain('RV3 skill v1')

    const idempotencyProbe = await adminPage.evaluate(async () => {
      const headers = {
        'Content-Type': 'application/json',
        'Idempotency-Key': 'rv3-repeat-version-write',
      }
      const write = () => fetch('/api/admin/skills', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          name: 'RV3 idempotent create',
          description: 'retry probe',
          body: 'RV3 idempotent create body',
        }),
      })
      const first = await write()
      const second = await write()
      const firstBody = await first.json()
      const secondBody = await second.json()
      return {
        statuses: [first.status, second.status],
        ids: [firstBody.id, secondBody.id],
        versions: [firstBody.current_version, secondBody.current_version],
      }
    })
    expect(idempotencyProbe.statuses).toEqual([201, 201])
    expect(idempotencyProbe.ids[0]).toBe(idempotencyProbe.ids[1])
    expect(idempotencyProbe.versions).toEqual([1, 1])

    const freshMemberContext = await request.newContext({ baseURL: getApiBaseUrl() })
    try {
      const loginResponse = await freshMemberContext.post('/auth/login', {
        data: {
          identifier: scenario.memberEmail,
          password: scenario.memberPassword,
        },
      })
      expect(loginResponse.status()).toBe(200)
      const [originalRunResponse, restoredRunResponse] = await Promise.all([
        freshMemberContext.get(`/agent-runs/${originalRun.id}`),
        freshMemberContext.get(`/agent-runs/${restoredRun.id}`),
      ])
      expect(originalRunResponse.status()).toBe(200)
      expect(restoredRunResponse.status()).toBe(200)
      const freshOriginalRun = (await originalRunResponse.json()) as {
        status: string
        input_message: string
        skill_version: number
      }
      const freshRestoredRun = (await restoredRunResponse.json()) as {
        status: string
        input_message: string
        skill_version: number
      }
      expect(freshOriginalRun).toMatchObject({
        status: 'succeeded',
        input_message: 'Run before Skill restore',
        skill_version: 1,
      })
      expect(freshRestoredRun).toMatchObject({
        status: 'succeeded',
        input_message: 'Run after Skill restore',
        skill_version: 3,
      })
    } finally {
      await freshMemberContext.dispose()
    }
  } finally {
    await memberContext.close()
    await adminContext.close()
    await scenario.dispose()
  }
})
