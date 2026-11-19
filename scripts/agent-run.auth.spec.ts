import { expect, test, type Response } from "@playwright/test";
import { writeFileSync } from "node:fs";
import {
  createAgentScenario,
  createAgentThroughUi,
  createSkillThroughUi,
  evidencePath,
  runAgentThroughUi,
  savePageVideo,
  showDemoCaption,
  signInMember,
  signInMemberInFreshContext,
  signInOrganizationAdmin,
} from "./agent-test-support";

test.setTimeout(220_000);

/**
 * rv-2 真实用户流程与主演示：组织管理员发布 Agent，成员运行并在新上下文重开历史。
 * 模型传输由 RV 运行器的 OpenAI-compatible 替身提供；页面、代理、认证、API、迁移、
 * Run 事务和事件读取均为真实实现。当前产品没有 Agent/Run 删除入口，本用例在专用
 * worktree 数据库保留带 RV 前缀的数据，清理时需删除该一次性数据库。
 */
test("rv-2 publishes, runs, reopens history, and inspects the same Run", async ({
  browser,
}) => {
  const progressPath = evidencePath(
    process.env.RV2_NEGATIVE_CONTROL === "1"
      ? "rv-2-negative-progress.txt"
      : "rv-2-progress.txt",
  );
  const progressStartedAt = Date.now();
  const progressLines: string[] = [];
  const markProgress = (label: string) => {
    progressLines.push(`${Date.now() - progressStartedAt}ms ${label}`);
    writeFileSync(progressPath, `${progressLines.join("\n")}\n`, "utf8");
  };
  markProgress("test started");
  const scenario = await createAgentScenario("rv2");
  markProgress("organization and test users prepared");
  let adminContext = await signInOrganizationAdmin(browser, scenario);
  let adminContextClosed = false;
  markProgress("organization admin session ready");
  const memberContext = await signInMember(browser, scenario);
  let memberContextClosed = false;
  markProgress("organization member session ready");
  let memberPage: Awaited<ReturnType<typeof memberContext.newPage>> | undefined;
  try {
    const adminPage = await adminContext.newPage();
    adminPage.setDefaultTimeout(30_000);
    adminPage.setDefaultNavigationTimeout(30_000);
    markProgress("organization sessions ready; admin page opened");
    await showDemoCaption(
      adminPage,
      "real user flow · Step 1/4: create a versioned Skill",
    );
    await createSkillThroughUi(adminPage, {
      name: "RV2 response policy",
      body: "RV2 skill v1: answer with a concise, traceable response.",
      onProgress: markProgress,
    });
    markProgress("Skill created through admin UI");
    await showDemoCaption(adminPage, "主演示 1/5｜组织管理员创建 Skill v1");
    await adminPage.screenshot({
      path: evidencePath("rv-2-demo-step-1-skill.png"),
    });

    const agentName = "RV2 online helper";
    const agentId = await createAgentThroughUi(adminPage, {
      name: agentName,
      skillName: "RV2 response policy",
    });
    markProgress("Agent created and published through admin UI");
    expect(agentId).not.toBe("");
    await showDemoCaption(
      adminPage,
      "主演示 2/5｜组织管理员发布并绑定 Skill 的 Agent",
    );
    await adminPage.screenshot({
      path: evidencePath("rv-2-demo-step-2-publish.png"),
    });
    await adminPage.close();
    await adminContext.close();
    adminContextClosed = true;
    markProgress("admin publishing context closed before member workflow");

    memberPage = await memberContext.newPage();
    memberPage.setDefaultTimeout(30_000);
    memberPage.setDefaultNavigationTimeout(30_000);
    const runId = await runAgentThroughUi(memberPage, {
      agentName,
      message:
        "Hello from rv-2 and please stream the answer as it is generated",
      onProgress: markProgress,
      onIncrementalReply: async (partialReply) => {
        await showDemoCaption(
          memberPage!,
          "增量回复可见：运行未结束时回复仍在增长（模型为 mock，未验证真实模型）",
        );
        await memberPage!.screenshot({
          path: evidencePath("rv-2-streaming-reply.png"),
        });
        const evidenceLines = [
          "incremental reply captured while the Run was still running",
          `partial reply length: ${partialReply.length}`,
          `partial reply text: ${partialReply}`,
        ];
        writeFileSync(
          evidencePath("rv-2-incremental-reply.txt"),
          `${evidenceLines.join("\n")}\n`,
          "utf8",
        );
      },
    });
    markProgress("member Run completed with an observed incremental reply");

    const fastSuccessRunId = await runAgentThroughUi(memberPage, {
      agentName,
      message: "RV2_FAST_SUCCESS: return a brief reply",
      expectedTerminalStatus: "succeeded",
      onProgress: markProgress,
    });
    const fastSuccessUi = await memberPage.getByTestId("agent-run-detail").innerText();
    const fastSuccessPersisted = await memberPage.evaluate(async (expectedRunId) => {
      const response = await fetch(`/api/agent-runs/${encodeURIComponent(expectedRunId)}`, {
        credentials: "include",
        cache: "no-store",
      });
      return (await response.json()) as { status: string; assistant_message: string | null };
    }, fastSuccessRunId);
    expect(fastSuccessPersisted.status).toBe("succeeded");

    const fastFailureRunId = await runAgentThroughUi(memberPage, {
      agentName,
      message: "RV2_FAST_FAILURE: return a malformed response",
      expectedTerminalStatus: "failed",
      onProgress: markProgress,
    });
    const fastFailureUi = await memberPage.getByTestId("agent-run-detail").innerText();
    const fastFailurePersisted = await memberPage.evaluate(async (expectedRunId) => {
      const response = await fetch(`/api/agent-runs/${encodeURIComponent(expectedRunId)}`, {
        credentials: "include",
        cache: "no-store",
      });
      return (await response.json()) as { status: string; assistant_message: string | null };
    }, fastFailureRunId);
    expect(fastFailurePersisted.status).toBe("failed");
    writeFileSync(
      evidencePath("rv-2-fast-terminal-states.txt"),
      [
        "Fast model responses through the production public page, same-origin API, backend, and PostgreSQL.",
        `success run ${fastSuccessRunId}: UI ${fastSuccessUi.includes("Status: succeeded") ? "succeeded" : "missing terminal state"}; fresh API ${fastSuccessPersisted.status}; reply visible=${Boolean(fastSuccessPersisted.assistant_message)}`,
        `failure run ${fastFailureRunId}: UI ${fastFailureUi.includes("Status: failed") ? "failed" : "missing terminal state"}; fresh API ${fastFailurePersisted.status}`,
      ].join("\n") + "\n",
      "utf8",
    );
    markProgress("fast success and fast failure both reached their visible persisted terminal states");

    const cancellationRequests: string[] = [];
    memberPage.on("request", (request) => {
      if (
        request.method() === "POST" &&
        request.url().includes("/agent-runs/") &&
        request.url().endsWith("/cancel")
      ) {
        cancellationRequests.push(request.url());
      }
    });
    await memberPage
      .getByLabel("Write a message…")
      .fill("Start another reply so I can cancel it");
    markProgress("second Run prompt ready for cancellation");
    await memberPage.getByRole("button", { name: "Send message" }).click();
    const cancelButton = memberPage.getByRole("button", {
      name: "Cancel run",
      exact: true,
    });
    await expect(cancelButton).toBeVisible({ timeout: 60_000 });
    await expect(cancelButton).toBeEnabled({ timeout: 10_000 });
    markProgress("Cancel run button appeared on the active Run");
    await memberPage.screenshot({
      path: evidencePath("scripts/.rv2-cancel-active.png"),
    });
    await cancelButton.click({ trial: true, timeout: 10_000 });
    markProgress("Cancel run button passed the pointer actionability check");
    const cancelledRunId = (
      await memberPage.getByTestId("agent-run-id").innerText()
    )
      .replace(/^Run ID:\s*/, "")
      .trim();
    const cancelResponsePromise = memberPage.waitForResponse(
      (response) =>
        response.request().method() === "POST" &&
        new URL(response.url()).pathname === `/api/agent-runs/${cancelledRunId}/cancel`,
      { timeout: 30_000 },
    );
    await cancelButton.click({ timeout: 10_000 });
    markProgress("member clicked the cancel control");
    let cancelResponse: Response;
    try {
      cancelResponse = await cancelResponsePromise;
    } catch (error) {
      markProgress(
        `cancel response wait failed: ${error instanceof Error ? error.name : "unknown error"}`,
      );
      throw error;
    }
    let cancelResponseBody: { status: string };
    try {
      cancelResponseBody = (await cancelResponse.json()) as { status: string };
    } catch (error) {
      markProgress(
        `cancel response body failed to parse: ${error instanceof Error ? error.name : "unknown error"} ` +
          `http_status=${cancelResponse.status()}`,
      );
      throw error;
    }
    markProgress(
      `cancel API returned HTTP ${cancelResponse.status()} with status ${cancelResponseBody.status}`,
    );
    expect(cancelResponse.status()).toBe(200);
    expect(cancelResponseBody.status).toBe("cancelled");
    await expect(memberPage.getByTestId("agent-run-detail")).toContainText(
      "Status: cancelled",
    );
    markProgress("member Run detail rendered the cancelled state");
    markProgress("cancel request reached the visible cancelled state");
    expect(
      cancellationRequests.some((url) =>
        url.includes(`/agent-runs/${cancelledRunId}/cancel`),
      ),
    ).toBeTruthy();
    await expect(
      memberPage.getByTestId(`agent-run-history-${cancelledRunId}`),
    ).toContainText("cancelled");
    markProgress("second Run cancelled and listed in member history");

    await showDemoCaption(
      memberPage,
      `主演示 3/5｜成员看到运行 ${runId} 成功完成`,
    );
    await memberPage.screenshot({
      path: evidencePath("rv-2-demo-step-3-run.png"),
    });
    await memberPage.screenshot({
      path: evidencePath("rv-2-agent-run.png"),
      fullPage: true,
    });
    markProgress("member run screenshots captured before fresh-session verification");

    await memberContext.close();
    memberContextClosed = true;
    markProgress("original member context closed before fresh-session verification");
    const freshMemberContext = await signInMemberInFreshContext(browser, scenario);
    markProgress("fresh member browser context authenticated through the same-origin login");
    try {
      const freshPage = await freshMemberContext.newPage();
      freshPage.setDefaultTimeout(30_000);
      freshPage.setDefaultNavigationTimeout(30_000);
      const browserErrors: string[] = [];
      const failedRequests: string[] = [];
      const applicationResponses = new Map<string, Response>();
      freshPage.on("pageerror", (error) => browserErrors.push(error.name));
      freshPage.on("console", (message) => {
        if (message.type() === "error") browserErrors.push(message.text().slice(0, 180));
      });
      freshPage.on("requestfailed", (request) => {
        const requestPath = new URL(request.url()).pathname;
        failedRequests.push(`${requestPath}: ${request.failure()?.errorText ?? "failed"}`);
      });
      freshPage.on("response", (response) => {
        if (response.request().method() !== "GET") return;
        const responsePath = new URL(response.url()).pathname;
        if (responsePath === "/api/agents" || responsePath === "/api/agent-runs") {
          applicationResponses.set(responsePath, response);
        }
      });
      await freshPage.goto("/app/agents", { waitUntil: "domcontentloaded" });
      markProgress("fresh member page document loaded");
      const applicationResponseDeadline = Date.now() + 45_000;
      while (
        (!applicationResponses.has("/api/agents") ||
          !applicationResponses.has("/api/agent-runs")) &&
        Date.now() < applicationResponseDeadline
      ) {
        await freshPage.waitForTimeout(250);
      }
      const memberAgentResponse = applicationResponses.get("/api/agents");
      const memberHistoryResponse = applicationResponses.get("/api/agent-runs");
      if (!memberAgentResponse || !memberHistoryResponse) {
        const appState = await freshPage.evaluate(async () => {
          const authResponse = await fetch("/api/auth/me", { credentials: "include" });
          const resourceEntries = performance
            .getEntriesByType("resource")
            .map((entry) => new URL(entry.name).pathname)
            .filter((path) => path.includes("/_next/") || path.startsWith("/api/"));
          return {
            path: window.location.pathname,
            authStatus: authResponse.status,
            documentReadyState: document.readyState,
            scriptCount: document.scripts.length,
            resourceEntries: resourceEntries.slice(-30),
          };
        });
        markProgress(
          `fresh page requests missing; state=${JSON.stringify(appState)} ` +
            `browser_errors=${JSON.stringify(browserErrors)} failed_requests=${JSON.stringify(failedRequests)}`,
        );
        throw new Error("fresh session did not load Agent directory and Run history in the real UI");
      }
      const freshHistory = (await memberHistoryResponse.json()) as {
        items: Array<{ id: string }>;
      };
      markProgress(
        `fresh UI requests agents=${memberAgentResponse.status()} history=${memberHistoryResponse.status()} ` +
          `has_run=${freshHistory.items.some((run) => run.id === runId)}`,
      );
      const freshPageState = await freshPage.evaluate(async (expectedRunId) => {
        const sessionResponse = await fetch("/api/auth/me", { credentials: "include" });
        return {
          path: window.location.pathname,
          sessionStatus: sessionResponse.status,
          hasExpectedRun: document.querySelector(
            `[data-testid="agent-run-history-${expectedRunId}"]`,
          ) !== null,
          renderedHistoryRows: document.querySelectorAll(
            "[data-testid^='agent-run-history-']",
          ).length,
          loading: Boolean(document.querySelector("div.flex.h-64")),
        };
      }, runId);
      markProgress(
        `fresh page state path=${freshPageState.path} session=${freshPageState.sessionStatus} ` +
          `has_run=${freshPageState.hasExpectedRun} rows=${freshPageState.renderedHistoryRows} ` +
          `loading=${freshPageState.loading} page_errors=${browserErrors.length}`,
      );
      await expect(
        freshPage.getByTestId(`agent-run-history-${runId}`),
      ).toBeVisible({ timeout: 30_000 });
      await freshPage.getByTestId(`agent-run-history-${runId}`).click();
      markProgress("fresh member reopened the same Run from persisted history");
      await expect(freshPage.getByTestId("agent-run-id")).toHaveText(
        `Run ID: ${runId}`,
      );
      await expect(freshPage.getByTestId("agent-run-detail")).toContainText(
        "succeeded",
      );
      await expect(freshPage.getByTestId("agent-run-detail")).toContainText(
        "stub-reply to: Hello from rv-2",
      );
      await expect(freshPage.getByTestId("agent-run-skill-version")).toHaveText(
        "Frozen Skill version: v1",
      );
      markProgress("fresh session confirmed the successful Run and frozen Skill v1");
      markProgress("fresh member session reopened the same successful Run");
      await showDemoCaption(
        freshPage,
        "主演示 4/5｜重新登录后重开同一条历史运行",
      );
      await freshPage.screenshot({
        path: evidencePath("rv-2-demo-step-4-history.png"),
      });
    } finally {
      await freshMemberContext.close();
    }

    adminContext = await signInOrganizationAdmin(browser, scenario);
    adminContextClosed = false;
    markProgress("fresh organization admin session ready for trace review");
    const tracePage = await adminContext.newPage();
    tracePage.setDefaultTimeout(30_000);
    tracePage.setDefaultNavigationTimeout(30_000);
    await tracePage.goto("/agents");
    markProgress("admin trace page navigation committed");
    await showDemoCaption(
      tracePage,
      "主演示 5/5｜管理员查看同一运行的低敏轨迹",
    );
    const runButton = tracePage.getByRole("button").filter({ hasText: runId });
    await runButton.click();
    const traceProjection = tracePage
      .locator("pre")
      .filter({ hasText: "model.call.completed" });
    await expect(traceProjection).toBeVisible();
    markProgress("admin trace projection rendered");
    await expect(traceProjection).not.toContainText("Hello from rv-2");
    markProgress("admin trace showed the Run without its message body");
    await tracePage.screenshot({
      path: evidencePath("rv-2-demo-step-5-trace.png"),
    });
  } finally {
    markProgress("workflow cleanup started");
    if (!memberContextClosed) await memberContext.close();
    if (memberPage) await savePageVideo(memberPage, "rv-2-agent-run.webm");
    if (!adminContextClosed) await adminContext.close();
    await scenario.dispose();
  }
});
