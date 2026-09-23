"""云沙箱真实链路验收（opt-in,需要真实云凭据与已发布的平台模板）。

默认不运行:``pytest.ini`` 的 ``addopts`` 排除了 ``real_api`` 标记。显式启用::

    E2B_LIVE=1 uv run pytest tests/backend/test_cloud_sandbox_e2b_live.py -m real_api -vv

本轮验收的第一道门是**平台模板必须已构建完成**:``[sandbox_agent.e2b] template_id``
指向的模板必须是 READY 状态。使用 ``build_e2b_template.sh`` 从同账号同地域 ACR 的
OCI 镜像发布模板；这些用例不会把模板缺失改成 skip。

覆盖的边界:控制面创建/续期/销毁/列举、执行通道命令与文件、默认断网、宿主与 Skill
字节隔离、沙箱被回收后的失败语义。
"""

from __future__ import annotations

import os
import time

import httpx
import pytest

from backend.core.shared.interfaces.sandbox_provider import (
    SANDBOX_SKILL_RUNTIME_ROOT,
    SandboxFileWrite,
)
from backend.infrastructure.config.sandbox_settings import load_sandbox_agent_config
from backend.infrastructure.sandbox.e2b_protocol import E2bEndpointConfig, E2bProtocolError
from backend.infrastructure.sandbox.e2b_provider import E2bSandboxProvider

pytestmark = pytest.mark.real_api

_INTERNET_PROBE_COMMAND = (
    "curl -sS -m 10 https://pypi.org/simple/ -o /tmp/live-egress-probe; "
    "echo CURL_EXIT=$?; ls -l /tmp/live-egress-probe 2>&1"
)
_STAGED_SKILL_ASSET_PATH = f"{SANDBOX_SKILL_RUNTIME_ROOT}/live-probe/scripts/probe.sh"
_HOST_PATH_MARKERS = ("/Users/", "/home/runner", "/private/")
_TEMPLATE_BUILD_FAILURE_HINT = (
    "平台模板未处于 READY 状态。请运行 deploy/sandbox/build_e2b_template.sh，"
    "从同账号同地域 ACR 的 linux/amd64 OCI 镜像发布模板。"
)
_RECLAIM_SETTLE_SECONDS = 12


def _live_endpoint_config() -> E2bEndpointConfig:
    """读取真实配置并解析凭据;缺失或环境未启用时跳过。"""
    if os.getenv("E2B_LIVE") != "1":
        pytest.skip("未设置 E2B_LIVE=1")
    sandbox_config = load_sandbox_agent_config()
    if sandbox_config is None or sandbox_config.e2b is None:
        pytest.skip("config.toml 未配置 [sandbox_agent.e2b]")
    api_key = os.getenv(sandbox_config.e2b.api_key_env, "").strip()
    if not api_key:
        pytest.skip(f"环境变量 {sandbox_config.e2b.api_key_env} 未配置")
    return E2bEndpointConfig(
        api_url=sandbox_config.e2b.api_url,
        api_key=api_key,
        domain="",
        template_id=sandbox_config.e2b.template_id,
        timeout_seconds=sandbox_config.e2b.timeout_seconds,
        username=sandbox_config.e2b.username,
        allow_internet_access=sandbox_config.e2b.allow_internet_access,
    )


def _assert_platform_template_is_ready(endpoint_config: E2bEndpointConfig) -> None:
    """断言配置指向的平台模板已构建完成。

    这是 rv-1 的关键值来源之一:临时用公开模板跑出来的结果不能证明用户任务跑在平台
    自建模板里。

    Raises:
        AssertionError: 模板不存在或未处于 READY 状态。
    """
    with httpx.Client(timeout=60.0) as client:
        response = client.get(
            f"{endpoint_config.api_url}/templates", headers={"X-API-KEY": endpoint_config.api_key}
        )
    assert response.status_code == 200, f"列举模板失败: HTTP {response.status_code}"
    matching_templates = [
        template
        for template in response.json()
        if endpoint_config.template_id
        in (
            [
                template.get("templateID", ""),
                *template.get("aliases", []),
                *template.get("names", []),
            ]
        )
    ]
    assert (
        matching_templates
    ), f"平台模板 {endpoint_config.template_id} 不存在。{_TEMPLATE_BUILD_FAILURE_HINT}"
    matching_template = matching_templates[0]
    ready_build_statuses = [
        matching_template.get("buildStatus"),
        *[build.get("status") for build in matching_template.get("builds", [])],
    ]
    assert "ready" in ready_build_statuses, (
        f"平台模板 {endpoint_config.template_id} 的构建状态为 {ready_build_statuses}。"
        f"{_TEMPLATE_BUILD_FAILURE_HINT}"
    )


