"""使用 Redis 维护跨进程共享的限流计数。"""

from __future__ import annotations

from hashlib import sha256

from redis import Redis

from backend.core.shared.interfaces.rate_limit_store import RateLimitDecision, RateLimitStore

_RATE_LIMIT_KEY_PREFIX: str = "security:rate-limit:"
_CONSUME_BUCKET_SCRIPT: str = """
local request_count = redis.call('INCR', KEYS[1])
if request_count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local retry_after_seconds = redis.call('TTL', KEYS[1])
return {request_count, retry_after_seconds}
"""


class RedisRateLimitStore(RateLimitStore):
    """基于 Redis 的固定窗口计数存储。"""

    def __init__(self, redis_client: Redis) -> None:
        """初始化 Redis 限流存储。

        Args:
            redis_client (Redis): 与会话存储共用的同步 Redis 客户端。
        """
        self._redis = redis_client

    def consume(
        self,
        bucket_key: str,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        """原子地增加请求计数，并让窗口从首次请求开始计时。

        Args:
            bucket_key (str): 由接入层构造的限流桶标识。
            max_requests (int): 一个窗口内允许的最大请求数。
            window_seconds (int): 限流窗口秒数。

        Returns:
            RateLimitDecision: 是否放行，以及拒绝时建议等待的秒数。
        """
        bucket_digest: str = sha256(bucket_key.encode("utf-8")).hexdigest()
        redis_key: str = f"{_RATE_LIMIT_KEY_PREFIX}{bucket_digest}"

        request_count, retry_after_seconds = self._redis.eval(
            _CONSUME_BUCKET_SCRIPT,
            1,
            redis_key,
            window_seconds,
        )

        if request_count <= max_requests:
            return RateLimitDecision(is_allowed=True, retry_after_seconds=0)

        return RateLimitDecision(
            is_allowed=False,
            retry_after_seconds=max(1, int(retry_after_seconds)),
        )


__all__ = ["RedisRateLimitStore"]
