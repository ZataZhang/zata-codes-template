# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: admin/organizations-and-admins.oidc.admin.spec.ts >> platform-created organization admin binds with OIDC and stays within its organization
- Location: tests/admin/organizations-and-admins.oidc.admin.spec.ts:150:1

# Error details

```
Error: locator.click: Error: strict mode violation: getByRole('button', { name: /search/i }) resolved to 2 elements:
    1) <button data-slot="button" aria-keyshortcuts="Meta+K Control+K" class="inline-flex items-center gap-2 whitespace-nowrap transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive border hover:text-accent-foreground dark:bg-in…>…</button> aka getByRole('button', { name: 'Search ⌘ K' })
    2) <button type="submit" data-slot="button" class="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive border bg-background shadow-xs …>Search</button> aka getByRole('button', { name: 'Search', exact: true })

Call log:
  - waiting for getByRole('button', { name: /search/i })

```

```
Error: page.waitForResponse: Test ended.
```

# Page snapshot

```yaml
- generic [ref=f3e2]:
  - generic [ref=f3e6]:
    - link "Skip to Main" [ref=f3e7] [cursor=pointer]:
      - /url: "#content"
    - generic [ref=f3e10]:
      - list [ref=f3e12]:
        - listitem [ref=f3e13]:
          - button "Zata Admin Vite + ShadcnUI" [ref=f3e14] [cursor=pointer]:
            - generic [ref=f3e18]:
              - generic [ref=f3e19]: Zata Admin
              - generic [ref=f3e20]: Vite + ShadcnUI
      - generic [ref=f3e24]:
        - generic [ref=f3e25]:
          - generic [ref=f3e26]: General
          - list [ref=f3e27]:
            - listitem [ref=f3e28]:
              - link "Dashboard" [ref=f3e29] [cursor=pointer]:
                - /url: /
            - listitem [ref=f3e36]:
              - link "Projects" [ref=f3e37] [cursor=pointer]:
                - /url: /projects
            - listitem [ref=f3e42]:
              - link "Tasks" [ref=f3e43] [cursor=pointer]:
                - /url: /tasks
            - listitem [ref=f3e48]:
              - link "Users" [ref=f3e49] [cursor=pointer]:
                - /url: /users
            - listitem [ref=f3e56]:
              - link "Registration settings" [ref=f3e57] [cursor=pointer]:
                - /url: /registration
            - listitem [ref=f3e71]:
              - link "Organizations" [ref=f3e72] [cursor=pointer]:
                - /url: /organizations
            - listitem [ref=f3e78]:
              - link "Administrators" [ref=f3e79] [cursor=pointer]:
                - /url: /admins
            - listitem [ref=f3e93]:
              - link "Run Tracing" [ref=f3e94] [cursor=pointer]:
                - /url: /run-tracing
        - generic [ref=f3e98]:
          - generic [ref=f3e99]: Other
          - list [ref=f3e100]:
            - listitem [ref=f3e101]:
              - button "Settings" [ref=f3e102] [cursor=pointer]
            - listitem [ref=f3e109]:
              - link "Help Center" [ref=f3e110] [cursor=pointer]:
                - /url: /help-center
      - list [ref=f3e116]:
        - listitem [ref=f3e117]:
          - button "SN playwright_admin playwright_admin" [ref=f3e118] [cursor=pointer]:
            - generic [ref=f3e119]: SN
            - generic [ref=f3e121]:
              - generic [ref=f3e122]: playwright_admin
              - generic [ref=f3e123]: playwright_admin
      - button "Toggle Sidebar" [ref=f3e127]
    - generic [ref=f3e128]:
      - banner [ref=f3e129]:
        - generic [ref=f3e130]:
          - button "Toggle Sidebar" [ref=f3e131] [cursor=pointer]
          - button "Search ⌘ K" [ref=f3e133] [cursor=pointer]:
            - generic [ref=f3e134]: Search
            - generic:
              - generic: ⌘
              - text: K
          - button "Toggle theme" [ref=f3e135] [cursor=pointer]
          - button "Open theme settings" [ref=f3e137] [cursor=pointer]
          - button "SN" [ref=f3e138] [cursor=pointer]
          - group "Language" [ref=f3e141]:
            - button "English" [ref=f3e146] [cursor=pointer]
            - button "Chinese" [ref=f3e147] [cursor=pointer]
      - main [ref=f3e148]:
        - generic [ref=f3e149]:
          - heading "Registration settings" [level=2] [ref=f3e150]
          - paragraph [ref=f3e151]: Choose which registration methods are available to public users.
        - generic [ref=f3e152]:
          - group "Registration mode" [ref=f3e153]:
            - radiogroup "Registration mode" [ref=f3e155]:
              - generic [ref=f3e156]:
                - radio "Password and organization account Allow registration with a password or an organization account." [checked] [ref=f3e157] [cursor=pointer]
                - radio [checked] [aria-hidden]
                - generic [ref=f3e160]:
                  - generic [ref=f3e161]: Password and organization account
                  - generic [ref=f3e162]: Allow registration with a password or an organization account.
              - generic [ref=f3e163]:
                - radio "Organization account only Allow new accounts through the configured organization identity provider." [ref=f3e164] [cursor=pointer]
                - radio [aria-hidden]
                - generic [ref=f3e165]:
                  - generic [ref=f3e166]: Organization account only
                  - generic [ref=f3e167]: Allow new accounts through the configured organization identity provider.
              - generic [ref=f3e168]:
                - radio "Registration closed Do not allow new public accounts." [ref=f3e169] [cursor=pointer]
                - radio [aria-hidden]
                - generic [ref=f3e170]:
                  - generic [ref=f3e171]: Registration closed
                  - generic [ref=f3e172]: Do not allow new public accounts.
          - generic [ref=f3e173]:
            - generic [ref=f3e174]: Allowed email domains
            - textbox "Allowed email domains" [ref=f3e175]:
              - /placeholder: "example.com\nacme.org"
            - paragraph [ref=f3e176]: Enter one domain per line. Leave empty to allow any email domain.
            - paragraph [ref=f3e177]: Password registration checks the entered email address only; it does not verify mailbox ownership.
          - button "Save settings" [active] [ref=f3e179] [cursor=pointer]
  - generic [ref=f3e180]:
    - heading "Command Palette" [level=2] [ref=f3e181]
    - paragraph [ref=f3e182]: Search for a command to run...
  - region "Notifications alt+T":
    - list:
      - listitem [ref=f3e183]:
        - generic [ref=f3e187]: Registration settings saved.
  - button "Open Tanstack query devtools" [ref=f3e239] [cursor=pointer]
  - generic:
    - contentinfo:
      - button "Open TanStack Router Devtools" [ref=f3e288] [cursor=pointer]:
        - generic [ref=f3e360]: "-"
        - generic [ref=f3e361]: TanStack Router
```

