"""在线 Agent、Skill 与 A2A 目录的持久化端口。"""

from __future__ import annotations

from typing import Protocol, Sequence

from backend.core.shared.interfaces.agent_types import (
    A2ACredential,
    A2APeer,
    A2APeerTarget,
    AgentDefinition,
    SkillDefinition,
    SkillRevision,
)


class AgentRepository(Protocol):
    """提供组织范围 Agent、Skill 与 A2A 目录访问。"""

    def create_agent(self, agent: AgentDefinition) -> AgentDefinition:
        """事务创建组织内 Agent。"""
        ...

    def get_agent(self, organization_id: str, agent_id: str) -> AgentDefinition | None:
        """按组织和 Agent ID 读取配置。"""
        ...

    def list_agents(
        self, organization_id: str, *, published_only: bool
    ) -> Sequence[AgentDefinition]:
        """列出当前组织 Agent，可选仅返回已发布项。"""
        ...

    def update_agent(self, agent: AgentDefinition) -> AgentDefinition:
        """替换当前组织 Agent 的配置。"""
        ...

    def create_skill(
        self, skill: SkillDefinition, initial_body: str
    ) -> tuple[SkillDefinition, SkillRevision]:
        """事务创建 Skill 及其版本一。"""
        ...

    def get_skill(self, organization_id: str, skill_id: str) -> SkillDefinition | None:
        """按组织和 Skill ID 读取目录项。"""
        ...

    def list_skills(self, organization_id: str) -> Sequence[SkillDefinition]:
        """列出当前组织 Skill。"""
        ...

    def append_skill_revision(
        self, organization_id: str, skill_id: str, created_by: str, body: str
    ) -> SkillRevision:
        """锁定 Skill 并追加下一个不可变版本。"""
        ...

    def list_skill_revisions(self, organization_id: str, skill_id: str) -> Sequence[SkillRevision]:
        """按版本号读取 Skill 历史。"""
        ...

    def get_skill_revision(
        self, organization_id: str, skill_id: str, version: int
    ) -> SkillRevision | None:
        """按组织、Skill ID 和序号读取不可变版本。"""
        ...

    def resolve_skill(
        self, organization_id: str, skill_id: str
    ) -> tuple[SkillDefinition, SkillRevision] | None:
        """读取 Skill 当前指向的版本快照。"""
        ...

    def create_a2a_credential(self, credential: A2ACredential, token_hash: str) -> A2ACredential:
        """只持久化凭据哈希并返回凭据元数据。"""
        ...

    def resolve_a2a_credential(self, token_hash: str) -> A2ACredential | None:
        """按明文 token 摘要解析活动凭据。"""
        ...

    def list_a2a_credentials(self, organization_id: str, agent_id: str) -> Sequence[A2ACredential]:
        """列出组织 Agent 的凭据元数据。"""
        ...

    def revoke_a2a_credential(self, organization_id: str, credential_id: str) -> bool:
        """按组织撤销服务凭据。"""
        ...

    def create_a2a_peer(self, peer: A2APeer, bearer_token: str | None) -> A2APeer:
        """创建待审批对端并加密保存可选凭据。"""
        ...

    def list_a2a_peers(self, organization_id: str) -> Sequence[A2APeer]:
        """列出当前组织对端目录，不返回密文。"""
        ...

    def approve_a2a_peer(self, peer_id: str, platform_admin_id: str) -> A2APeer | None:
        """记录平台管理员批准并启用的对端。"""
        ...

    def list_pending_a2a_peers(self) -> Sequence[A2APeer]:
        """列出待平台网络策略审批的 A2A 对端。"""
        ...

    def get_a2a_peer_target(self, organization_id: str, peer_id: str) -> A2APeerTarget | None:
        """解析当前组织已批准对端与仅供本次调用的明文凭据。"""
        ...

    def rotate_a2a_peer_credential(
        self, organization_id: str, peer_id: str, bearer_token: str
    ) -> bool:
        """加密替换组织已登记对端的出站凭据。"""
        ...


__all__ = ["AgentRepository"]
