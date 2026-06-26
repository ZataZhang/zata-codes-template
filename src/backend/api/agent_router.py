"""Agent HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException

from backend.api.dependencies import get_agent_use_case, get_current_public_user
from backend.api.schemas import AgentCreateRequest, AgentResponse, AgentUpdateRequest
from backend.core.agent.use_cases import AgentUseCase
from backend.core.auth.models import AuthenticatedPrincipal

router = APIRouter(prefix="/agents", tags=["agents"])


def _format_datetime(value: object) -> str | None:
    """格式化 datetime 为 ISO 字符串。"""
    return value.isoformat() if value is not None else None


def _to_agent_response(agent: object) -> AgentResponse:
    """将 Agent 领域对象转换为响应 DTO。"""
    return AgentResponse(
        id=agent.id,
        owner_id=agent.owner_id,
        name=agent.name,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model=agent.model,
        tool_ids=list(agent.tool_ids),
        status=agent.status,
        created_at=_format_datetime(agent.created_at),
        updated_at=_format_datetime(agent.updated_at),
    )


@router.get("", response_model=list[AgentResponse])
async def list_agents(
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: AgentUseCase = Depends(get_agent_use_case),
) -> list[AgentResponse]:
    """列出当前用户的所有 Agent。"""
    agents = use_case.list_agents(current_user.user_id)
    return [_to_agent_response(agent) for agent in agents]


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request_payload: AgentCreateRequest,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: AgentUseCase = Depends(get_agent_use_case),
) -> AgentResponse:
    """创建 Agent。"""
    try:
        agent = use_case.create_agent(
            owner_id=current_user.user_id,
            name=request_payload.name,
            description=request_payload.description,
            system_prompt=request_payload.system_prompt,
            model=request_payload.model,
            tool_ids=request_payload.tool_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _to_agent_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: AgentUseCase = Depends(get_agent_use_case),
) -> AgentResponse:
    """读取指定 Agent。"""
    try:
        agent = use_case.get_agent(agent_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return _to_agent_response(agent)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: str,
    request_payload: AgentUpdateRequest,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: AgentUseCase = Depends(get_agent_use_case),
) -> AgentResponse:
    """更新指定 Agent。"""
    try:
        agent = use_case.update_agent(
            agent_id=agent_id,
            requester_id=current_user.user_id,
            name=request_payload.name,
            description=request_payload.description,
            system_prompt=request_payload.system_prompt,
            model=request_payload.model,
            tool_ids=request_payload.tool_ids,
            status=request_payload.status,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    return _to_agent_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: AgentUseCase = Depends(get_agent_use_case),
) -> None:
    """删除指定 Agent。"""
    try:
        use_case.delete_agent(agent_id, current_user.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
