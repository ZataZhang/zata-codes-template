"""在线 Agent、Skill、Run 与 A2A 管理端 DTO。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentCreateRequest(BaseModel):
    """创建 Agent 的声明式配置。"""

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=8_000)
    instructions: str = Field(min_length=1, max_length=32_000)
    model_name: str | None = Field(default=None, max_length=255)
    skill_id: str | None = Field(default=None, max_length=64)


class AgentUpdateRequest(AgentCreateRequest):
    """替换 Agent 配置并设置启用状态。"""

    is_enabled: bool = True


class AgentResponse(BaseModel):
    """管理员可见的 Agent 配置 DTO。"""

    id: str
    name: str
    description: str
    instructions: str
    model_name: str | None
    skill_id: str | None
    is_enabled: bool
    is_published: bool
    is_runnable: bool
    unavailable_reason: str | None
    a2a_card_url: str | None = None
    created_at: str
    updated_at: str


class MemberAgentResponse(BaseModel):
    """成员可见的已发布 Agent 目录 DTO。"""

    id: str
    name: str
    description: str
    is_enabled: bool
    is_runnable: bool
    unavailable_reason: str | None


class AgentListResponse(BaseModel):
    """Agent 目录响应。"""

    items: list[AgentResponse]


class MemberAgentListResponse(BaseModel):
    """成员可用 Agent 目录响应。"""

    items: list[MemberAgentResponse]


class SkillCreateRequest(BaseModel):
    """创建带初始版本的声明式 Skill。"""

    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=8_000)
    body: str = Field(min_length=1, max_length=100_000)


class SkillRevisionRequest(BaseModel):
    """追加一个 Skill 正文版本。"""

    body: str = Field(min_length=1, max_length=100_000)


class SkillResponse(BaseModel):
    """组织内 Skill 目录 DTO。"""

    id: str
    name: str
    description: str
    current_version: int
    created_at: str
    updated_at: str


class SkillRevisionResponse(BaseModel):
    """不可变 Skill 正文版本 DTO。"""

    id: str
    skill_id: str
    version: int
    body: str
    checksum: str
    created_at: str


class SkillListResponse(BaseModel):
    """Skill 目录响应。"""

    items: list[SkillResponse]


class SkillRevisionListResponse(BaseModel):
    """Skill 版本历史响应。"""

    items: list[SkillRevisionResponse]


class SkillCompareResponse(BaseModel):
    """Skill 两个版本的原始正文对照。"""

    from_version: SkillRevisionResponse
    to_version: SkillRevisionResponse


class AgentRunCreateRequest(BaseModel):
    """成员创建 Agent Run 的请求。"""

    agent_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=32_000)
    conversation_id: str | None = Field(default=None, max_length=64)


class AgentRunListItem(BaseModel):
    """成员历史 Run 列表项。"""

    id: str
    conversation_id: str | None
    agent_id: str
    agent_name: str
    status: str
    created_at: str
    finished_at: str | None


class AgentRunResponse(AgentRunListItem):
    """成员 Run 详情 DTO。"""

    input_message: str
    assistant_message: str | None
    unavailable_reason: str | None = None


class AgentRunListResponse(BaseModel):
    """成员 Run 历史响应。"""

    items: list[AgentRunListItem]
    total: int


class AgentRunEventResponse(BaseModel):
    """Canonical Run Event 的成员可见序列化。"""

    seq: int
    event_type: str
    occurred_at: str
    payload: dict[str, object]


class AgentRunEventsResponse(BaseModel):
    """Run 事件游标响应。"""

    items: list[AgentRunEventResponse]
    next_after_seq: int


class AdminAgentRunListResponse(BaseModel):
    """组织管理员可见的低敏 Run 轨迹摘要。"""

    items: list[dict[str, object]]
    total: int


class A2ACredentialCreateRequest(BaseModel):
    """创建一个仅可调用指定 Agent 的服务凭据。"""

    name: str = Field(min_length=1, max_length=128)


class A2ACredentialResponse(BaseModel):
    """A2A 入站凭据元数据；明文仅在创建响应出现一次。"""

    id: str
    agent_id: str
    name: str
    is_active: bool
    created_at: str
    token: str | None = None


class A2APeerCreateRequest(BaseModel):
    """登记待平台网络审批的 A2A 对端。"""

    name: str = Field(min_length=1, max_length=128)
    card_url: str = Field(min_length=1, max_length=2_048)
    endpoint_url: str = Field(min_length=1, max_length=2_048)
    credential_env_alias: str | None = Field(default=None, max_length=128)


class A2APeerCredentialRotateRequest(BaseModel):
    """从服务端密钥引用轮换对端凭据。"""

    credential_env_alias: str = Field(min_length=3, max_length=128)


class A2APeerResponse(BaseModel):
    """当前组织登记的对端，不包含出站凭据。"""

    id: str
    name: str
    card_url: str
    endpoint_url: str
    is_approved: bool
    is_enabled: bool
    created_at: str


class A2APeerListResponse(BaseModel):
    """组织的 A2A 对端目录响应。"""

    items: list[A2APeerResponse]


class A2APeerApprovalResponse(A2APeerResponse):
    """平台审批所需的对端控制面摘要。"""

    organization_id: str


class A2APeerApprovalListResponse(BaseModel):
    """待平台网络策略审批的对端列表。"""

    items: list[A2APeerApprovalResponse]
