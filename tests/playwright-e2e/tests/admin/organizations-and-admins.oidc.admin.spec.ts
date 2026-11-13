import { expect, test, type Browser, type Page } from "@playwright/test";
import { getAdminBaseUrl, getBaseUrl } from "../../support/env";
import {
  beginOidcAuthorization,
  createRecordedContext,
  fillTestIdentity,
  readApiResponseFromPage,
  requireOidcTestEnvironment,
  saveEvidenceScreenshot,
  saveEvidenceVideo,
  waitForCanonicalResponse,
  waitForOidcCallback,
} from "../../support/oidc-test-helpers";

const organizationPrdStem =
  "P1-FEAT-20261112-142923-organizations-and-two-tier-admins";
const registrationPrdStem =
  "P1-FEAT-20261112-134527-registration-policy-and-user-oidc";
const organizationOidcPath = "/api/admin/auth/oidc/callback";

type RegistrationPolicy = {
  registration_mode: "both" | "oidc_only" | "closed";
  allowed_email_domains: string[];
};

type PublicUserSession = {
  user_id: string;
  email: string;
  display_name: string;
};

type CreatedAdmin = {
  id: string;
  username: string;
  email: string;
  role: "platform" | "org";
  organization_id: string;
  oidc_bound: boolean;
};

type OrganizationAdminCreationOptions = {
  username: string;
  email: string;
  organizationName: string;
  initialPassword?: string;
  evidenceScreenshot: string;
};

type TestAdminSession = {
  user_id: string;
  username: string;
  role: "platform" | "org";
  organization_id: string | null;
  organization_name: string | null;
};

async function setRegistrationPolicy(
  page: Page,
  registrationPolicy: RegistrationPolicy,
): Promise<void> {
  const registrationModeId = registrationPolicy.registration_mode.replace(
    "_",
    "-",
  );
  await page.locator(`#registration-${registrationModeId}`).click();
  await page
    .getByTestId("registration-policy-domains")
    .fill(registrationPolicy.allowed_email_domains.join("\n"));
  const policyResponsePromise = waitForCanonicalResponse(
    page,
    "PUT",
    "/api/admin/settings/registration-policy",
  );
  await page.getByTestId("registration-policy-save").click();
  const policyResponse = await policyResponsePromise;
  expect(policyResponse.status()).toBe(200);
  expect(policyResponse.request().postDataJSON()).toEqual(registrationPolicy);
}

async function registerPublicUser(
  browser: Browser,
  identity: {
    email: string;
    displayName: string;
    captureRegistrationEvidence?: boolean;
  },
): Promise<PublicUserSession> {
  const publicContext = await browser.newContext({
    baseURL: getBaseUrl(),
    storageState: { cookies: [], origins: [] },
    viewport: { width: 1440, height: 1200 },
    locale: "en-US",
    colorScheme: "light",
  });
  const publicPage = await publicContext.newPage();
  try {
    await publicPage.goto("/register");
    await expect(
      publicPage.getByTestId("public-registration-password-form"),
    ).toBeVisible();
    await expect(publicPage.getByTestId("public-oidc-sign-in")).toHaveAttribute(
      "href",
      "/api/auth/oidc/start",
    );
    if (identity.captureRegistrationEvidence) {
      await saveEvidenceScreenshot(
        publicPage,
        registrationPrdStem,
        "rv-1-register-both.png",
      );
    }
    await publicPage
      .getByTestId("register-display-name")
      .fill(identity.displayName);
    await publicPage.getByTestId("register-email").fill(identity.email);
    await publicPage.getByTestId("register-password").fill("E2E-password-123");
    await publicPage
      .getByTestId("register-confirm-password")
      .fill("E2E-password-123");
    const registrationResponsePromise = waitForCanonicalResponse(
      publicPage,
      "POST",
      "/api/auth/register",
    );
    await publicPage.getByTestId("register-submit").click();
    const registrationResponse = await registrationResponsePromise;
    expect([200, 201]).toContain(registrationResponse.status());
    const registeredUser =
      (await registrationResponse.json()) as PublicUserSession;
    expect(registeredUser.email).toBe(identity.email);
    expect(registeredUser.user_id).toBeTruthy();
    await expect(publicPage).toHaveURL(/\/app\/dashboard/);
    return registeredUser;
  } finally {
    await publicContext.close();
  }
}

