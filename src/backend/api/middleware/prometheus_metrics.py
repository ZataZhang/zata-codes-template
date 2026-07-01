"""Prometheus 指标中间件。

使用路由模板作为 ``path`` 标签，为每个 HTTP 请求记录 RED
（Rate、Errors、Duration）指标，避免标签基数爆炸。
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

# 指标故意在模块导入时定义，以便重载后使用同一注册表，/metrics 端点可见。
_HTTP_REQUESTS_TOTAL: Counter = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "status", "path"],
)
_HTTP_REQUEST_DURATION_SECONDS: Histogram = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "status", "path"],
)

# 不应被记录为业务流量的路径。
_EXCLUDED_PATHS: frozenset[str] = frozenset(
    {
        "/metrics",
        "/health",
        "/ready",
        "/live",
        "/docs",
        "/openapi.json",
        "/favicon.ico",
    }
)


def _get_route_path(request: "Request") -> str:
    """返回路由模板（如 ``/auth/login``），存在时优先使用。

    仅对未注册路由回退到原始路径，以保持正常流量的标签基数较低。
    """
    route = request.scope.get("route")
    if route is not None:
        return getattr(route, "path", request.url.path)
    return request.url.path


def _should_record(request: "Request") -> bool:
    """判断该请求路径是否应计入 RED 指标。"""
    return _get_route_path(request) not in _EXCLUDED_PATHS


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """记录 RED Prometheus 指标的 FastAPI/Starlette 中间件。"""

    async def dispatch(self, request: "Request", call_next) -> "Response":
        """记录该请求的 Prometheus 指标。"""
        if not _should_record(request):
            return await call_next(request)

        start_time: float = time.perf_counter()
        status_code: int = 500

        try:
            response: "Response" = await call_next(request)
            status_code = response.status_code
            return response
        except Exception:
            status_code = 500
            raise
        finally:
            duration: float = time.perf_counter() - start_time
            labels: dict[str, str] = {
                "method": request.method,
                "status": str(status_code),
                "path": _get_route_path(request),
            }
            _HTTP_REQUESTS_TOTAL.labels(**labels).inc()
            _HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration)


__all__ = ["PrometheusMetricsMiddleware"]
