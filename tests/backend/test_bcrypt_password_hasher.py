"""bcrypt 密码哈希实现测试。"""

from __future__ import annotations

from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher


def test_hash_is_not_plaintext_and_verifies() -> None:
    """哈希不等于明文，且能校验通过正确密码。"""
    hasher = BcryptPasswordHasher()
    hashed_password = hasher.hash("secret123")
    assert hashed_password != "secret123"
    assert hasher.verify("secret123", hashed_password) is True


def test_hash_is_salted_unique() -> None:
    """相同明文两次哈希结果不同（带随机盐）。"""
    hasher = BcryptPasswordHasher()
    first_hash = hasher.hash("secret123")
    second_hash = hasher.hash("secret123")
    assert first_hash != second_hash


def test_verify_rejects_wrong_password() -> None:
    """错误密码校验失败。"""
    hasher = BcryptPasswordHasher()
    hashed_password = hasher.hash("secret123")
    assert hasher.verify("wrong-password", hashed_password) is False


def test_verify_handles_malformed_hash() -> None:
    """非法哈希串不抛异常，返回 False。"""
    hasher = BcryptPasswordHasher()
    assert hasher.verify("secret123", "not-a-bcrypt-hash") is False
