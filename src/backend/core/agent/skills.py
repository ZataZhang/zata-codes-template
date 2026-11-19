"""组织范围 Skill 声明与不可变版本用例。"""

from __future__ import annotations

import hashlib
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence

from backend.core.agent.catalog import SkillNotFoundError
from backend.core.agent.helpers import _checksum
from backend.core.shared.interfaces.agent_repository import AgentRepository
from backend.core.shared.interfaces.agent_types import (
    SkillDefinition,
    SkillRevision,
    SkillRevisionDraft,
    SkillWriteIdempotency,
)


@dataclass(frozen=True)
class CreateSkillCommand:
    """创建 Skill 与首个版本的命令。"""

    organization_id: str
    actor_id: str
    name: str
    description: str
    body: str
    idempotency_key: str = ""


@dataclass(frozen=True)
class AppendSkillRevisionCommand:
    """追加 Skill 版本的命令。"""

    organization_id: str
    skill_id: str
    actor_id: str
    body: str
    idempotency_key: str = ""


@dataclass(frozen=True)
class RestoreSkillRevisionCommand:
    """以历史正文追加恢复版本的命令。"""

    organization_id: str
    skill_id: str
    actor_id: str
    version: int
    idempotency_key: str = ""


class SkillUseCase:
    """Skill 创建、线性版本和恢复用例。"""

    def __init__(self, repository: AgentRepository) -> None:
        """初始化 Skill 用例。

        Args:
            repository (AgentRepository): Skill 持久化端口。
        """
        self._repository = repository

    def create_skill(self, command: CreateSkillCommand) -> tuple[SkillDefinition, SkillRevision]:
        """创建 Skill 并追加初始版本；相同重试键返回首次写入结果。"""
        normalized_name = command.name.strip()
        if not normalized_name:
            raise ValueError("skill_name_required")
        initial_body = validate_skill_body(command.body)
        normalized_description = command.description.strip()
        now = datetime.now(UTC)
        skill = SkillDefinition(
            id=uuid.uuid4().hex,
            organization_id=command.organization_id,
            created_by=command.actor_id,
            name=normalized_name,
            description=normalized_description,
            current_version=0,
            created_at=now,
            updated_at=now,
        )
        idempotency = _skill_write_idempotency(
            scope=f"{command.organization_id}:{command.actor_id}",
            idempotency_key=command.idempotency_key,
            request_document={
                "name": normalized_name,
                "description": normalized_description,
                "body": initial_body,
            },
        )
        return self._repository.create_skill(skill, initial_body, idempotency=idempotency)

    def list_skills(self, organization_id: str) -> Sequence[SkillDefinition]:
        """列出当前组织 Skill。"""
        return self._repository.list_skills(organization_id)

    def list_revisions(self, organization_id: str, skill_id: str) -> Sequence[SkillRevision]:
        """按版本号顺序列出当前组织 Skill 历史。"""
        self._require_skill(organization_id, skill_id)
        return self._repository.list_skill_revisions(organization_id, skill_id)

    def add_revision(self, command: AppendSkillRevisionCommand) -> SkillRevision:
        """追加一个新的不可变 Skill 版本；重试不会生成重复版本。"""
        self._require_skill(command.organization_id, command.skill_id)
        normalized_body = validate_skill_body(command.body)
        return self._repository.append_skill_revision(
            SkillRevisionDraft(
                organization_id=command.organization_id,
                skill_id=command.skill_id,
                created_by=command.actor_id,
                body=normalized_body,
                idempotency=_skill_write_idempotency(
                    scope=f"{command.organization_id}:{command.skill_id}:{command.actor_id}",
                    idempotency_key=command.idempotency_key,
                    request_document={"body": normalized_body},
                ),
            )
        )

    def restore_revision(self, command: RestoreSkillRevisionCommand) -> SkillRevision:
        """把旧版本正文作为一个新版本追加，不改写历史记录。"""
        selected_revision = self._repository.get_skill_revision(
            command.organization_id, command.skill_id, command.version
        )
        if selected_revision is None:
            raise SkillNotFoundError("Skill version 不存在")
        restored_body = validate_skill_body(selected_revision.body)
        return self._repository.append_skill_revision(
            SkillRevisionDraft(
                organization_id=command.organization_id,
                skill_id=command.skill_id,
                created_by=command.actor_id,
                body=restored_body,
                idempotency=_skill_write_idempotency(
                    scope=f"{command.organization_id}:{command.skill_id}:{command.actor_id}",
                    idempotency_key=command.idempotency_key,
                    request_document={"body": restored_body},
                ),
            )
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


def _skill_write_idempotency(
    *, scope: str, idempotency_key: str, request_document: dict[str, str]
) -> SkillWriteIdempotency | None:
    """把可选调用方重试键转换为组织内唯一摘要和请求摘要。"""
    normalized_key = idempotency_key.strip()
    if not normalized_key:
        return None
    if len(normalized_key) > 128:
        raise ValueError("idempotency_key_too_large")
    return SkillWriteIdempotency(
        key_hash=hashlib.sha256(f"{scope}:{normalized_key}".encode("utf-8")).hexdigest(),
        request_checksum=_checksum(request_document),
    )


_CODE_FENCE_LINE_PATTERN = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_SAFE_REFERENCE_FENCE_LANGUAGES = frozenset(
    {
        "text",
        "plaintext",
        "txt",
        "markdown",
        "md",
        "json",
        "jsonc",
        "yaml",
        "yml",
        "toml",
        "ini",
        "csv",
        "diff",
        "mermaid",
    }
)

_SHEBANG_PATTERN = re.compile(r"(?m)^\s*#!")

_EXECUTABLE_CONTENT_LINE_PATTERNS = (
    re.compile(r"(?m)^\s*(?:from\s+[\w.]+\s+import\b|import\s+[\w.]+(?:\s+as\s+\w+)?\s*$)"),
    re.compile(r"(?m)^\s*(?:async\s+)?def\s+[A-Za-z_]\w*\s*\("),
    re.compile(r"(?m)^\s*class\s+[A-Za-z_]\w*(?:\s*\([^)]*\))?\s*:"),
    re.compile(
        r"(?m)^\s*(?:[A-Za-z_]\w*\s*=\s*)?"
        r"(?:print|open|eval|exec|os\.system|subprocess\.\w+)\s*\("
    ),
    re.compile(
        r"(?m)^\s*(?:function\s+[A-Za-z_$][\w$]*\s*\(|"
        r"(?:const|let|var)\s+[\w$]+\s*=|"
        r"console\.(?:log|error|warn)\s*\()"
    ),
    re.compile(
        r"(?m)^\s*(?:\$\s*)?(?:sudo\s+)?"
        r"(?:rm|curl|wget|python(?:3(?:\.\d+)?)?|node|npm|npx|pip(?:3)?|uv|docker|"
        r"chmod|chown|bash|sh|apt(?:-get)?|brew|mkdir|touch|cp|mv|tar|echo|printf)\b"
        r"(?:\s|$)"
    ),
)


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
    open_code_fence: tuple[str, int] | None = None
    for body_line in normalized_body.splitlines():
        fence_match = _CODE_FENCE_LINE_PATTERN.match(body_line)
        if fence_match is None:
            continue
        fence_marker, fence_info = fence_match.groups()
        if open_code_fence is None:
            if fence_marker.startswith("`") and "`" in fence_info:
                raise ValueError("skill_executable_content_not_allowed")
            language = fence_info.strip().split(maxsplit=1)[0].lower() if fence_info.strip() else ""
            if language not in _SAFE_REFERENCE_FENCE_LANGUAGES:
                raise ValueError("skill_executable_content_not_allowed")
            open_code_fence = (fence_marker[0], len(fence_marker))
        elif (
            fence_marker[0] == open_code_fence[0]
            and len(fence_marker) >= open_code_fence[1]
            and not fence_info.strip()
        ):
            open_code_fence = None
    if (
        open_code_fence is not None
        or any(
            unicodedata.category(character) in {"Cc", "Cs"} and character not in "\t\n\r"
            for character in normalized_body
        )
        or any(
            pattern.search(normalized_body)
            for pattern in (_SHEBANG_PATTERN, *_EXECUTABLE_CONTENT_LINE_PATTERNS)
        )
    ):
        raise ValueError("skill_executable_content_not_allowed")
    return normalized_body
