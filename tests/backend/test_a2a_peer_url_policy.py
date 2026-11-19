"""A2A 对端登记和出站调用的 URL 安全策略测试。"""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from typing import cast

import pytest

from backend.core.agent.catalog import AgentCatalogUseCase
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.agent_types import A2APeer, A2APeerTarget
from backend.core.shared.models.a2a_peer_policy import (
    A2APeerUrlValidationError,
    validate_a2a_peer_urls,
)
from backend.infrastructure.a2a.http_client import HttpA2AClient, OutboundA2APolicyError


class _PeerRepository:
    """保存测试中尝试写入的对端记录。"""

    def __init__(self, peer_target: A2APeerTarget | None = None) -> None:
        """初始化测试 repository。"""
        self.created_peer: A2APeer | None = None
        self.peer_target = peer_target

    def create_a2a_peer(self, peer: A2APeer, _bearer_token: str | None) -> A2APeer:
        """记录对端创建，供断言非法地址未落库。"""
        self.created_peer = peer
        return peer

    def get_a2a_peer_target(self, _organization_id: str, _peer_id: str) -> A2APeerTarget | None:
        """返回预置的出站对端。"""
        return self.peer_target


@pytest.mark.parametrize(
    ("card_url", "endpoint_url"),
    [
        (
            "https://alice:secret@agent.example/.well-known/agent-card.json",
            "https://agent.example/a2a",
        ),
        (
            "https://agent.example/.well-known/agent-card.json?token=secret",
            "https://agent.example/a2a",
        ),
        ("file:///etc/passwd", "file:///a2a"),
        ("https://agent.example/card", "https://other.example/a2a"),
    ],
)
def test_peer_url_validation_rejects_secrets_and_untrusted_shapes(
    card_url: str, endpoint_url: str
) -> None:
    """拒绝内嵌凭据、查询密钥、非 HTTP 地址和跨源端点。"""
    with pytest.raises(A2APeerUrlValidationError):
        validate_a2a_peer_urls(card_url=card_url, endpoint_url=endpoint_url)


def test_register_peer_rejects_embedded_credentials_before_repository_write() -> None:
    """登记时拒绝会被管理 API 回显的 URL 凭据。"""
    peer_repository = _PeerRepository()
    catalog = AgentCatalogUseCase(cast(AgentRepository, peer_repository), object())

    with pytest.raises(A2APeerUrlValidationError, match="peer_url_invalid"):
        catalog.register_a2a_peer(
            organization_id="org-a",
            actor_id="admin-a",
            name="Private peer",
            card_url="https://alice:secret@agent.example/.well-known/agent-card.json",
            endpoint_url="https://agent.example/a2a",
            credential_env_alias=None,
        )

    assert peer_repository.created_peer is None


def test_outbound_call_revalidates_legacy_peer_before_dns_or_http(monkeypatch) -> None:
    """调用端重验旧数据，避免登记规则上线前的 URL 被审批后回显或请求。"""
    now = datetime.now(UTC)
    peer = A2APeer(
        id="peer-1",
        organization_id="org-a",
        created_by="admin-a",
        name="Legacy peer",
        card_url="https://alice:secret@agent.example/.well-known/agent-card.json",
        endpoint_url="https://agent.example/a2a",
        is_approved=True,
        is_enabled=True,
        approved_by="platform-admin",
        created_at=now,
        updated_at=now,
    )
    peer_repository = _PeerRepository(A2APeerTarget(peer=peer, bearer_token=None))

    def unexpected_network(*_args, **_kwargs):
        raise AssertionError("invalid peer URLs must be rejected before network access")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(
        "backend.infrastructure.a2a.http_client.httpx.AsyncClient", unexpected_network
    )
    outbound_client = HttpA2AClient(cast(AgentRepository, peer_repository))

    with pytest.raises(OutboundA2APolicyError, match="peer_url_invalid"):
        asyncio.run(
            outbound_client.send_message(
                organization_id="org-a",
                peer_id=peer.id,
                message="hello",
                idempotency_key="run-1:a2a:0",
            )
        )
