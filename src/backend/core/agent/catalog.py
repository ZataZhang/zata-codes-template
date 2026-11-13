"""组织范围 Agent 与 A2A 目录治理用例。"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Sequence

from backend.core.shared.interfaces.agent_executor import AgentExecutor
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.agent_types import (
    A2ACredential,
    A2APeer,
    AgentCatalogEntry,
    AgentDefinition,
)
from backend.core.shared.interfaces.secret_resolver import SecretResolver


@dataclass(frozen=True)
class CreateAgentCommand:
    """创建 Agent 的组织范围命令。"""

    organization_id: str
    actor_id: str
    name: str
    description: str
    instructions: str
    model_name: str | None = None
    skill_id: str | None = None


@dataclass(frozen=True)
class UpdateAgentCommand:
    """替换 Agent 声明式配置的命令。"""

    organization_id: str
    agent_id: str
    name: str
    description: str
    instructions: str
    model_name: str | None
    skill_id: str | None
    is_enabled: bool


class AgentUnavailableError(ValueError):
    """Agent 未发布、已停用或没有可用模型。"""


class AgentNotFoundError(LookupError):
    """当前组织范围内不存在 Agent。"""


class SkillNotFoundError(LookupError):
    """当前组织范围内不存在 Skill 或 Skill 版本。"""


class AgentCatalogUseCase:
    """组织范围 Agent 与 A2A 目录治理用例。"""

    def __init__(
        self,
        repository: AgentRepository,
        executor: AgentExecutor,
        secret_resolver: SecretResolver | None = None,
    ) -> None:
        """初始化 Agent 目录用例。

        Args:
            repository (AgentRepository): 组织范围持久化端口。
            executor (AgentExecutor): 已装配的 Agent 执行端口。
            secret_resolver (SecretResolver | None): 部署方服务端密钥解析端口。
        """
        self._repository = repository
        self._executor = executor
        self._secret_resolver = secret_resolver

    def create_agent(self, command: CreateAgentCommand) -> AgentDefinition:
        """创建组织内未发布 Agent。

        Args:
            command (CreateAgentCommand): Agent 声明式配置。

        Returns:
            AgentDefinition: 新建 Agent。

        Raises:
            ValueError: 名称、指令或 Skill 归属非法时抛出。
        """
        name = command.name.strip()
        instructions = command.instructions.strip()
        if not name or not instructions:
            raise ValueError("agent_name_and_instructions_required")
        if (
            command.skill_id
            and self._repository.get_skill(command.organization_id, command.skill_id) is None
        ):
            raise SkillNotFoundError("Skill 不存在")
        now = datetime.now(UTC)
        return self._repository.create_agent(
            AgentDefinition(
                id=uuid.uuid4().hex,
                organization_id=command.organization_id,
                created_by=command.actor_id,
                name=name,
                description=command.description.strip(),
                instructions=instructions,
                model_name=command.model_name.strip() if command.model_name else None,
                skill_id=command.skill_id,
                is_enabled=True,
                is_published=False,
                created_at=now,
                updated_at=now,
            )
        )

    def update_agent(self, command: UpdateAgentCommand) -> AgentDefinition:
        """更新当前组织 Agent 的声明式配置。

        Args:
            command (UpdateAgentCommand): 已完成字段验证的更新命令。

        Returns:
            AgentDefinition: 更新后的 Agent。

        Raises:
            AgentNotFoundError: Agent 不属于当前组织时抛出。
            ValueError: 名称、指令或 Skill 归属非法时抛出。
        """
        existing_agent = self._repository.get_agent(command.organization_id, command.agent_id)
        if existing_agent is None:
            raise AgentNotFoundError("Agent 不存在")
        normalized_name = command.name.strip()
        normalized_instructions = command.instructions.strip()
        if not normalized_name or not normalized_instructions:
            raise ValueError("agent_name_and_instructions_required")
        if (
            command.skill_id
            and self._repository.get_skill(command.organization_id, command.skill_id) is None
        ):
            raise SkillNotFoundError("Skill 不存在")
        return self._repository.update_agent(
            AgentDefinition(
                id=existing_agent.id,
                organization_id=existing_agent.organization_id,
                created_by=existing_agent.created_by,
                name=normalized_name,
                description=command.description.strip(),
                instructions=normalized_instructions,
                model_name=command.model_name.strip() if command.model_name else None,
                skill_id=command.skill_id,
                is_enabled=command.is_enabled,
                is_published=existing_agent.is_published,
                created_at=existing_agent.created_at,
                updated_at=datetime.now(UTC),
            )
        )

    def set_published(
        self, organization_id: str, agent_id: str, is_published: bool
    ) -> AgentDefinition:
        """发布或撤下当前组织 Agent。

        Args:
            organization_id (str): 服务端会话解析的组织 ID。
            agent_id (str): 稳定 Agent ID。
            is_published (bool): 目标发布状态。

        Returns:
            AgentDefinition: 更新后的 Agent。

        Raises:
            AgentNotFoundError: Agent 不属于当前组织时抛出。
        """
        existing_agent = self._repository.get_agent(organization_id, agent_id)
        if existing_agent is None:
            raise AgentNotFoundError("Agent 不存在")
        return self._repository.update_agent(
            AgentDefinition(
                **{
                    **asdict(existing_agent),
                    "is_published": is_published,
                    "updated_at": datetime.now(UTC),
                }
            )
        )

    def list_agents(
        self, organization_id: str, *, published_only: bool
    ) -> Sequence[AgentCatalogEntry]:
        """列出当前组织 Agent 并标注不可运行原因。

        Args:
            organization_id (str): 服务端会话解析的组织 ID。
            published_only (bool): 是否只列出已发布 Agent。

        Returns:
            Sequence[AgentCatalogEntry]: Agent 目录与可用状态。
        """
        agent_definitions = self._repository.list_agents(
            organization_id, published_only=published_only
        )
        return [
            AgentCatalogEntry(
                agent=agent,
                is_runnable=not reason,
                unavailable_reason=reason,
            )
            for agent in agent_definitions
            for reason in [self._unavailable_reason(agent)]
        ]

    def get_agent(self, organization_id: str, agent_id: str) -> AgentDefinition:
        """读取当前组织内 Agent。

        Args:
            organization_id (str): 服务端会话解析的组织 ID。
            agent_id (str): 稳定 Agent ID。

        Returns:
            AgentDefinition: 组织内 Agent。

        Raises:
            AgentNotFoundError: Agent 不属于当前组织时抛出。
        """
        agent_definition = self._repository.get_agent(organization_id, agent_id)
        if agent_definition is None:
            raise AgentNotFoundError("Agent 不存在")
        return agent_definition

    def create_a2a_credential(
        self, organization_id: str, actor_id: str, agent_id: str, name: str
    ) -> tuple[A2ACredential, str]:
        """创建只返回一次明文的入站 A2A 服务凭据。

        Args:
            organization_id (str): 会话组织范围。
            actor_id (str): 创建凭据的组织管理员 ID。
            agent_id (str): 被授权的 Agent ID。
            name (str): 凭据用途名称。

        Returns:
            tuple[A2ACredential, str]: 凭据元数据与一次性明文 token。

        Raises:
            AgentNotFoundError: Agent 不属于当前组织时抛出。
            ValueError: 名称为空时抛出。
        """
        if self._repository.get_agent(organization_id, agent_id) is None:
            raise AgentNotFoundError("Agent 不存在")
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("credential_name_required")
        token = f"a2a_{uuid.uuid4().hex}{uuid.uuid4().hex}"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        credential = A2ACredential(
            id=uuid.uuid4().hex,
            organization_id=organization_id,
            agent_id=agent_id,
            name=normalized_name,
            is_active=True,
            created_at=datetime.now(UTC),
            revoked_at=None,
        )
        stored_credential = self._repository.create_a2a_credential(credential, token_hash)
        return stored_credential, token

    def resolve_a2a_credential(self, token: str) -> A2ACredential | None:
        """按明文 bearer token 的摘要解析有效凭据。

        Args:
            token (str): A2A Authorization bearer token。

        Returns:
            A2ACredential | None: 有效凭据元数据；无效凭据返回空值。
        """
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return self._repository.resolve_a2a_credential(token_hash)

    def list_a2a_credentials(self, organization_id: str, agent_id: str) -> Sequence[A2ACredential]:
        """列出指定本组织 Agent 的入站凭据元数据。"""
        self.get_agent(organization_id, agent_id)
        return self._repository.list_a2a_credentials(organization_id, agent_id)

    def revoke_a2a_credential(self, organization_id: str, credential_id: str) -> None:
        """撤销本组织服务凭据；不存在或跨组织时返回相同结果。"""
        if not self._repository.revoke_a2a_credential(organization_id, credential_id):
            raise LookupError("credential_not_found")

    def register_a2a_peer(
        self,
        *,
        organization_id: str,
        actor_id: str,
        name: str,
        card_url: str,
        endpoint_url: str,
        credential_env_alias: str | None,
    ) -> A2APeer:
        """登记待平台审批的组织 A2A 对端。

        Args:
            organization_id (str): 会话组织范围。
            actor_id (str): 登记管理员 ID。
            name (str): 目录名称。
            card_url (str): 经登记的 Agent Card URL。
            endpoint_url (str): A2A 1.0 REST 消息端点。
            credential_env_alias (str | None): 部署方注入密钥的环境变量名。

        Returns:
            A2APeer: 不含凭据的对端目录记录。
        """
        now = datetime.now(UTC)
        peer = A2APeer(
            id=uuid.uuid4().hex,
            organization_id=organization_id,
            created_by=actor_id,
            name=name.strip(),
            card_url=card_url.strip(),
            endpoint_url=endpoint_url.strip(),
            is_approved=False,
            is_enabled=True,
            approved_by=None,
            created_at=now,
            updated_at=now,
        )
        if not peer.name or not peer.card_url or not peer.endpoint_url:
            raise ValueError("peer_name_and_urls_required")
        credential_value = None
        if credential_env_alias:
            if self._secret_resolver is None:
                raise ValueError("a2a_secret_resolver_unavailable")
            credential_value = self._secret_resolver.get_secret(credential_env_alias)
            if credential_value is None:
                raise ValueError("a2a_peer_credential_not_configured")
        return self._repository.create_a2a_peer(peer, credential_value)

    def list_a2a_peers(self, organization_id: str) -> Sequence[A2APeer]:
        """列出当前组织登记的 A2A 对端，不返回凭据。"""
        return self._repository.list_a2a_peers(organization_id)

    def approve_a2a_peer(self, peer_id: str, platform_admin_id: str) -> A2APeer:
        """经平台管理员审批对端目录记录。"""
        peer = self._repository.approve_a2a_peer(peer_id, platform_admin_id)
        if peer is None:
            raise LookupError("peer_not_found")
        return peer

    def list_pending_a2a_peers(self) -> Sequence[A2APeer]:
        """列出不含密钥的待审批对端控制面元数据。"""
        return self._repository.list_pending_a2a_peers()

    def list_approved_a2a_peers(self, organization_id: str) -> Sequence[A2APeer]:
        """列出当前组织已批准且启用的出站 Agent。"""
        return tuple(
            peer
            for peer in self._repository.list_a2a_peers(organization_id)
            if peer.is_enabled and peer.is_approved
        )

    def rotate_a2a_peer_credential(
        self, *, organization_id: str, peer_id: str, credential_env_alias: str
    ) -> None:
        """从服务端密钥引用读取凭据并加密轮换当前组织对端密钥。"""
        if self._secret_resolver is None:
            raise ValueError("a2a_secret_resolver_unavailable")
        credential_value = self._secret_resolver.get_secret(credential_env_alias)
        if credential_value is None:
            raise ValueError("a2a_peer_credential_not_configured")
        if not self._repository.rotate_a2a_peer_credential(
            organization_id, peer_id, credential_value
        ):
            raise LookupError("peer_not_found")

    def _unavailable_reason(self, agent: AgentDefinition) -> str | None:
        """返回成员目录所用的稳定不可用标识。"""
        if not agent.is_enabled:
            return "agent_disabled"
        if not self._executor.is_available:
            return self._executor.unavailable_reason or "model_unavailable"
        if not (agent.model_name or self._executor.default_model_name):
            return "model_not_configured"
        return None