async function createOrganizationAdmin(
  page: Page,
  options: OrganizationAdminCreationOptions,
): Promise<CreatedAdmin> {
  await page.goto("/admins");
  await page.getByTestId("admin-username").fill(options.username);
  await page.getByTestId("admin-email").fill(options.email);
  await page.locator("#admin-role").click();
  await page
    .getByRole("option", { name: /organization administrator|组织管理员/i })
    .click();
  await page.locator("#admin-organization").click();
  await page
    .getByRole("option", { name: options.organizationName, exact: true })
    .click();
  await page.getByTestId("admin-password").fill(options.initialPassword ?? "");
  if (options.initialPassword === undefined) {
    await expect(page.getByTestId("admin-password")).toHaveValue("");
  }
  await saveEvidenceScreenshot(
    page,
    organizationPrdStem,
    options.evidenceScreenshot,
  );

  const createAdminResponsePromise = waitForCanonicalResponse(
    page,
    "POST",
    "/api/admin/admins",
  );
  await page.getByTestId("admin-create").click();
  const createAdminResponse = await createAdminResponsePromise;
  expect([200, 201]).toContain(createAdminResponse.status());
  const createdAdmin = (await createAdminResponse.json()) as CreatedAdmin;
  expect(createdAdmin.id).toBeTruthy();
  expect(createdAdmin.email).toBe(options.email);
  expect(createdAdmin.username).toBe(options.username);
  expect(createdAdmin.role).toBe("org");
  expect(createdAdmin.oidc_bound).toBe(false);
  expect(createdAdmin.organization_id).toBeTruthy();
  const adminCreationRequestBody =
    createAdminResponse.request().postData() ?? "";
  expect(/"password"\s*:/.test(adminCreationRequestBody)).toBe(
    options.initialPassword !== undefined,
  );
  if (options.initialPassword !== undefined) {
    expect(adminCreationRequestBody).toContain(options.initialPassword);
  }
  await expect(
    page.getByRole("row").filter({ hasText: options.email }),
  ).toBeVisible();
  return createdAdmin;
}

async function startAndSubmitAdminIdentity(
  page: Page,
  options: {
    issuerUrl: string;
    email: string;
    subject: string;
    emailVerified: boolean;
    disabled?: boolean;
  },
): Promise<{
  authorizationState: string | null;
  callbackStatus: number;
  callbackSetCookie: string | undefined;
}> {
  await page.goto("/sign-in");
  const authorizationUrl = await beginOidcAuthorization(page, {
    buttonTestId: "admin-oidc-sign-in",
    startApiPath: "/api/admin/auth/oidc/start",
    issuerUrl: options.issuerUrl,
  });
  const authorizationState = authorizationUrl.searchParams.get("state");
  const oidcCallback = waitForOidcCallback(page, {
    callbackApiPath: organizationOidcPath,
  });
  await fillTestIdentity(page, {
    email: options.email,
    subject: options.subject,
    emailVerified: options.emailVerified,
    disabled: options.disabled,
  });
  await page.getByTestId("oidc-test-submit").click();
  const [callbackRequest, callbackResponse] = await Promise.all([
    oidcCallback.request,
    oidcCallback.response,
  ]);
  expect(new URL(callbackRequest.url()).searchParams.get("state")).toBe(
    authorizationState,
  );
  expect(new URL(callbackRequest.url()).searchParams.get("code")).toBeTruthy();
  return {
    authorizationState,
    callbackStatus: callbackResponse.status(),
    callbackSetCookie: callbackResponse.headers()["set-cookie"],
  };
}

