"""出站凭据引用必须绑定部署方授权的组织和完整对端地址。"""

import pytest

from backend.infrastructure.config.settings import config
from backend.infrastructure.security.environment_secret_resolver import EnvironmentSecretResolver


def test_secret_reference_requires_organization_and_endpoint_grant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拒绝平台密钥、跨组织和跨对端引用，同时允许显式授权的轮换别名。"""
    monkeypatch.setattr(
        config.a2a,
        "credential_bindings",
        {"org-a": {"https://peer.example/a2a": ["PEER_TOKEN", "PEER_TOKEN_NEXT"]}},
    )
    monkeypatch.setenv("MODEL_API_KEY", "platform-marker")
    monkeypatch.setenv("PEER_TOKEN", "peer-marker")
    monkeypatch.setenv("PEER_TOKEN_NEXT", "rotated-marker")
    resolver = EnvironmentSecretResolver()
    for alias, organization_id, endpoint_url in (
        ("MODEL_API_KEY", "org-a", "https://peer.example/a2a"),
        ("PEER_TOKEN", "org-b", "https://peer.example/a2a"),
        ("PEER_TOKEN", "org-a", "https://other.example/a2a"),
    ):
        with pytest.raises(ValueError, match="secret_reference_not_authorized"):
            resolver.get_secret(alias, organization_id=organization_id, endpoint_url=endpoint_url)
    assert (
        resolver.get_secret(
            "PEER_TOKEN", organization_id="org-a", endpoint_url="https://peer.example/a2a"
        )
        == "peer-marker"
    )
    assert (
        resolver.get_secret(
            "PEER_TOKEN_NEXT", organization_id="org-a", endpoint_url="https://peer.example/a2a"
        )
        == "rotated-marker"
    )
