"""运行时配置 provider 的本地逻辑与 Nacos SDK 边界用例。"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from backend.infrastructure.config.providers import ConfigProviderError, build_config_provider
from backend.infrastructure.config.providers.local_provider import LocalConfigProvider
from backend.infrastructure.config.providers.nacos_provider import NacosConfigProvider
from backend.infrastructure.config.settings import ConfigProviderSettings


def test_local_config_provider_loads_runtime_table(tmp_path: Path) -> None:
    """本地 provider 从 config.toml 的 runtime_config 表读取快照。"""
    config_file_path = tmp_path / "config.toml"
    config_file_path.write_text(
        "[runtime_config]\nfeature_enabled = true\nmax_batch_size = 20\n",
        encoding="utf-8",
    )

    config_snapshot = asyncio.run(LocalConfigProvider(config_file_path).load())

    assert config_snapshot == {"feature_enabled": True, "max_batch_size": 20}


def test_local_config_provider_returns_empty_snapshot_without_section(
    tmp_path: Path,
) -> None:
    """本地配置没有 runtime_config 表时以空快照启动。"""
    config_file_path = tmp_path / "config.toml"
    config_file_path.write_text("[app]\napp_name = 'test-app'\n", encoding="utf-8")

    config_snapshot = asyncio.run(LocalConfigProvider(config_file_path).load())

    assert config_snapshot == {}


def test_provider_factory_requires_nacos_bootstrap_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """填写 Nacos 地址后自动选择 Nacos，只要求应用账号凭据。"""
    monkeypatch.delenv("NACOS_USERNAME", raising=False)
    monkeypatch.delenv("NACOS_PASSWORD", raising=False)
    provider_settings = ConfigProviderSettings(
        _env_file=None,
        nacos_server_addr="nacos:8848",
    )

    with pytest.raises(ConfigProviderError) as raised_provider_error:
        build_config_provider(provider_settings, config_file_path=tmp_path / "config.toml")

    assert "NACOS_USERNAME" in str(raised_provider_error.value)
    assert "NACOS_PASSWORD" in str(raised_provider_error.value)


def test_provider_factory_selects_nacos_from_address_and_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """地址与账号凭据齐全时无需额外 provider 开关即可选择 Nacos。"""
    monkeypatch.setenv("NACOS_USERNAME", "runtime-reader")
    monkeypatch.setenv("NACOS_PASSWORD", "secret-value")
    provider_settings = ConfigProviderSettings(
        _env_file=None,
        nacos_server_addr="nacos:8848",
    )

    config_provider = build_config_provider(
        provider_settings,
        config_file_path=tmp_path / "config.toml",
    )

    assert isinstance(config_provider, NacosConfigProvider)


def test_nacos_provider_reads_subscribes_and_closes_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nacos 适配器将 SDK 文档解析为快照并转发有效更新。"""
    monkeypatch.setenv("NACOS_USERNAME", "runtime-reader")
    monkeypatch.setenv("NACOS_PASSWORD", "secret-value")
    fake_client = _FakeNacosConfigClient()
    fake_nacos_module = ModuleType("v2.nacos")
    fake_nacos_module.ClientConfigBuilder = _FakeClientConfigBuilder  # type: ignore[attr-defined]
    fake_nacos_module.ConfigParam = _FakeConfigParam  # type: ignore[attr-defined]
    fake_nacos_module.NacosConfigService = _FakeNacosConfigService(fake_client)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "v2", ModuleType("v2"))
    monkeypatch.setitem(sys.modules, "v2.nacos", fake_nacos_module)
    provider_settings = ConfigProviderSettings(
        _env_file=None,
        provider="nacos",
        nacos_server_addr="nacos:8848",
    )
    nacos_provider = NacosConfigProvider(provider_settings)

    async def exercise_nacos_provider() -> tuple[dict[str, object], list[dict[str, object]]]:
        initial_config_snapshot = dict(await nacos_provider.load())
        updated_config_snapshots: list[dict[str, object]] = []

        async def collect_config_update(config_snapshot: Any) -> None:
            updated_config_snapshots.append(dict(config_snapshot))

        await nacos_provider.subscribe(collect_config_update)
        assert fake_client.listener is not None
        await fake_client.listener(
            "production",
            "DEFAULT_GROUP",
            "my-app-runtime.json",
            '{"feature_enabled": true}',
        )
        await fake_client.listener(
            "production",
            "DEFAULT_GROUP",
            "my-app-runtime.json",
            "[]",
        )
        await nacos_provider.close()
        return initial_config_snapshot, updated_config_snapshots

    initial_config_snapshot, updated_config_snapshots = asyncio.run(exercise_nacos_provider())

    assert initial_config_snapshot == {"feature_enabled": False}
    assert updated_config_snapshots == [{"feature_enabled": True}]
    assert fake_client.closed


class _FakeClientConfigBuilder:
    """Nacos 客户端构造器替身。"""

    def server_address(self, server_address: str) -> _FakeClientConfigBuilder:
        self._server_address = server_address
        return self

    def namespace_id(self, namespace_id: str) -> _FakeClientConfigBuilder:
        self._namespace_id = namespace_id
        return self

    def username(self, username: str) -> _FakeClientConfigBuilder:
        self._username = username
        return self

    def password(self, password: str) -> _FakeClientConfigBuilder:
        self._password = password
        return self

    def build(self) -> SimpleNamespace:
        return SimpleNamespace(
            server_address=self._server_address,
            namespace_id=self._namespace_id,
            username=self._username,
            password=self._password,
        )


class _FakeConfigParam:
    """Nacos 配置读取参数替身。"""

    def __init__(self, *, data_id: str, group: str) -> None:
        self.data_id = data_id
        self.group = group


class _FakeNacosConfigClient:
    """隔离网络 I/O 的 Nacos 配置客户端替身。"""

    def __init__(self) -> None:
        self.listener: Any | None = None
        self.closed = False

    async def get_config(self, config_param: _FakeConfigParam) -> str:
        assert config_param.data_id == "my-app-runtime.json"
        assert config_param.group == "DEFAULT_GROUP"
        return '{"feature_enabled": false}'

    async def add_listener(self, data_id: str, group: str, listener: Any) -> None:
        assert data_id == "my-app-runtime.json"
        assert group == "DEFAULT_GROUP"
        self.listener = listener

    async def shutdown(self) -> None:
        self.closed = True


class _FakeNacosConfigService:
    """返回配置客户端替身的 Nacos SDK 服务。"""

    def __init__(self, config_client: _FakeNacosConfigClient) -> None:
        self._config_client = config_client

    async def create_config_service(self, client_config: SimpleNamespace) -> _FakeNacosConfigClient:
        assert client_config.server_address == "nacos:8848"
        assert client_config.namespace_id == ""
        assert client_config.username == "runtime-reader"
        assert client_config.password == "secret-value"
        return self._config_client
