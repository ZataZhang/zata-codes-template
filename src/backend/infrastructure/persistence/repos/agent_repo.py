"""Agent、Skill 与 A2A 目录的 SQLAlchemy 仓库实现。"""

from __future__ import annotations

import base64
import hashlib
import os
import uuid
from datetime import UTC, datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.agent_types import (
    A2ACredential,
    A2APeer,
    A2APeerTarget,
    AgentDefinition,
    SkillDefinition,
    SkillRevision,
)
from backend.infrastructure.config.settings import config
from backend.infrastructure.persistence.models.agent import (
    A2ACredentialModel,
    A2APeerModel,
    AgentModel,
    SkillModel,
    SkillVersionModel,
)

_A2A_CREDENTIAL_ASSOCIATED_DATA = b"zata-a2a-peer-credential-v1"


def _to_agent(agent_model: AgentModel) -> AgentDefinition:
    """把 Agent ORM 记录转为领域对象。"""
    return AgentDefinition(
        id=agent_model.id,
        organization_id=agent_model.organization_id,
        created_by=agent_model.created_by,
        name=agent_model.name,
        description=agent_model.description,
        instructions=agent_model.instructions,
        model_name=agent_model.model_name,
        skill_id=agent_model.skill_id,
        is_enabled=agent_model.is_enabled,
        is_published=agent_model.is_published,
        created_at=agent_model.created_at,
        updated_at=agent_model.updated_at,
    )


def _to_skill(skill_model: SkillModel) -> SkillDefinition:
    """把 Skill ORM 记录转为领域对象。"""
    return SkillDefinition(
        id=skill_model.id,
        organization_id=skill_model.organization_id,
        created_by=skill_model.created_by,
        name=skill_model.name,
        description=skill_model.description,
        current_version=skill_model.current_version,
        created_at=skill_model.created_at,
        updated_at=skill_model.updated_at,
    )


def _to_revision(revision_model: SkillVersionModel) -> SkillRevision:
    """把 Skill 版本 ORM 记录转为领域对象。"""
    return SkillRevision(
        id=revision_model.id,
        skill_id=revision_model.skill_id,
        organization_id=revision_model.organization_id,
        version=revision_model.version,
        body=revision_model.body,
        checksum=revision_model.checksum,
        created_by=revision_model.created_by,
        created_at=revision_model.created_at,
    )


def _to_credential(credential_model: A2ACredentialModel) -> A2ACredential:
    """把服务凭据记录转换为不含密钥的领域元数据。"""
    return A2ACredential(
        id=credential_model.id,
        organization_id=credential_model.organization_id,
        agent_id=credential_model.agent_id,
        name=credential_model.name,
        is_active=credential_model.is_active,
        created_at=credential_model.created_at,
        revoked_at=credential_model.revoked_at,
    )


def _to_peer(peer_model: A2APeerModel) -> A2APeer:
    """把对端 ORM 记录转为不含凭据的目录对象。"""
    return A2APeer(
        id=peer_model.id,
        organization_id=peer_model.organization_id,
        created_by=peer_model.created_by,
        name=peer_model.name,
        card_url=peer_model.card_url,
        endpoint_url=peer_model.endpoint_url,
        is_approved=peer_model.is_approved,
        is_enabled=peer_model.is_enabled,
        approved_by=peer_model.approved_by,
        created_at=peer_model.created_at,
        updated_at=peer_model.updated_at,
    )


