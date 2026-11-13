"""组织 Agent 管理 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from backend.api.admin.agent_admin_helpers import (
    _raise_agent_error,
    _revision_response,
    _skill_response,
)
from backend.api.agent_schemas import (
    SkillCompareResponse,
    SkillCreateRequest,
    SkillListResponse,
    SkillResponse,
    SkillRevisionListResponse,
    SkillRevisionRequest,
    SkillRevisionResponse,
)
from backend.api.dependencies import (
    get_current_organization_admin,
    get_skill_use_case,
)
from backend.core.agent import (
    SkillUseCase,
)
from backend.core.auth.models import AuthenticatedPrincipal

router = APIRouter(prefix="/admin", tags=["admin-agent-management"])


@router.get("/skills", response_model=SkillListResponse)
def list_skills(
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    skills: SkillUseCase = Depends(get_skill_use_case),
) -> SkillListResponse:
    """列出当前组织 Skill。"""
    return SkillListResponse(
        items=[_skill_response(skill) for skill in skills.list_skills(admin.organization_id or "")]
    )


@router.post("/skills", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(
    request: SkillCreateRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    skills: SkillUseCase = Depends(get_skill_use_case),
) -> SkillResponse:
    """创建 Skill 和不可变版本 1。"""
    try:
        skill, _revision = skills.create_skill(
            organization_id=admin.organization_id or "",
            actor_id=admin.user_id,
            name=request.name,
            description=request.description,
            body=request.body,
        )
        return _skill_response(skill)
    except (ValueError, LookupError) as skill_error:
        _raise_agent_error(skill_error)


@router.get("/skills/{skill_id}/versions", response_model=SkillRevisionListResponse)
def list_skill_versions(
    skill_id: str,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    skills: SkillUseCase = Depends(get_skill_use_case),
) -> SkillRevisionListResponse:
    """按版本号升序读取当前组织 Skill 历史。"""
    try:
        revisions = skills.list_revisions(admin.organization_id or "", skill_id)
    except (ValueError, LookupError) as skill_error:
        _raise_agent_error(skill_error)
    return SkillRevisionListResponse(items=[_revision_response(item) for item in revisions])


@router.post("/skills/{skill_id}/versions", response_model=SkillRevisionResponse)
def append_skill_version(
    skill_id: str,
    request: SkillRevisionRequest,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    skills: SkillUseCase = Depends(get_skill_use_case),
) -> SkillRevisionResponse:
    """追加 Skill 新版本，拒绝任何对旧记录的改写。"""
    try:
        revision = skills.add_revision(
            organization_id=admin.organization_id or "",
            skill_id=skill_id,
            actor_id=admin.user_id,
            body=request.body,
        )
    except (ValueError, LookupError) as skill_error:
        _raise_agent_error(skill_error)
    return _revision_response(revision)


@router.get("/skills/{skill_id}/compare", response_model=SkillCompareResponse)
def compare_skill_versions(
    skill_id: str,
    from_version: int = Query(ge=1),
    to_version: int = Query(ge=1),
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    skills: SkillUseCase = Depends(get_skill_use_case),
) -> SkillCompareResponse:
    """读取两个版本的原文供管理端比较。"""
    try:
        earlier, later = skills.compare_revisions(
            organization_id=admin.organization_id or "",
            skill_id=skill_id,
            from_version=from_version,
            to_version=to_version,
        )
    except (ValueError, LookupError) as skill_error:
        _raise_agent_error(skill_error)
    return SkillCompareResponse(
        from_version=_revision_response(earlier), to_version=_revision_response(later)
    )


@router.post("/skills/{skill_id}/restore/{version}", response_model=SkillRevisionResponse)
def restore_skill_version(
    skill_id: str,
    version: int,
    admin: AuthenticatedPrincipal = Depends(get_current_organization_admin),
    skills: SkillUseCase = Depends(get_skill_use_case),
) -> SkillRevisionResponse:
    """以旧版本正文创建新版本。"""
    try:
        revision = skills.restore_revision(
            organization_id=admin.organization_id or "",
            skill_id=skill_id,
            version=version,
            actor_id=admin.user_id,
        )
    except (ValueError, LookupError) as skill_error:
        _raise_agent_error(skill_error)
    return _revision_response(revision)


__all__ = ["router"]
