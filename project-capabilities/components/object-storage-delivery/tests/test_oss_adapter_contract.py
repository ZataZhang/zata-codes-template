"""对象存储 overlay 的配置与 OSS V4 签名契约测试。"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from backend.infrastructure.config.object_storage_settings import (
    ObjectStorageConfigError,
    ObjectStorageSettings,
    load_object_storage_settings,
)
from backend.infrastructure.storage.oss_object_storage import (
    AliyunOSSObjectStorage,
    _sign_post_policy,
)

_TEST_ACCESS_KEY_ID = "AKIDEXAMPLE"
_TEST_ACCESS_KEY_SECRET = "fixture-secret-never-used-for-access"


@pytest.fixture
def configured_oss_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> ObjectStorageSettings:
    """创建启用 OSS 的隔离配置并注入仅供测试的凭据。"""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[object_storage]",
                "enabled = true",
                'provider = "aliyun_oss"',
                'endpoint = "https://oss-cn-hangzhou.aliyuncs.com"',
                'region = "cn-hangzhou"',
                'bucket = "storage-e2e-test"',
                'cdn_base_url = "https://cdn.example.test/assets"',
                'access_key_id_env = "TEST_OSS_ACCESS_KEY_ID"',
                'access_key_secret_env = "TEST_OSS_ACCESS_KEY_SECRET"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("TEST_OSS_ACCESS_KEY_ID", _TEST_ACCESS_KEY_ID)
    monkeypatch.setenv("TEST_OSS_ACCESS_KEY_SECRET", _TEST_ACCESS_KEY_SECRET)

    storage_settings = load_object_storage_settings(config_path)

    assert storage_settings is not None
    return storage_settings


def test_disabled_object_storage_does_not_require_credentials(tmp_path: Path) -> None:
    """关闭配置时不读取 OSS 凭据。"""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "[object_storage]\nenabled = false\n",
        encoding="utf-8",
    )

    assert load_object_storage_settings(config_path) is None


def test_enabled_object_storage_reports_missing_server_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """启用配置但缺少凭据时明确拒绝装配。"""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        "\n".join(
            [
                "[object_storage]",
                "enabled = true",
                'provider = "aliyun_oss"',
                'endpoint = "https://oss-cn-hangzhou.aliyuncs.com"',
                'bucket = "storage-e2e-test"',
                'access_key_id_env = "TEST_OSS_ACCESS_KEY_ID"',
                'access_key_secret_env = "TEST_OSS_ACCESS_KEY_SECRET"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("TEST_OSS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("TEST_OSS_ACCESS_KEY_SECRET", raising=False)

    with pytest.raises(ObjectStorageConfigError) as config_error:
        load_object_storage_settings(config_path)

    assert "TEST_OSS_ACCESS_KEY_ID" in str(config_error.value)
    assert "TEST_OSS_ACCESS_KEY_SECRET" in str(config_error.value)


def test_server_credentials_are_hidden_from_settings_repr(
    configured_oss_settings: ObjectStorageSettings,
) -> None:
    """配置对象的调试表示不泄露服务端密钥。"""
    settings_repr = repr(configured_oss_settings)

    assert _TEST_ACCESS_KEY_ID not in settings_repr
    assert _TEST_ACCESS_KEY_SECRET not in settings_repr


def test_public_url_uses_cdn_origin_and_encodes_key(
    configured_oss_settings: ObjectStorageSettings,
) -> None:
    """公开对象地址只使用 CDN 域名并编码路径空格。"""
    storage_adapter = AliyunOSSObjectStorage.__new__(AliyunOSSObjectStorage)
    storage_adapter._settings = configured_oss_settings

    public_url = storage_adapter.public_url("images/a photo.png")

    assert public_url == "https://cdn.example.test/assets/images/a%20photo.png"


def test_post_policy_v4_signature_matches_fixed_vector() -> None:
    """OSS V4 POST 签名按固定输入产生可复现的十六进制结果。"""
    policy_json = (
        '{"expiration":"2026-11-17T12:15:00.000Z","conditions":['
        '{"bucket":"storage-e2e-test"},'
        '{"x-oss-signature-version":"OSS4-HMAC-SHA256"},'
        '{"x-oss-credential":"AKIDEXAMPLE/20261117/cn-hangzhou/oss/aliyun_v4_request"},'
        '{"x-oss-date":"20261117T120000Z"},'
        '["eq","$key","rv-1/example.png"],'
        '["eq","$Content-Type","image/png"],'
        '["eq","$Cache-Control","public, max-age=31536000, immutable"],'
        '["eq","$success_action_status","201"],'
        '["content-length-range",1,65536]]}'
    )
    encoded_policy = base64.b64encode(policy_json.encode("utf-8")).decode("ascii")

    signature = _sign_post_policy(
        _TEST_ACCESS_KEY_SECRET,
        "cn-hangzhou",
        "20261117",
        encoded_policy,
    )

    assert signature == "b948775c97aa203530c1c9006b7fbe6c8536a2ba44889836f7c3b5817856d433"
