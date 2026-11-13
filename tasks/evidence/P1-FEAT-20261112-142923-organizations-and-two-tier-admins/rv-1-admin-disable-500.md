# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: admin/organizations-and-admins.oidc.admin.spec.ts >> platform-created organization admin binds with OIDC and stays within its organization
- Location: tests/admin/organizations-and-admins.oidc.admin.spec.ts:177:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 200
Received: 500
```

# Page snapshot

```yaml
- generic [ref=f6e2]:
  - generic [ref=f6e5]:
    - link "Skip to Main" [ref=f6e6] [cursor=pointer]:
      - /url: "#content"
    - generic [ref=f6e9]:
      - list [ref=f6e11]:
        - listitem [ref=f6e12]:
          - button "Zata Admin Vite + ShadcnUI" [ref=f6e13] [cursor=pointer]:
            - generic [ref=f6e17]:
              - generic [ref=f6e18]: Zata Admin
              - generic [ref=f6e19]: Vite + ShadcnUI
      - generic [ref=f6e23]:
        - generic [ref=f6e24]:
          - generic [ref=f6e25]: General
          - list [ref=f6e26]:
            - listitem [ref=f6e27]:
              - link "Dashboard" [ref=f6e28] [cursor=pointer]:
                - /url: /
            - listitem [ref=f6e35]:
              - link "Projects" [ref=f6e36] [cursor=pointer]:
                - /url: /projects
            - listitem [ref=f6e41]:
              - link "Tasks" [ref=f6e42] [cursor=pointer]:
                - /url: /tasks
            - listitem [ref=f6e47]:
              - link "Users" [ref=f6e48] [cursor=pointer]:
                - /url: /users
            - listitem [ref=f6e55]:
              - link "Registration settings" [ref=f6e56] [cursor=pointer]:
                - /url: /registration
            - listitem [ref=f6e70]:
              - link "Organizations" [ref=f6e71] [cursor=pointer]:
                - /url: /organizations
            - listitem [ref=f6e77]:
              - link "Administrators" [ref=f6e78] [cursor=pointer]:
                - /url: /admins
            - listitem [ref=f6e92]:
              - link "Run Tracing" [ref=f6e93] [cursor=pointer]:
                - /url: /run-tracing
        - generic [ref=f6e97]:
          - generic [ref=f6e98]: Other
          - list [ref=f6e99]:
            - listitem [ref=f6e100]:
              - button "Settings" [ref=f6e101] [cursor=pointer]
            - listitem [ref=f6e108]:
              - link "Help Center" [ref=f6e109] [cursor=pointer]:
                - /url: /help-center
      - list [ref=f6e115]:
        - listitem [ref=f6e116]:
          - button "SN playwright_admin playwright_admin" [ref=f6e117] [cursor=pointer]:
            - generic [ref=f6e118]: SN
            - generic [ref=f6e120]:
              - generic [ref=f6e121]: playwright_admin
              - generic [ref=f6e122]: playwright_admin
      - button "Toggle Sidebar" [ref=f6e126]
    - generic [ref=f6e127]:
      - banner [ref=f6e128]:
        - generic [ref=f6e129]:
          - button "Toggle Sidebar" [ref=f6e130] [cursor=pointer]
          - button "Search ⌘ K" [ref=f6e132] [cursor=pointer]:
            - generic [ref=f6e133]: Search
            - generic:
              - generic: ⌘
              - text: K
          - button "Toggle theme" [ref=f6e134] [cursor=pointer]
          - button "Open theme settings" [ref=f6e136] [cursor=pointer]
          - button "SN" [ref=f6e137] [cursor=pointer]
          - group "Language" [ref=f6e140]:
            - button "English" [ref=f6e145] [cursor=pointer]
            - button "Chinese" [ref=f6e146] [cursor=pointer]
      - main [ref=f6e147]:
        - generic [ref=f6e148]:
          - heading "Registration settings" [level=2] [ref=f6e149]
          - paragraph [ref=f6e150]: Choose which registration methods are available to public users.
        - generic [ref=f6e151]:
          - group "Registration mode" [ref=f6e152]:
            - radiogroup "Registration mode" [ref=f6e154]:
              - generic [ref=f6e155]:
                - radio "Password and organization account Allow registration with a password or an organization account." [checked] [ref=f6e156] [cursor=pointer]
                - radio [checked] [aria-hidden]
                - generic [ref=f6e159]:
                  - generic [ref=f6e160]: Password and organization account
                  - generic [ref=f6e161]: Allow registration with a password or an organization account.
              - generic [ref=f6e162]:
                - radio "Organization account only Allow new accounts through the configured organization identity provider." [ref=f6e163] [cursor=pointer]
                - radio [aria-hidden]
                - generic [ref=f6e164]:
                  - generic [ref=f6e165]: Organization account only
                  - generic [ref=f6e166]: Allow new accounts through the configured organization identity provider.
              - generic [ref=f6e167]:
                - radio "Registration closed Do not allow new public accounts." [ref=f6e168] [cursor=pointer]
                - radio [aria-hidden]
                - generic [ref=f6e169]:
                  - generic [ref=f6e170]: Registration closed
                  - generic [ref=f6e171]: Do not allow new public accounts.
          - generic [ref=f6e172]:
            - generic [ref=f6e173]: Allowed email domains
            - textbox "Allowed email domains" [ref=f6e174]:
              - /placeholder: "example.com\nacme.org"
            - paragraph [ref=f6e175]: Enter one domain per line. Leave empty to allow any email domain.
            - paragraph [ref=f6e176]: Password registration checks the entered email address only; it does not verify mailbox ownership.
          - button "Save settings" [active] [ref=f6e178] [cursor=pointer]
  - generic [ref=f6e179]:
    - heading "Command Palette" [level=2] [ref=f6e180]
    - paragraph [ref=f6e181]: Search for a command to run...
  - region "Notifications alt+T":
    - list:
      - listitem [ref=f6e182]:
        - generic [ref=f6e186]: Registration settings saved.
  - button "Open Tanstack query devtools" [ref=f6e238] [cursor=pointer]
  - generic:
    - contentinfo:
      - button "Open TanStack Router Devtools" [ref=f6e287] [cursor=pointer]:
        - generic [ref=f6e359]: "-"
        - generic [ref=f6e360]: TanStack Router
