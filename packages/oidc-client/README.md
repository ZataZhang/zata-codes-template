# zata-oidc

`zata-oidc` is an installable Python package for server-side OpenID Connect authorization-code flows. It provides protocol contracts, a verified identity value object, PKCE helpers, discovery and JWKS retrieval, code exchange, and ID Token validation.

The host application owns user lookup and binding, registration policy, authorization, login transactions, sessions, cookies, routes, persistence, and UI. The package does not depend on the host backend or read environment variables.

## Install

Development in this repository uses the local package source through the root `uv` project. To install a tested wheel in another repository:

```sh
uv pip install ./dist/zata_oidc-0.1.0-py3-none-any.whl
```

Pin the wheel version or its artifact hash in the consuming project. Build artifacts locally with:

```sh
uv build --project packages/oidc-client
```

No public package registry is required. A private registry or another artifact channel is a separate publishing decision.

## Use

```python
from zata_oidc import HttpOidcClient, OidcClientSettings, generate_pkce_verifier

settings = OidcClientSettings(
    issuer="https://identity.example.com/realms/app",
    client_id="web-app",
    client_secret="loaded-by-the-host",
    callback_uri="https://app.example.com/oidc/callback",
)
code_verifier = generate_pkce_verifier()

with HttpOidcClient(settings) as oidc_client:
    authorization_url = oidc_client.build_authorization_url(
        state="random-state-created-by-host",
        nonce="random-nonce-created-by-host",
        code_verifier=code_verifier,
    )
    # 将浏览器跳转到 authorization_url。重定向前，宿主应将 state、nonce 与 verifier
    # 保存到短时、一次性的登录事务中；回调时核对 state 并取回 verifier。
```

Exchange the callback code on the server:

```python
identity = oidc_client.exchange_and_verify_authorization_code(
    code=authorization_code,
    code_verifier=code_verifier,
    nonce=expected_nonce,
)
```

`VerifiedOidcIdentity` only represents protocol-validated issuer, subject, email claims, and display name. It does not mean a local account is authorized. The host must check and persist its own account policy before issuing a session.

## Validation and errors

The client validates discovery issuer, RS256 ID Token signatures against the issuer JWKS, issuer, audience, expiry, issue time, subject, authorized party for multi-audience tokens, and the expected nonce. PKCE uses S256. `OidcAuthenticationError.reason` contains a safe failure category; exception messages do not include authorization codes, client secrets, tokens, or full claims.

The package declares `httpx` and `joserfc` as runtime dependencies. The client owns and closes its default HTTP client when used as a context manager. An injected `httpx.Client` remains the caller's responsibility and is not closed by the OIDC client.

The host supplies configuration explicitly. Load issuer and client values from the host's configuration system and keep the client secret in its secret store. Do not put account matching, role mapping, Redis transaction state, session cookies, or host-specific logging into this package.
