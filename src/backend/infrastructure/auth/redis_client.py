"""Redis 客户端构造工具。"""

from __future__ import annotations

from redis import Redis


def create_redis_client(redis_url: str) -> Redis:
    """按连接 URL 构造同步 Redis 客户端。

    Args:
        redis_url (str): 形如 ``redis://host:port/db`` 的连接串。

    Returns:
        Redis: 已配置 ``decode_responses=True`` 的同步客户端，``get`` 返回 str。
    """
    return Redis.from_url(redis_url, decode_responses=True)
