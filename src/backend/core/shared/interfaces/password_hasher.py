"""密码哈希抽象端口。"""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    """密码哈希与校验抽象，具体算法由基础设施层实现。"""

    def hash(self, plain_password: str) -> str:
        """对明文密码生成不可逆哈希。

        Args:
            plain_password (str): 明文密码。

        Returns:
            str: 可持久化的哈希串（含算法标识与盐）。
        """
        ...

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """校验明文密码与既有哈希是否匹配。

        Args:
            plain_password (str): 待校验的明文密码。
            hashed_password (str): 既有哈希串。

        Returns:
            bool: 匹配返回 True，否则返回 False。
        """
        ...
