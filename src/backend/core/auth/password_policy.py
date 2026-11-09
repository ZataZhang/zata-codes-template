"""认证密码长度契约。"""

from __future__ import annotations

from backend.core.shared.interfaces.password_hasher import MAX_PASSWORD_UTF8_BYTES


def is_password_within_byte_limit(password: str) -> bool:
    """判断密码编码后是否处于哈希实现支持的有效长度内。

    Args:
        password (str): 待校验的密码。

    Returns:
        bool: UTF-8 编码不超过 ``MAX_PASSWORD_UTF8_BYTES`` 时返回 True。
    """
    return len(password.encode("utf-8")) <= MAX_PASSWORD_UTF8_BYTES


__all__ = ["MAX_PASSWORD_UTF8_BYTES", "is_password_within_byte_limit"]
