"""基于 Redis 的一次性 OIDC 登录事务存储。"""

from __future__ import annotations

import json

from redis import Redis

from backend.core.shared.interfaces.oidc_transaction_store import (
    OidcLoginTransaction,
    OidcTransactionStore,
)


class RedisOidcTransactionStore(OidcTransactionStore):
    """使用 GETDEL 原子消费、按认证域前缀隔离的 OIDC 登录事务。"""

    def __init__(self, *, redis_client: Redis, key_prefix: str) -> None:
        """注入 Redis 客户端与域专属 key 前缀。"""
        self._redis = redis_client
        self._key_prefix = key_prefix

    def save(
        self,
        transaction_id: str,
        transaction: OidcLoginTransaction,
        *,
        ttl_seconds: int,
    ) -> bool:
        """存储 state、nonce 与 PKCE verifier 并限制其有效期。"""
        payload = json.dumps(
            {
                "state": transaction.state,
                "nonce": transaction.nonce,
                "code_verifier": transaction.code_verifier,
            }
        )
        return bool(
            self._redis.set(
                self._build_key(transaction_id),
                payload,
                ex=ttl_seconds,
                nx=True,
            )
        )

    def pop(self, transaction_id: str) -> OidcLoginTransaction | None:
        """原子读取并删除已保存事务。"""
        raw_payload = self._redis.getdel(self._build_key(transaction_id))
        if raw_payload is None:
            return None
        payload = json.loads(raw_payload)
        if not isinstance(payload, dict) or set(payload) != {
            "state",
            "nonce",
            "code_verifier",
        }:
            return None
        if not all(isinstance(payload[name], str) for name in payload):
            return None
        return OidcLoginTransaction(
            state=payload["state"],
            nonce=payload["nonce"],
            code_verifier=payload["code_verifier"],
        )

    def _build_key(self, transaction_id: str) -> str:
        """拼接一次性事务 key。"""
        return f"{self._key_prefix}{transaction_id}"


__all__ = ["RedisOidcTransactionStore"]
