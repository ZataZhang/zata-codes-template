import { createHash } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { expect, test, type Browser, type Page, type Request } from '@playwright/test'
import { request as playwrightRequest } from '@playwright/test'

type UploadResult = {
  upload_id: string
  object_key: string
  status: number
  completion?: { content_length: number; content_type: string; cache_control: string }
  api_response_contains_file_body: boolean
}

type ObjectStorageFixture = {
  uploadSelectedFile(visibility: 'public' | 'private' | 'uncached-control'): Promise<UploadResult>
  uploadOversizedControl(): Promise<{
    object_key: string
    status: number
    api_response_contains_file_body: boolean
  }>
  getPublicDelivery(uploadId: string): Promise<{
    url: string
    object_key: string
    cache_control: string
  }>
  displayPublicImage(url: string): Promise<{ complete: boolean; natural_width: number }>
  readPublicImage(url: string): Promise<{
    status: number
    digest_sha256: string
    cache_control: string | null
    age: string | null
    x_cache: string | null
  }>
  requestPrivateRead(uploadId: string, identity: string): Promise<{
    status: number
    body: { read_url?: string; expires_at?: string; object_key?: string }
  }>
}

declare global {
  interface Window {
    objectStorageFixture: ObjectStorageFixture
  }
}

type NetworkRecord = { method: string; host: string; path: string; status?: number }

function requiredEnvironmentValue(environmentName: string): string {
  const environmentValue = process.env[environmentName]
  if (!environmentValue) {
    throw new Error(`Missing ${environmentName}`)
  }
  return environmentValue
}

function expectedOssBucketHost(): string {
  const endpointHost = new URL(requiredEnvironmentValue('OBJECT_STORAGE_E2E_ENDPOINT')).host
  const bucketName = requiredEnvironmentValue('OBJECT_STORAGE_E2E_BUCKET')
  return endpointHost.startsWith(`${bucketName}.`) ? endpointHost : `${bucketName}.${endpointHost}`
}

async function openFixturePage(page: Page): Promise<NetworkRecord[]> {
  const apiBaseUrl = requiredEnvironmentValue('OBJECT_STORAGE_E2E_API_BASE_URL')
  const fixtureOrigin = requiredEnvironmentValue('OBJECT_STORAGE_E2E_BROWSER_ORIGIN')
  const networkRecordList: NetworkRecord[] = []
  const requestRecordByObject = new WeakMap<Request, NetworkRecord>()

  page.on('request', (browserRequest) => {
    const requestUrl = new URL(browserRequest.url())
    const networkRecord: NetworkRecord = {
      method: browserRequest.method(),
      host: requestUrl.host,
      path: requestUrl.pathname,
    }
    networkRecordList.push(networkRecord)
    requestRecordByObject.set(browserRequest, networkRecord)
  })
  page.on('response', (browserResponse) => {
    const networkRecord = requestRecordByObject.get(browserResponse.request())
    if (networkRecord) {
      networkRecord.status = browserResponse.status()
    }
  })

  await page.goto(`${fixtureOrigin}/?api=${encodeURIComponent(apiBaseUrl)}`)
  return networkRecordList
}

function summarizeNetworkRecords(networkRecordList: NetworkRecord[]): string[] {
  return networkRecordList.map((networkRecord) => {
    const statusText = networkRecord.status === undefined ? 'pending' : String(networkRecord.status)
    return `${networkRecord.method} ${networkRecord.host}${networkRecord.path} ${statusText}`
  })
}

async function saveResult(resultValue: Record<string, unknown>): Promise<void> {
  const resultFilePath = requiredEnvironmentValue('OBJECT_STORAGE_E2E_RESULT_FILE')
  await writeFile(resultFilePath, JSON.stringify(resultValue, null, 2), { encoding: 'utf-8' })
}

async function selectFixtureFile(page: Page): Promise<void> {
  const fixtureFilePath = requiredEnvironmentValue('OBJECT_STORAGE_E2E_FIXTURE_FILE')
  await page.locator('#file-input').setInputFiles(fixtureFilePath)
}

function isImmutablePublicCache(cacheControlHeader: string | null): boolean {
  const cacheDirectiveList = (cacheControlHeader ?? '')
    .toLowerCase()
    .split(',')
    .map((directiveText) => directiveText.trim())
  return (
    cacheDirectiveList.includes('public') &&
    cacheDirectiveList.includes('max-age=31536000') &&
    cacheDirectiveList.includes('immutable')
  )
}

function responseHasCacheHit(imageResult: {
  age: string | null
  x_cache: string | null
}): boolean {
  const ageSeconds = Number.parseInt(imageResult.age ?? '', 10)
  return ageSeconds > 0 || (imageResult.x_cache ?? '').toUpperCase().includes('HIT')
}

