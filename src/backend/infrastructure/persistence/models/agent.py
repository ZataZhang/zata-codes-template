"""在线 Agent、Skill 版本与 A2A 对端的持久化模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.infrastructure.persistence.database import Base

from .base import TimestampMixin


class AgentModel(Base, TimestampMixin):
    """组织内稳定 Agent 身份与发布配置。"""

    __tablename__ = "agent"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_agent_organization_name"),
        {"comment": "组织内 Agent 定义与发布状态。"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="稳定 Agent ID。")
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Agent 创建时所属组织，不随成员调动改变。",
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, comment="创建管理员 ID。")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Agent 名称。")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="Agent 说明。")
    instructions: Mapped[str] = mapped_column(Text, nullable=False, comment="模型系统指令。")
    model_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="覆盖默认模型的可选名称。"
    )
    skill_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("skill.id", ondelete="RESTRICT"),
        nullable=True,
        comment="绑定 Skill ID。",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用。"
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否对本组织成员发布。"
    )


class SkillModel(Base, TimestampMixin):
    """组织内声明式 Skill 的稳定身份。"""

    __tablename__ = "skill"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_skill_organization_name"),
        {"comment": "组织内声明式 Skill 目录。"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="稳定 Skill ID。")
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Skill 创建时所属组织，不随成员调动改变。",
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, comment="创建管理员 ID。")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="Skill 名称。")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="Skill 说明。")
    current_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, comment="当前版本序号。"
    )


class SkillVersionModel(Base):
    """不可变 Skill 正文版本。"""

    __tablename__ = "skill_version"
    __table_args__ = (
        UniqueConstraint("skill_id", "version", name="uq_skill_version_number"),
        {"comment": "只追加的 Skill 正文版本历史。"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="Skill 版本 ID。")
    skill_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("skill.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="所属 Skill ID。",
    )
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="版本创建时所属组织。",
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, comment="从 1 开始的线性版本号。")
    body: Mapped[str] = mapped_column(Text, nullable=False, comment="声明式 Skill 正文。")
    checksum: Mapped[str] = mapped_column(String(64), nullable=False, comment="正文 SHA-256。")
    created_by: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="创建版本的管理员 ID。"
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, comment="版本创建时间（UTC）。")


class A2ACredentialModel(Base):
    """外部 A2A 客户端调用本平台 Agent 的哈希凭据。"""

    __tablename__ = "a2a_credential"
    __table_args__ = ({"comment": "按组织与 Agent 限定的入站 A2A 服务凭据。"},)

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="凭据 ID。")
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="凭据组织范围。",
    )
    agent_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("agent.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="凭据可调用的 Agent。",
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="凭据用途名称。")
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, comment="服务凭据 SHA-256，不保存明文。"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="凭据是否可用。"
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, comment="创建时间（UTC）。")
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True, comment="撤销时间（UTC）。")


class A2APeerModel(Base, TimestampMixin):
    """经平台批准的组织级外部 A2A Agent 目录记录。"""

    __tablename__ = "a2a_peer"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_a2a_peer_organization_name"),
        {"comment": "组织登记并经平台批准的外部 A2A 对端目录。"},
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="对端目录 ID。")
    organization_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("organization.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="登记对端的组织。",
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False, comment="登记管理员 ID。")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="对端名称。")
    card_url: Mapped[str] = mapped_column(Text, nullable=False, comment="经登记的 Agent Card URL。")
    endpoint_url: Mapped[str] = mapped_column(
        Text, nullable=False, comment="经验证的 A2A 1.0 REST 端点。"
    )
    credential_ciphertext: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="经服务端密钥加密的出站凭据。"
    )
    is_approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="是否通过平台网络策略审批。"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, comment="是否启用。"
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="审批平台管理员 ID。"
    )


__all__ = [
    "A2ACredentialModel",
    "A2APeerModel",
    "AgentModel",
    "SkillModel",
    "SkillVersionModel",
]
