"""Skill 正文只接受声明式文本与参考文件的边界测试。"""

from __future__ import annotations

import pytest

from backend.core.agent.skills import validate_skill_body


@pytest.mark.parametrize(
    "executable_line",
    [
        'print("hello")',
        "def run_task():",
        'console.log("hello")',
        "rm -rf /tmp/skill",
        "python3 main.py",
    ],
)
def test_rejects_unfenced_executable_skill_lines(executable_line: str) -> None:
    """拒绝常见语言的未围栏代码行与 Shell 命令。"""
    with pytest.raises(ValueError, match="skill_executable_content_not_allowed"):
        validate_skill_body(f"执行步骤：\n{executable_line}")


@pytest.mark.parametrize(
    "declarative_body",
    [
        "请用简洁的自然语言回答，并列出关键限制。",
        "Import the approved reference and summarize its key points.",
        "Docker is available only to platform operators.",
        '{\n  "tone": "concise",\n  "format": "bullets"\n}',
        "```yaml\ntone: concise\nformat: bullets\n```",
    ],
)
def test_accepts_declarative_skill_text_and_references(declarative_body: str) -> None:
    """继续接受自然语言正文和允许的声明式参考格式。"""
    assert validate_skill_body(declarative_body) == declarative_body
