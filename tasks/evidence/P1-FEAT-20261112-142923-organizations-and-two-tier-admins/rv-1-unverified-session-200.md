# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: admin/organizations-and-admins.oidc.admin.spec.ts >> platform-created organization admin binds with OIDC and stays within its organization
- Location: tests/admin/organizations-and-admins.oidc.admin.spec.ts:168:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 401
Received: 200
```

# Page snapshot

```yaml
- generic [ref=f4e2]:
  - generic [ref=f4e6]:
    - link "Skip to Main" [ref=f4e7] [cursor=pointer]:
      - /url: "#content"
    - generic [ref=f4e10]:
      - list [ref=f4e12]:
        - listitem [ref=f4e13]:
          - button "Zata Admin Vite + ShadcnUI" [ref=f4e14] [cursor=pointer]:
            - generic [ref=f4e18]:
              - generic [ref=f4e19]: Zata Admin
              - generic [ref=f4e20]: Vite + ShadcnUI
      - generic [ref=f4e24]:
        - generic [ref=f4e25]:
          - generic [ref=f4e26]: General
          - list [ref=f4e27]:
            - listitem [ref=f4e28]:
              - link "Dashboard" [ref=f4e29] [cursor=pointer]:
                - /url: /
            - listitem [ref=f4e36]:
              - link "Projects" [ref=f4e37] [cursor=pointer]:
                - /url: /projects
            - listitem [ref=f4e42]:
              - link "Tasks" [ref=f4e43] [cursor=pointer]:
                - /url: /tasks
            - listitem [ref=f4e48]:
              - link "Users" [ref=f4e49] [cursor=pointer]:
                - /url: /users
            - listitem [ref=f4e56]:
              - link "Registration settings" [ref=f4e57] [cursor=pointer]:
                - /url: /registration
            - listitem [ref=f4e71]:
              - link "Organizations" [ref=f4e72] [cursor=pointer]:
                - /url: /organizations
            - listitem [ref=f4e78]:
              - link "Administrators" [ref=f4e79] [cursor=pointer]:
                - /url: /admins
            - listitem [ref=f4e93]:
              - link "Run Tracing" [ref=f4e94] [cursor=pointer]:
                - /url: /run-tracing
        - generic [ref=f4e98]:
          - generic [ref=f4e99]: Other
          - list [ref=f4e100]:
            - listitem [ref=f4e101]:
              - button "Settings" [ref=f4e102] [cursor=pointer]
            - listitem [ref=f4e109]:
              - link "Help Center" [ref=f4e110] [cursor=pointer]:
                - /url: /help-center
      - list [ref=f4e116]:
        - listitem [ref=f4e117]:
          - button "SN playwright_admin playwright_admin" [ref=f4e118] [cursor=pointer]:
            - generic [ref=f4e119]: SN
            - generic [ref=f4e121]:
              - generic [ref=f4e122]: playwright_admin
              - generic [ref=f4e123]: playwright_admin
      - button "Toggle Sidebar" [ref=f4e127]
    - generic [ref=f4e128]:
      - banner [ref=f4e129]:
        - generic [ref=f4e130]:
          - button "Toggle Sidebar" [ref=f4e131] [cursor=pointer]
          - button "Search ⌘ K" [ref=f4e133] [cursor=pointer]:
            - generic [ref=f4e134]: Search
            - generic:
              - generic: ⌘
              - text: K
          - button "Toggle theme" [ref=f4e135] [cursor=pointer]
          - button "Open theme settings" [ref=f4e137] [cursor=pointer]
          - button "SN" [ref=f4e138] [cursor=pointer]
          - group "Language" [ref=f4e141]:
            - button "English" [ref=f4e146] [cursor=pointer]
            - button "Chinese" [ref=f4e147] [cursor=pointer]
      - main [ref=f4e148]:
        - generic [ref=f4e149]:
          - heading "Registration settings" [level=2] [ref=f4e150]
          - paragraph [ref=f4e151]: Choose which registration methods are available to public users.
        - generic [ref=f4e152]:
          - group "Registration mode" [ref=f4e153]:
            - radiogroup "Registration mode" [ref=f4e155]:
              - generic [ref=f4e156]:
                - radio "Password and organization account Allow registration with a password or an organization account." [checked] [ref=f4e157] [cursor=pointer]
                - radio [checked] [aria-hidden]
                - generic [ref=f4e160]:
                  - generic [ref=f4e161]: Password and organization account
                  - generic [ref=f4e162]: Allow registration with a password or an organization account.
              - generic [ref=f4e163]:
                - radio "Organization account only Allow new accounts through the configured organization identity provider." [ref=f4e164] [cursor=pointer]
                - radio [aria-hidden]
                - generic [ref=f4e165]:
                  - generic [ref=f4e166]: Organization account only
                  - generic [ref=f4e167]: Allow new accounts through the configured organization identity provider.
              - generic [ref=f4e168]:
                - radio "Registration closed Do not allow new public accounts." [ref=f4e169] [cursor=pointer]
                - radio [aria-hidden]
                - generic [ref=f4e170]:
                  - generic [ref=f4e171]: Registration closed
                  - generic [ref=f4e172]: Do not allow new public accounts.
          - generic [ref=f4e173]:
            - generic [ref=f4e174]: Allowed email domains
            - textbox "Allowed email domains" [ref=f4e175]:
              - /placeholder: "example.com\nacme.org"
            - paragraph [ref=f4e176]: Enter one domain per line. Leave empty to allow any email domain.
            - paragraph [ref=f4e177]: Password registration checks the entered email address only; it does not verify mailbox ownership.
          - button "Save settings" [active] [ref=f4e179] [cursor=pointer]
  - generic [ref=f4e180]:
    - heading "Command Palette" [level=2] [ref=f4e181]
    - paragraph [ref=f4e182]: Search for a command to run...
  - region "Notifications alt+T":
    - list:
      - listitem [ref=f4e183]:
        - generic [ref=f4e187]: Registration settings saved.
  - button "Open Tanstack query devtools" [ref=f4e239] [cursor=pointer]
  - generic:
    - contentinfo:
      - button "Open TanStack Router Devtools" [ref=f4e288] [cursor=pointer]:
        - generic [ref=f4e360]: "-"
        - generic [ref=f4e361]: TanStack Router
