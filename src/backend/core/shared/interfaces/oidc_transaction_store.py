"""一次性 OIDC 登录事务存储端口。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class OidcLoginTransaction:
    """等待回调的一次性协议参数。"""

    state: str
    nonce: str
    code_verifier: str


class OidcTransactionStore(Protocol):
    """按登录域隔离、带 TTL 的一次性登录事务存储。"""

    def save(
        self,
        transaction_id: str,
        transaction: OidcLoginTransaction,
        *,
        ttl_seconds: int,
    ) -> bool:
        """保存一个事务；已存在时不覆盖并返回 False。"""

    def pop(self, transaction_id: str) -> OidcLoginTransaction | None:
        """原子读取并删除事务；不存在或已过期时返回 None。"""


__all__ = ["OidcLoginTransaction", "OidcTransactionStore"]