test("platform-created organization admin binds with OIDC and stays within its organization", async ({
  browser,
  page,
}) => {
  test.setTimeout(240_000);
  const issuerUrl = requireOidcTestEnvironment();
  const previousPolicyResponsePromise = waitForCanonicalResponse(
    page,
    "GET",
    "/api/admin/settings/registration-policy",
  );
  await page.goto("/registration");
  const platformSession = await readApiResponseFromPage<TestAdminSession>(
    page,
    "/api/admin/auth/me",
  );
  expect(platformSession.status).toBe(200);
  expect(platformSession.body?.role).toBe("platform");
  const previousPolicyResponse = await previousPolicyResponsePromise;
  expect(previousPolicyResponse.status()).toBe(200);
  const previousPolicy =
    (await previousPolicyResponse.json()) as RegistrationPolicy;

  const uniqueSuffix = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  const organizationName = `E2E Organization ${uniqueSuffix}`;
  const organizationAdminEmail = `org-admin-${uniqueSuffix}@example.com`;
  const organizationAdminUsername = `org-admin-${uniqueSuffix}`;
  const passwordOrganizationAdminEmail = `org-password-${uniqueSuffix}@example.com`;
  const passwordOrganizationAdminUsername = `org-password-${uniqueSuffix}`;
  const passwordOrganizationAdminPassword = `E2E-${uniqueSuffix}-Org-Password!`;
  const identitySubject = `playwright-org-admin-${uniqueSuffix}`;
  const inOrganizationEmail = `org-member-${uniqueSuffix}@example.com`;
  const defaultOrganizationEmail = `default-member-${uniqueSuffix}@example.com`;

  let orgLoginContext: Awaited<ReturnType<Browser["newContext"]>> | null = null;
  let orgLoginPage: Page | null = null;
  let copiedOrgSessionContext: Awaited<
    ReturnType<Browser["newContext"]>
  > | null = null;
  let copiedOrgSessionPage: Page | null = null;
  let passwordOrgContext: Awaited<ReturnType<Browser["newContext"]>> | null =
    null;
  let passwordOrgPage: Page | null = null;
  let reboundOrgContext: Awaited<ReturnType<Browser["newContext"]>> | null =
    null;
  let reboundOrgPage: Page | null = null;
  let recoveredOrgContext: Awaited<ReturnType<Browser["newContext"]>> | null =
    null;
  let recoveredOrgPage: Page | null = null;
  let providerDisabledContext: Awaited<
    ReturnType<Browser["newContext"]>
  > | null = null;
  let organizationFlowFailed = false;
  let organizationCleanupError: unknown;

  try {
    await setRegistrationPolicy(page, {
      registration_mode: "both",
      allowed_email_domains: [],
    });

    await page.goto("/organizations");
    await page.getByTestId("organization-name").fill(organizationName);
    const createOrganizationResponsePromise = waitForCanonicalResponse(
      page,
      "POST",
      "/api/admin/organizations",
    );
    await page.getByTestId("organization-create").click();
    const createOrganizationResponse = await createOrganizationResponsePromise;
    expect([200, 201]).toContain(createOrganizationResponse.status());
    const createdOrganization = (await createOrganizationResponse.json()) as {
      id: string;
      name: string;
      is_active: boolean;
    };
    expect(createdOrganization.id).toBeTruthy();
    expect(createdOrganization.name).toBe(organizationName);
    const organizationRow = page
      .getByRole("row")
      .filter({ hasText: organizationName });
    await expect(organizationRow).toBeVisible();
    await saveEvidenceScreenshot(
      page,
      organizationPrdStem,
      "rv-1-organizations.png",
    );

    const inOrganizationUser = await registerPublicUser(browser, {
      email: inOrganizationEmail,
      displayName: `E2E In Organization ${uniqueSuffix}`,
      captureRegistrationEvidence: true,
    });
    const defaultOrganizationUser = await registerPublicUser(browser, {
      email: defaultOrganizationEmail,
      displayName: `E2E Default Organization ${uniqueSuffix}`,
    });

    await page.goto("/users");
    const searchInput = page.getByPlaceholder(/search/i);
    await searchInput.fill(inOrganizationEmail);
    const filteredUsersResponsePromise = waitForCanonicalResponse(
      page,
      "GET",
      "/api/admin/users",
    );
    await page.getByRole("button", { name: "Search", exact: true }).click();
    const filteredUsersResponse = await filteredUsersResponsePromise;
    expect(filteredUsersResponse.status()).toBe(200);
    const inOrganizationRow = page
      .getByRole("row")
      .filter({ hasText: inOrganizationEmail });
    await expect(inOrganizationRow).toBeVisible();
    const userOrganizationSelect = page.getByTestId(
      `user-organization-${inOrganizationUser.user_id}`,
    );
    await userOrganizationSelect.click();
    const moveUserResponsePromise = waitForCanonicalResponse(
      page,
      "PATCH",
      `/api/admin/users/${inOrganizationUser.user_id}/organization`,
    );
    await page
      .getByRole("option", { name: organizationName, exact: true })
      .click();
    const moveUserResponse = await moveUserResponsePromise;
    expect(moveUserResponse.status()).toBe(200);
    expect(await moveUserResponse.json()).toMatchObject({
      id: inOrganizationUser.user_id,
      organization_id: createdOrganization.id,
    });
    expect(defaultOrganizationUser.user_id).toBeTruthy();

    const createdAdmin = await createOrganizationAdmin(page, {
      username: organizationAdminUsername,
      email: organizationAdminEmail,
      organizationName,
      evidenceScreenshot: "rv-1-admin-create.png",
    });
    expect(createdAdmin.organization_id).toBe(createdOrganization.id);

    const passwordCreatedAdmin = await createOrganizationAdmin(page, {
      username: passwordOrganizationAdminUsername,
      email: passwordOrganizationAdminEmail,
      organizationName,
      initialPassword: passwordOrganizationAdminPassword,
      evidenceScreenshot: "rv-1-admin-create-with-password.png",
    });
    expect(passwordCreatedAdmin.organization_id).toBe(createdOrganization.id);

    // 首次登录使用未验证邮箱时必须失败，且不能创建会话。
    const unverifiedContext = await browser.newContext({
      baseURL: getAdminBaseUrl(),
      storageState: { cookies: [], origins: [] },
    });
    const unverifiedPage = await unverifiedContext.newPage();
    expect(
      (await unverifiedContext.cookies(getAdminBaseUrl())).some(
        (cookie) => cookie.name === "admin_session_id",
      ),
    ).toBe(false);
    const unverifiedLogin = await startAndSubmitAdminIdentity(unverifiedPage, {
      issuerUrl,
      email: organizationAdminEmail,
      subject: identitySubject,
      emailVerified: false,
    });
    expect(unverifiedLogin.callbackStatus).toBe(302);
    expect(unverifiedLogin.callbackSetCookie ?? "").not.toContain(
      "admin_session_id=",
    );
    await expect(unverifiedPage).toHaveURL(/\/sign-in\?sso_error=1/);
    await expect(unverifiedPage.getByRole("alert")).toHaveText(
      "Organization sign-in failed. Please contact your administrator.",
    );
    const unverifiedSession = await readApiResponseFromPage(
      unverifiedPage,
      "/api/admin/auth/me",
    );
    expect(unverifiedSession.status).toBe(401);
    expect(
      (await unverifiedContext.cookies(getAdminBaseUrl())).some(
        (cookie) => cookie.name === "admin_session_id",
      ),
    ).toBe(false);
    await unverifiedPage.goto(
      "/sign-in?sso_error=%7B%22unexpected%22%3Atrue%7D",
    );
    await expect(
      unverifiedPage.getByTestId("admin-sign-in-heading"),
    ).toBeVisible();
    await expect(unverifiedPage.getByRole("alert")).toHaveCount(0);
    await unverifiedContext.close();

    // 新浏览器上下文使用已验证企业账号登录。
    orgLoginContext = await createRecordedContext(browser, getAdminBaseUrl());
    orgLoginPage = await orgLoginContext.newPage();
    const successfulOrgLogin = await startAndSubmitAdminIdentity(orgLoginPage, {
      issuerUrl,
      email: organizationAdminEmail,
      subject: identitySubject,
      emailVerified: true,
    });
    expect(successfulOrgLogin.callbackStatus).toBe(302);
    await expect(orgLoginPage).toHaveURL(/\/users/);
    const organizationAdminSession =
      await readApiResponseFromPage<TestAdminSession>(
        orgLoginPage,
        "/api/admin/auth/me",
      );
    expect(organizationAdminSession.status).toBe(200);
    expect(organizationAdminSession.body).toMatchObject({
      user_id: createdAdmin.id,
      username: organizationAdminUsername,
      role: "org",
      organization_id: createdOrganization.id,
      organization_name: organizationName,
    });
    await expect(orgLoginPage.locator('a[href="/organizations"]')).toHaveCount(
      0,
    );
    await expect(orgLoginPage.locator('a[href="/admins"]')).toHaveCount(0);
    await orgLoginPage.goto("/organizations");
    await expect(orgLoginPage).toHaveURL(/\/users/);
    await expect(
      orgLoginPage.getByRole("row").filter({ hasText: inOrganizationEmail }),
    ).toBeVisible();
    await expect(
      orgLoginPage
        .getByRole("row")
        .filter({ hasText: defaultOrganizationEmail }),
    ).toHaveCount(0);
    await saveEvidenceScreenshot(
      orgLoginPage,
      organizationPrdStem,
      "rv-1-org-admin-users.png",
    );

    // 将新签发的会话 Cookie 复制到新上下文，验证会话可持久使用。
    const organizationAdminCookie = (
      await orgLoginContext.cookies(getAdminBaseUrl())
    ).find((cookie) => cookie.name === "admin_session_id");
    expect(organizationAdminCookie?.value).toBeTruthy();
    copiedOrgSessionContext = await browser.newContext({
      baseURL: getAdminBaseUrl(),
      storageState: await orgLoginContext.storageState(),
    });
    copiedOrgSessionPage = await copiedOrgSessionContext.newPage();
    await copiedOrgSessionPage.goto("/sign-in");
    const freshOrganizationSession =
      await readApiResponseFromPage<TestAdminSession>(
        copiedOrgSessionPage,
        "/api/admin/auth/me",
      );
    expect(freshOrganizationSession.status).toBe(200);
    expect(freshOrganizationSession.body?.user_id).toBe(createdAdmin.id);

    passwordOrgContext = await createRecordedContext(
      browser,
      getAdminBaseUrl(),
    );
    passwordOrgPage = await passwordOrgContext.newPage();
    await passwordOrgPage.goto("/sign-in");
    await passwordOrgPage
      .getByTestId("admin-login-identifier-input")
      .fill(passwordOrganizationAdminUsername);
    await passwordOrgPage
      .getByTestId("admin-login-password-input")
      .fill(passwordOrganizationAdminPassword);
    const passwordLoginResponsePromise = waitForCanonicalResponse(
      passwordOrgPage,
      "POST",
      "/api/admin/auth/login",
    );
    await passwordOrgPage
      .getByTestId("admin-login-submit-button")
      .click();
    const passwordLoginResponse = await passwordLoginResponsePromise;
    expect(passwordLoginResponse.status()).toBe(200);
    await expect(passwordOrgPage).toHaveURL(/\/users/);
    const passwordOrganizationSession =
      await readApiResponseFromPage<TestAdminSession>(
        passwordOrgPage,
        "/api/admin/auth/me",
      );
    expect(passwordOrganizationSession.status).toBe(200);
    expect(passwordOrganizationSession.body).toMatchObject({
      user_id: passwordCreatedAdmin.id,
      username: passwordOrganizationAdminUsername,
      role: "org",
      organization_id: createdOrganization.id,
    });
    await expect(
      passwordOrgPage.locator('a[href="/organizations"]'),
    ).toHaveCount(0);
    await expect(passwordOrgPage.locator('a[href="/admins"]')).toHaveCount(0);
    await expect(
      passwordOrgPage
        .getByRole("row")
        .filter({ hasText: inOrganizationEmail }),
    ).toBeVisible();
    await expect(
      passwordOrgPage
        .getByRole("row")
        .filter({ hasText: defaultOrganizationEmail }),
    ).toHaveCount(0);
    await saveEvidenceScreenshot(
      passwordOrgPage,
      organizationPrdStem,
      "rv-1-org-admin-password-users.png",
    );

    await saveEvidenceVideo(
      orgLoginPage,
      organizationPrdStem,
      "rv-1-org-admin-sign-in.webm",
    );

    // 解绑只清除本地关联；仍符合条件的已验证身份可以重新绑定。
    await page.goto("/admins");
    const boundAdminRow = page
      .getByRole("row")
      .filter({ hasText: organizationAdminEmail });
    await expect(boundAdminRow.getByText(/bound/i)).toBeVisible();
    await boundAdminRow.getByRole("button", { name: /unbind/i }).click();
    const unbindDialog = page.getByRole("alertdialog");
    await expect(unbindDialog).toContainText(
      /does not disable the identity provider account/i,
    );
    await expect(unbindDialog).toContainText(
      /same verified identity may bind again/i,
    );
    const unbindResponsePromise = waitForCanonicalResponse(
      page,
      "POST",
      `/api/admin/admins/${createdAdmin.id}/unbind-oidc`,
    );
    await unbindDialog.getByRole("button", { name: /confirm/i }).click();
    const unbindResponse = await unbindResponsePromise;
    expect(unbindResponse.status()).toBe(200);
    await expect(boundAdminRow.getByText(/not bound/i)).toBeVisible();

    // 模拟身份中心停用身份：不发起回调，也不创建本地会话。
    providerDisabledContext = await browser.newContext({
      baseURL: getAdminBaseUrl(),
      storageState: { cookies: [], origins: [] },
    });
    const providerDisabledPage = await providerDisabledContext.newPage();
    await providerDisabledPage.goto("/sign-in");
    await beginOidcAuthorization(providerDisabledPage, {
      buttonTestId: "admin-oidc-sign-in",
      startApiPath: "/api/admin/auth/oidc/start",
      issuerUrl,
    });
    await fillTestIdentity(providerDisabledPage, {
      email: organizationAdminEmail,
      subject: identitySubject,
      emailVerified: true,
      disabled: true,
    });
    await providerDisabledPage.getByTestId("oidc-test-submit").click();
    await expect(providerDisabledPage.getByRole("alert")).toContainText(
      "This test identity is disabled at the provider.",
    );
    const providerDisabledAppPage = await providerDisabledContext.newPage();
    await providerDisabledAppPage.goto("/sign-in");
    const disabledIdentitySession = await readApiResponseFromPage(
      providerDisabledAppPage,
      "/api/admin/auth/me",
    );
    expect(disabledIdentitySession.status).toBe(401);
    await providerDisabledContext.close();
    providerDisabledContext = null;

    // 解绑后复用同一启用身份，遵循已确认的首次绑定规则。
    reboundOrgContext = await browser.newContext({
      baseURL: getAdminBaseUrl(),
      storageState: { cookies: [], origins: [] },
    });
    reboundOrgPage = await reboundOrgContext.newPage();
    const reboundLogin = await startAndSubmitAdminIdentity(reboundOrgPage, {
      issuerUrl,
      email: organizationAdminEmail,
      subject: identitySubject,
      emailVerified: true,
    });
    expect(reboundLogin.callbackStatus).toBe(302);
    await expect(reboundOrgPage).toHaveURL(/\/users/);
    const reboundSession = await readApiResponseFromPage<TestAdminSession>(
      reboundOrgPage,
      "/api/admin/auth/me",
    );
    expect(reboundSession.status).toBe(200);
    expect(reboundSession.body?.user_id).toBe(createdAdmin.id);
    await page.goto("/admins");
    const reboundAdminRow = page
      .getByRole("row")
      .filter({ hasText: organizationAdminEmail });
    await expect(reboundAdminRow.getByText(/bound/i)).toBeVisible();

    // 本地禁用后，两条既有 OIDC 会话都应在下一次 API 请求失效。
    await reboundAdminRow.getByRole("button", { name: /disable/i }).click();
    const disableDialog = page.getByRole("alertdialog");
    await expect(disableDialog).toContainText(
      /password and organization account sign-in will be blocked/i,
    );
    await expect(disableDialog).toContainText(
      /existing sessions will stop working on the next request/i,
    );
    const disableResponsePromise = waitForCanonicalResponse(
      page,
      "POST",
      `/api/admin/admins/${createdAdmin.id}/disable`,
    );
    await disableDialog.getByRole("button", { name: /confirm/i }).click();
    const disableResponse = await disableResponsePromise;
    expect(disableResponse.status()).toBe(200);

    const existingOrgSession = await readApiResponseFromPage(
      copiedOrgSessionPage,
      "/api/admin/auth/me",
    );
    expect(existingOrgSession.status).toBe(401);
    const reboundExistingOrgSession = await readApiResponseFromPage(
      reboundOrgPage,
      "/api/admin/auth/me",
    );
    expect(reboundExistingOrgSession.status).toBe(401);

    await page.goto("/admins");
    const passwordAdminRow = page
      .getByRole("row")
      .filter({ hasText: passwordOrganizationAdminEmail });
    await passwordAdminRow.getByRole("button", { name: /disable/i }).click();
    const passwordDisableDialog = page.getByRole("alertdialog");
    await expect(passwordDisableDialog).toContainText(
      /password and organization account sign-in will be blocked/i,
    );
    const passwordDisableResponsePromise = waitForCanonicalResponse(
      page,
      "POST",
      `/api/admin/admins/${passwordCreatedAdmin.id}/disable`,
    );
    await passwordDisableDialog
      .getByRole("button", { name: /confirm/i })
      .click();
    const passwordDisableResponse = await passwordDisableResponsePromise;
    expect(passwordDisableResponse.status()).toBe(200);
    const existingPasswordOrgSession = await readApiResponseFromPage(
      passwordOrgPage,
      "/api/admin/auth/me",
    );
    expect(existingPasswordOrgSession.status).toBe(401);
    await saveEvidenceVideo(
      passwordOrgPage,
      organizationPrdStem,
      "rv-1-org-admin-password-sign-in.webm",
    );

    await page.goto("/admins");
    const disabledOidcAdminRow = page
      .getByRole("row")
      .filter({ hasText: organizationAdminEmail });
    const enableAdminResponsePromise = waitForCanonicalResponse(
      page,
      "POST",
      `/api/admin/admins/${createdAdmin.id}/enable`,
    );
    await disabledOidcAdminRow
      .getByRole("button", { name: /enable/i })
      .click();
    const enableDialog = page.getByRole("alertdialog");
    await expect(enableDialog).toBeVisible();
    await enableDialog.getByRole("button", { name: /confirm/i }).click();
    const enableAdminResponse = await enableAdminResponsePromise;
    expect(enableAdminResponse.status()).toBe(200);

    recoveredOrgContext = await createRecordedContext(
      browser,
      getAdminBaseUrl(),
    );
    recoveredOrgPage = await recoveredOrgContext.newPage();
    const recoveredOidcLogin = await startAndSubmitAdminIdentity(
      recoveredOrgPage,
      {
        issuerUrl,
        email: organizationAdminEmail,
        subject: identitySubject,
        emailVerified: true,
      },
    );
    expect(recoveredOidcLogin.callbackStatus).toBe(302);
    await expect(recoveredOrgPage).toHaveURL(/\/users/);
    const recoveredOrganizationSession =
      await readApiResponseFromPage<TestAdminSession>(
        recoveredOrgPage,
        "/api/admin/auth/me",
      );
    expect(recoveredOrganizationSession.status).toBe(200);
    expect(recoveredOrganizationSession.body?.user_id).toBe(createdAdmin.id);
    await saveEvidenceScreenshot(
      recoveredOrgPage,
      organizationPrdStem,
      "rv-1-org-admin-reenabled-users.png",
    );
    await saveEvidenceVideo(
      recoveredOrgPage,
      organizationPrdStem,
      "rv-1-org-admin-reenabled-sign-in.webm",
    );
  } catch (error) {
    organizationFlowFailed = true;
    throw error;
  } finally {
    if (providerDisabledContext) await providerDisabledContext.close();
    if (reboundOrgContext) await reboundOrgContext.close();
    if (copiedOrgSessionContext) await copiedOrgSessionContext.close();
    if (orgLoginContext) await orgLoginContext.close();
    if (passwordOrgContext) await passwordOrgContext.close();
    if (recoveredOrgContext) await recoveredOrgContext.close();
    try {
      await page.goto("/registration");
      await setRegistrationPolicy(page, previousPolicy);
    } catch (cleanupError) {
      organizationCleanupError = cleanupError;
      if (organizationFlowFailed) {
        test.info().annotations.push({
          type: "cleanup",
          description:
            "Registration policy cleanup failed after the main organization flow had already failed; the dedicated E2E database will be recreated before a retry.",
        });
      }
    }
  }
  if (organizationCleanupError !== undefined) {
    if (organizationCleanupError instanceof Error) {
      throw organizationCleanupError;
    }
    throw new Error("Registration policy cleanup failed.", {
      cause: organizationCleanupError,
    });
  }
});