# Test source

```ts
  8   |   type Page,
  9   |   type Request,
  10  |   type Response,
  11  | } from '@playwright/test'
  12  |
  13  | export type TestOidcIdentity = {
  14  |   email: string
  15  |   subject: string
  16  |   emailVerified?: boolean
  17  |   disabled?: boolean
  18  | }
  19  |
  20  | const moduleDirectoryPath = dirname(fileURLToPath(import.meta.url))
  21  | const repositoryRootPath = resolve(moduleDirectoryPath, '../../..')
  22  |
  23  | export function requireOidcTestEnvironment(): string {
  24  |   if (process.env.PLAYWRIGHT_OIDC_TESTS !== '1') {
  25  |     throw new Error(
  26  |       'Run these OIDC flows through the E2E stack wrapper with PLAYWRIGHT_OIDC_TESTS=1.'
  27  |     )
  28  |   }
  29  |   const configuredIssuerUrl = process.env.PLAYWRIGHT_OIDC_ISSUER_URL?.trim()
  30  |   if (!configuredIssuerUrl) {
  31  |     throw new Error('PLAYWRIGHT_OIDC_ISSUER_URL is required for real OIDC E2E flows.')
  32  |   }
  33  |   const issuerUrl = new URL(configuredIssuerUrl)
  34  |   if (
  35  |     issuerUrl.protocol !== 'http:' ||
  36  |     !['127.0.0.1', 'localhost', '[::1]'].includes(issuerUrl.hostname)
  37  |   ) {
  38  |     throw new Error('The Playwright OIDC test issuer must use a loopback HTTP URL.')
  39  |   }
  40  |   return issuerUrl.origin
  41  | }
  42  |
  43  | export function getBootstrapAdminEmail(): string {
  44  |   const bootstrapAdminEmail =
  45  |     process.env.PLAYWRIGHT_ADMIN_EMAIL?.trim() ||
  46  |     process.env.AUTH_ADMIN_BOOTSTRAP_EMAIL?.trim() ||
  47  |     ''
  48  |   if (!bootstrapAdminEmail) {
  49  |     throw new Error(
  50  |       'Set AUTH_ADMIN_BOOTSTRAP_EMAIL for the admin OIDC real-entry test; the issuer identity must match the seeded admin email.'
  51  |     )
  52  |   }
  53  |   return bootstrapAdminEmail.toLowerCase()
  54  | }
  55  |
  56  | export function getEvidenceDirectory(prdStem: string): string {
  57  |   return resolve(repositoryRootPath, 'tasks/evidence', prdStem)
  58  | }
  59  |
  60  | export async function saveEvidenceScreenshot(
  61  |   page: Page,
  62  |   prdStem: string,
  63  |   fileName: string
  64  | ): Promise<void> {
  65  |   const targetDirectoryPath = getEvidenceDirectory(prdStem)
  66  |   await mkdir(targetDirectoryPath, { recursive: true })
  67  |   await page.screenshot({
  68  |     path: resolve(targetDirectoryPath, fileName),
  69  |     fullPage: true,
  70  |   })
  71  | }
  72  |
  73  | export async function saveEvidenceVideo(
  74  |   page: Page,
  75  |   prdStem: string,
  76  |   fileName: string
  77  | ): Promise<void> {
  78  |   const pageVideo = page.video()
  79  |   if (!pageVideo) {
  80  |     throw new Error('Video capture is disabled for this Playwright page.')
  81  |   }
  82  |   const targetDirectoryPath = getEvidenceDirectory(prdStem)
  83  |   await mkdir(targetDirectoryPath, { recursive: true })
  84  |   if (!page.isClosed()) await page.close()
  85  |   await pageVideo.saveAs(resolve(targetDirectoryPath, fileName))
  86  | }
  87  |
  88  | export async function createRecordedContext(
  89  |   browser: Browser,
  90  |   baseURL?: string
  91  | ): Promise<BrowserContext> {
  92  |   const configuredResultsDirectory =
  93  |     process.env.PLAYWRIGHT_TEST_RESULTS_DIR?.trim() || 'test-results'
  94  |   const resultsDirectoryPath = resolve(process.cwd(), configuredResultsDirectory)
  95  |   await mkdir(resultsDirectoryPath, { recursive: true })
  96  |   return browser.newContext({
  97  |     ...(baseURL ? { baseURL } : {}),
  98  |     viewport: { width: 1440, height: 1200 },
  99  |     recordVideo: { dir: resultsDirectoryPath },
  100 |   })
  101 | }
  102 |
  103 | export function waitForCanonicalResponse(
  104 |   page: Page,
  105 |   method: string,
  106 |   canonicalApiPath: string
  107 | ): Promise<Response> {
> 108 |   return page.waitForResponse((response) => {
      |               ^ Error: page.waitForResponse: Test ended.
  109 |     const responseUrl = new URL(response.url())
  110 |     return (
  111 |       response.request().method() === method &&
  112 |       responseUrl.pathname === canonicalApiPath
  113 |     )
  114 |   })
  115 | }
  116 |
  117 | export function waitForCanonicalRequest(
  118 |   page: Page,
  119 |   method: string,
  120 |   canonicalApiPath: string
  121 | ): Promise<Request> {
  122 |   return page.waitForRequest((request) => {
  123 |     const requestUrl = new URL(request.url())
  124 |     return request.method() === method && requestUrl.pathname === canonicalApiPath
  125 |   })
  126 | }
  127 |
  128 | export async function beginOidcAuthorization(
  129 |   page: Page,
  130 |   options: {
  131 |     buttonTestId: string
  132 |     startApiPath: string
  133 |     issuerUrl: string
  134 |   }
  135 | ): Promise<URL> {
  136 |   const startResponsePromise = waitForCanonicalResponse(
  137 |     page,
  138 |     'GET',
  139 |     options.startApiPath
  140 |   )
  141 |   const startRequestPromise = waitForCanonicalRequest(
  142 |     page,
  143 |     'GET',
  144 |     options.startApiPath
  145 |   )
  146 |   await page.getByTestId(options.buttonTestId).click()
  147 |   const [startResponse, startRequest] = await Promise.all([
  148 |     startResponsePromise,
  149 |     startRequestPromise,
  150 |   ])
  151 |   expect(startRequest.url()).toContain(options.startApiPath)
  152 |   expect(startResponse.status()).toBe(302)
  153 |   const authorizationUrl = new URL(startResponse.headers().location ?? '')
  154 |   expect(authorizationUrl.origin).toBe(options.issuerUrl)
  155 |   expect(authorizationUrl.pathname).toBe('/authorize')
  156 |   expect(authorizationUrl.searchParams.get('response_type')).toBe('code')
  157 |   expect(authorizationUrl.searchParams.get('code_challenge_method')).toBe('S256')
  158 |   expect(authorizationUrl.searchParams.get('state')).toBeTruthy()
  159 |   expect(authorizationUrl.searchParams.get('nonce')).toBeTruthy()
  160 |   expect(authorizationUrl.searchParams.get('code_challenge')).toBeTruthy()
  161 |   return authorizationUrl
  162 | }
  163 |
  164 | export function waitForOidcCallback(
  165 |   page: Page,
  166 |   options: { callbackApiPath: string }
  167 | ): { request: Promise<Request>; response: Promise<Response> } {
  168 |   return {
  169 |     request: waitForCanonicalRequest(page, 'GET', options.callbackApiPath),
  170 |     response: waitForCanonicalResponse(page, 'GET', options.callbackApiPath),
  171 |   }
  172 | }
  173 |
  174 | export async function fillTestIdentity(
  175 |   page: Page,
  176 |   identity: TestOidcIdentity
  177 | ): Promise<void> {
  178 |   await page.getByTestId('oidc-test-email').fill(identity.email)
  179 |   await page.getByTestId('oidc-test-subject').fill(identity.subject)
  180 |   const verifiedCheckbox = page.getByTestId('oidc-test-email-verified')
  181 |   if (identity.emailVerified === false) await verifiedCheckbox.uncheck()
  182 |   else await verifiedCheckbox.check()
  183 |   if (identity.disabled) {
  184 |     await page.getByTestId('oidc-test-identity-disabled').check()
  185 |   }
  186 | }
  187 |
  188 | export async function readApiResponseFromPage<T>(
  189 |   page: Page,
  190 |   canonicalApiPath: string
  191 | ): Promise<{ status: number; body: T | null }> {
  192 |   return page.evaluate(async (apiPath) => {
  193 |     const apiResponse = await fetch(apiPath, { credentials: 'include' })
  194 |     const responseBody = (await apiResponse.json().catch(() => null)) as T | null
  195 |     return { status: apiResponse.status, body: responseBody }
  196 |   }, canonicalApiPath)
  197 | }
  198 |
```
