"""Admin 域：public 用户管理路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.exceptions import HTTPException
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from backend.api.dependencies import (
    get_current_admin_user,
    get_current_platform_admin,
    get_public_user_directory,
)
from backend.api.schemas import (
    PublicUserListResponse,
    PublicUserOrganizationRequest,
    PublicUserResponse,
)
from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthenticatedPrincipal
from backend.core.shared.models.account_list_filter import AccountListFilter
from backend.core.shared.models.user_account import UserAccount

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _to_public_user_response(account: UserAccount) -> PublicUserResponse:
    """把 public 用户账户映射为 admin 管理响应。"""
    return PublicUserResponse(
        id=account.id,
        email=account.identifier,
        display_name=account.display_name,
        status="active" if account.is_active else "disabled",
        created_at=account.created_at.isoformat() if account.created_at is not None else None,
        organization_id=account.organization_id or "default",
        organization_name=account.organization_name or "",
    )


@router.get("", response_model=PublicUserListResponse)
async def list_public_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None, description="active / disabled，缺省不过滤"),
    keyword: str | None = Query(None, description="按邮箱或展示名模糊匹配"),
    organization_id: str | None = Query(None),
    admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    directory: PublicUserDirectory = Depends(get_public_user_directory),
) -> PublicUserListResponse:
    """分页列出 public 用户。"""
    page_result = directory.list_users(
        page=page,
        page_size=page_size,
        filters=AccountListFilter(
            status=status,
            keyword=keyword,
            organization_id=(admin.organization_id if admin.role == "org" else organization_id),
        ),
    )
    return PublicUserListResponse(
        items=[_to_public_user_response(account) for account in page_result.accounts],
        total=page_result.total,
        page=page,
        page_size=page_size,
    )


@router.get("/{user_id}", response_model=PublicUserResponse)
async def get_public_user(
    user_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    directory: PublicUserDirectory = Depends(get_public_user_directory),
) -> PublicUserResponse:
    """读取单个 public 用户。"""
    account = directory.get_user(
        user_id,
        organization_id=admin.organization_id if admin.role == "org" else None,
    )
    if account is None:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="用户不存在")
    return _to_public_user_response(account)


@router.post("/{user_id}/enable", response_model=PublicUserResponse)
async def enable_public_user(
    user_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    directory: PublicUserDirectory = Depends(get_public_user_directory),
) -> PublicUserResponse:
    """启用某个 public 用户。"""
    account = directory.set_user_active(
        user_id,
        True,
        organization_id=admin.organization_id if admin.role == "org" else None,
    )
    if account is None:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="用户不存在")
    return _to_public_user_response(account)


@router.post("/{user_id}/disable", response_model=PublicUserResponse)
async def disable_public_user(
    user_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_admin_user),
    directory: PublicUserDirectory = Depends(get_public_user_directory),
) -> PublicUserResponse:
    """禁用某个 public 用户（其既有会话下次请求即失效）。"""
    account = directory.set_user_active(
        user_id,
        False,
        organization_id=admin.organization_id if admin.role == "org" else None,
    )
    if account is None:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="用户不存在")
    return _to_public_user_response(account)


@router.patch("/{user_id}/organization", response_model=PublicUserResponse)
def set_public_user_organization(
    user_id: str,
    request: PublicUserOrganizationRequest,
    _admin: AuthenticatedPrincipal = Depends(get_current_platform_admin),
    directory: PublicUserDirectory = Depends(get_public_user_directory),
) -> PublicUserResponse:
    """把 public 用户调整到其他组织。"""
    try:
        account = directory.set_user_organization(user_id, request.organization_id)
    except ValueError as error:
        if str(error) == "organization_not_found":
            raise HTTPException(
                status_code=HTTP_400_BAD_REQUEST,
                detail="organization_not_found",
            ) from error
        raise
    if account is None:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="用户不存在")
    return _to_public_user_response(account)
