import { expect, test } from '@playwright/test'
import {
  createAgentScenario,
  createAgentThroughUi,
  createSkillThroughUi,
  evidencePath,
  runAgentThroughUi,
  showDemoCaption,
  signInMember,
  signInOrganizationAdmin,
} from './agent-test-support'

test.setTimeout(150_000)

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
    const adminPage = await adminContext.newPage()
    const skillId = await createSkillThroughUi(adminPage, {
      name: 'RV3 versioned policy',
      body: 'RV3 skill v1: use the original answer.',
    })
    const agentName = 'RV3 versioned helper'
    await createAgentThroughUi(adminPage, {
      name: agentName,
      skillName: 'RV3 versioned policy',
    })

    const memberPage = await memberContext.newPage()
    const originalRunId = await runAgentThroughUi(memberPage, {
      agentName,
      message: 'Run before Skill restore',
    })
    await expect(memberPage.getByTestId('agent-run-skill-version')).toHaveText('Frozen Skill version: v1')
    await expect(memberPage.getByTestId('agent-run-detail')).toContainText('RV3 skill v1')

    await showDemoCaption(adminPage, 'real user flow · append v2 and compare it with v1')
    await adminPage.goto('/agents')
    const revisionForm = adminPage.locator('form').filter({
      has: adminPage.getByRole('button', { name: 'Append version' }),
    })
    await revisionForm.getByLabel('New declarative version content').fill('RV3 skill v2: use the changed answer.')
    await revisionForm.getByRole('button', { name: 'Append version' }).click()
    await expect(adminPage.getByTestId('skill-revision-2')).toBeVisible()
    await adminPage.getByTestId('skill-revision-1').getByRole('button', { name: 'Compare' }).click()
    await expect(adminPage.locator('pre').filter({ hasText: 'RV3 skill v1' })).toBeVisible()
    await expect(adminPage.locator('pre').filter({ hasText: 'RV3 skill v2' })).toBeVisible()

    adminPage.once('dialog', (dialog) => void dialog.accept())
    await adminPage.getByTestId('skill-revision-1').getByRole('button', { name: 'Restore as new version' }).click()
    await expect(adminPage.getByTestId('skill-revision-3')).toBeVisible()
    await expect(adminPage.getByRole('option', { name: 'RV3 versioned policy · v3' }).first()).toHaveText(
      'RV3 versioned policy · v3',
    )
    await showDemoCaption(adminPage, 'real user flow · restore appended v3; v1 and v2 remain immutable')
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

    await showDemoCaption(memberPage, 'real user flow · the new Run freezes restored v3; old Run stays on v1')
    const restoredRunId = await runAgentThroughUi(memberPage, {
      agentName,
      message: 'Run after Skill restore',
    })
    expect(restoredRunId).not.toBe(originalRunId)
    await expect(memberPage.getByTestId('agent-run-skill-version')).toHaveText('Frozen Skill version: v3')
    await expect(memberPage.getByTestId('agent-run-detail')).toContainText('RV3 skill v1')
    await memberPage.getByTestId(`agent-run-history-${originalRunId}`).click()
    await expect(memberPage.getByTestId('agent-run-skill-version')).toHaveText('Frozen Skill version: v1')

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

    const freshMemberContext = await signInMember(browser, scenario)
    try {
      const freshPage = await freshMemberContext.newPage()
      await freshPage.goto('/app/agents')
      await freshPage.getByTestId(`agent-run-history-${restoredRunId}`).click()
      await expect(freshPage.getByTestId('agent-run-skill-version')).toHaveText('Frozen Skill version: v3')
      await expect(freshPage.getByTestId('agent-run-detail')).toContainText('Run after Skill restore')
    } finally {
      await freshMemberContext.close()
    }
  } finally {
    await memberContext.close()
    await adminContext.close()
    await scenario.dispose()
  }
})
