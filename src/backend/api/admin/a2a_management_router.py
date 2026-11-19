"""组织 Agent 管理 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from backend.api.admin.agent_admin_helpers import (
    _credential_response,
    _peer_response,
    _raise_agent_error,
)
from backend.api.agent_schemas import (
    A2ACredentialCreateRequest,
    A2ACredentialResponse,
    A2APeerApprovalListResponse,
    A2APeerApprovalResponse,
    A2APeerCreateRequest,
    A2APeerCredentialRotateRequest,
    A2APeerListResponse,
    A2APeerResponse,
)
from backend.api.dependencies import (
    get_agent_catalog_use_case,
    get_current_organization_admin,
    get_current_platform_admin,
)
from backend.core.agent import (
    AgentCatalogUseCase,
)
from backend.core.auth.models import AuthenticatedPrincipal

router = APIRouter(prefix="/admin", tags=["admin-agent-management"])


@router.get("/a2a-peers/pending", response_model=A2APeerApprovalListResponse)
def list_pending_a2a_peers(
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> A2APeerApprovalListResponse:
    """列出供平台安全策略审批的对端地址和所属组织。"""
    _ = admin
    return A2APeerApprovalListResponse(
        items=[
            A2APeerApprovalResponse(
                id=peer.id,
                organization_id=peer.organization_id,
                name=peer.name,
                card_url=peer.card_url,
                endpoint_url=peer.endpoint_url,
                is_approved=peer.is_approved,
                is_enabled=peer.is_enabled,
                created_at=peer.created_at.isoformat(),
            )
            for peer in catalog.list_pending_a2a_peers()
        ]
    )


@router.get("/agents/{agent_id}/a2a-credentials", response_model=list[A2ACredentialResponse])
def list_a2a_credentials(
    agent_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> list[A2ACredentialResponse]:
    """列出 Agent 的入站 A2A 凭据元数据。"""
    try:
        return [
            _credential_response(credential)
            for credential in catalog.list_a2a_credentials(admin.organization_id or "", agent_id)
        ]
    except LookupError as credential_error:
        _raise_agent_error(credential_error)


@router.post(
    "/agents/{agent_id}/a2a-credentials",
    response_model=A2ACredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_a2a_credential(
    agent_id: str,
    request: A2ACredentialCreateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> A2ACredentialResponse:
    """创建并仅在本次响应展示一次入站 bearer token。"""
    try:
        credential, token = catalog.create_a2a_credential(
            admin.organization_id or "", admin.user_id, agent_id, request.name
        )
    except (ValueError, LookupError) as credential_error:
        _raise_agent_error(credential_error)
    return _credential_response(credential, token)


@router.delete("/a2a-credentials/{credential_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_a2a_credential(
    credential_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> None:
    """撤销当前组织凭据。"""
    try:
        catalog.revoke_a2a_credential(admin.organization_id or "", credential_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="credential_not_found") from None


@router.get("/a2a-peers", response_model=A2APeerListResponse)
def list_a2a_peers(
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> A2APeerListResponse:
    """列出当前组织登记的 A2A 对端，不返回密钥。"""
    return A2APeerListResponse(
        items=[_peer_response(peer) for peer in catalog.list_a2a_peers(admin.organization_id or "")]
    )


@router.post("/a2a-peers", response_model=A2APeerResponse, status_code=status.HTTP_201_CREATED)
def register_a2a_peer(
    request: A2APeerCreateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> A2APeerResponse:
    """登记待平台网络策略审批的外部 A2A 对端。"""
    try:
        peer = catalog.register_a2a_peer(
            organization_id=admin.organization_id or "",
            actor_id=admin.user_id,
            name=request.name,
            card_url=request.card_url,
            endpoint_url=request.endpoint_url,
            credential_env_alias=request.credential_env_alias,
        )
    except ValueError as peer_error:
        _raise_agent_error(peer_error)
    return _peer_response(peer)


@router.post("/a2a-peers/{peer_id}/approve", response_model=A2APeerResponse)
def approve_a2a_peer(
    peer_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> A2APeerResponse:
    """由平台管理员审批登记对端，启用后才允许出站请求。"""
    try:
        peer = catalog.approve_a2a_peer(peer_id, admin.user_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="peer_not_found") from None
    return _peer_response(peer)


@router.put("/a2a-peers/{peer_id}/credential", status_code=status.HTTP_204_NO_CONTENT)
def rotate_a2a_peer_credential(
    peer_id: str,
    request: A2APeerCredentialRotateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> None:
    """按服务端密钥别名轮换对端凭据，浏览器不提交密钥明文。"""
    try:
        catalog.rotate_a2a_peer_credential(
            organization_id=admin.organization_id or "",
            peer_id=peer_id,
            credential_env_alias=request.credential_env_alias,
        )
    except ValueError as credential_error:
        raise HTTPException(status_code=422, detail=str(credential_error)) from None
    except LookupError:
        raise HTTPException(status_code=404, detail="peer_not_found") from None


__all__ = ["router"]
