"""独立 OIDC 包公开契约与 PKCE 测试。"""

from __future__ import annotations

import string

import pytest
from zata_oidc import (
    OidcAuthenticationError,
    OidcFailureReason,
    VerifiedOidcIdentity,
    build_pkce_s256_challenge,
    generate_pkce_verifier,
)


def test_pkce_s256_matches_rfc_7636_example() -> None:
    """PKCE challenge 符合 RFC 7636 中已知输入。"""

    verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"

    assert build_pkce_s256_challenge(verifier) == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_generate_pkce_verifier_uses_unreserved_characters_and_valid_length() -> None:
    """生成的 verifier 满足 RFC 7636 的长度与字符要求。"""

    verifier = generate_pkce_verifier()

    assert 43 <= len(verifier) <= 128
    assert set(verifier) <= set(string.ascii_letters + string.digits + "-._~")


@pytest.mark.parametrize("verifier", ["short", "x" * 129, "x" * 42 + "!"])
def test_pkce_challenge_rejects_invalid_verifier(verifier: str) -> None:
    """非法长度或字符不能进入授权请求。"""

    with pytest.raises(ValueError):
        build_pkce_s256_challenge(verifier)


def test_identity_and_failure_reason_are_application_neutral() -> None:
    """公开身份契约不带宿主用户或权限字段。"""

    identity = VerifiedOidcIdentity(
        issuer="https://id.example.test/realms/main",
        subject="subject-1",
        email="person@example.com",
        email_verified=True,
        name="Person Example",
    )
    error = OidcAuthenticationError(
        "Token validation failed.", reason=OidcFailureReason.TOKEN_VALIDATION
    )

    assert identity.subject == "subject-1"
    assert identity.email_verified is True
    assert error.reason is OidcFailureReason.TOKEN_VALIDATION
