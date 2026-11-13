import { expect, test } from "@playwright/test";
import { getAdminBaseUrl, getAdminCredentials } from "../../support/env";
import {
  beginOidcAuthorization,
  fillTestIdentity,
  getBootstrapAdminEmail,
  readApiResponseFromPage,
  requireOidcTestEnvironment,
  saveEvidenceScreenshot,
  saveEvidenceVideo,
  waitForCanonicalResponse,
  waitForOidcCallback,
} from "../../support/oidc-test-helpers";

const adminOidcPrdStem = "P1-SECURITY-20261112-134527-admin-oidc-sign-in";

test.use({
  baseURL: getAdminBaseUrl(),
  storageState: { cookies: [], origins: [] },
});

test("seed admin signs in with OIDC and password login remains available", async ({
  browser,
  page,
}) => {
  const issuerUrl = requireOidcTestEnvironment();
  const adminCredentials = getAdminCredentials();
  const bootstrapAdminEmail = getBootstrapAdminEmail();
  const identitySubject = "playwright-seeded-platform-admin";

  const oidcStatusResponsePromise = waitForCanonicalResponse(
    page,
    "GET",
    "/api/admin/auth/oidc/status",
  );
  await page.goto("/sign-in");
  const oidcStatusResponse = await oidcStatusResponsePromise;
  expect(oidcStatusResponse.status()).toBe(200);
  expect(await oidcStatusResponse.json()).toEqual({ enabled: true });
  const oidcButton = page.getByTestId("admin-oidc-sign-in");
  await expect(oidcButton).toBeVisible();
  await saveEvidenceScreenshot(
    page,
    adminOidcPrdStem,
    "rv-1-sign-in-button.png",
  );

  const authorizationUrl = await beginOidcAuthorization(page, {
    buttonTestId: "admin-oidc-sign-in",
    startApiPath: "/api/admin/auth/oidc/start",
    issuerUrl,
  });
  const authorizationState = authorizationUrl.searchParams.get("state");
  expect(authorizationState).toBeTruthy();

  await expect(page.getByTestId("oidc-test-email")).toBeVisible();
  await page.getByTestId("oidc-test-email").fill(bootstrapAdminEmail);
  await page.getByTestId("oidc-test-subject").fill(identitySubject);
  await page.getByTestId("oidc-test-email-verified").check();
  const oidcCallback = waitForOidcCallback(page, {
    callbackApiPath: "/api/admin/auth/oidc/callback",
  });
  await page.getByTestId("oidc-test-submit").click();
  const [callbackRequest, callbackResponse] = await Promise.all([
    oidcCallback.request,
    oidcCallback.response,
  ]);
  const callbackUrl = new URL(callbackRequest.url());
  expect(callbackUrl.searchParams.get("state")).toBe(authorizationState);
  expect(callbackUrl.searchParams.get("code")).toBeTruthy();
  expect(callbackResponse.status()).toBe(302);

  await expect(page).not.toHaveURL(/\/sign-in/);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  const adminSessionCookie = (
    await page.context().cookies(getAdminBaseUrl())
  ).find((cookie) => cookie.name === "admin_session_id");
  expect(adminSessionCookie?.value).toBeTruthy();

  const currentAdminSession = await readApiResponseFromPage<{
    user_id: string;
    username: string;
    role: string;
  }>(page, "/api/admin/auth/me");
  expect(currentAdminSession.status).toBe(200);
  expect(currentAdminSession.body?.username).toBe(adminCredentials.identifier);
  expect(currentAdminSession.body?.role).toBe("platform");

  await saveEvidenceScreenshot(
    page,
    adminOidcPrdStem,
    "rv-1-admin-dashboard.png",
  );

  // 新建浏览器上下文，验证服务端会话可在浏览器重开后继续使用。
  const freshBrowserContext = await browser.newContext({
    baseURL: getAdminBaseUrl(),
    storageState: await page.context().storageState(),
  });
  const freshBrowserPage = await freshBrowserContext.newPage();
  await freshBrowserPage.goto("/sign-in");
  const freshAdminSession = await readApiResponseFromPage<{
    user_id: string;
    username: string;
  }>(freshBrowserPage, "/api/admin/auth/me");
  expect(freshAdminSession.status).toBe(200);
  expect(freshAdminSession.body?.user_id).toBe(
    currentAdminSession.body?.user_id,
  );
  await freshBrowserContext.close();

  // 在不携带 Cookie 的新上下文中再次登录，验证首次回调保存的身份绑定仍有效。
  const reboundBrowserContext = await browser.newContext({
    baseURL: getAdminBaseUrl(),
    storageState: { cookies: [], origins: [] },
  });
  const reboundBrowserPage = await reboundBrowserContext.newPage();
  await reboundBrowserPage.goto("/sign-in");
  const reboundAuthorizationUrl = await beginOidcAuthorization(
    reboundBrowserPage,
    {
      buttonTestId: "admin-oidc-sign-in",
      startApiPath: "/api/admin/auth/oidc/start",
      issuerUrl,
    },
  );
  const reboundCallback = waitForOidcCallback(reboundBrowserPage, {
    callbackApiPath: "/api/admin/auth/oidc/callback",
  });
  await fillTestIdentity(reboundBrowserPage, {
    email: `changed-${Date.now()}@example.test`,
    subject: identitySubject,
    emailVerified: true,
  });
  await reboundBrowserPage.getByTestId("oidc-test-submit").click();
  const [reboundCallbackRequest, reboundCallbackResponse] = await Promise.all([
    reboundCallback.request,
    reboundCallback.response,
  ]);
  expect(new URL(reboundCallbackRequest.url()).searchParams.get("state")).toBe(
    reboundAuthorizationUrl.searchParams.get("state"),
  );
  expect(
    new URL(reboundCallbackRequest.url()).searchParams.get("code"),
  ).toBeTruthy();
  expect(reboundCallbackResponse.status()).toBe(302);
  await expect(
    reboundBrowserPage.getByRole("heading", { name: "Dashboard" }),
  ).toBeVisible();
  const reboundAdminSession = await readApiResponseFromPage<{
    user_id: string;
    username: string;
  }>(reboundBrowserPage, "/api/admin/auth/me");
  expect(reboundAdminSession.status).toBe(200);
  expect(reboundAdminSession.body?.user_id).toBe(
    currentAdminSession.body?.user_id,
  );
  await reboundBrowserContext.close();

  // 首次绑定 OIDC 后，原有密码登录仍可使用。
  const passwordBrowserContext = await browser.newContext({
    baseURL: getAdminBaseUrl(),
    storageState: { cookies: [], origins: [] },
  });
  const passwordBrowserPage = await passwordBrowserContext.newPage();
  await passwordBrowserPage.goto("/sign-in");
  await passwordBrowserPage
    .getByTestId("admin-login-identifier-input")
    .fill(adminCredentials.identifier);
  await passwordBrowserPage
    .getByTestId("admin-login-password-input")
    .fill(adminCredentials.password);
  await passwordBrowserPage.getByTestId("admin-login-submit-button").click();
  await expect(
    passwordBrowserPage.getByRole("heading", { name: "Dashboard" }),
  ).toBeVisible();
  const passwordAdminSession = await readApiResponseFromPage<{
    user_id: string;
    username: string;
  }>(passwordBrowserPage, "/api/admin/auth/me");
  expect(passwordAdminSession.status).toBe(200);
  expect(passwordAdminSession.body?.user_id).toBe(
    currentAdminSession.body?.user_id,
  );
  await passwordBrowserContext.close();

  await saveEvidenceVideo(
    page,
    adminOidcPrdStem,
    "rv-1-admin-oidc-sign-in.webm",
  );
});
