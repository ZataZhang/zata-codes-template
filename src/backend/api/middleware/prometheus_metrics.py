"""Prometheus metrics middleware.

Records RED (Rate, Errors, Duration) metrics for every HTTP request using
route templates as the ``path`` label to avoid cardinality explosion.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

# Metrics are intentionally defined at module import time so that the same
# registry is used across reloads and the /metrics endpoint sees them.
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

# Paths that should not be recorded as business traffic.
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
    """Return the route template (e.g. ``/auth/login``) when available.

    Falls back to the raw path only for unregistered routes, which keeps
    cardinality low for normal traffic.
    """
    route = request.scope.get("route")
    if route is not None:
        return getattr(route, "path", request.url.path)
    return request.url.path


def _should_record(request: "Request") -> bool:
    """Return whether the request path should contribute to RED metrics."""
    return _get_route_path(request) not in _EXCLUDED_PATHS


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that records RED Prometheus metrics."""

    async def dispatch(self, request: "Request", call_next) -> "Response":
        """Record Prometheus metrics for the request."""
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
