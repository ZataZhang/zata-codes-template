"""Docker 沙箱后端的确定性单元测试（不需要 Docker daemon）。

容器生命周期依赖真实 daemon，属于 live 范畴；这里只覆盖与 daemon 无关的部分：
daemon 不可达时的失败闭合语义，以及容器标签与单文件归档的构造规则。
"""

from __future__ import annotations

import io
import tarfile
from typing import Any

import pytest

from backend.infrastructure.sandbox import docker_provider
from backend.infrastructure.sandbox.docker_provider import (
    DockerSandboxProvider,
    _single_file_archive,
    _thread_label_value,
)
from backend.infrastructure.sandbox.egress_policy import SandboxEgressPolicy


def _build_provider() -> DockerSandboxProvider:
    """构造一个使用断网策略的 Docker 后端。"""
    return DockerSandboxProvider(
        image="sandbox-test:latest",
        command_timeout_seconds=30,
        egress_policy=SandboxEgressPolicy(mode="none"),
    )


def test_provider_fails_closed_when_daemon_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """daemon 不可达时后端标记为不可用，且 acquire 拒绝——不静默回落宿主执行。"""
    monkeypatch.setattr(
        docker_provider,
        "_connect_docker_client",
        lambda: (None, "无法连接 Docker daemon: boom"),
    )
    sandbox_provider = _build_provider()

    assert sandbox_provider.is_available() is False
    assert sandbox_provider.availability_detail() == "无法连接 Docker daemon: boom"
    with pytest.raises(RuntimeError, match="Docker 沙箱不可用"):
        sandbox_provider.acquire("thread-a")


def test_missing_docker_sdk_is_reported_as_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未安装 docker 依赖时给出可诊断的原因，而不是抛 ImportError。"""
    monkeypatch.setattr(
        docker_provider,
        "_connect_docker_client",
        lambda: (None, "未安装 docker 依赖"),
    )

    assert _build_provider().availability_detail() == "未安装 docker 依赖"


def test_thread_label_value_hides_raw_identifier() -> None:
    """会话标识被哈希成标签值：原始标识不出现在容器元数据里，且同输入稳定。"""
    raw_thread_id = "thread-with-secret-name"
    label_value = _thread_label_value(raw_thread_id)

    assert raw_thread_id not in label_value
    assert len(label_value) == 32
    assert label_value == _thread_label_value(raw_thread_id)
    assert label_value != _thread_label_value("another-thread")


def test_single_file_archive_contains_one_regular_file_with_sandbox_owner() -> None:
    """单文件归档只含一个普通文件，归属 uid/gid 65534、权限 0600、路径无前导斜杠。"""
    archive_bytes = _single_file_archive("/workspace/outputs/report.txt", b"payload")

    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        members = archive.getmembers()
        assert len(members) == 1
        member: Any = members[0]
        assert member.name == "workspace/outputs/report.txt"
        assert member.isfile()
        assert member.uid == 65534
        assert member.gid == 65534
        assert member.mode == 0o600
        extracted = archive.extractfile(member)
        assert extracted is not None
        assert extracted.read() == b"payload"