async function openPageInNewContext(browser: Browser): Promise<{
  page: Page
  networkRecordList: NetworkRecord[]
  close: () => Promise<void>
}> {
  const freshBrowserContext = await browser.newContext()
  const freshBrowserPage = await freshBrowserContext.newPage()
  const networkRecordList = await openFixturePage(freshBrowserPage)
  return {
    page: freshBrowserPage,
    networkRecordList,
    close: () => freshBrowserContext.close(),
  }
}

test('rv-1 browser posts a bounded upload directly to OSS after API authorization @rv-1', async ({ page }) => {
  const networkRecordList = await openFixturePage(page)
  const oversizeControl = await page.evaluate(() => window.objectStorageFixture.uploadOversizedControl())

  expect(oversizeControl.status).not.toBe(201)
  expect(oversizeControl.api_response_contains_file_body).toBe(false)

  await selectFixtureFile(page)
  const uploadResult = await page.evaluate(() => window.objectStorageFixture.uploadSelectedFile('public'))
  expect(uploadResult.status).toBe(201)
  expect(uploadResult.api_response_contains_file_body).toBe(false)
  expect(uploadResult.completion?.content_length).toBeGreaterThan(0)
  expect(uploadResult.completion?.content_type).toBe('image/png')

  const expectedBucketHost = expectedOssBucketHost()
  const browserPostedToOss = networkRecordList.some(
    (networkRecord) => networkRecord.method === 'POST' && networkRecord.host === expectedBucketHost,
  )
  expect(browserPostedToOss).toBe(true)

  const expectedFixtureDigest = createHash('sha256')
    .update(await readFile(requiredEnvironmentValue('OBJECT_STORAGE_E2E_FIXTURE_FILE')))
    .digest('hex')
  await saveResult({
    expected_fixture_sha256: expectedFixtureDigest,
    negative_control: {
      name: 'oversized POST policy request',
      status: oversizeControl.status,
      object_key: oversizeControl.object_key,
      rejected: oversizeControl.status >= 400,
    },
    valid_upload: {
      upload_id: uploadResult.upload_id,
      object_key: uploadResult.object_key,
      status: uploadResult.status,
      completion: uploadResult.completion,
      api_response_contains_file_body: uploadResult.api_response_contains_file_body,
    },
    network: summarizeNetworkRecords(networkRecordList),
  })
})

test('rv-2 browser reads immutable public content from CDN and observes a cache hit @rv-2', async ({ page, browser }) => {
  const networkRecordList = await openFixturePage(page)

  await selectFixtureFile(page)
  const uncachedControl = await page.evaluate(() =>
    window.objectStorageFixture.uploadSelectedFile('uncached-control'),
  )
  expect(uncachedControl.status).toBe(201)
  const uncachedDelivery = await page.evaluate((uploadId) =>
    window.objectStorageFixture.getPublicDelivery(uploadId), uncachedControl.upload_id,
  )
  const uncachedResponse = await page.evaluate((publicUrl) =>
    window.objectStorageFixture.readPublicImage(publicUrl), uncachedDelivery.url,
  )
  expect(uncachedResponse.status).toBe(200)
  expect(isImmutablePublicCache(uncachedResponse.cache_control)).toBe(false)

  const publicUpload = await page.evaluate(() => window.objectStorageFixture.uploadSelectedFile('public'))
  expect(publicUpload.status).toBe(201)
  const publicDelivery = await page.evaluate((uploadId) =>
    window.objectStorageFixture.getPublicDelivery(uploadId), publicUpload.upload_id,
  )
  const publicUrl = new URL(publicDelivery.url)
  const configuredCdnHost = new URL(requiredEnvironmentValue('OBJECT_STORAGE_E2E_CDN_BASE_URL')).host
  expect(publicUrl.host).toBe(configuredCdnHost)

  const imageDisplayResult = await page.evaluate((imageUrl) =>
    window.objectStorageFixture.displayPublicImage(imageUrl), publicDelivery.url,
  )
  expect(imageDisplayResult.complete).toBe(true)
  expect(imageDisplayResult.natural_width).toBeGreaterThan(1)

  const firstImageResponse = await page.evaluate((imageUrl) =>
    window.objectStorageFixture.readPublicImage(imageUrl), publicDelivery.url,
  )
  expect(firstImageResponse.status).toBe(200)
  expect(isImmutablePublicCache(firstImageResponse.cache_control)).toBe(true)

  const expectedFixtureDigest = createHash('sha256')
    .update(await readFile(requiredEnvironmentValue('OBJECT_STORAGE_E2E_FIXTURE_FILE')))
    .digest('hex')
  expect(firstImageResponse.digest_sha256).toBe(expectedFixtureDigest)

  const freshContext = await openPageInNewContext(browser)
  const freshImageResponse = await freshContext.page.evaluate((imageUrl) =>
    window.objectStorageFixture.readPublicImage(imageUrl), publicDelivery.url,
  )
  expect(freshImageResponse.status).toBe(200)
  expect(freshImageResponse.digest_sha256).toBe(expectedFixtureDigest)
  expect(isImmutablePublicCache(freshImageResponse.cache_control)).toBe(true)
  expect(responseHasCacheHit(freshImageResponse)).toBe(true)

  const screenshotFilePath = requiredEnvironmentValue('OBJECT_STORAGE_E2E_SCREENSHOT_FILE')
  await page.screenshot({ path: screenshotFilePath, fullPage: true })
  await saveResult({
    expected_fixture_sha256: expectedFixtureDigest,
    negative_control: {
      name: 'uncached-control object',
      object_key: uncachedDelivery.object_key,
      cache_control: uncachedResponse.cache_control,
      immutable_policy_rejected: !isImmutablePublicCache(uncachedResponse.cache_control),
    },
    public_delivery: {
      object_key: publicDelivery.object_key,
      host: publicUrl.host,
      status: firstImageResponse.status,
      digest_sha256: firstImageResponse.digest_sha256,
      cache_control: firstImageResponse.cache_control,
      second_read_age: freshImageResponse.age,
      second_read_x_cache: freshImageResponse.x_cache,
      second_read_cache_hit: responseHasCacheHit(freshImageResponse),
    },
    network: [
      ...summarizeNetworkRecords(networkRecordList),
      ...summarizeNetworkRecords(freshContext.networkRecordList),
    ],
  })
  await freshContext.close()
})

