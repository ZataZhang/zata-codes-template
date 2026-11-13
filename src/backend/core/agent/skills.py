"""组织范围 Skill 声明与不可变版本用例。"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Sequence

from backend.core.agent.catalog import SkillNotFoundError
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.agent_types import (
    SkillDefinition,
    SkillRevision,
)


class SkillUseCase:
    """Skill 创建、线性版本和恢复用例。"""

    def __init__(self, repository: AgentRepository) -> None:
        """初始化 Skill 用例。

        Args:
            repository (AgentRepository): Skill 持久化端口。
        """
        self._repository = repository

    def create_skill(
        self, *, organization_id: str, actor_id: str, name: str, description: str, body: str
    ) -> tuple[SkillDefinition, SkillRevision]:
        """创建 Skill 并追加初始版本。

        Args:
            organization_id (str): 会话组织范围。
            actor_id (str): 创建管理员 ID。
            name (str): Skill 名称。
            description (str): Skill 说明。
            body (str): 声明式 Skill 正文。

        Returns:
            tuple[SkillDefinition, SkillRevision]: 新 Skill 与版本 1。
        """
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("skill_name_required")
        initial_body = validate_skill_body(body)
        now = datetime.now(UTC)
        skill = SkillDefinition(
            id=uuid.uuid4().hex,
            organization_id=organization_id,
            created_by=actor_id,
            name=normalized_name,
            description=description.strip(),
            current_version=0,
            created_at=now,
            updated_at=now,
        )
        return self._repository.create_skill(skill, initial_body)

    def list_skills(self, organization_id: str) -> Sequence[SkillDefinition]:
        """列出当前组织 Skill。"""
        return self._repository.list_skills(organization_id)

    def list_revisions(self, organization_id: str, skill_id: str) -> Sequence[SkillRevision]:
        """按版本号顺序列出当前组织 Skill 历史。"""
        self._require_skill(organization_id, skill_id)
        return self._repository.list_skill_revisions(organization_id, skill_id)

    def add_revision(
        self, *, organization_id: str, skill_id: str, actor_id: str, body: str
    ) -> SkillRevision:
        """追加一个新的不可变 Skill 版本。"""
        self._require_skill(organization_id, skill_id)
        return self._repository.append_skill_revision(
            organization_id, skill_id, actor_id, validate_skill_body(body)
        )

    def restore_revision(
        self, *, organization_id: str, skill_id: str, version: int, actor_id: str
    ) -> SkillRevision:
        """把旧版本正文作为一个新版本追加，不改写历史记录。"""
        selected_revision = self._repository.get_skill_revision(organization_id, skill_id, version)
        if selected_revision is None:
            raise SkillNotFoundError("Skill version 不存在")
        return self._repository.append_skill_revision(
            organization_id, skill_id, actor_id, selected_revision.body
        )

    def compare_revisions(
        self, *, organization_id: str, skill_id: str, from_version: int, to_version: int
    ) -> tuple[SkillRevision, SkillRevision]:
        """读取同一组织 Skill 的两份不可变版本用于差异展示。"""
        first_revision = self._repository.get_skill_revision(
            organization_id, skill_id, from_version
        )
        second_revision = self._repository.get_skill_revision(organization_id, skill_id, to_version)
        if first_revision is None or second_revision is None:
            raise SkillNotFoundError("Skill version 不存在")
        return first_revision, second_revision

    def _require_skill(self, organization_id: str, skill_id: str) -> SkillDefinition:
        """验证 Skill 在请求组织内可见。"""
        skill_definition = self._repository.get_skill(organization_id, skill_id)
        if skill_definition is None:
            raise SkillNotFoundError("Skill 不存在")
        return skill_definition


_EXECUTABLE_SKILL_LANGUAGE_PATTERN = re.compile(
    r"(?im)^```(?:python|py|bash|sh|shell|javascript|js|typescript|ts|powershell|ps1)\b"
)

_SHEBANG_PATTERN = re.compile(r"(?m)^\s*#!")

_RUNNABLE_COMMAND_PATTERN = re.compile(r"(?im)^\s*(?:os\.system\(|subprocess\.|eval\(|exec\()")


def validate_skill_body(body: str) -> str:
    """仅接受声明式 Skill 正文，不接受可执行脚本片段。

    Args:
        body (str): 用户提交的 Skill 正文。

    Returns:
        str: 去除首尾空白的正文。

    Raises:
        ValueError: 正文为空、过长或包含明显可执行内容时抛出。
    """
    normalized_body = body.strip()
    if not normalized_body:
        raise ValueError("skill_body_required")
    if len(normalized_body) > 100_000:
        raise ValueError("skill_body_too_large")
    if any(
        pattern.search(normalized_body)
        for pattern in (
            _EXECUTABLE_SKILL_LANGUAGE_PATTERN,
            _SHEBANG_PATTERN,
            _RUNNABLE_COMMAND_PATTERN,
        )
    ):
        raise ValueError("skill_executable_content_not_allowed")
    return normalized_body