def test_live_platform_template_is_ready() -> None:
    """前置项:平台自建执行模板已发布且可用。"""
    endpoint_config = _live_endpoint_config()

    _assert_platform_template_is_ready(endpoint_config)


def test_live_sandbox_lifecycle_files_and_skills() -> None:
    """rv-1:真实沙箱内执行、文件往返与 Skill 运行资产中立可用。"""
    endpoint_config = _live_endpoint_config()
    _assert_platform_template_is_ready(endpoint_config)
    sandbox_provider = E2bSandboxProvider(config=endpoint_config, command_timeout_seconds=120)
    assert sandbox_provider.is_available(), sandbox_provider.availability_detail()
    sandbox_id = ""
    try:
        sandbox_session = sandbox_provider.acquire("live-acceptance-thread")
        sandbox_id = sandbox_session.sandbox_id

        execution_result = sandbox_session.execute(
            "set -eu; id -u; ls -d /workspace/inputs /workspace/outputs; "
            "python3 -c \"import openpyxl,pandas,numpy,scipy; print('python-data-ok')\"; "
            "node --version",
            timeout_seconds=60,
        )
        assert execution_result.exit_code == 0, execution_result.output
        assert execution_result.output.splitlines()[0] != "0", execution_result.output
        assert "python-data-ok" in execution_result.output, execution_result.output
        assert "v22." in execution_result.output, execution_result.output

        sandbox_session.replace_runtime_assets(
            [
                SandboxFileWrite(
                    sandbox_path=_STAGED_SKILL_ASSET_PATH,
                    content=b"#!/bin/sh\necho skill-asset-executed\n",
                )
            ]
        )
        skill_execution = sandbox_session.execute(
            f"sh {_STAGED_SKILL_ASSET_PATH}", timeout_seconds=60
        )
        assert skill_execution.exit_code == 0, skill_execution.output
        assert "skill-asset-executed" in skill_execution.output

        uploaded_input_path = "/workspace/inputs/live/input.csv"
        sandbox_session.upload_files(
            [SandboxFileWrite(sandbox_path=uploaded_input_path, content=b"a,b\n1,2\n")]
        )
        assert sandbox_session.list_files("/workspace/inputs") == [uploaded_input_path]
        downloaded_files = sandbox_session.download_files([uploaded_input_path])
        assert downloaded_files[0].content == b"a,b\n1,2\n"
    finally:
        sandbox_provider.destroy("live-acceptance-thread")
    assert _await_sandbox_reclaimed(
        sandbox_provider, sandbox_id
    ), f"销毁后云侧仍列出沙箱 {sandbox_id};列举接口有约 2 秒最终一致延迟,这里等到超时"


def _await_sandbox_reclaimed(
    sandbox_provider: E2bSandboxProvider, sandbox_id: str, *, timeout_seconds: int = 30
) -> bool:
    """等待被销毁的沙箱从云侧列表中消失。

    实测该列举接口有约 2 秒最终一致延迟,因此这里轮询而不是即时断言。

    Returns:
        bool: 沙箱已消失为真;超时仍存在为假。
    """
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if sandbox_id not in sandbox_provider.active_sandbox_ids():
            return True
        time.sleep(2)
    return False


