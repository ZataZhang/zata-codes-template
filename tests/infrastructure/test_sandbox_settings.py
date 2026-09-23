"""沙箱 Runtime 配置加载测试。

覆盖配置面:``[sandbox_agent] skills_paths`` 缺省为空、声明了可信宿主来源时被
解析、坏来源 fail-fast。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.infrastructure.config.sandbox_settings import (
    SandboxAgentConfigError,
    load_sandbox_agent_config,
)


def _write_sandbox_agent_config(config_file_path: Path, *, skills_paths_line: str = "") -> None:
    """写入最小可加载的沙箱配置。"""
    config_file_path.write_text(
        f"""
[sandbox_agent]
provider = "docker"
image = "zata-sandbox:latest"
command_timeout_seconds = 120
memory_limit = "1g"
{skills_paths_line}
[sandbox_agent.egress]
mode = "none"
""",
        encoding="utf-8",
    )


def test_sandbox_config_defaults_to_no_skill_sources(tmp_path: Path) -> None:
    """缺省 skills_paths 为空:沙箱 Runtime 不暴露任何 Skill。"""
    config_file_path = tmp_path / "config.toml"
    _write_sandbox_agent_config(config_file_path)

    sandbox_config = load_sandbox_agent_config(config_file_path)

    assert sandbox_config is not None
    assert sandbox_config.skills_paths == ()


def test_sandbox_config_parses_trusted_host_skill_sources(tmp_path: Path) -> None:
    """声明的宿主 Skill 来源被解析为配置字段。"""
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    config_file_path = tmp_path / "config.toml"
    _write_sandbox_agent_config(
        config_file_path, skills_paths_line=f'skills_paths = ["{skills_root}"]'
    )

    sandbox_config = load_sandbox_agent_config(config_file_path)

    assert sandbox_config is not None
    assert sandbox_config.skills_paths == (str(skills_root),)


def test_sandbox_config_rejects_missing_skill_source(tmp_path: Path) -> None:
    """坏来源 fail-fast:目录不存在时不注册"看起来有 Skill"的沙箱 Runtime。"""
    config_file_path = tmp_path / "config.toml"
    _write_sandbox_agent_config(
        config_file_path, skills_paths_line=f'skills_paths = ["{tmp_path / "missing"}"]'
    )

    with pytest.raises(SandboxAgentConfigError, match="目录不存在"):
        load_sandbox_agent_config(config_file_path)


@pytest.mark.parametrize(
    ("skills_paths_line", "expected_message"),
    [
        ('skills_paths = "src/backend/engines/skills"', "必须是数组"),
        ('skills_paths = ["  "]', "不允许空路径"),
    ],
)
def test_sandbox_config_rejects_malformed_skill_sources(
    tmp_path: Path, skills_paths_line: str, expected_message: str
) -> None:
    """类型错误与空路径都有稳定失败报文。"""
    config_file_path = tmp_path / "config.toml"
    _write_sandbox_agent_config(config_file_path, skills_paths_line=skills_paths_line)

    with pytest.raises(SandboxAgentConfigError, match=expected_message):
        load_sandbox_agent_config(config_file_path)
