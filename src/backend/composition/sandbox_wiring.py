"""沙箱执行环境 composition 装配。

未配置 ``[sandbox_agent]`` 段时返回 ``None``:沙箱能力不注册,而不是让调用方在
运行时才发现后端缺失。

装配失败(Docker daemon 不可达、云沙箱凭据缺失或控制面不可达)同样只是返回
``None``,不中断应用启动:一个执行后端的故障不应该让整个应用不可用。任何装配
失败都不会把执行面回落到宿主 shell——那正是沙箱后端要消除的路径。

区分两类"配置问题":**整段缺失**按未配置处理(返回 ``None``,应用照常启动);**段
存在但字段非法或缺失**(例如 ``provider = "e2b"`` 却没写 ``api_url``)则在启动期
fail-fast——一个"看起来已启用、实际根本没配上"的后端比不注册更难排查。

本模块只负责按配置构造 :class:`SandboxProvider`;谁来消费它(执行器、资源暂存、
产物发布)由派生项目自行装配。
"""

from __future__ import annotations

import os
from pathlib import Path

from backend.core.shared.interfaces.sandbox_provider import SandboxProvider
from backend.infrastructure.config.sandbox_settings import (
    SandboxAgentConfig,
    load_sandbox_agent_config,
)
from backend.infrastructure.logger import logger
from backend.infrastructure.sandbox import (
    DockerSandboxProvider,
    E2bEndpointConfig,
    E2bSandboxProvider,
    FilesystemSandboxProvider,
)


def build_sandbox_provider(config: SandboxAgentConfig | None = None) -> SandboxProvider | None:
    """按配置装配沙箱执行后端;未配置或后端不可用时返回 ``None``。

    Args:
        config (SandboxAgentConfig | None): 已加载的沙箱配置;为 ``None`` 时从
            ``config.toml`` 的 ``[sandbox_agent]`` 段加载。

    Returns:
        SandboxProvider | None: 沙箱后端;未配置、凭据缺失或后端不可用时为 ``None``。
    """
    sandbox_config = config if config is not None else load_sandbox_agent_config()
    if sandbox_config is None:
        return None
    sandbox_provider = _select_provider(sandbox_config)
    if sandbox_provider is None:
        return None
    if not sandbox_provider.is_available():
        logger.warning(
            "sandbox runtime 未注册：后端不可用 provider=%s reason=%s",
            sandbox_config.provider,
            sandbox_provider.availability_detail(),
        )
        return None
    return sandbox_provider


def _select_provider(sandbox_config: SandboxAgentConfig) -> SandboxProvider | None:
    """按配置选择沙箱后端实现。

    云沙箱档缺少凭据环境变量时打印明确告警并返回 ``None``:该后端不注册,而不是
    拿着空凭据去探测后只留下一条 401,运维需要一眼看到是哪个变量没填。

    Args:
        sandbox_config (SandboxAgentConfig): 已校验的沙箱配置。

    Returns:
        SandboxProvider | None: Docker、本地目录或云沙箱后端;云沙箱档缺少凭据时
            为 ``None``。
    """
    if sandbox_config.provider == "docker":
        return DockerSandboxProvider(
            image=sandbox_config.image,
            command_timeout_seconds=sandbox_config.command_timeout_seconds,
            egress_policy=sandbox_config.egress,
            memory_limit=sandbox_config.memory_limit,
        )
    if sandbox_config.provider == "e2b":
        return _build_e2b_provider(sandbox_config)
    return FilesystemSandboxProvider(_workspace_root_path(sandbox_config))


def _build_e2b_provider(sandbox_config: SandboxAgentConfig) -> SandboxProvider | None:
    """按配置构建云沙箱后端。

    密钥值只从环境变量读取,配置里存的是变量名;这里不做任何"缺凭据就换本地执行"
    的兜底——那会把不可用变成静默的宿主执行。

    Args:
        sandbox_config (SandboxAgentConfig): 已校验的沙箱配置。

    Returns:
        SandboxProvider | None: 云沙箱后端;配置段或凭据缺失时为 ``None``。
    """
    e2b_settings = sandbox_config.e2b
    if e2b_settings is None:
        logger.warning("sandbox runtime 未注册：provider=e2b 缺少 [sandbox_agent.e2b] 配置段")
        return None
    api_key = os.getenv(e2b_settings.api_key_env, "").strip()
    if not api_key:
        logger.warning(
            "sandbox runtime 未注册：provider=e2b 的环境变量 %s 未配置",
            e2b_settings.api_key_env,
        )
        return None
    return E2bSandboxProvider(
        config=E2bEndpointConfig(
            api_url=e2b_settings.api_url,
            sandbox_url=e2b_settings.sandbox_url,
            api_key=api_key,
            domain="",
            template_id=e2b_settings.template_id,
            timeout_seconds=e2b_settings.timeout_seconds,
            username=e2b_settings.username,
            allow_internet_access=e2b_settings.allow_internet_access,
        ),
        command_timeout_seconds=sandbox_config.command_timeout_seconds,
    )


def _workspace_root_path(sandbox_config: SandboxAgentConfig) -> Path:
    """返回 filesystem 档会话目录的父目录路径。"""
    return Path(sandbox_config.workspace_root)


__all__ = ["build_sandbox_provider"]