test('rv-3 private reads require authorization and expired URLs fail from a fresh client @rv-3', async ({ page }) => {
  const networkRecordList = await openFixturePage(page)
  await selectFixtureFile(page)
  const privateUpload = await page.evaluate(() => window.objectStorageFixture.uploadSelectedFile('private'))
  expect(privateUpload.status).toBe(201)

  const unauthorizedRead = await page.evaluate((uploadId) =>
    window.objectStorageFixture.requestPrivateRead(uploadId, 'intruder'), privateUpload.upload_id,
  )
  expect(unauthorizedRead.status).toBe(403)
  expect(unauthorizedRead.body.read_url).toBeUndefined()

  const authorizedRead = await page.evaluate((uploadId) =>
    window.objectStorageFixture.requestPrivateRead(uploadId, 'owner'), privateUpload.upload_id,
  )
  expect(authorizedRead.status).toBe(200)
  expect(authorizedRead.body.read_url).toBeTruthy()
  expect(authorizedRead.body.expires_at).toBeTruthy()
  const privateReadUrl = authorizedRead.body.read_url as string
  const privateReadUrlParts = new URL(privateReadUrl)
  expect(privateReadUrlParts.protocol).toBe('https:')
  expect(privateReadUrlParts.host).toBe(expectedOssBucketHost())

  const authorizedHttpClient = await playwrightRequest.newContext()
  const authorizedResponse = await authorizedHttpClient.get(privateReadUrl)
  expect(authorizedResponse.status()).toBe(200)
  const authorizedBody = await authorizedResponse.body()
  const authorizedDigest = createHash('sha256').update(authorizedBody).digest('hex')
  const expectedFixtureDigest = createHash('sha256')
    .update(await readFile(requiredEnvironmentValue('OBJECT_STORAGE_E2E_FIXTURE_FILE')))
    .digest('hex')
  expect(authorizedDigest).toBe(expectedFixtureDigest)
  await authorizedHttpClient.dispose()

  const expiryTimeMilliseconds = Date.parse(authorizedRead.body.expires_at as string)
  await page.waitForTimeout(Math.max(0, expiryTimeMilliseconds - Date.now() + 1_500))
  const freshExpiredHttpClient = await playwrightRequest.newContext()
  const expiredResponse = await freshExpiredHttpClient.get(privateReadUrl)
  expect(expiredResponse.status()).toBe(403)

  await saveResult({
    negative_controls: {
      unauthorized_request_status: unauthorizedRead.status,
      unauthorized_response_has_url: Boolean(unauthorizedRead.body.read_url),
      expired_request_status: expiredResponse.status(),
      expired_request_rejected: expiredResponse.status() === 403,
    },
    authorized_read: {
      host: new URL(privateReadUrl).host,
      status: authorizedResponse.status(),
      digest_sha256: authorizedDigest,
      expired_at: authorizedRead.body.expires_at,
    },
    network: summarizeNetworkRecords(networkRecordList),
  })
  await freshExpiredHttpClient.dispose()
})
