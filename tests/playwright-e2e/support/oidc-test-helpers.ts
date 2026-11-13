import { mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  expect,
  type Browser,
  type BrowserContext,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";

const canonicalRequestTimeoutMs = 30_000;

export type TestOidcIdentity = {
  email: string;
  subject: string;
  emailVerified?: boolean;
  disabled?: boolean;
};

const moduleDirectoryPath = dirname(fileURLToPath(import.meta.url));
const repositoryRootPath = resolve(moduleDirectoryPath, "../../..");

export function requireOidcTestEnvironment(): string {
  if (process.env.PLAYWRIGHT_OIDC_TESTS !== "1") {
    throw new Error(
      "Run these OIDC flows through the E2E stack wrapper with PLAYWRIGHT_OIDC_TESTS=1.",
    );
  }
  const configuredIssuerUrl = process.env.PLAYWRIGHT_OIDC_ISSUER_URL?.trim();
  if (!configuredIssuerUrl) {
    throw new Error(
      "PLAYWRIGHT_OIDC_ISSUER_URL is required for real OIDC E2E flows.",
    );
  }
  const issuerUrl = new URL(configuredIssuerUrl);
  if (
    issuerUrl.protocol !== "http:" ||
    !["127.0.0.1", "localhost", "[::1]"].includes(issuerUrl.hostname)
  ) {
    throw new Error(
      "The Playwright OIDC test issuer must use a loopback HTTP URL.",
    );
  }
  return issuerUrl.origin;
}

export function getBootstrapAdminEmail(): string {
  const bootstrapAdminEmail =
    process.env.PLAYWRIGHT_ADMIN_EMAIL?.trim() ||
    process.env.AUTH_ADMIN_BOOTSTRAP_EMAIL?.trim() ||
    "";
  if (!bootstrapAdminEmail) {
    throw new Error(
      "Set AUTH_ADMIN_BOOTSTRAP_EMAIL for the admin OIDC real-entry test; the issuer identity must match the seeded admin email.",
    );
  }
  return bootstrapAdminEmail.toLowerCase();
}

export function getEvidenceDirectory(prdStem: string): string {
  return resolve(repositoryRootPath, "tasks/evidence", prdStem);
}

export async function saveEvidenceScreenshot(
  page: Page,
  prdStem: string,
  fileName: string,
): Promise<void> {
  const targetDirectoryPath = getEvidenceDirectory(prdStem);
  await mkdir(targetDirectoryPath, { recursive: true });
  await page.screenshot({
    path: resolve(targetDirectoryPath, fileName),
    fullPage: true,
  });
}

export async function saveEvidenceVideo(
  page: Page,
  prdStem: string,
  fileName: string,
): Promise<void> {
  const pageVideo = page.video();
  if (!pageVideo) {
    throw new Error("Video capture is disabled for this Playwright page.");
  }
  const targetDirectoryPath = getEvidenceDirectory(prdStem);
  await mkdir(targetDirectoryPath, { recursive: true });
  if (!page.isClosed()) await page.close();
  await pageVideo.saveAs(resolve(targetDirectoryPath, fileName));
}

export async function createRecordedContext(
  browser: Browser,
  baseURL?: string,
): Promise<BrowserContext> {
  const configuredResultsDirectory =
    process.env.PLAYWRIGHT_TEST_RESULTS_DIR?.trim() || "test-results";
  const resultsDirectoryPath = resolve(
    process.cwd(),
    configuredResultsDirectory,
  );
  await mkdir(resultsDirectoryPath, { recursive: true });
  return browser.newContext({
    ...(baseURL ? { baseURL } : {}),
    storageState: { cookies: [], origins: [] },
    viewport: { width: 1440, height: 1200 },
    recordVideo: { dir: resultsDirectoryPath },
  });
}

export function waitForCanonicalResponse(
  page: Page,
  method: string,
  canonicalApiPath: string,
): Promise<Response> {
  return page.waitForResponse(
    (response) => {
      const responseUrl = new URL(response.url());
      return (
        response.request().method() === method &&
        responseUrl.pathname === canonicalApiPath
      );
    },
    { timeout: canonicalRequestTimeoutMs },
  );
}

export function waitForCanonicalRequest(
  page: Page,
  method: string,
  canonicalApiPath: string,
): Promise<Request> {
  return page.waitForRequest(
    (request) => {
      const requestUrl = new URL(request.url());
      return (
        request.method() === method && requestUrl.pathname === canonicalApiPath
      );
    },
    { timeout: canonicalRequestTimeoutMs },
  );
}

export async function beginOidcAuthorization(
  page: Page,
  options: {
    buttonTestId: string;
    startApiPath: string;
    issuerUrl: string;
  },
): Promise<URL> {
  const startResponsePromise = waitForCanonicalResponse(
    page,
    "GET",
    options.startApiPath,
  );
  const startRequestPromise = waitForCanonicalRequest(
    page,
    "GET",
    options.startApiPath,
  );
  await page.getByTestId(options.buttonTestId).click();
  const [startResponse, startRequest] = await Promise.all([
    startResponsePromise,
    startRequestPromise,
  ]);
  expect(startRequest.url()).toContain(options.startApiPath);
  expect(startResponse.status()).toBe(302);
  const authorizationUrl = new URL(startResponse.headers().location ?? "");
  expect(authorizationUrl.origin).toBe(options.issuerUrl);
  expect(authorizationUrl.pathname).toBe("/authorize");
  expect(authorizationUrl.searchParams.get("response_type")).toBe("code");
  expect(authorizationUrl.searchParams.get("code_challenge_method")).toBe(
    "S256",
  );
  expect(authorizationUrl.searchParams.get("state")).toBeTruthy();
  expect(authorizationUrl.searchParams.get("nonce")).toBeTruthy();
  expect(authorizationUrl.searchParams.get("code_challenge")).toBeTruthy();
  return authorizationUrl;
}

export function waitForOidcCallback(
  page: Page,
  options: { callbackApiPath: string },
): { request: Promise<Request>; response: Promise<Response> } {
  return {
    request: waitForCanonicalRequest(page, "GET", options.callbackApiPath),
    response: waitForCanonicalResponse(page, "GET", options.callbackApiPath),
  };
}

export async function fillTestIdentity(
  page: Page,
  identity: TestOidcIdentity,
): Promise<void> {
  await page.getByTestId("oidc-test-email").fill(identity.email);
  await page.getByTestId("oidc-test-subject").fill(identity.subject);
  const verifiedCheckbox = page.getByTestId("oidc-test-email-verified");
  if (identity.emailVerified === false) await verifiedCheckbox.uncheck();
  else await verifiedCheckbox.check();
  if (identity.disabled) {
    await page.getByTestId("oidc-test-identity-disabled").check();
  }
}

export async function readApiResponseFromPage<T>(
  page: Page,
  canonicalApiPath: string,
): Promise<{ status: number; body: T | null }> {
  return page.evaluate(async (apiPath) => {
    const apiResponse = await fetch(apiPath, { credentials: "include" });
    const responseBody = (await apiResponse
      .json()
      .catch(() => null)) as T | null;
    return { status: apiResponse.status, body: responseBody };
  }, canonicalApiPath);
}
