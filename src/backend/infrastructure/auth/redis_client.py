"""Redis 客户端构造工具。"""

from __future__ import annotations

from redis import Redis

_REDIS_CONNECT_TIMEOUT_SECONDS: float = 2.0
_REDIS_SOCKET_TIMEOUT_SECONDS: float = 2.0


def create_redis_client(redis_url: str) -> Redis:
    """按连接 URL 构造同步 Redis 客户端。

    Args:
        redis_url (str): 形如 ``redis://host:port/db`` 的连接串。

    Returns:
        Redis: 已配置响应解码与有限连接 / 读写超时的同步客户端。
    """
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=_REDIS_CONNECT_TIMEOUT_SECONDS,
        socket_timeout=_REDIS_SOCKET_TIMEOUT_SECONDS,
    )
