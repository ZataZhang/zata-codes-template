"""基于 bcrypt 的密码哈希实现。"""

from __future__ import annotations

import bcrypt

from backend.core.shared.interfaces.password_hasher import MAX_PASSWORD_UTF8_BYTES, PasswordHasher

# bcrypt 只消费固定上限内的输入字节；调用方先校验，本类保留截断以兼容旧哈希。
_BCRYPT_MAX_BYTES: int = MAX_PASSWORD_UTF8_BYTES


def _encode_truncated(plain_password: str) -> bytes:
    """把明文密码编码为 UTF-8 并截断到 bcrypt 可消费的最大字节数。"""
    return plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


class BcryptPasswordHasher(PasswordHasher):
    """使用 bcrypt 生成与校验密码哈希。"""

    def hash(self, plain_password: str) -> str:
        """对明文密码生成带盐的 bcrypt 哈希。

        Args:
            plain_password (str): 明文密码。

        Returns:
            str: bcrypt 哈希串（含算法参数与盐）。
        """
        hashed_bytes: bytes = bcrypt.hashpw(_encode_truncated(plain_password), bcrypt.gensalt())
        return hashed_bytes.decode("utf-8")

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """校验明文密码是否匹配既有 bcrypt 哈希。

        Args:
            plain_password (str): 待校验明文密码。
            hashed_password (str): 既有 bcrypt 哈希串。

        Returns:
            bool: 匹配返回 True；哈希格式非法或不匹配返回 False。
        """
        try:
            return bcrypt.checkpw(
                _encode_truncated(plain_password),
                hashed_password.encode("utf-8"),
            )
        except ValueError:
            return False
