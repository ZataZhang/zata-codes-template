import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: '.',
  testMatch: 'direct-transfer.spec.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  reporter: [['list']],
  outputDir: '../../test-results/object-storage',
  use: {
    browserName: 'chromium',
    screenshot: 'off',
    video: 'off',
    trace: 'off',
    viewport: { width: 1200, height: 900 },
  },
})
