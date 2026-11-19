import { expect, test, type Page } from '@playwright/test'
import {
  createAgentScenario,
  createAgentThroughUi,
  createSkillThroughUi,
  evidencePath,
  runAgentThroughUi,
  savePageVideo,
  showDemoCaption,
  signInMember,
  signInOrganizationAdmin,
} from './agent-test-support'

test.setTimeout(300_000)

/**
 * 主演示：严格按 PRD §9.1 的五步脚本录制单独的真实浏览器录屏。
 *
 * 1. 组织管理员发布已配置模型的 Agent。
 * 2. 成员在前台选择该 Agent 并提交消息，回复在运行结束前逐步增长。
 * 3. 关闭页面后重新进入历史，并在管理端查看同一运行的低敏轨迹。
 * 4. 授权人员更新 Skill、比较两个版本、把旧版本内容恢复为新的当前版本。
 * 5. 用恢复后的版本再发起一次运行：新运行冻结所选版本，旧运行仍指向原版本。
 */
test('primary demo follows the five scripted steps', async ({ browser }) => {
  const scenario = await createAgentScenario('primary-demo')
  const skillName = 'Primary demo response policy'
  const agentName = 'Primary demo helper'
  let firstRunId = ''
  let secondRunId = ''

  const adminContext = await signInOrganizationAdmin(browser, scenario)
  let adminPage: Page | undefined
  try {
    adminPage = await adminContext.newPage()
    // 准备动作（不在脚本五步内）：先创建 Skill v1，供第 1 步绑定发布。
    await createSkillThroughUi(adminPage, {
      name: skillName,
      body: 'Primary demo skill v1: answer with the original policy.',
    })

    await adminPage.goto('/agents')
    await createAgentThroughUi(adminPage, { name: agentName, skillName })
    await showDemoCaption(
      adminPage,
      '主演示 1/5｜组织管理员发布已配置模型的 Agent；模型为 mock，未验证真实模型',
    )
    await adminPage.waitForTimeout(4_000)
  } finally {
    await adminContext.close()
    if (adminPage) await savePageVideo(adminPage, 'rv-2-demo-step-1-admin-publish.webm')
  }

  const memberContext = await signInMember(browser, scenario)
  let memberPage: Page | undefined
  try {
    memberPage = await memberContext.newPage()
    firstRunId = await runAgentThroughUi(memberPage, {
      agentName,
      message: 'Summarize the saved response policy while streaming the answer',
      onIncrementalReply: async (partialReply) => {
        await showDemoCaption(
          memberPage!,
          `主演示 2/5｜运行未结束时回复已逐步增长（已收到 ${partialReply.length} 个字符）`,
        )
        await memberPage!.screenshot({ path: evidencePath('rv-2-streaming-reply.png') })
        await memberPage!.waitForTimeout(4_000)
      },
    })
    await showDemoCaption(
      memberPage,
      `主演示 2/5｜成员看到同一运行 ${firstRunId} 的最终回复；模型为 mock，未验证真实模型`,
    )
    await memberPage.waitForTimeout(4_000)
  } finally {
    await memberContext.close()
    if (memberPage) await savePageVideo(memberPage, 'rv-2-demo-step-2-member-run.webm')
  }

  const historyContext = await signInMember(browser, scenario)
  let historyPage: Page | undefined
  try {
    historyPage = await historyContext.newPage()
    await historyPage.goto('/app/agents')
    await historyPage.getByTestId(`agent-run-history-${firstRunId}`).click()
    await expect(historyPage.getByTestId('agent-run-id')).toHaveText(`Run ID: ${firstRunId}`)
    await expect(historyPage.getByTestId('agent-run-detail')).toContainText('succeeded')
    await showDemoCaption(
      historyPage,
      '主演示 3/5｜关闭页面后重新进入，重开同一条历史运行；回复来自 mock，未验证真实模型',
    )
    await historyPage.waitForTimeout(4_000)
  } finally {
    await historyContext.close()
    if (historyPage) await savePageVideo(historyPage, 'rv-2-demo-step-3-history.webm')
  }

  const traceContext = await signInOrganizationAdmin(browser, scenario)
  let tracePage: Page | undefined
  try {
    tracePage = await traceContext.newPage()
    await tracePage.goto('/agents')
    await tracePage.getByRole('button').filter({ hasText: firstRunId }).click()
    const traceProjection = tracePage.locator('pre').filter({ hasText: 'model.call.completed' })
    await expect(traceProjection).toBeVisible()
    await expect(traceProjection).not.toContainText('Summarize the saved response policy')
    await showDemoCaption(
      tracePage,
      '主演示 3/5｜切到管理端查看同一运行的低敏轨迹，不包含用户消息正文',
    )
    await tracePage.waitForTimeout(4_000)
  } finally {
    await traceContext.close()
    if (tracePage) await savePageVideo(tracePage, 'rv-2-demo-step-4-trace.webm')
  }

  const skillContext = await signInOrganizationAdmin(browser, scenario)
  let skillPage: Page | undefined
  try {
    skillPage = await skillContext.newPage()
    await skillPage.goto('/agents')
    const revisionForm = skillPage.locator('form').filter({
      has: skillPage.getByRole('button', { name: 'Append version' }),
    })
    await revisionForm
      .getByLabel('New declarative version content')
      .fill('Primary demo skill v2: answer with the changed policy.')
    await revisionForm.getByRole('button', { name: 'Append version' }).click()
    await expect(skillPage.getByTestId('skill-revision-2')).toBeVisible()
    await showDemoCaption(skillPage, '主演示 4/5｜授权人员更新 Skill，追加 v2')
    await skillPage.waitForTimeout(3_500)

    await skillPage.getByTestId('skill-revision-1').getByRole('button', { name: 'Compare' }).click()
    await expect(skillPage.locator('pre').filter({ hasText: 'Primary demo skill v1' })).toBeVisible()
    await expect(skillPage.locator('pre').filter({ hasText: 'Primary demo skill v2' })).toBeVisible()
    await showDemoCaption(skillPage, '主演示 4/5｜比较 v1 与 v2 的正文差异')
    await skillPage.waitForTimeout(3_500)

    skillPage.once('dialog', (dialog) => void dialog.accept())
    await skillPage
      .getByTestId('skill-revision-1')
      .getByRole('button', { name: 'Restore as new version' })
      .click()
    await expect(skillPage.getByTestId('skill-revision-3')).toBeVisible()
    await expect(
      skillPage.getByRole('option', { name: `${skillName} · v3` }).first(),
    ).toHaveText(`${skillName} · v3`)
    await showDemoCaption(
      skillPage,
      '主演示 4/5｜以 v1 内容恢复为新的当前版本 v3，v1 与 v2 记录保持不变',
    )
    await skillPage.waitForTimeout(4_000)
  } finally {
    await skillContext.close()
    if (skillPage) await savePageVideo(skillPage, 'rv-2-demo-step-5-skill-version.webm')
  }

  const secondRunContext = await signInMember(browser, scenario)
  let secondRunPage: Page | undefined
  try {
    secondRunPage = await secondRunContext.newPage()
    secondRunId = await runAgentThroughUi(secondRunPage, {
      agentName,
      message: 'Run again with the restored Skill version',
    })
    await expect(secondRunPage.getByTestId('agent-run-skill-version')).toHaveText(
      'Frozen Skill version: v3',
    )
    await showDemoCaption(
      secondRunPage,
      `主演示 5/5｜恢复后再运行 ${secondRunId}，新运行冻结 v3；模型为 mock，未验证真实模型`,
    )
    await secondRunPage.waitForTimeout(4_000)

    await secondRunPage.getByTestId(`agent-run-history-${firstRunId}`).click()
    await expect(secondRunPage.getByTestId('agent-run-skill-version')).toHaveText(
      'Frozen Skill version: v1',
    )
    await showDemoCaption(
      secondRunPage,
      `主演示 5/5｜旧运行 ${firstRunId} 仍指向 v1，两次运行的冻结版本并存`,
    )
    await secondRunPage.waitForTimeout(4_000)
  } finally {
    await secondRunContext.close()
    if (secondRunPage) await savePageVideo(secondRunPage, 'rv-2-demo-step-6-second-run.webm')
    await scenario.dispose()
  }
})
