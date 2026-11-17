"""A2A 1.0 卡片、DNS 与跨组织出站策略的回归测试。"""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime

import pytest

from backend.api.a2a_router import get_agent_card
from backend.core.shared.interfaces.agent_types import A2ACredential, AgentDefinition
from backend.infrastructure.a2a.http_client import HttpA2AClient, OutboundA2APolicyError
from backend.infrastructure.config.settings import config


def _credential() -> A2ACredential:
    now = datetime.now(UTC)
    return A2ACredential(
        id="credential-1",
        organization_id="org-a",
        agent_id="agent-1",
        name="test",
        is_active=True,
        created_at=now,
        revoked_at=None,
    )


def _agent() -> AgentDefinition:
    now = datetime.now(UTC)
    return AgentDefinition(
        id="agent-1",
        organization_id="org-a",
        created_by="admin-1",
        name="Helper",
        description="Organization helper",
        instructions="Help",
        model_name=None,
        skill_id=None,
        is_enabled=True,
        is_published=True,
        created_at=now,
        updated_at=now,
    )


class _Catalog:
    def get_agent(self, organization_id: str, agent_id: str) -> AgentDefinition:
        assert (organization_id, agent_id) == ("org-a", "agent-1")
        return _agent()


def test_agent_card_declares_only_v10_rest_and_security_variant() -> None:
    """卡片只声明已实现的 REST 能力和 1.0 安全字段。"""
    card = get_agent_card(
        a2a_version="1.0",
        credential=_credential(),
        catalog=_Catalog(),
        configured_base_url="https://agents.example.com",
        allow_http_origin=False,
    )

    assert card["supportedInterfaces"] == [
        {
            "url": "https://agents.example.com/a2a/agents/agent-1",
            "protocolBinding": "HTTP+JSON",
            "protocolVersion": "1.0",
        }
    ]
    assert card["capabilities"]["pushNotifications"] is False
    assert card["securitySchemes"]["bearerAuth"]["httpAuthSecurityScheme"]["scheme"] == "bearer"
    assert card["securityRequirements"] == [{"schemes": {"bearerAuth": {"list": []}}}]


def test_unlisted_and_loopback_targets_fail_before_dns_or_http(monkeypatch) -> None:
    """未登记主机与回环目标在 DNS 和 HTTP 之前失败闭合。"""
    monkeypatch.setattr(config.a2a, "allowed_outbound_hosts", [])
    monkeypatch.setattr(config.a2a, "allow_loopback_for_dev", False)

    def unexpected_resolution(*args, **kwargs):
        raise AssertionError("DNS must not be resolved for a rejected host")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_resolution)
    with pytest.raises(OutboundA2APolicyError, match="a2a_host_not_allowlisted"):
        HttpA2AClient._validate_url("https://unregistered.example.com/a2a")
    with pytest.raises(OutboundA2APolicyError, match="a2a_loopback_target_denied"):
        HttpA2AClient._validate_url("http://127.0.0.1:8000/a2a")


def test_dns_rebinding_to_private_address_is_rejected(monkeypatch) -> None:
    """允许的主机名若解析到私网地址，仍在发出 HTTP 前被拒绝。"""
    monkeypatch.setattr(config.a2a, "allowed_outbound_hosts", ["agent.example"])
    monkeypatch.setattr(config.a2a, "allow_loopback_for_dev", False)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.8", 443))],
    )
    with pytest.raises(OutboundA2APolicyError, match="a2a_non_public_address_denied"):
        HttpA2AClient._validate_url("https://agent.example/a2a")


def test_global_allowlisted_address_passes_url_policy(monkeypatch) -> None:
    """HTTPS、精确主机白名单和公网解析结果同时满足时才允许继续。"""
    monkeypatch.setattr(config.a2a, "allowed_outbound_hosts", ["agent.example"])
    monkeypatch.setattr(config.a2a, "allow_loopback_for_dev", False)
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443))],
    )
    HttpA2AClient._validate_url("https://agent.example/a2a")


def test_cross_organization_peer_is_rejected_before_http_construction(monkeypatch) -> None:
    """对端目录无当前组织授权时不得创建 HTTP 客户端。"""

    class EmptyRepository:
        def get_a2a_peer_target(self, organization_id: str, peer_id: str):
            return None

    def unexpected_client(*args, **kwargs):
        raise AssertionError("HTTP client must not be constructed")

    monkeypatch.setattr(
        "backend.infrastructure.a2a.http_client.httpx.AsyncClient", unexpected_client
    )
    client = HttpA2AClient(EmptyRepository())
    with pytest.raises(OutboundA2APolicyError, match="a2a_peer_not_authorized"):
        asyncio.run(
            client.send_message(
                organization_id="org-a",
                peer_id="org-b-peer",
                message="must not leave the process",
                idempotency_key="negative-control",
            )
        )
