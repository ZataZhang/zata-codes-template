"""平台管理员目录管理路由。"""

from __future__ import annotations

import logging
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND, HTTP_409_CONFLICT

from backend.api.dependencies import get_admin_directory, get_current_platform_admin
from backend.api.schemas import (
    AdminCreateRequest,
    AdminDirectoryListResponse,
    AdminDirectoryResponse,
)
from backend.core.auth.admin_directory import AdminCreateCommand, AdminDirectory
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.shared.models.user_account import UserAccount

logger = logging.getLogger(__name__)

admin_directory_router = APIRouter(prefix="/admin/admins", tags=["admin-directory"])


def _to_admin_response(account: UserAccount) -> AdminDirectoryResponse:
    """把管理员账户映射为管理端 DTO。"""
    return AdminDirectoryResponse(
        id=account.id,
        username=account.identifier,
        display_name=account.display_name,
        email=account.email,
        role=cast(Literal["platform", "org"], account.role),
        organization_id=account.organization_id,
        organization_name=account.organization_name,
        status="active" if account.is_active else "disabled",
        oidc_bound=account.oidc_issuer is not None and account.oidc_subject is not None,
        created_at=account.created_at.isoformat() if account.created_at is not None else None,
    )


def _raise_admin_directory_error(error_code: str) -> None:
    """把管理员目录稳定错误码映射为 HTTP 状态。"""
    status_code: int = HTTP_400_BAD_REQUEST
    if error_code in {"username_conflict", "email_conflict"}:
        status_code = HTTP_409_CONFLICT
    elif error_code == "organization_not_found":
        status_code = HTTP_404_NOT_FOUND
    raise HTTPException(status_code=status_code, detail=error_code)


@admin_directory_router.get("", response_model=AdminDirectoryListResponse)
def list_admins(
    _admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: AdminDirectory = Depends(get_admin_directory),
) -> AdminDirectoryListResponse:
    """列出平台管理员与组织管理员。"""
    admin_responses: list[AdminDirectoryResponse] = [
        _to_admin_response(account) for account in directory.list_admins()
    ]
    return AdminDirectoryListResponse(items=admin_responses)


@admin_directory_router.post("", response_model=AdminDirectoryResponse)
def create_admin(
    request: AdminCreateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: AdminDirectory = Depends(get_admin_directory),
) -> AdminDirectoryResponse:
    """创建管理员并记录不含凭据的审计事件。"""
    create_command = AdminCreateCommand(
        username=request.username,
        email=request.email,
        display_name=request.display_name,
        role=request.role,
        organization_id=request.organization_id,
        password=request.password,
    )
    try:
        created_account: UserAccount = directory.create_admin(create_command)
    except ValueError as directory_error:
        error_code: str = str(directory_error).partition(":")[0]
        logger.warning(
            "admin.audit actor_id=%s action=admin.create target_id=unknown outcome=failure "
            "reason=%s",
            admin.user_id,
            error_code,
        )
        _raise_admin_directory_error(error_code)
    logger.info(
        "admin.audit actor_id=%s action=admin.create target_id=%s outcome=success",
        admin.user_id,
        created_account.id,
    )
    return _to_admin_response(created_account)


@admin_directory_router.post("/{account_id}/enable", response_model=AdminDirectoryResponse)
def enable_admin(
    account_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: AdminDirectory = Depends(get_admin_directory),
) -> AdminDirectoryResponse:
    """启用管理员并记录结构化审计事件。"""
    return _set_admin_active(account_id, is_active=True, admin=admin, directory=directory)


@admin_directory_router.post("/{account_id}/disable", response_model=AdminDirectoryResponse)
def disable_admin(
    account_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: AdminDirectory = Depends(get_admin_directory),
) -> AdminDirectoryResponse:
    """禁用管理员并记录结构化审计事件。"""
    return _set_admin_active(account_id, is_active=False, admin=admin, directory=directory)


def _set_admin_active(
    account_id: str,
    *,
    is_active: bool,
    admin: AuthenticatedPrincipal,
    directory: AdminDirectory,
) -> AdminDirectoryResponse:
    """更新管理员状态并记录成功或失败结果。"""
    action_name: str = "admin.enable" if is_active else "admin.disable"
    try:
        updated_account: UserAccount | None = directory.set_admin_active(
            admin.user_id,
            account_id,
            is_active=is_active,
        )
    except ValueError as directory_error:
        error_code: str = str(directory_error)
        logger.warning(
            "admin.audit actor_id=%s action=%s target_id=%s outcome=failure reason=%s",
            admin.user_id,
            action_name,
            account_id,
            error_code,
        )
        _raise_admin_directory_error(error_code)
    if updated_account is None:
        logger.warning(
            "admin.audit actor_id=%s action=%s target_id=%s outcome=failure reason=not_found",
            admin.user_id,
            action_name,
            account_id,
        )
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="admin_not_found")
    logger.info(
        "admin.audit actor_id=%s action=%s target_id=%s outcome=success",
        admin.user_id,
        action_name,
        account_id,
    )
    return _to_admin_response(updated_account)


@admin_directory_router.post("/{account_id}/unbind-oidc", response_model=AdminDirectoryResponse)
def unbind_admin_oidc(
    account_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: AdminDirectory = Depends(get_admin_directory),
) -> AdminDirectoryResponse:
    """解除管理员的本地企业账号绑定，不停用身份中心账号。"""
    try:
        unbound_account: UserAccount | None = directory.unbind_admin_oidc_identity(account_id)
    except ValueError as directory_error:
        error_code: str = str(directory_error)
        logger.warning(
            "admin.audit actor_id=%s action=admin.unbind_oidc target_id=%s "
            "outcome=failure reason=%s",
            admin.user_id,
            account_id,
            error_code,
        )
        _raise_admin_directory_error(error_code)
    if unbound_account is None:
        logger.warning(
            "admin.audit actor_id=%s action=admin.unbind_oidc target_id=%s "
            "outcome=failure reason=not_found",
            admin.user_id,
            account_id,
        )
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="admin_not_found")
    logger.info(
        "admin.audit actor_id=%s action=admin.unbind_oidc target_id=%s outcome=success",
        admin.user_id,
        account_id,
    )
    return _to_admin_response(unbound_account)


__all__ = ["admin_directory_router"]
