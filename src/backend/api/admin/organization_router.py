"""平台管理员组织管理路由。"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from backend.api.dependencies import (
    get_current_platform_admin,
    get_organization_directory,
)
from backend.api.schemas import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationResponse,
)
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.auth.organization_directory import OrganizationDirectory
from backend.core.shared.models.organization import Organization

logger = logging.getLogger(__name__)

organization_router = APIRouter(prefix="/admin/organizations", tags=["admin-organizations"])


def _to_organization_response(organization: Organization) -> OrganizationResponse:
    """把组织领域对象映射为管理端 DTO。"""
    return OrganizationResponse(
        id=organization.id,
        name=organization.name,
        is_active=organization.is_active,
        created_at=(
            organization.created_at.isoformat() if organization.created_at is not None else None
        ),
    )


def _raise_organization_error(error_code: str) -> None:
    """把组织目录稳定错误码映射为 HTTP 状态。"""
    status_code: int = HTTP_400_BAD_REQUEST
    if error_code == "organization_name_conflict":
        status_code = HTTP_409_CONFLICT
    elif error_code == "organization_not_found":
        status_code = HTTP_404_NOT_FOUND
    raise HTTPException(status_code=status_code, detail=error_code)


@organization_router.get("", response_model=OrganizationListResponse)
def list_organizations(
    _admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: OrganizationDirectory = Depends(get_organization_directory),
) -> OrganizationListResponse:
    """列出所有组织。"""
    organizations: list[OrganizationResponse] = [
        _to_organization_response(organization) for organization in directory.list_organizations()
    ]
    return OrganizationListResponse(items=organizations)


@organization_router.post("", response_model=OrganizationResponse)
def create_organization(
    request: OrganizationCreateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: OrganizationDirectory = Depends(get_organization_directory),
) -> OrganizationResponse:
    """创建组织并记录结构化审计事件。"""
    try:
        created_organization: Organization = directory.create_organization(request.name)
    except ValueError as directory_error:
        error_code: str = str(directory_error)
        logger.warning(
            "admin.audit actor_id=%s action=organization.create target_id=unknown "
            "outcome=failure reason=%s",
            admin.user_id,
            error_code,
        )
        _raise_organization_error(error_code)
    logger.info(
        "admin.audit actor_id=%s action=organization.create target_id=%s outcome=success",
        admin.user_id,
        created_organization.id,
    )
    return _to_organization_response(created_organization)


@organization_router.post("/{organization_id}/enable", response_model=OrganizationResponse)
def enable_organization(
    organization_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: OrganizationDirectory = Depends(get_organization_directory),
) -> OrganizationResponse:
    """启用组织并记录结构化审计事件。"""
    return _set_organization_active(
        organization_id=organization_id,
        is_active=True,
        admin=admin,
        directory=directory,
    )


@organization_router.post("/{organization_id}/disable", response_model=OrganizationResponse)
def disable_organization(
    organization_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: OrganizationDirectory = Depends(get_organization_directory),
) -> OrganizationResponse:
    """停用组织并记录结构化审计事件。"""
    return _set_organization_active(
        organization_id=organization_id,
        is_active=False,
        admin=admin,
        directory=directory,
    )


def _set_organization_active(
    organization_id: str,
    *,
    is_active: bool,
    admin: AuthenticatedPrincipal,
    directory: OrganizationDirectory,
) -> OrganizationResponse:
    """更新组织启用状态并记录结果。"""
    action_name: str = "organization.enable" if is_active else "organization.disable"
    try:
        updated_organization: Organization | None = directory.set_organization_active(
            organization_id,
            is_active=is_active,
        )
    except ValueError as directory_error:
        error_code: str = str(directory_error)
        logger.warning(
            "admin.audit actor_id=%s action=%s target_id=%s outcome=failure reason=%s",
            admin.user_id,
            action_name,
            organization_id,
            error_code,
        )
        _raise_organization_error(error_code)
    if updated_organization is None:
        logger.warning(
            "admin.audit actor_id=%s action=%s target_id=%s outcome=failure reason=not_found",
            admin.user_id,
            action_name,
            organization_id,
        )
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="organization_not_found")
    logger.info(
        "admin.audit actor_id=%s action=%s target_id=%s outcome=success",
        admin.user_id,
        action_name,
        organization_id,
    )
    return _to_organization_response(updated_organization)


__all__ = ["organization_router"]
