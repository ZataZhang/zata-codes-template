"""API 限流计数存储端口。"""

from __future__ import annotations

from typing import NamedTuple, Protocol


class RateLimitDecision(NamedTuple):
    """单次限流计数结果。"""

    is_allowed: bool
    retry_after_seconds: int


class RateLimitStore(Protocol):
    """提供跨后端实例共享的请求计数。"""

    def consume(
        self,
        bucket_key: str,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        """记录一次请求并判断当前计数是否仍在限制内。

        Args:
            bucket_key (str): 由接入层构造的限流桶标识。
            max_requests (int): 一个窗口内允许的最大请求数。
            window_seconds (int): 限流窗口秒数。

        Returns:
            RateLimitDecision: 是否放行，以及拒绝时建议等待的秒数。
        """


__all__ = ["RateLimitDecision", "RateLimitStore"]
