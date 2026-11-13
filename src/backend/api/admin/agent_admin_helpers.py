"""Agent 管理路由的 DTO 映射与稳定错误转换。"""

from __future__ import annotations

from fastapi import HTTPException

from backend.api.agent_schemas import (
    A2ACredentialResponse,
    A2APeerResponse,
    AgentResponse,
    SkillResponse,
    SkillRevisionResponse,
)
from backend.core.agent import AgentNotFoundError, SkillNotFoundError
from backend.core.shared.interfaces.agent_types import (
    A2ACredential,
    A2APeer,
    AgentCatalogEntry,
    SkillDefinition,
    SkillRevision,
)


def _agent_response(entry: AgentCatalogEntry, *, public_base_url: str = "") -> AgentResponse:
    """映射组织管理员可见的 Agent 配置和可用性。"""
    agent = entry.agent
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        description=agent.description,
        instructions=agent.instructions,
        model_name=agent.model_name,
        skill_id=agent.skill_id,
        is_enabled=agent.is_enabled,
        is_published=agent.is_published,
        is_runnable=entry.is_runnable,
        unavailable_reason=entry.unavailable_reason,
        a2a_card_url=(
            f"{public_base_url.rstrip('/')}/a2a/agents/{agent.id}"
            if agent.is_published and public_base_url
            else None
        ),
        created_at=agent.created_at.isoformat(),
        updated_at=agent.updated_at.isoformat(),
    )


def _skill_response(skill: SkillDefinition) -> SkillResponse:
    """映射 Skill 目录项。"""
    return SkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        current_version=skill.current_version,
        created_at=skill.created_at.isoformat(),
        updated_at=skill.updated_at.isoformat(),
    )


def _revision_response(revision: SkillRevision) -> SkillRevisionResponse:
    """映射只读 Skill 版本。"""
    return SkillRevisionResponse(
        id=revision.id,
        skill_id=revision.skill_id,
        version=revision.version,
        body=revision.body,
        checksum=revision.checksum,
        created_at=revision.created_at.isoformat(),
    )


def _peer_response(peer: A2APeer) -> A2APeerResponse:
    """映射不含出站密钥的 A2A 对端。"""
    return A2APeerResponse(
        id=peer.id,
        name=peer.name,
        card_url=peer.card_url,
        endpoint_url=peer.endpoint_url,
        is_approved=peer.is_approved,
        is_enabled=peer.is_enabled,
        created_at=peer.created_at.isoformat(),
    )


def _credential_response(
    credential: A2ACredential, token: str | None = None
) -> A2ACredentialResponse:
    """映射凭据元数据；只有创建响应带一次性明文。"""
    return A2ACredentialResponse(
        id=credential.id,
        agent_id=credential.agent_id,
        name=credential.name,
        is_active=credential.is_active,
        created_at=credential.created_at.isoformat(),
        token=token,
    )


def _raise_agent_error(error: Exception) -> None:
    """把组织范围内的 Agent 和 Skill 错误映射为稳定 HTTP 状态。"""
    if isinstance(error, (AgentNotFoundError, SkillNotFoundError, LookupError)):
        raise HTTPException(status_code=404, detail="resource_not_found") from None
    if isinstance(error, ValueError):
        raise HTTPException(status_code=422, detail=str(error)) from None
    raise error
