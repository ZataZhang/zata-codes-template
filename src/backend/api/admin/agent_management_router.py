"""组织 Agent 管理 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from backend.api.admin.agent_admin_helpers import _agent_response, _raise_agent_error
from backend.api.agent_schemas import (
    AgentCreateRequest,
    AgentListResponse,
    AgentResponse,
    AgentUpdateRequest,
)
from backend.api.dependencies import (
    get_agent_catalog_use_case,
    get_current_organization_admin,
)
from backend.core.agent import (
    AgentCatalogUseCase,
    CreateAgentCommand,
    UpdateAgentCommand,
)
from backend.core.auth.models import AuthenticatedPrincipal
from backend.infrastructure.config.settings import config

router = APIRouter(prefix="/admin", tags=["admin-agent-management"])


@router.get("/agents", response_model=AgentListResponse)
def list_agents(
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> AgentListResponse:
    """列出当前组织全部 Agent 与可运行状态。"""
    return AgentListResponse(
        items=[
            _agent_response(entry, public_base_url=config.a2a.public_base_url)
            for entry in catalog.list_agents(admin.organization_id or "", published_only=False)
        ]
    )


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    request: AgentCreateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> AgentResponse:
    """创建当前组织未发布 Agent。"""
    try:
        agent = catalog.create_agent(
            CreateAgentCommand(
                organization_id=admin.organization_id or "",
                actor_id=admin.user_id,
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                model_name=request.model_name,
                skill_id=request.skill_id,
            )
        )
        return _agent_response(
            next(
                entry
                for entry in catalog.list_agents(admin.organization_id or "", published_only=False)
                if entry.agent.id == agent.id
            ),
            public_base_url=config.a2a.public_base_url,
        )
    except (ValueError, LookupError) as agent_error:
        _raise_agent_error(agent_error)


@router.put("/agents/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: str,
    request: AgentUpdateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> AgentResponse:
    """更新当前组织 Agent 的配置并允许停用。"""
    try:
        agent = catalog.update_agent(
            UpdateAgentCommand(
                organization_id=admin.organization_id or "",
                agent_id=agent_id,
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                model_name=request.model_name,
                skill_id=request.skill_id,
                is_enabled=request.is_enabled,
            )
        )
        entry = next(
            item
            for item in catalog.list_agents(admin.organization_id or "", published_only=False)
            if item.agent.id == agent.id
        )
        return _agent_response(entry, public_base_url=config.a2a.public_base_url)
    except (ValueError, LookupError) as agent_error:
        _raise_agent_error(agent_error)


@router.post("/agents/{agent_id}/publish", response_model=AgentResponse)
def publish_agent(
    agent_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> AgentResponse:
    """发布一个启用状态的 Agent。"""
    try:
        agent = catalog.set_published(admin.organization_id or "", agent_id, True)
        return _agent_response(
            next(
                entry
                for entry in catalog.list_agents(admin.organization_id or "", published_only=False)
                if entry.agent.id == agent.id
            ),
            public_base_url=config.a2a.public_base_url,
        )
    except (ValueError, LookupError) as agent_error:
        _raise_agent_error(agent_error)


@router.post("/agents/{agent_id}/unpublish", response_model=AgentResponse)
def unpublish_agent(
    agent_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    catalog: AgentCatalogUseCase = Depends(get_agent_catalog_use_case),
) -> AgentResponse:
    """撤下当前组织 Agent。"""
    try:
        agent = catalog.set_published(admin.organization_id or "", agent_id, False)
        return _agent_response(
            next(
                entry
                for entry in catalog.list_agents(admin.organization_id or "", published_only=False)
                if entry.agent.id == agent.id
            ),
            public_base_url=config.a2a.public_base_url,
        )
    except (ValueError, LookupError) as agent_error:
        _raise_agent_error(agent_error)


__all__ = ["router"]
