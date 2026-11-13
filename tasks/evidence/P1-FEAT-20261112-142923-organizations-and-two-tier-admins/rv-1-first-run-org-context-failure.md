# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: admin/organizations-and-admins.oidc.admin.spec.ts >> platform-created organization admin binds with OIDC and stays within its organization
- Location: tests/admin/organizations-and-admins.oidc.admin.spec.ts:150:1

# Error details

```
Error: page.evaluate: TypeError: Failed to execute 'fetch' on 'Window': Failed to parse URL from /api/admin/auth/me
    at eval (eval at evaluate (:370:30), <anonymous>:2:31)
    at UtilityScript.evaluate (<anonymous>:372:16)
    at UtilityScript.<anonymous> (<anonymous>:1:44)
```
