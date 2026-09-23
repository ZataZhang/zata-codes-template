"""沙箱执行后端装配测试（composition root）。

覆盖配置 → 后端选择的映射，以及"不可用时不注册"的失败闭合语义。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.composition import sandbox_wiring
from backend.infrastructure.config.sandbox_settings import SandboxAgentConfig
from backend.infrastructure.sandbox import docker_provider
from backend.infrastructure.sandbox.egress_policy import SandboxEgressPolicy
from backend.infrastructure.sandbox.filesystem_provider import FilesystemSandboxProvider


def _filesystem_config(workspace_root: Path) -> SandboxAgentConfig:
    """构造一份 filesystem 档配置对象。"""
    return SandboxAgentConfig(
        provider="filesystem",
        image="unused",
        command_timeout_seconds=30,
        workspace_root=str(workspace_root),
        memory_limit="1g",
        model=None,
        egress=SandboxEgressPolicy(mode="none"),
        skills_paths=(),
    )


def test_unconfigured_sandbox_is_not_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置 ``[sandbox_agent]`` 段时返回 None，调用方在装配期即拿到明确结果。"""
    monkeypatch.setattr(sandbox_wiring, "load_sandbox_agent_config", lambda: None)

    assert sandbox_wiring.build_sandbox_provider() is None


def test_filesystem_provider_is_selected_by_config(tmp_path: Path) -> None:
    """filesystem 档构造本地目录后端并视为可用。"""
    sandbox_provider = sandbox_wiring.build_sandbox_provider(
        _filesystem_config(tmp_path / "workspace")
    )

    assert isinstance(sandbox_provider, FilesystemSandboxProvider)
    assert sandbox_provider.is_available() is True


def test_unavailable_backend_is_not_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Docker daemon 不可达时装配返回 None，而不是给出一个运行时必失败的句柄。"""
    monkeypatch.setattr(
        docker_provider,
        "_connect_docker_client",
        lambda: (None, "无法连接 Docker daemon: boom"),
    )
    docker_config = SandboxAgentConfig(
        provider="docker",
        image="sandbox-test:latest",
        command_timeout_seconds=30,
        workspace_root="unused",
        memory_limit="1g",
        model=None,
        egress=SandboxEgressPolicy(mode="none"),
        skills_paths=(),
    )

    assert sandbox_wiring.build_sandbox_provider(docker_config) is None
