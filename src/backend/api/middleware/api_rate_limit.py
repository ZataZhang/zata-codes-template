"""FastAPI 通用 API 速率限制中间件。"""

from __future__ import annotations

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from backend.api.security.rate_limiter import ApiRateLimiter


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    """在进入路由处理前限制单个来源的请求频率。"""

    def __init__(self, app: ASGIApp, *, rate_limiter: ApiRateLimiter) -> None:
        """初始化中间件。

        Args:
            app: 下游 ASGI 应用。
            rate_limiter (ApiRateLimiter): 共享限流策略执行器。
        """
        super().__init__(app)
        self._rate_limiter = rate_limiter

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """超限时直接返回 429，避免请求进入业务路由。"""
        try:
            await self._rate_limiter.check_request(request)
        except HTTPException as rate_limit_error:
            return JSONResponse(
                status_code=rate_limit_error.status_code,
                content={"detail": rate_limit_error.detail},
                headers=rate_limit_error.headers,
            )
        return await call_next(request)


__all__ = ["ApiRateLimitMiddleware"]
