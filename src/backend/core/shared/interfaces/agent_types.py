"""Agent、Skill 与 A2A 目录的领域数据类型。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AgentDefinition:
    """组织内 Agent 的稳定身份与声明式配置。"""

    id: str
    organization_id: str
    created_by: str
    name: str
    description: str
    instructions: str
    model_name: str | None
    skill_id: str | None
    is_enabled: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime
    allowed_peer_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillDefinition:
    """Skill 当前目录项。"""

    id: str
    organization_id: str
    created_by: str
    name: str
    description: str
    current_version: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SkillRevision:
    """只追加的 Skill 正文版本。"""

    id: str
    skill_id: str
    organization_id: str
    version: int
    body: str
    checksum: str
    created_by: str
    created_at: datetime


@dataclass(frozen=True)
class SkillWriteIdempotency:
    """Skill 写入的调用方重试键与服务端请求摘要。"""

    key_hash: str
    request_checksum: str


@dataclass(frozen=True)
class SkillRevisionDraft:
    """一次待串行追加的 Skill 版本写入。"""

    organization_id: str
    skill_id: str
    created_by: str
    body: str
    idempotency: SkillWriteIdempotency | None = None


@dataclass(frozen=True)
class A2ACredential:
    """绑定组织和 Agent 的入站服务凭据元数据。"""

    id: str
    organization_id: str
    agent_id: str
    name: str
    is_active: bool
    created_at: datetime
    revoked_at: datetime | None


@dataclass(frozen=True)
class A2APeer:
    """组织登记的 A2A 对端，不包含任何凭据。"""

    id: str
    organization_id: str
    created_by: str
    name: str
    card_url: str
    endpoint_url: str
    is_approved: bool
    is_enabled: bool
    approved_by: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class A2APeerTarget:
    """供一次受权出站调用使用的对端地址和内存凭据。"""

    peer: A2APeer
    bearer_token: str | None


@dataclass(frozen=True)
class AgentExecutionSnapshot:
    """创建 Run 时冻结的 Agent、模型、Skill 版本与 A2A 对端授权。"""

    agent_id: str
    organization_id: str
    agent_name: str
    instructions: str
    model_name: str
    skill_id: str | None
    skill_version_id: str | None
    skill_version: int | None
    skill_body: str | None
    allowed_peer_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentCatalogEntry:
    """面向成员目录的 Agent 及可运行状态。"""

    agent: AgentDefinition
    is_runnable: bool
    unavailable_reason: str | None