```

# Test source

```ts
  248 |       captureRegistrationEvidence: true,
  249 |     });
  250 |     const defaultOrganizationUser = await registerPublicUser(browser, {
  251 |       email: defaultOrganizationEmail,
  252 |       displayName: `E2E Default Organization ${uniqueSuffix}`,
  253 |     });
  254 |
  255 |     await page.goto("/users");
  256 |     const searchInput = page.getByPlaceholder(/search/i);
  257 |     await searchInput.fill(inOrganizationEmail);
  258 |     const filteredUsersResponsePromise = waitForCanonicalResponse(
  259 |       page,
  260 |       "GET",
  261 |       "/api/admin/users",
  262 |     );
  263 |     await page.getByRole("button", { name: "Search", exact: true }).click();
  264 |     const filteredUsersResponse = await filteredUsersResponsePromise;
  265 |     expect(filteredUsersResponse.status()).toBe(200);
  266 |     const inOrganizationRow = page
  267 |       .getByRole("row")
  268 |       .filter({ hasText: inOrganizationEmail });
  269 |     await expect(inOrganizationRow).toBeVisible();
  270 |     const userOrganizationSelect = page.getByTestId(
  271 |       `user-organization-${inOrganizationUser.user_id}`,
  272 |     );
  273 |     await userOrganizationSelect.click();
  274 |     const moveUserResponsePromise = waitForCanonicalResponse(
  275 |       page,
  276 |       "PATCH",
  277 |       `/api/admin/users/${inOrganizationUser.user_id}/organization`,
  278 |     );
  279 |     await page
  280 |       .getByRole("option", { name: organizationName, exact: true })
  281 |       .click();
  282 |     const moveUserResponse = await moveUserResponsePromise;
  283 |     expect(moveUserResponse.status()).toBe(200);
  284 |     expect(await moveUserResponse.json()).toMatchObject({
  285 |       id: inOrganizationUser.user_id,
  286 |       organization_id: createdOrganization.id,
  287 |     });
  288 |     expect(defaultOrganizationUser.user_id).toBeTruthy();
  289 |
  290 |     await page.goto("/admins");
  291 |     await page.getByTestId("admin-username").fill(organizationAdminUsername);
  292 |     await page.getByTestId("admin-email").fill(organizationAdminEmail);
  293 |     await page.locator("#admin-role").click();
  294 |     await page
  295 |       .getByRole("option", { name: /organization administrator|组织管理员/i })
  296 |       .click();
  297 |     await page.locator("#admin-organization").click();
  298 |     await page
  299 |       .getByRole("option", { name: organizationName, exact: true })
  300 |       .click();
  301 |     await page.getByTestId("admin-password").fill("");
  302 |     await expect(page.getByTestId("admin-password")).toHaveValue("");
  303 |     await saveEvidenceScreenshot(
  304 |       page,
  305 |       organizationPrdStem,
  306 |       "rv-1-admin-create.png",
  307 |     );
  308 |
  309 |     const createAdminResponsePromise = waitForCanonicalResponse(
  310 |       page,
  311 |       "POST",
  312 |       "/api/admin/admins",
  313 |     );
  314 |     await page.getByTestId("admin-create").click();
  315 |     const createAdminResponse = await createAdminResponsePromise;
  316 |     expect([200, 201]).toContain(createAdminResponse.status());
  317 |     const createdAdmin = (await createAdminResponse.json()) as CreatedAdmin;
  318 |     expect(createdAdmin.id).toBeTruthy();
  319 |     expect(createdAdmin.email).toBe(organizationAdminEmail);
  320 |     expect(createdAdmin.role).toBe("org");
  321 |     expect(createdAdmin.organization_id).toBe(createdOrganization.id);
  322 |     expect(createdAdmin.oidc_bound).toBe(false);
  323 |     expect(createAdminResponse.request().postDataJSON()).not.toHaveProperty(
  324 |       "password",
  325 |     );
  326 |     const createdAdminRow = page
  327 |       .getByRole("row")
  328 |       .filter({ hasText: organizationAdminEmail });
  329 |     await expect(createdAdminRow).toBeVisible();
  330 |
  331 |     // 首次登录使用未验证邮箱时必须失败，且不能创建会话。
  332 |     const unverifiedContext = await browser.newContext({
  333 |       baseURL: getAdminBaseUrl(),
  334 |     });
  335 |     const unverifiedPage = await unverifiedContext.newPage();
  336 |     const unverifiedLogin = await startAndSubmitAdminIdentity(unverifiedPage, {
  337 |       issuerUrl,
  338 |       email: organizationAdminEmail,
  339 |       subject: identitySubject,
  340 |       emailVerified: false,
  341 |     });
  342 |     expect(unverifiedLogin.callbackStatus).toBe(302);
  343 |     await expect(unverifiedPage).toHaveURL(/\/sign-in\?sso_error=1/);
  344 |     const unverifiedSession = await readApiResponseFromPage(
  345 |       unverifiedPage,
  346 |       "/api/admin/auth/me",
  347 |     );
