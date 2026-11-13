#!/usr/bin/env node
/** 本地 OIDC 身份中心替身，仅供 Playwright 测试使用。 */

import { spawn } from 'node:child_process'
import { constants, createHash, generateKeyPairSync, randomBytes, sign } from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'
import { createServer } from 'node:http'

const scriptPath = fileURLToPath(import.meta.url)
const defaultPort = 49183
const issuerPort = Number(process.env.PLAYWRIGHT_OIDC_TEST_PORT ?? defaultPort)
const issuerUrl = `http://127.0.0.1:${issuerPort}`
const adminClientId = 'playwright-admin-client'
const publicClientId = 'playwright-public-client'
const testClientSecret = 'playwright-oidc-test-secret'
const authCodeTtlMs = 5 * 60 * 1000

const { publicKey, privateKey } = generateKeyPairSync('rsa', {
  modulusLength: 2048,
  publicKeyEncoding: { format: 'jwk' },
  privateKeyEncoding: { format: 'pem', type: 'pkcs8' },
})

const signingKeyId = randomBytes(12).toString('hex')
const signingJwk = {
  ...publicKey,
  alg: 'RS256',
  kid: signingKeyId,
  use: 'sig',
}
const authorizationTransactions = new Map()
const authorizationCodes = new Map()

function sendJson(response, statusCode, jsonBody) {
  response.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Type': 'application/json; charset=utf-8',
  })
  response.end(JSON.stringify(jsonBody))
}

function sendHtml(response, statusCode, htmlBody, formActionOrigin = null) {
  const formActionPolicy = formActionOrigin
    ? `form-action 'self' ${formActionOrigin}`
    : "form-action 'self'"
  response.writeHead(statusCode, {
    'Cache-Control': 'no-store',
    'Content-Security-Policy': `default-src 'none'; ${formActionPolicy}; style-src 'unsafe-inline'`,
    'Content-Type': 'text/html; charset=utf-8',
    'X-Content-Type-Options': 'nosniff',
  })
  response.end(htmlBody)
}

async function readFormBody(request) {
  const chunks = []
  let totalBytes = 0
  for await (const bodyChunk of request) {
    totalBytes += bodyChunk.length
    if (totalBytes > 16_384) {
      throw new Error('OIDC test issuer form is too large.')
    }
    chunks.push(bodyChunk)
  }
  return new URLSearchParams(Buffer.concat(chunks).toString('utf8'))
}

function expectedCallbackPath(clientId) {
  if (clientId === adminClientId) return '/api/admin/auth/oidc/callback'
  if (clientId === publicClientId) return '/api/auth/oidc/callback'
  return null
}

function isValidClientCallback(clientId, rawCallbackUri) {
  const expectedPath = expectedCallbackPath(clientId)
  if (!expectedPath || !rawCallbackUri) return false
  try {
    const callbackUrl = new URL(rawCallbackUri)
    const isLoopbackHost = ['127.0.0.1', 'localhost', '[::1]'].includes(callbackUrl.hostname)
    return (
      callbackUrl.protocol === 'http:' &&
      isLoopbackHost &&
      !callbackUrl.username &&
      !callbackUrl.password &&
      callbackUrl.pathname === expectedPath &&
      !callbackUrl.search &&
      !callbackUrl.hash
    )
  } catch {
    return false
  }
}

function encodeBase64Url(value) {
  return Buffer.from(value).toString('base64url')
}

