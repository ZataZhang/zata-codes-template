"""保存 PR 交付上下文与逐轮事实，不把合并状态当成任务成功标签。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

BEGIN_MARKER = "<!-- just-ai-pr:begin -->"
END_MARKER = "<!-- just-ai-pr:end -->"


@dataclass(frozen=True)
class DeliveryContext:
    """当前对话 Agent 提供的交付输入；不从 diff 反推用户原话。"""

    payload: dict[str, Any]

    @classmethod
    def read(cls, context_path: Path) -> DeliveryContext:
        """读取并校验发布所需的最小上下文。

        Args:
            context_path: 当前 Agent 准备的 UTF-8 JSON 文件。

        Returns:
            已校验的上下文。

        Raises:
            ValueError: 字段缺失、文件路径越界或状态非法。
        """
        payload = json.loads(context_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("Expected a context object with schema_version=1.")
        for field_name in ("title", "task", "summary", "commit_message"):
            if not isinstance(payload.get(field_name), str) or not payload[field_name].strip():
                raise ValueError(f"Missing non-empty string: {field_name}")
        if "\n" in payload["title"] or payload["title"].startswith("-"):
            raise ValueError("title must be one line and must not start with '-'.")
        if payload.get("request_source") not in {"conversation", "retrospective"}:
            raise ValueError("request_source must be conversation or retrospective.")
        messages = payload.get("user_messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError("user_messages must contain relevant verbatim user messages.")
        if any(not isinstance(message, str) or not message.strip() for message in messages):
            raise ValueError("Each user message must be a non-empty string.")
        validation = payload.get("validation")
        if not isinstance(validation, dict) or validation.get("status") not in {
            "passed",
            "pending",
            "failed",
        }:
            raise ValueError("validation.status must be passed, pending or failed.")
        if not isinstance(validation.get("details"), str) or not validation["details"].strip():
            raise ValueError("validation.details must explain evidence and limitations.")
        file_paths = payload.get("files")
        if not isinstance(file_paths, list) or any(
            not isinstance(file_path, str)
            or not file_path
            or PurePosixPath(file_path).is_absolute()
            or any(part in {"..", ".git"} for part in PurePosixPath(file_path).parts)
            or file_path in {".", "./"}
            for file_path in file_paths
        ):
            raise ValueError("files must list literal repository-relative file paths.")
        issue_number = payload.get("issue")
        if issue_number is not None and (type(issue_number) is not int or issue_number < 1):
            raise ValueError("issue must be a positive issue number in the target repository.")
        return cls(payload)

    @property
    def validation_passed(self) -> bool:
        """真实入口验收是否被调用方声明为已完成。"""
        return self.payload["validation"]["status"] == "passed"

    def issue_body(self, base_sha: str) -> str:
        """生成只含任务输入的 Issue 正文，避免泄露实现答案。

        Args:
            base_sha: 本次任务代码起点。

        Returns:
            原话、来源与 AI 整理任务分开的 Markdown。
        """
        quotations = "\n\n".join(
            "\n".join(f"> {line}" for line in message.split("\n"))
            for message in self.payload["user_messages"]
        )
        return (
            f"## User requests (verbatim)\n\n{quotations}\n\n"
            f"Source: `{self.payload['request_source']}`; captured at delivery time.\n\n"
            f"## Task (AI synthesis)\n\n{self.payload['task']}\n\n"
            f"Code starting point: `{base_sha}`\n\n"
            "<!-- just-ai-pr:task-v1 -->\n"
        )


class DeliveryJournal:
    """在 Git 元数据中追加交付事件，状态文件只用于中断恢复。"""

    def __init__(self, common_git_dir: Path, branch_name: str) -> None:
        """按分支隔离可恢复状态。

        Args:
            common_git_dir: Git common dir 的绝对路径。
            branch_name: 当前交付分支。
        """
        branch_key = hashlib.sha256(branch_name.encode("utf-8")).hexdigest()[:24]
        self.directory = common_git_dir / "ai-pr" / branch_key
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_path = self.directory / "state.json"
        self.state = (
            json.loads(self.state_path.read_text(encoding="utf-8"))
            if self.state_path.exists()
            else {}
        )

    def save(self, **updates: Any) -> None:
        """原子替换恢复状态，不覆盖事件历史。

        Args:
            **updates: 已完成操作对应的恢复字段。
        """
        self.state.update(updates)
        pending_path = self.directory / "state.pending"
        pending_path.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        pending_path.replace(self.state_path)

    def append(self, event_name: str, **facts: Any) -> dict[str, Any]:
        """逐行追加事实，并返回可发布的同一记录。

        Args:
            event_name: 事件名称，不代表样本质量。
            **facts: 当前观察到的上下文、SHA 与状态。

        Returns:
            已落盘的事件。
        """
        event = {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "event": event_name,
            **facts,
        }
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as event_file:
            event_file.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


def render_iteration(event: dict[str, Any]) -> str:
    """把逐轮事实原样嵌入评论，squash 后仍可关联失败与修正。

    Args:
        event: 包含本轮上下文与代码 SHA 的记录。

    Returns:
        同时可供人阅读与后续解析的 Markdown。
    """
    context = event["context"]
    encoded_event = json.dumps(event, ensure_ascii=False, indent=2)
    # 超过载荷中最长反引号段，避免原话关闭代码围栏。
    fence = "`" * max(3, max((len(run) for run in re.findall(r"`+", encoded_event)), default=0) + 1)
    return (
        f"## Delivery observation: {context['validation']['status']}\n\n"
        f"Head: `{event['head_sha']}`; task base: `{event['base_sha']}`\n\n"
        f"{context['summary']}\n\n{context['validation']['details']}\n\n"
        f"<details><summary>Original task and iteration record</summary>\n\n"
        f"{fence}json\n{encoded_event}\n{fence}\n\n</details>\n"
    )


def update_pr_body(existing_body: str, managed_body: str) -> str:
    """仅更新命令拥有的正文区，保留审查者与用户已有内容。

    Args:
        existing_body: GitHub 当前 PR 正文。
        managed_body: 本次生成的最新交付概况。

    Returns:
        原内容与最新受管区组合后的正文。
    """
    managed_section = f"{BEGIN_MARKER}\n{managed_body}\n{END_MARKER}"
    if BEGIN_MARKER in existing_body and END_MARKER in existing_body:
        prefix, remainder = existing_body.split(BEGIN_MARKER, 1)
        _, suffix = remainder.split(END_MARKER, 1)
        return prefix + managed_section + suffix
    return existing_body.rstrip() + "\n\n" + managed_section
