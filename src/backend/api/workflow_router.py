"""Workflow HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.exceptions import HTTPException

from backend.api.dependencies import get_current_public_user, get_workflow_use_case
from backend.api.schemas import (
    WorkflowCreateRequest,
    WorkflowEdgeDto,
    WorkflowNodeDto,
    WorkflowResponse,
    WorkflowUpdateRequest,
)
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.workflow.use_cases import WorkflowUseCase

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _format_datetime(value: object) -> str | None:
    """格式化 datetime 为 ISO 字符串。"""
    return value.isoformat() if value is not None else None


def _to_workflow_response(workflow: object) -> WorkflowResponse:
    """将 Workflow 领域对象转换为响应 DTO。"""
    return WorkflowResponse(
        id=workflow.id,
        owner_id=workflow.owner_id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        nodes=[
            WorkflowNodeDto(
                id=node.id,
                node_type=node.node_type,
                label=node.label,
                config=node.config,
                position_x=node.position_x,
                position_y=node.position_y,
            )
            for node in workflow.nodes
        ],
        edges=[
            WorkflowEdgeDto(
                id=edge.id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
            )
            for edge in workflow.edges
        ],
        created_at=_format_datetime(workflow.created_at),
        updated_at=_format_datetime(workflow.updated_at),
    )


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
) -> list[WorkflowResponse]:
    """列出当前用户的所有工作流。"""
    workflows = use_case.list_workflows(current_user.user_id)
    return [_to_workflow_response(workflow) for workflow in workflows]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request_payload: WorkflowCreateRequest,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
) -> WorkflowResponse:
    """创建工作流。"""
    try:
        workflow = use_case.create_workflow(
            owner_id=current_user.user_id,
            name=request_payload.name,
            description=request_payload.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return _to_workflow_response(workflow)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
) -> WorkflowResponse:
    """读取指定工作流。"""
    try:
        workflow = use_case.get_workflow(workflow_id, current_user.user_id)
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
    return _to_workflow_response(workflow)


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    request_payload: WorkflowUpdateRequest,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
) -> WorkflowResponse:
    """更新指定工作流。"""
    try:
        workflow = use_case.update_workflow(
            workflow_id=workflow_id,
            requester_id=current_user.user_id,
            name=request_payload.name,
            description=request_payload.description,
            nodes=[node.model_dump() for node in request_payload.nodes],
            edges=[edge.model_dump() for edge in request_payload.edges],
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
    return _to_workflow_response(workflow)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
) -> None:
    """删除指定工作流。"""
    try:
        use_case.delete_workflow(workflow_id, current_user.user_id)
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


@router.post("/{workflow_id}/run", response_model=dict)
async def run_workflow(
    workflow_id: str,
    current_user: AuthenticatedPrincipal = Depends(get_current_public_user),
    use_case: WorkflowUseCase = Depends(get_workflow_use_case),
) -> dict:
    """运行指定工作流。"""
    try:
        result = use_case.run_workflow(workflow_id, current_user.user_id)
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
    return result