class SqlAlchemyAgentRepository(AgentRepository):
    """每个 Agent / Skill / A2A 目录操作使用独立短事务。"""

    def __init__(self, *, session_factory: sessionmaker[Session]) -> None:
        """初始化 Agent 仓库。

        Args:
            session_factory (sessionmaker[Session]): 数据库会话工厂。
        """
        self._session_factory = session_factory

    def create_agent(self, agent: AgentDefinition) -> AgentDefinition:
        """创建组织内 Agent。"""
        agent_model = AgentModel(
            id=agent.id,
            organization_id=agent.organization_id,
            created_by=agent.created_by,
            name=agent.name,
            description=agent.description,
            instructions=agent.instructions,
            model_name=agent.model_name,
            skill_id=agent.skill_id,
            is_enabled=agent.is_enabled,
            is_published=agent.is_published,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )
        try:
            with self._session_factory.begin() as database_session:
                database_session.add(agent_model)
        except IntegrityError as integrity_error:
            raise ValueError("agent_name_conflict_or_invalid_skill") from integrity_error
        return agent

    def get_agent(self, organization_id: str, agent_id: str) -> AgentDefinition | None:
        """按组织范围读取 Agent。"""
        with self._session_factory() as database_session:
            agent_model = database_session.scalar(
                select(AgentModel).where(
                    AgentModel.organization_id == organization_id,
                    AgentModel.id == agent_id,
                )
            )
            return _to_agent(agent_model) if agent_model else None

    def list_agents(self, organization_id: str, *, published_only: bool) -> list[AgentDefinition]:
        """仅列出指定组织 Agent。"""
        query = select(AgentModel).where(AgentModel.organization_id == organization_id)
        if published_only:
            query = query.where(AgentModel.is_published.is_(True))
        with self._session_factory() as database_session:
            agent_models = database_session.scalars(query.order_by(AgentModel.name.asc())).all()
            return [_to_agent(agent_model) for agent_model in agent_models]

    def update_agent(self, agent: AgentDefinition) -> AgentDefinition:
        """更新本组织 Agent 配置。"""
        try:
            with self._session_factory.begin() as database_session:
                agent_model = database_session.scalar(
                    select(AgentModel).where(
                        AgentModel.organization_id == agent.organization_id,
                        AgentModel.id == agent.id,
                    )
                )
                if agent_model is None:
                    raise LookupError("agent_not_found")
                agent_model.name = agent.name
                agent_model.description = agent.description
                agent_model.instructions = agent.instructions
                agent_model.model_name = agent.model_name
                agent_model.skill_id = agent.skill_id
                agent_model.is_enabled = agent.is_enabled
                agent_model.is_published = agent.is_published
                agent_model.updated_at = agent.updated_at
        except IntegrityError as integrity_error:
            raise ValueError("agent_name_conflict_or_invalid_skill") from integrity_error
        return self.get_agent(agent.organization_id, agent.id) or agent

    def create_skill(
        self, skill: SkillDefinition, initial_body: str
    ) -> tuple[SkillDefinition, SkillRevision]:
        """在同一事务创建 Skill 与首个不可变版本。"""
        now = datetime.now(UTC)
        checksum = hashlib.sha256(initial_body.encode("utf-8")).hexdigest()
        skill_model = SkillModel(
            id=skill.id,
            organization_id=skill.organization_id,
            created_by=skill.created_by,
            name=skill.name,
            description=skill.description,
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        revision_model = SkillVersionModel(
            id=uuid.uuid4().hex,
            skill_id=skill.id,
            organization_id=skill.organization_id,
            version=1,
            body=initial_body,
            checksum=checksum,
            created_by=skill.created_by,
            created_at=now,
        )
        try:
            with self._session_factory.begin() as database_session:
                database_session.add(skill_model)
                database_session.add(revision_model)
                database_session.flush()
                committed_revision = SkillRevision(
                    id=revision_model.id,
                    skill_id=revision_model.skill_id,
                    organization_id=revision_model.organization_id,
                    version=revision_model.version,
                    body=revision_model.body,
                    checksum=revision_model.checksum,
                    created_by=revision_model.created_by,
                    created_at=revision_model.created_at,
                )
        except IntegrityError as integrity_error:
            raise ValueError("skill_name_conflict") from integrity_error
        committed_skill = self.get_skill(skill.organization_id, skill.id) or skill
        return committed_skill, committed_revision

    def get_skill(self, organization_id: str, skill_id: str) -> SkillDefinition | None:
        """按组织范围读取 Skill。"""
        with self._session_factory() as database_session:
            skill_model = database_session.scalar(
                select(SkillModel).where(
                    SkillModel.organization_id == organization_id,
                    SkillModel.id == skill_id,
                )
            )
            return _to_skill(skill_model) if skill_model else None

    def list_skills(self, organization_id: str) -> list[SkillDefinition]:
        """按名称列出指定组织 Skill。"""
        with self._session_factory() as database_session:
            skill_models = database_session.scalars(
                select(SkillModel)
                .where(SkillModel.organization_id == organization_id)
                .order_by(SkillModel.name.asc())
            ).all()
            return [_to_skill(skill_model) for skill_model in skill_models]

    def append_skill_revision(
        self, organization_id: str, skill_id: str, created_by: str, body: str
    ) -> SkillRevision:
        """锁定 Skill 主记录并追加下一个版本。"""
        revision_now = datetime.now(UTC)
        revision_checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
        committed_revision: SkillRevision | None = None
        try:
            with self._session_factory.begin() as database_session:
                skill_model = database_session.scalar(
                    select(SkillModel)
                    .where(
                        SkillModel.organization_id == organization_id,
                        SkillModel.id == skill_id,
                    )
                    .with_for_update()
                )
                if skill_model is None:
                    raise LookupError("skill_not_found")
                next_version = skill_model.current_version + 1
                revision_model = SkillVersionModel(
                    id=uuid.uuid4().hex,
                    skill_id=skill_model.id,
                    organization_id=skill_model.organization_id,
                    version=next_version,
                    body=body,
                    checksum=revision_checksum,
                    created_by=created_by,
                    created_at=revision_now,
                )
                skill_model.current_version = next_version
                skill_model.updated_at = revision_now
                database_session.add(revision_model)
                database_session.flush()
                committed_revision = SkillRevision(
                    id=revision_model.id,
                    skill_id=revision_model.skill_id,
                    organization_id=revision_model.organization_id,
                    version=revision_model.version,
                    body=revision_model.body,
                    checksum=revision_model.checksum,
                    created_by=revision_model.created_by,
                    created_at=revision_model.created_at,
                )
        except IntegrityError as integrity_error:
            raise ValueError("skill_version_conflict") from integrity_error
        if committed_revision is None:
            raise RuntimeError("skill_revision_not_created")
        return committed_revision

    def list_skill_revisions(self, organization_id: str, skill_id: str) -> list[SkillRevision]:
        """按版本号升序列出同组织 Skill 历史。"""
        with self._session_factory() as database_session:
            revision_models = database_session.scalars(
                select(SkillVersionModel)
                .where(
                    SkillVersionModel.organization_id == organization_id,
                    SkillVersionModel.skill_id == skill_id,
                )
                .order_by(SkillVersionModel.version.asc())
            ).all()
            return [_to_revision(revision_model) for revision_model in revision_models]

    def get_skill_revision(
        self, organization_id: str, skill_id: str, version: int
    ) -> SkillRevision | None:
        """按组织、Skill 和版本号精确读取正文。"""
        with self._session_factory() as database_session:
            revision_model = database_session.scalar(
                select(SkillVersionModel).where(
                    SkillVersionModel.organization_id == organization_id,
                    SkillVersionModel.skill_id == skill_id,
                    SkillVersionModel.version == version,
                )
            )
            return _to_revision(revision_model) if revision_model else None

    def resolve_skill(
        self, organization_id: str, skill_id: str
    ) -> tuple[SkillDefinition, SkillRevision] | None:
        """读取当前版本的 Skill 快照。"""
        skill_definition = self.get_skill(organization_id, skill_id)
        if skill_definition is None:
            return None
        current_revision = self.get_skill_revision(
            organization_id, skill_id, skill_definition.current_version
        )
        if current_revision is None:
            return None
        return skill_definition, current_revision

    def create_a2a_credential(self, credential: A2ACredential, token_hash: str) -> A2ACredential:
        """持久化入站凭据摘要，不保存 bearer token 明文。"""
        credential_model = A2ACredentialModel(
            id=credential.id,
            organization_id=credential.organization_id,
            agent_id=credential.agent_id,
            name=credential.name,
            token_hash=token_hash,
            is_active=credential.is_active,
            created_at=credential.created_at,
            revoked_at=credential.revoked_at,
        )
        with self._session_factory.begin() as database_session:
            database_session.add(credential_model)
        return credential

    def resolve_a2a_credential(self, token_hash: str) -> A2ACredential | None:
        """按摘要解析未撤销的 A2A 入站凭据。"""
        with self._session_factory() as database_session:
            credential_model = database_session.scalar(
                select(A2ACredentialModel).where(
                    A2ACredentialModel.token_hash == token_hash,
                    A2ACredentialModel.is_active.is_(True),
                    A2ACredentialModel.revoked_at.is_(None),
                )
            )
            return _to_credential(credential_model) if credential_model else None

    def list_a2a_credentials(self, organization_id: str, agent_id: str) -> list[A2ACredential]:
        """列出组织 Agent 的凭据元数据。"""
        with self._session_factory() as database_session:
            credential_models = database_session.scalars(
                select(A2ACredentialModel)
                .where(
                    A2ACredentialModel.organization_id == organization_id,
                    A2ACredentialModel.agent_id == agent_id,
                )
                .order_by(A2ACredentialModel.created_at.desc())
            ).all()
            return [_to_credential(credential_model) for credential_model in credential_models]

    def revoke_a2a_credential(self, organization_id: str, credential_id: str) -> bool:
        """撤销本组织入站 A2A 凭据。"""
        with self._session_factory.begin() as database_session:
            credential_model = database_session.scalar(
                select(A2ACredentialModel).where(
                    A2ACredentialModel.organization_id == organization_id,
                    A2ACredentialModel.id == credential_id,
                )
            )
            if credential_model is None:
                return False
            credential_model.is_active = False
            credential_model.revoked_at = datetime.now(UTC)
            return True

    def create_a2a_peer(self, peer: A2APeer, bearer_token: str | None) -> A2APeer:
        """加密存储组织外部 A2A 凭据并创建待审批记录。"""
        encrypted_credential = self._encrypt_credential(bearer_token) if bearer_token else None
        peer_model = A2APeerModel(
            id=peer.id,
            organization_id=peer.organization_id,
            created_by=peer.created_by,
            name=peer.name,
            card_url=peer.card_url,
            endpoint_url=peer.endpoint_url,
            credential_ciphertext=encrypted_credential,
            is_approved=peer.is_approved,
            is_enabled=peer.is_enabled,
            approved_by=peer.approved_by,
            created_at=peer.created_at,
            updated_at=peer.updated_at,
        )
        try:
            with self._session_factory.begin() as database_session:
                database_session.add(peer_model)
        except IntegrityError as integrity_error:
            raise ValueError("a2a_peer_name_conflict") from integrity_error
        return peer

    def list_a2a_peers(self, organization_id: str) -> list[A2APeer]:
        """按组织列出登记对端，不读取凭据密文。"""
        with self._session_factory() as database_session:
            peer_models = database_session.scalars(
                select(A2APeerModel)
                .where(A2APeerModel.organization_id == organization_id)
                .order_by(A2APeerModel.name.asc())
            ).all()
            return [_to_peer(peer_model) for peer_model in peer_models]

    def approve_a2a_peer(self, peer_id: str, platform_admin_id: str) -> A2APeer | None:
        """记录平台管理员对特定对端的显式审批。"""
        organization_id: str | None = None
        with self._session_factory.begin() as database_session:
            peer_model = database_session.get(A2APeerModel, peer_id)
            if peer_model is None:
                return None
            organization_id = peer_model.organization_id
            peer_model.is_approved = True
            peer_model.approved_by = platform_admin_id
            peer_model.updated_at = datetime.now(UTC)
        if organization_id is None:
            return None
        return next(
            (peer for peer in self.list_a2a_peers(organization_id) if peer.id == peer_id),
            None,
        )

    def list_pending_a2a_peers(self) -> list[A2APeer]:
        """列出待平台审批的对端，不读取密文凭据。"""
        with self._session_factory() as database_session:
            peer_models = database_session.scalars(
                select(A2APeerModel)
                .where(A2APeerModel.is_approved.is_(False))
                .order_by(A2APeerModel.created_at.asc())
            ).all()
            return [_to_peer(peer_model) for peer_model in peer_models]

    def get_a2a_peer_target(self, organization_id: str, peer_id: str) -> A2APeerTarget | None:
        """返回已批准组织对端及只在本次调用内解密的 bearer token。"""
        with self._session_factory() as database_session:
            peer_model = database_session.scalar(
                select(A2APeerModel).where(
                    A2APeerModel.organization_id == organization_id,
                    A2APeerModel.id == peer_id,
                    A2APeerModel.is_approved.is_(True),
                    A2APeerModel.is_enabled.is_(True),
                )
            )
            if peer_model is None:
                return None
            ciphertext = peer_model.credential_ciphertext
            return A2APeerTarget(
                peer=_to_peer(peer_model),
                bearer_token=self._decrypt_credential(ciphertext) if ciphertext else None,
            )

    def rotate_a2a_peer_credential(
        self, organization_id: str, peer_id: str, bearer_token: str
    ) -> bool:
        """加密替换当前组织对端的出站凭据。"""
        with self._session_factory.begin() as database_session:
            peer_model = database_session.scalar(
                select(A2APeerModel).where(
                    A2APeerModel.organization_id == organization_id,
                    A2APeerModel.id == peer_id,
                )
            )
            if peer_model is None:
                return False
            peer_model.credential_ciphertext = self._encrypt_credential(bearer_token)
            peer_model.updated_at = datetime.now(UTC)
            return True

    @staticmethod
    def _credential_encryption_key() -> bytes:
        """按 config.toml 指定的密钥别名读取 AES-GCM 密钥材料。"""
        key_env_name = config.a2a.credential_encryption_key_env
        configured_secret = os.getenv(key_env_name, "").strip()
        if not configured_secret:
            raise RuntimeError("a2a_credential_encryption_key_required")
        return hashlib.sha256(configured_secret.encode("utf-8")).digest()

    @classmethod
    def _encrypt_credential(cls, bearer_token: str) -> str:
        """使用 AES-GCM 加密出站 bearer token。"""
        nonce = os.urandom(12)
        ciphertext = AESGCM(cls._credential_encryption_key()).encrypt(
            nonce,
            bearer_token.encode("utf-8"),
            _A2A_CREDENTIAL_ASSOCIATED_DATA,
        )
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    @classmethod
    def _decrypt_credential(cls, ciphertext_text: str) -> str:
        """解密一次受控对端调用的 bearer token。"""
        encrypted_bytes = base64.urlsafe_b64decode(ciphertext_text.encode("ascii"))
        nonce, ciphertext = encrypted_bytes[:12], encrypted_bytes[12:]
        cleartext = AESGCM(cls._credential_encryption_key()).decrypt(
            nonce,
            ciphertext,
            _A2A_CREDENTIAL_ASSOCIATED_DATA,
        )
        return cleartext.decode("utf-8")


__all__ = ["SqlAlchemyAgentRepository"]