```

# Test source

```ts
  444 |     );
  445 |
  446 |     // 解绑只清除本地关联；仍符合条件的已验证身份可以重新绑定。
  447 |     await page.goto("/admins");
  448 |     const boundAdminRow = page
  449 |       .getByRole("row")
  450 |       .filter({ hasText: organizationAdminEmail });
  451 |     await expect(boundAdminRow.getByText(/bound/i)).toBeVisible();
  452 |     await boundAdminRow.getByRole("button", { name: /unbind/i }).click();
  453 |     const unbindDialog = page.getByRole("alertdialog");
  454 |     await expect(unbindDialog).toContainText(
  455 |       /does not disable the identity provider account/i,
  456 |     );
  457 |     await expect(unbindDialog).toContainText(
  458 |       /same verified identity may bind again/i,
  459 |     );
  460 |     const unbindResponsePromise = waitForCanonicalResponse(
  461 |       page,
  462 |       "POST",
  463 |       `/api/admin/admins/${createdAdmin.id}/unbind-oidc`,
  464 |     );
  465 |     await unbindDialog.getByRole("button", { name: /confirm/i }).click();
  466 |     const unbindResponse = await unbindResponsePromise;
  467 |     expect(unbindResponse.status()).toBe(200);
  468 |     await expect(boundAdminRow.getByText(/not bound/i)).toBeVisible();
  469 |
  470 |     // 模拟身份中心停用身份：不发起回调，也不创建本地会话。
  471 |     providerDisabledContext = await browser.newContext({
  472 |       baseURL: getAdminBaseUrl(),
  473 |       storageState: { cookies: [], origins: [] },
  474 |     });
  475 |     const providerDisabledPage = await providerDisabledContext.newPage();
  476 |     await providerDisabledPage.goto("/sign-in");
  477 |     await beginOidcAuthorization(providerDisabledPage, {
  478 |       buttonTestId: "admin-oidc-sign-in",
  479 |       startApiPath: "/api/admin/auth/oidc/start",
  480 |       issuerUrl,
  481 |     });
  482 |     await fillTestIdentity(providerDisabledPage, {
  483 |       email: organizationAdminEmail,
  484 |       subject: identitySubject,
  485 |       emailVerified: true,
  486 |       disabled: true,
  487 |     });
  488 |     await providerDisabledPage.getByTestId("oidc-test-submit").click();
  489 |     await expect(providerDisabledPage.getByRole("alert")).toContainText(
  490 |       "This test identity is disabled at the provider.",
  491 |     );
  492 |     const providerDisabledAppPage = await providerDisabledContext.newPage();
  493 |     await providerDisabledAppPage.goto("/sign-in");
  494 |     const disabledIdentitySession = await readApiResponseFromPage(
  495 |       providerDisabledAppPage,
  496 |       "/api/admin/auth/me",
  497 |     );
  498 |     expect(disabledIdentitySession.status).toBe(401);
  499 |     await providerDisabledContext.close();
  500 |     providerDisabledContext = null;
  501 |
  502 |     // 解绑后复用同一启用身份，遵循已确认的首次绑定规则。
  503 |     reboundOrgContext = await browser.newContext({
  504 |       baseURL: getAdminBaseUrl(),
  505 |       storageState: { cookies: [], origins: [] },
  506 |     });
  507 |     reboundOrgPage = await reboundOrgContext.newPage();
  508 |     const reboundLogin = await startAndSubmitAdminIdentity(reboundOrgPage, {
  509 |       issuerUrl,
  510 |       email: organizationAdminEmail,
  511 |       subject: identitySubject,
  512 |       emailVerified: true,
  513 |     });
  514 |     expect(reboundLogin.callbackStatus).toBe(302);
  515 |     await expect(reboundOrgPage).toHaveURL(/\/users/);
  516 |     const reboundSession = await readApiResponseFromPage<TestAdminSession>(
  517 |       reboundOrgPage,
  518 |       "/api/admin/auth/me",
  519 |     );
  520 |     expect(reboundSession.status).toBe(200);
  521 |     expect(reboundSession.body?.user_id).toBe(createdAdmin.id);
  522 |     await page.goto("/admins");
  523 |     const reboundAdminRow = page
  524 |       .getByRole("row")
  525 |       .filter({ hasText: organizationAdminEmail });
  526 |     await expect(reboundAdminRow.getByText(/bound/i)).toBeVisible();
  527 |
  528 |     // 本地禁用后，两条既有 OIDC 会话都应在下一次 API 请求失效。
  529 |     await reboundAdminRow.getByRole("button", { name: /disable/i }).click();
  530 |     const disableDialog = page.getByRole("alertdialog");
  531 |     await expect(disableDialog).toContainText(
  532 |       /password and organization account sign-in will be blocked/i,
  533 |     );
  534 |     await expect(disableDialog).toContainText(
  535 |       /existing sessions will stop working on the next request/i,
  536 |     );
  537 |     const disableResponsePromise = waitForCanonicalResponse(
  538 |       page,
  539 |       "POST",
  540 |       `/api/admin/admins/${createdAdmin.id}/disable`,
  541 |     );
  542 |     await disableDialog.getByRole("button", { name: /confirm/i }).click();
  543 |     const disableResponse = await disableResponsePromise;
> 544 |     expect(disableResponse.status()).toBe(200);
      |                                      ^ Error: expect(received).toBe(expected) // Object.is equality
  545 |
  546 |     const existingOrgSession = await readApiResponseFromPage(
  547 |       copiedOrgSessionPage,
  548 |       "/api/admin/auth/me",
  549 |     );
  550 |     expect(existingOrgSession.status).toBe(401);
  551 |     const reboundExistingOrgSession = await readApiResponseFromPage(
  552 |       reboundOrgPage,
  553 |       "/api/admin/auth/me",
  554 |     );
  555 |     expect(reboundExistingOrgSession.status).toBe(401);
  556 |   } finally {
  557 |     if (providerDisabledContext) await providerDisabledContext.close();
  558 |     if (reboundOrgContext) await reboundOrgContext.close();
  559 |     if (copiedOrgSessionContext) await copiedOrgSessionContext.close();
  560 |     if (orgLoginContext) await orgLoginContext.close();
  561 |     await page.goto("/registration");
  562 |     await setRegistrationPolicy(page, previousPolicy);
  563 |   }
  564 | });
  565 |
```
