"""HTTP API 请求限流策略。"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

from fastapi import HTTPException, Request
from redis.exceptions import RedisError
from starlette.concurrency import run_in_threadpool

from backend.core.shared.interfaces.rate_limit_store import RateLimitStore

AuthRateLimitOperation = Literal["public_login", "admin_login", "public_register"]


@dataclass(frozen=True)
class ApiRateLimitConfig:
    """API 与认证端点的限流阈值。"""

    enabled: bool
    api_requests_per_minute: int
    public_login_ip_attempts: int
    public_login_identifier_attempts: int
    admin_login_ip_attempts: int
    admin_login_identifier_attempts: int
    login_ip_window_seconds: int
    login_identifier_window_seconds: int
    register_ip_attempts: int
    register_window_seconds: int


class ApiRateLimiter:
    """基于共享计数存储的 HTTP 限流策略执行器。"""

    def __init__(self, rate_limit_store: RateLimitStore, config: ApiRateLimitConfig) -> None:
        """初始化 API 限流策略执行器。

        Args:
            rate_limit_store (RateLimitStore): 跨进程共享的计数存储。
            config (ApiRateLimitConfig): 限流阈值配置。
        """
        self._rate_limit_store = rate_limit_store
        self._config = config

    async def check_request(self, request: Request) -> None:
        """执行通用 API 来源 IP 限流，健康探针不参与计数。

        Args:
            request (Request): 当前 HTTP 请求。
        """
        if not self._config.enabled or request.url.path in {"/health", "/ready", "/live"}:
            return

        await self._enforce_bucket(
            bucket_key=f"api:ip:{self._client_ip(request)}",
            max_requests=self._config.api_requests_per_minute,
            window_seconds=60,
        )

    async def check_auth_attempt(
        self,
        request: Request,
        *,
        operation: AuthRateLimitOperation,
        identifier: str,
    ) -> None:
        """按来源 IP 和登录标识限制登录或注册尝试。

        Args:
            request (Request): 当前 HTTP 请求。
            operation (AuthRateLimitOperation): 认证域与操作类型。
            identifier (str): 用户提交的登录标识。
        """
        if not self._config.enabled:
            return

        client_ip: str = self._client_ip(request)
        if operation == "public_register":
            await self._enforce_bucket(
                bucket_key=f"auth:register:ip:{client_ip}",
                max_requests=self._config.register_ip_attempts,
                window_seconds=self._config.register_window_seconds,
            )
            return

        if operation == "admin_login":
            ip_attempts: int = self._config.admin_login_ip_attempts
            identifier_attempts: int = self._config.admin_login_identifier_attempts
            limiter_prefix: str = "auth:admin-login"
        else:
            ip_attempts = self._config.public_login_ip_attempts
            identifier_attempts = self._config.public_login_identifier_attempts
            limiter_prefix = "auth:public-login"

        await self._enforce_bucket(
            bucket_key=f"{limiter_prefix}:ip:{client_ip}",
            max_requests=ip_attempts,
            window_seconds=self._config.login_ip_window_seconds,
        )
        normalized_identifier: str = identifier.strip().lower()
        identifier_digest: str = sha256(normalized_identifier.encode("utf-8")).hexdigest()
        await self._enforce_bucket(
            bucket_key=f"{limiter_prefix}:identifier:{identifier_digest}",
            max_requests=identifier_attempts,
            window_seconds=self._config.login_identifier_window_seconds,
        )

    async def _enforce_bucket(
        self,
        *,
        bucket_key: str,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        """消费一个限流桶请求，拒绝超限流量并在存储故障时 fail-closed。"""
        try:
            decision = await run_in_threadpool(
                self._rate_limit_store.consume,
                bucket_key,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
        except RedisError as redis_error:
            raise HTTPException(
                status_code=503,
                detail="Request protection is temporarily unavailable",
                headers={"Retry-After": "5"},
            ) from redis_error

        if not decision.is_allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(decision.retry_after_seconds)},
            )

    @staticmethod
    def _client_ip(request: Request) -> str:
        """返回 ASGI 服务器解析出的来源 IP；缺失时使用共享兜底桶。"""
        if request.client is None or not request.client.host:
            return "unknown"
        return request.client.host


__all__ = ["ApiRateLimitConfig", "ApiRateLimiter", "AuthRateLimitOperation"]
