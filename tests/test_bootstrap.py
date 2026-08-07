"""验证应用 bootstrap 的初始用户种子行为（admin 与 public 两域）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.composition import bootstrap


def _fake_password_hasher() -> MagicMock:
    """返回固定哈希值的密码哈希替身。"""
    password_hasher = MagicMock()
    password_hasher.hash.return_value = "hashed-password"
    return password_hasher


def test_seed_admin_user_creates_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配置初始管理员时跳过；配置后首次创建。"""
    monkeypatch.setattr(
        bootstrap.config.auth,
        "admin_bootstrap_username",
        "Admin",
    )
    monkeypatch.setattr(
        bootstrap.config.auth,
        "admin_bootstrap_password",
        type("_Secret", (), {"get_secret_value": lambda self: "adminpass1"})(),
    )

    admin_repository = MagicMock()
    admin_repository.find_by_identifier.return_value = None

    bootstrap.seed_admin_user(admin_repository, _fake_password_hasher())

    admin_repository.find_by_identifier.assert_called_once_with("admin")
    admin_repository.create.assert_called_once()
    created_account = admin_repository.create.call_args.args[0]
    assert created_account.identifier == "admin"
    assert created_account.password_hash == "hashed-password"


def test_seed_admin_user_syncs_password_when_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已存在管理员时同步密码而不是重复创建。"""
    monkeypatch.setattr(
        bootstrap.config.auth,
        "admin_bootstrap_username",
        "Admin",
    )
    monkeypatch.setattr(
        bootstrap.config.auth,
        "admin_bootstrap_password",
        type("_Secret", (), {"get_secret_value": lambda self: "adminpass1"})(),
    )

    admin_repository = MagicMock()
    existing_admin = MagicMock()
    existing_admin.id = "existing-id"
    admin_repository.find_by_identifier.return_value = existing_admin

    bootstrap.seed_admin_user(admin_repository, _fake_password_hasher())

    admin_repository.create.assert_not_called()
    admin_repository.set_password.assert_called_once_with("existing-id", "hashed-password")


def test_seed_admin_user_skips_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配置 AUTH_ADMIN_BOOTSTRAP_* 时直接跳过。"""
    monkeypatch.setattr(bootstrap.config.auth, "admin_bootstrap_username", "")
    monkeypatch.setattr(
        bootstrap.config.auth,
        "admin_bootstrap_password",
        type("_Secret", (), {"get_secret_value": lambda self: ""})(),
    )

    admin_repository = MagicMock()
    bootstrap.seed_admin_user(admin_repository, _fake_password_hasher())

    admin_repository.find_by_identifier.assert_not_called()
    admin_repository.create.assert_not_called()


def test_seed_public_user_creates_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """配置 APP_BOOTSTRAP_* 后首次创建 public 用户。"""
    monkeypatch.setenv("APP_BOOTSTRAP_EMAIL", "user@example.com")
    monkeypatch.setenv("APP_BOOTSTRAP_PASSWORD", "userpass1")

    public_repository = MagicMock()
    public_repository.find_by_identifier.return_value = None

    bootstrap.seed_public_user(public_repository, _fake_password_hasher())

    public_repository.find_by_identifier.assert_called_once_with("user@example.com")
    public_repository.create.assert_called_once()
    created_account = public_repository.create.call_args.args[0]
    assert created_account.identifier == "user@example.com"
    assert created_account.password_hash == "hashed-password"


def test_seed_public_user_skips_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """未配置 APP_BOOTSTRAP_* 时直接跳过。"""
    monkeypatch.delenv("APP_BOOTSTRAP_EMAIL", raising=False)
    monkeypatch.delenv("APP_BOOTSTRAP_PASSWORD", raising=False)

    public_repository = MagicMock()
    bootstrap.seed_public_user(public_repository, _fake_password_hasher())

    public_repository.find_by_identifier.assert_not_called()
    public_repository.create.assert_not_called()
