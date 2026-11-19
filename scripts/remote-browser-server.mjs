import { writeFileSync } from 'node:fs'
import { chromium } from '/Users/zata/code/zata_code_template/tests/playwright-e2e/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright/index.mjs'

const endpointFile = '/work/tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/.rv58-browser-endpoint'
const secureLocalOrigins = process.env.RV58_SECURE_LOCAL_ORIGINS?.trim()
const chromiumArguments = ['--no-sandbox', '--disable-dev-shm-usage']
if (secureLocalOrigins) {
  chromiumArguments.push(`--unsafely-treat-insecure-origin-as-secure=${secureLocalOrigins}`)
}
const server = await chromium.launchServer({
  headless: true,
  executablePath: '/usr/bin/chromium',
  args: chromiumArguments,
  host: '0.0.0.0',
  port: 3000,
})
writeFileSync(endpointFile, server.wsEndpoint(), 'utf-8')
console.log(`Remote Chromium ready: ${server.wsEndpoint()}`)
await new Promise(() => {})
