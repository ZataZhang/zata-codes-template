"""受控 A2A 1.0 HTTP+JSON 出站客户端与 SSRF 策略。"""

from __future__ import annotations

import hashlib
import ipaddress
import socket
from urllib.parse import urlsplit

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend

from backend.core.shared.interfaces.agent_executor import A2AClient, A2AResponse
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.models.a2a_peer_policy import (
    A2APeerUrlValidationError,
    validate_a2a_peer_urls,
)
from backend.infrastructure.config.settings import config


class OutboundA2APolicyError(ValueError):
    """目标地址不符合部署策略或 A2A Card 契约。"""


class _PinnedNetworkBackend:
    """将 HTTP 连接固定到通过出站策略检查的 DNS 地址。"""

    def __init__(self, pinned_addresses: dict[tuple[str, int], tuple[str, ...]]) -> None:
        """保存 URL 主机与已验证 IP 的映射。"""
        self._pinned_addresses = pinned_addresses
        self._backend = AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: tuple[object, ...] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        """只连接预先解析和校验的地址，避免 HTTP 客户端再次解析 DNS。"""
        target_key = (host.lower().rstrip("."), port)
        pinned_addresses = self._pinned_addresses.get(target_key)
        if not pinned_addresses:
            raise OutboundA2APolicyError("a2a_unpinned_host_denied")
        last_error: OSError | TimeoutError | None = None
        for pinned_address in pinned_addresses:
            try:
                return await self._backend.connect_tcp(
                    pinned_address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (OSError, TimeoutError) as connection_error:
                last_error = connection_error
        if last_error is not None:
            raise last_error
        raise OutboundA2APolicyError("a2a_host_resolution_failed")

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: tuple[object, ...] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        """拒绝 Unix Socket；对端目录只允许 HTTP(S) 网络地址。"""
        raise OutboundA2APolicyError("a2a_unix_socket_denied")


class HttpA2AClient(A2AClient):
    """通过经目录批准的地址调用外部 A2A 1.0 Agent。"""

    def __init__(self, agent_repository: AgentRepository) -> None:
        """初始化出站客户端。

        Args:
            agent_repository (AgentRepository): 已批准对端目录与密文读取端口。
        """
        self._agent_repository = agent_repository

    async def send_message(
        self, *, organization_id: str, peer_id: str, message: str, idempotency_key: str
    ) -> A2AResponse:
        """读取受控 Agent Card 并发送 A2A 1.0 消息。

        Args:
            organization_id (str): 当前 Run 创建时冻结的组织 ID。
            peer_id (str): 管理员登记且平台批准的对端 ID。
            message (str): 模型生成的对端请求。
            idempotency_key (str): 从父 Run 和调用序号派生的重试稳定键。

        Returns:
            A2AResponse: 对端返回的 Task ID 与 Artifact 文本。

        Raises:
            OutboundA2APolicyError: 对端未登记、未批准、Card 不匹配或地址被策略拒绝。
            RuntimeError: 对端网络请求失败或返回不完整的 A2A Task。
        """
        peer_target = self._agent_repository.get_a2a_peer_target(organization_id, peer_id)
        if peer_target is None:
            raise OutboundA2APolicyError("a2a_peer_not_authorized")
        try:
            card_url, endpoint_url = validate_a2a_peer_urls(
                card_url=peer_target.peer.card_url,
                endpoint_url=peer_target.peer.endpoint_url,
            )
        except A2APeerUrlValidationError as url_error:
            raise OutboundA2APolicyError(str(url_error)) from url_error
        pinned_addresses = self._validate_url(card_url)
        registered_endpoint_addresses = self._validate_url(endpoint_url)
        if registered_endpoint_addresses != pinned_addresses:
            raise OutboundA2APolicyError("a2a_card_and_endpoint_resolution_mismatch")
        transport = httpx.AsyncHTTPTransport(retries=0)
        transport._pool._network_backend = _PinnedNetworkBackend(  # pyright: ignore[reportPrivateUsage]
            {
                self._url_network_key(card_url): tuple(
                    str(address) for address in sorted(pinned_addresses)
                )
            }
        )
        authorization_headers = {"A2A-Version": "1.0"}
        if peer_target.bearer_token:
            authorization_headers["Authorization"] = f"Bearer {peer_target.bearer_token}"
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as http_client:
            try:
                card_response = await http_client.get(
                    card_url,
                    headers=authorization_headers,
                )
                card_response.raise_for_status()
                card_document = card_response.json()
                endpoint_url = self._validated_rest_endpoint(
                    card_document,
                    endpoint_url,
                )
                endpoint_addresses = self._validate_url(endpoint_url)
                if endpoint_addresses != pinned_addresses:
                    raise OutboundA2APolicyError("a2a_card_and_endpoint_resolution_mismatch")
                message_response = await http_client.post(
                    f"{endpoint_url.rstrip('/')}/message:send",
                    headers={**authorization_headers, "Content-Type": "application/json"},
                    json={
                        "message": {
                            "messageId": "msg_"
                            + hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()[:32],
                            "role": "ROLE_USER",
                            "parts": [{"text": message}],
                        },
                        "configuration": {
                            "acceptedOutputModes": ["text/plain"],
                            "returnImmediately": False,
                        },
                    },
                )
                message_response.raise_for_status()
                response_document = message_response.json()
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as request_error:
                raise RuntimeError("a2a_peer_request_failed") from request_error
        response_task_id = self._extract_task_id(response_document)
        response_text = self._extract_task_text(response_document)
        if not response_task_id or not response_text:
            raise RuntimeError("a2a_peer_task_or_text_missing")
        return A2AResponse(task_id=response_task_id, content=response_text)

    @staticmethod
    def _validated_rest_endpoint(card_document: object, registered_endpoint: str) -> str:
        """验证 Agent Card 声明的 A2A HTTP+JSON 1.0 接口与已登记端点一致。"""
        if not isinstance(card_document, dict):
            raise OutboundA2APolicyError("a2a_peer_card_invalid")
        interfaces = card_document.get("supportedInterfaces")
        if not isinstance(interfaces, list):
            raise OutboundA2APolicyError("a2a_peer_card_interface_missing")
        for interface in interfaces:
            if not isinstance(interface, dict):
                continue
            if (
                interface.get("protocolBinding") == "HTTP+JSON"
                and interface.get("protocolVersion") == "1.0"
                and interface.get("url") == registered_endpoint
            ):
                return registered_endpoint
        raise OutboundA2APolicyError("a2a_peer_card_contract_mismatch")

    @staticmethod
    def _url_network_key(url: str) -> tuple[str, int]:
        """返回用于 DNS 固定的标准化主机与端口。"""
        parsed_url = urlsplit(url)
        return (
            (parsed_url.hostname or "").lower().rstrip("."),
            parsed_url.port or (443 if parsed_url.scheme == "https" else 80),
        )

    @staticmethod
    def _extract_task_text(response_document: object) -> str:
        """提取 A2A Task Artifact 或直接 Message 的文本部分。"""
        if not isinstance(response_document, dict):
            raise RuntimeError("a2a_peer_response_invalid")
        response_document = response_document.get("task", response_document)
        if not isinstance(response_document, dict):
            raise RuntimeError("a2a_peer_response_invalid")
        text_parts: list[str] = []
        artifacts = response_document.get("artifacts", [])
        if isinstance(artifacts, list):
            for artifact in artifacts:
                if not isinstance(artifact, dict):
                    continue
                parts = artifact.get("parts", [])
                if isinstance(parts, list):
                    text_parts.extend(
                        str(part["text"])
                        for part in parts
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
        if not text_parts and isinstance(response_document.get("parts"), list):
            text_parts.extend(
                str(part["text"])
                for part in response_document["parts"]
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        return "\n".join(text_parts).strip()

    @staticmethod
    def _extract_task_id(response_document: object) -> str | None:
        """读取 A2A 1.0 Task 或绑定消息中的远端 Task ID。"""
        if not isinstance(response_document, dict):
            return None
        task_document = response_document.get("task", response_document)
        if not isinstance(task_document, dict):
            return None
        task_id = task_document.get("id") or task_document.get("taskId")
        return task_id if isinstance(task_id, str) and task_id.strip() else None

    @staticmethod
    def _validate_url(url: str) -> frozenset[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        """拒绝不安全 scheme、非批准主机、重定向目标和私网解析结果。"""
        parsed_url = urlsplit(url)
        hostname = (parsed_url.hostname or "").lower().rstrip(".")
        if (
            parsed_url.scheme not in {"https", "http"}
            or not hostname
            or parsed_url.username
            or parsed_url.password
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise OutboundA2APolicyError("a2a_peer_url_invalid")
        loopback_dev_allowed = config.a2a.allow_loopback_for_dev
        try:
            literal_address = ipaddress.ip_address(hostname)
        except ValueError:
            literal_address = None
        is_loopback_name = hostname == "localhost" or (
            literal_address is not None and literal_address.is_loopback
        )
        if is_loopback_name:
            if not loopback_dev_allowed:
                raise OutboundA2APolicyError("a2a_loopback_target_denied")
            if (
                parsed_url.scheme != "http"
                and literal_address is not None
                and not literal_address.is_loopback
            ):
                raise OutboundA2APolicyError("a2a_loopback_target_denied")
        else:
            allowlisted_hosts = {
                host.strip().lower().rstrip(".") for host in config.a2a.allowed_outbound_hosts
            }
            if hostname not in allowlisted_hosts:
                raise OutboundA2APolicyError("a2a_host_not_allowlisted")
            if parsed_url.scheme != "https":
                raise OutboundA2APolicyError("a2a_https_required")
        try:
            resolved_addresses = {
                ipaddress.ip_address(address_info[4][0])
                for address_info in socket.getaddrinfo(
                    hostname,
                    parsed_url.port or (443 if parsed_url.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except (OSError, ValueError) as resolution_error:
            raise OutboundA2APolicyError("a2a_host_resolution_failed") from resolution_error
        if not resolved_addresses:
            raise OutboundA2APolicyError("a2a_host_resolution_failed")
        if is_loopback_name and loopback_dev_allowed:
            if not all(address.is_loopback for address in resolved_addresses):
                raise OutboundA2APolicyError("a2a_dns_rebinding_denied")
        elif not all(address.is_global for address in resolved_addresses):
            raise OutboundA2APolicyError("a2a_non_public_address_denied")
        return frozenset(resolved_addresses)


__all__ = ["HttpA2AClient", "OutboundA2APolicyError"]
