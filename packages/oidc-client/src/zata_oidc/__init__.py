"""提供与应用无关的 OpenID Connect 协议客户端与契约。"""

from zata_oidc.client import HttpOidcClient, OidcClientSettings
from zata_oidc.contracts import (
    OidcAuthenticationError,
    OidcFailureReason,
    OidcGateway,
    VerifiedOidcIdentity,
    build_pkce_s256_challenge,
    generate_pkce_verifier,
)

__all__ = [
    "HttpOidcClient",
    "OidcAuthenticationError",
    "OidcClientSettings",
    "OidcFailureReason",
    "OidcGateway",
    "VerifiedOidcIdentity",
    "build_pkce_s256_challenge",
    "generate_pkce_verifier",
]