function createIdToken(identityClaims, transaction) {
  const issuedAtSeconds = Math.floor(Date.now() / 1000)
  const tokenHeader = {
    alg: 'RS256',
    kid: signingKeyId,
    typ: 'JWT',
  }
  const tokenClaims = {
    aud: transaction.clientId,
    email: identityClaims.email,
    email_verified: identityClaims.emailVerified,
    exp: issuedAtSeconds + 300,
    iat: issuedAtSeconds,
    iss: issuerUrl,
    name: identityClaims.email.split('@')[0],
    nonce: transaction.nonce,
    sub: identityClaims.subject,
  }
  const signingInput = `${encodeBase64Url(JSON.stringify(tokenHeader))}.${encodeBase64Url(
    JSON.stringify(tokenClaims)
  )}`
  const tokenSignature = sign('RSA-SHA256', Buffer.from(signingInput), {
    key: privateKey,
    padding: constants.RSA_PKCS1_PADDING,
  })
  return `${signingInput}.${tokenSignature.toString('base64url')}`
}

function renderLoginPage(transactionId) {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Playwright Test Identity Provider</title>
    <style>
      body { font: 16px system-ui, sans-serif; margin: 4rem auto; max-width: 30rem; padding: 0 1.5rem; }
      label { display: block; margin: 1rem 0 .35rem; }
      input[type="email"], input[type="text"] { box-sizing: border-box; padding: .65rem; width: 100%; }
      button { margin-top: 1rem; padding: .65rem 1rem; }
      .verified { align-items: center; display: flex; gap: .5rem; margin-top: 1rem; }
    </style>
  </head>
  <body>
    <main>
      <h1>Test identity provider</h1>
      <p>Choose a test identity to continue to the local application.</p>
      <form method="post" action="/login">
        <input type="hidden" name="transaction_id" value="${transactionId}">
        <label for="oidc-test-email">Email</label>
        <input id="oidc-test-email" data-testid="oidc-test-email" name="email" type="email" required>
        <label for="oidc-test-subject">Identity ID</label>
        <input id="oidc-test-subject" data-testid="oidc-test-subject" name="subject" type="text" required>
        <label class="verified" for="oidc-test-email-verified">
          <input id="oidc-test-email-verified" data-testid="oidc-test-email-verified" name="email_verified" type="checkbox" value="true" checked>
          Email is verified
        </label>
        <label class="verified" for="oidc-test-identity-disabled">
          <input id="oidc-test-identity-disabled" data-testid="oidc-test-identity-disabled" name="identity_disabled" type="checkbox" value="true">
          Identity is disabled at the provider
        </label>
        <button data-testid="oidc-test-submit" type="submit">Sign in</button>
      </form>
    </main>
  </body>
</html>`
}

async function routeRequest(request, response) {
  const requestUrl = new URL(request.url ?? '/', issuerUrl)

  if (request.method === 'GET' && requestUrl.pathname === '/health') {
    sendJson(response, 200, { ok: true, pid: process.pid })
    return
  }

  if (request.method === 'GET' && requestUrl.pathname === '/.well-known/openid-configuration') {
    sendJson(response, 200, {
      authorization_endpoint: `${issuerUrl}/authorize`,
      claims_supported: ['sub', 'email', 'email_verified', 'name'],
      grant_types_supported: ['authorization_code'],
      id_token_signing_alg_values_supported: ['RS256'],
      issuer: issuerUrl,
      jwks_uri: `${issuerUrl}/jwks`,
      response_types_supported: ['code'],
      subject_types_supported: ['public'],
      token_endpoint: `${issuerUrl}/token`,
      token_endpoint_auth_methods_supported: ['client_secret_post'],
    })
    return
  }

  if (request.method === 'GET' && requestUrl.pathname === '/jwks') {
    sendJson(response, 200, { keys: [signingJwk] })
    return
  }

  if (request.method === 'GET' && requestUrl.pathname === '/authorize') {
    const authorizationParameters = requestUrl.searchParams
    const clientId = authorizationParameters.get('client_id') ?? ''
    const callbackUri = authorizationParameters.get('redirect_uri') ?? ''
    const state = authorizationParameters.get('state') ?? ''
    const nonce = authorizationParameters.get('nonce') ?? ''
    const codeChallenge = authorizationParameters.get('code_challenge') ?? ''
    if (
      authorizationParameters.get('response_type') !== 'code' ||
      !expectedCallbackPath(clientId) ||
      !isValidClientCallback(clientId, callbackUri) ||
      !authorizationParameters.get('scope')?.split(/\s+/).includes('openid') ||
      !state ||
      !nonce ||
      !codeChallenge ||
      authorizationParameters.get('code_challenge_method') !== 'S256'
    ) {
      sendJson(response, 400, { error: 'invalid_request' })
      return
    }

    const transactionId = randomBytes(24).toString('base64url')
    authorizationTransactions.set(transactionId, {
      callbackUri,
      clientId,
      codeChallenge,
      expiresAt: Date.now() + authCodeTtlMs,
      nonce,
      state,
    })
    // 仅允许已校验的 loopback 回调作为登录表单 POST 的重定向目标。
    const callbackOrigin = new URL(callbackUri).origin
    sendHtml(response, 200, renderLoginPage(transactionId), callbackOrigin)
    return
  }

  if (request.method === 'POST' && requestUrl.pathname === '/login') {
    let loginForm
    try {
      loginForm = await readFormBody(request)
    } catch {
      sendJson(response, 413, { error: 'invalid_request' })
      return
    }
    const transactionId = loginForm.get('transaction_id') ?? ''
    const transaction = authorizationTransactions.get(transactionId)
    authorizationTransactions.delete(transactionId)
    const email = loginForm.get('email')?.trim().toLowerCase() ?? ''
    const subject = loginForm.get('subject')?.trim() ?? ''
    if (
      !transaction ||
      transaction.expiresAt <= Date.now() ||
      !email.includes('@') ||
      !subject ||
      subject.length > 255
    ) {
      sendHtml(response, 400, '<!doctype html><title>Invalid test login</title><p>Invalid test login.</p>')
      return
    }
    if (loginForm.get('identity_disabled') === 'true') {
      sendHtml(
        response,
        403,
        '<!doctype html><html lang="en"><meta charset="utf-8"><title>Account disabled</title><p role="alert">This test identity is disabled at the provider.</p></html>'
      )
      return
    }

    const authCode = randomBytes(32).toString('base64url')
    authorizationCodes.set(authCode, {
      ...transaction,
      email,
      emailVerified: loginForm.get('email_verified') === 'true',
      subject,
    })
    const callbackUrl = new URL(transaction.callbackUri)
    callbackUrl.searchParams.set('code', authCode)
    callbackUrl.searchParams.set('state', transaction.state)
    response.writeHead(303, { Location: callbackUrl.toString(), 'Cache-Control': 'no-store' })
    response.end()
    return
  }

  if (request.method === 'POST' && requestUrl.pathname === '/token') {
    let tokenForm
    try {
      tokenForm = await readFormBody(request)
    } catch {
      sendJson(response, 413, { error: 'invalid_request' })
      return
    }
    const authCode = tokenForm.get('code') ?? ''
    const transaction = authorizationCodes.get(authCode)
    authorizationCodes.delete(authCode)
    const codeVerifier = tokenForm.get('code_verifier') ?? ''
    const computedCodeChallenge = createHash('sha256')
      .update(codeVerifier)
      .digest('base64url')
    if (
      !transaction ||
      transaction.expiresAt <= Date.now() ||
      tokenForm.get('grant_type') !== 'authorization_code' ||
      tokenForm.get('client_id') !== transaction.clientId ||
      tokenForm.get('client_secret') !== testClientSecret ||
      tokenForm.get('redirect_uri') !== transaction.callbackUri ||
      computedCodeChallenge !== transaction.codeChallenge
    ) {
      sendJson(response, 400, { error: 'invalid_grant' })
      return
    }
    sendJson(response, 200, {
      access_token: randomBytes(24).toString('base64url'),
      expires_in: 300,
      id_token: createIdToken(transaction, transaction),
      token_type: 'Bearer',
    })
    return
  }

  sendJson(response, 404, { error: 'not_found' })
}

async function serveIssuer() {
  if (!Number.isInteger(issuerPort) || issuerPort < 1024 || issuerPort > 65535) {
    throw new Error('PLAYWRIGHT_OIDC_TEST_PORT must be an unused port from 1024 through 65535.')
  }
  const issuerServer = createServer((request, response) => {
    void routeRequest(request, response).catch(() => {
      if (!response.headersSent) sendJson(response, 500, { error: 'server_error' })
      else response.destroy()
    })
  })
  issuerServer.on('error', (error) => {
    process.stderr.write(`OIDC test issuer failed to listen: ${error.message}\n`)
    process.exitCode = 1
  })
  issuerServer.listen(issuerPort, '127.0.0.1')
  await new Promise((resolveListen, rejectListen) => {
    issuerServer.once('listening', resolveListen)
    issuerServer.once('error', rejectListen)
  })
}

async function waitUntilReady(expectedPid, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const healthResponse = await fetch(`${issuerUrl}/health`, {
        signal: AbortSignal.timeout(1_000),
      })
      const healthPayload = await healthResponse.json()
      if (healthResponse.ok && healthPayload.pid === expectedPid) return
    } catch {
      // 子进程启动前持续轮询，直到就绪或达到等待上限。
    }
    await delay(100)
  }
  throw new Error('Timed out waiting for the OIDC test issuer to become ready.')
}

async function startIssuerChild() {
  const issuerChild = spawn(process.execPath, [scriptPath, '--serve'], {
    detached: true,
    env: process.env,
    stdio: 'ignore',
  })
  if (!issuerChild.pid) throw new Error('Could not start the OIDC test issuer process.')
  issuerChild.unref()
  try {
    await waitUntilReady(issuerChild.pid)
  } catch (error) {
    try {
      process.kill(issuerChild.pid, 'SIGTERM')
    } catch {
      // 检查就绪期间子进程可能已经退出。
    }
    throw error
  }
  process.stdout.write(`${JSON.stringify({ issuerUrl, pid: issuerChild.pid })}\n`)
}

async function stopIssuerChild(processId) {
  if (!Number.isInteger(processId) || processId <= 1) {
    throw new Error('Provide a valid OIDC test issuer process ID.')
  }
  let healthPayload
  try {
    const healthResponse = await fetch(`${issuerUrl}/health`, {
      signal: AbortSignal.timeout(1_000),
    })
    if (healthResponse.ok) healthPayload = await healthResponse.json()
  } catch {
    // 身份中心已停止时无需处理，避免误向无关进程发送信号。
  }
  if (healthPayload?.pid !== processId) return

  const deadline = Date.now() + 10_000
  let issuerStopped = false
  try {
    process.kill(processId, 'SIGTERM')
  } catch (error) {
    if (error.code === 'ESRCH') issuerStopped = true
    else throw error
  }

  while (!issuerStopped && Date.now() < deadline) {
    try {
      const healthResponse = await fetch(`${issuerUrl}/health`, {
        signal: AbortSignal.timeout(500),
      })
      const activeIssuer = healthResponse.ok ? await healthResponse.json() : null
      issuerStopped = activeIssuer?.pid !== processId
    } catch {
      issuerStopped = true
    }
    if (!issuerStopped) await delay(100)
  }
  if (!issuerStopped) {
    throw new Error(`Timed out waiting for OIDC test issuer process ${processId} to stop.`)
  }
}

const [mode, argument] = process.argv.slice(2)
try {
  if (mode === '--serve') await serveIssuer()
  else if (mode === '--start') await startIssuerChild()
  else if (mode === '--stop') await stopIssuerChild(Number(argument))
  else throw new Error('Use --start, --stop <pid>, or --serve.')
} catch (error) {
  process.stderr.write(`${error.message}\n`)
  process.exitCode = 1
}