> 348 |     expect(unverifiedSession.status).toBe(401);
      |                                      ^ Error: expect(received).toBe(expected) // Object.is equality
  349 |     await unverifiedContext.close();
  350 |
  351 |     // 新浏览器上下文使用已验证企业账号登录。
  352 |     orgLoginContext = await createRecordedContext(browser, getAdminBaseUrl());
  353 |     orgLoginPage = await orgLoginContext.newPage();
  354 |     const successfulOrgLogin = await startAndSubmitAdminIdentity(orgLoginPage, {
  355 |       issuerUrl,
  356 |       email: organizationAdminEmail,
  357 |       subject: identitySubject,
  358 |       emailVerified: true,
  359 |     });
  360 |     expect(successfulOrgLogin.callbackStatus).toBe(302);
  361 |     await expect(orgLoginPage).toHaveURL(/\/users/);
  362 |     const organizationAdminSession =
  363 |       await readApiResponseFromPage<TestAdminSession>(
  364 |         orgLoginPage,
  365 |         "/api/admin/auth/me",
  366 |       );
  367 |     expect(organizationAdminSession.status).toBe(200);
  368 |     expect(organizationAdminSession.body).toMatchObject({
  369 |       user_id: createdAdmin.id,
  370 |       username: organizationAdminUsername,
  371 |       role: "org",
  372 |       organization_id: createdOrganization.id,
  373 |       organization_name: organizationName,
  374 |     });
  375 |     await expect(orgLoginPage.locator('a[href="/organizations"]')).toHaveCount(
  376 |       0,
  377 |     );
  378 |     await expect(orgLoginPage.locator('a[href="/admins"]')).toHaveCount(0);
  379 |     await orgLoginPage.goto("/organizations");
  380 |     await expect(orgLoginPage).toHaveURL(/\/users/);
  381 |     await expect(
  382 |       orgLoginPage.getByRole("row").filter({ hasText: inOrganizationEmail }),
  383 |     ).toBeVisible();
  384 |     await expect(
  385 |       orgLoginPage
  386 |         .getByRole("row")
  387 |         .filter({ hasText: defaultOrganizationEmail }),
  388 |     ).toHaveCount(0);
  389 |     await saveEvidenceScreenshot(
  390 |       orgLoginPage,
  391 |       organizationPrdStem,
  392 |       "rv-1-org-admin-users.png",
  393 |     );
  394 |
  395 |     // 将新签发的会话 Cookie 复制到新上下文，验证会话可持久使用。
  396 |     const organizationAdminCookie = (
  397 |       await orgLoginContext.cookies(getAdminBaseUrl())
  398 |     ).find((cookie) => cookie.name === "admin_session_id");
  399 |     expect(organizationAdminCookie?.value).toBeTruthy();
  400 |     copiedOrgSessionContext = await browser.newContext({
  401 |       baseURL: getAdminBaseUrl(),
  402 |       storageState: await orgLoginContext.storageState(),
  403 |     });
  404 |     copiedOrgSessionPage = await copiedOrgSessionContext.newPage();
  405 |     await copiedOrgSessionPage.goto("/sign-in");
  406 |     const freshOrganizationSession =
  407 |       await readApiResponseFromPage<TestAdminSession>(
  408 |         copiedOrgSessionPage,
  409 |         "/api/admin/auth/me",
  410 |       );
  411 |     expect(freshOrganizationSession.status).toBe(200);
  412 |     expect(freshOrganizationSession.body?.user_id).toBe(createdAdmin.id);
  413 |
  414 |     await saveEvidenceVideo(
  415 |       orgLoginPage,
  416 |       organizationPrdStem,
  417 |       "rv-1-org-admin-sign-in.webm",
  418 |     );
  419 |
  420 |     // 解绑只清除本地关联；仍符合条件的已验证身份可以重新绑定。
  421 |     await page.goto("/admins");
  422 |     const boundAdminRow = page
  423 |       .getByRole("row")
  424 |       .filter({ hasText: organizationAdminEmail });
  425 |     await expect(boundAdminRow.getByText(/bound/i)).toBeVisible();
  426 |     await boundAdminRow.getByRole("button", { name: /unbind/i }).click();
  427 |     const unbindDialog = page.getByRole("alertdialog");
  428 |     await expect(unbindDialog).toContainText(
  429 |       /does not disable the identity provider account/i,
  430 |     );
  431 |     await expect(unbindDialog).toContainText(
  432 |       /same verified identity may bind again/i,
  433 |     );
  434 |     const unbindResponsePromise = waitForCanonicalResponse(
  435 |       page,
  436 |       "POST",
  437 |       `/api/admin/admins/${createdAdmin.id}/unbind-oidc`,
  438 |     );
  439 |     await unbindDialog.getByRole("button", { name: /confirm/i }).click();
  440 |     const unbindResponse = await unbindResponsePromise;
  441 |     expect(unbindResponse.status()).toBe(200);
  442 |     await expect(boundAdminRow.getByText(/not bound/i)).toBeVisible();
  443 |
  444 |     // 模拟身份中心停用身份：不发起回调，也不创建本地会话。
  445 |     providerDisabledContext = await browser.newContext({
  446 |       baseURL: getAdminBaseUrl(),
  447 |     });
  448 |     const providerDisabledPage = await providerDisabledContext.newPage();
```