def test_live_sandbox_is_offline_by_default() -> None:
    """rv-1:默认姿态下沙箱内访问外网失败,且该失败可被独立断言。"""
    endpoint_config = _live_endpoint_config()
    _assert_platform_template_is_ready(endpoint_config)
    assert (
        endpoint_config.allow_internet_access is False
    ), "验收要求默认断网;当前配置显式放开了出网,不能作为断网证据。"
    sandbox_provider = E2bSandboxProvider(config=endpoint_config, command_timeout_seconds=120)
    try:
        sandbox_session = sandbox_provider.acquire("live-acceptance-offline-thread")
        execution_result = sandbox_session.execute(_INTERNET_PROBE_COMMAND, timeout_seconds=60)
    finally:
        sandbox_provider.destroy("live-acceptance-offline-thread")

    assert "CURL_EXIT=0" not in execution_result.output, execution_result.output
    assert "No such file or directory" in execution_result.output, execution_result.output


def test_live_host_paths_and_skill_sources_are_absent() -> None:
    """rv-1:沙箱内看不到宿主路径,未暂存时也没有 Skill 字节。"""
    endpoint_config = _live_endpoint_config()
    _assert_platform_template_is_ready(endpoint_config)
    sandbox_provider = E2bSandboxProvider(config=endpoint_config, command_timeout_seconds=120)
    try:
        sandbox_session = sandbox_provider.acquire("live-acceptance-isolation-thread")
        execution_result = sandbox_session.execute(
            f"test ! -e {SANDBOX_SKILL_RUNTIME_ROOT} && echo NO-SKILL-RUNTIME; ls /",
            timeout_seconds=60,
        )
    finally:
        sandbox_provider.destroy("live-acceptance-isolation-thread")

    assert "NO-SKILL-RUNTIME" in execution_result.output, execution_result.output
    for host_path_marker in _HOST_PATH_MARKERS:
        assert host_path_marker not in execution_result.output, execution_result.output


def test_live_reclaimed_sandbox_fails_instead_of_succeeding_empty() -> None:
    """rv-3:沙箱被回收后操作抛错,Run 无法把它当成"空产物但成功"。

    实测沙箱销毁后 envd 网关不会让请求失败,而是以 HTTP 200 提供另一个干净环境的
    结果,因此这里断言"通道还在、沙箱已换"必须被识别成失败。等待十余秒是为了让网关
    切过去,确保测的是真实形态而不是时序巧合。

    **覆盖边界**:本用例证明的是"销毁后上层判为失败"。它**不能**证伪身份校验本身——
    在公开模板(无 ``/workspace``)下,网关转到的环境同样没有 ``/workspace``,命令在
    ``Process/Start`` 阶段就被 HTTP 400 挡下,``exit 97 + 标记``这条分支根本不会被触及,
    删掉身份校验本用例照样通过。只有平台自建模板(预建 ``/workspace``)才是该分支的唯一
    判据;在那之前该分支由无云单测覆盖。
    """
    endpoint_config = _live_endpoint_config()
    _assert_platform_template_is_ready(endpoint_config)
    sandbox_provider = E2bSandboxProvider(config=endpoint_config, command_timeout_seconds=60)
    sandbox_session = sandbox_provider.acquire("live-acceptance-reclaim-thread")
    reclaimed_sandbox_id = sandbox_session.sandbox_id
    sandbox_provider.destroy("live-acceptance-reclaim-thread")
    time.sleep(_RECLAIM_SETTLE_SECONDS)

    try:
        # 控制面判据:官方 getInfo 在销毁后立刻 404,据此必须重建而不是复用死沙箱。
        rebuilt_session = sandbox_provider.acquire("live-acceptance-reclaim-thread")
        assert rebuilt_session.sandbox_id != reclaimed_sandbox_id

        # 命令通道判据:即使控制面判据被绕过,身份自校验也会让每条命令失败。
        assert sandbox_session.is_alive() is False
        with pytest.raises(E2bProtocolError):
            sandbox_session.list_files("/workspace/outputs")
        with pytest.raises(E2bProtocolError):
            sandbox_session.execute("echo should-not-succeed", timeout_seconds=30)
    finally:
        sandbox_provider.destroy("live-acceptance-reclaim-thread")
