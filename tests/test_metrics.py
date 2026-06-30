"""Tests for Prometheus metrics endpoint and middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.metrics_router import metrics_router
from backend.api.middleware.prometheus_metrics import PrometheusMetricsMiddleware


@pytest.mark.anyio
async def test_metrics_endpoint_returns_prometheus_format() -> None:
    app = FastAPI()
    app.include_router(metrics_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/metrics")

    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]


@pytest.mark.anyio
async def test_middleware_records_red_metrics() -> None:
    app = FastAPI()
    app.add_middleware(PrometheusMetricsMiddleware)
    app.include_router(metrics_router)

    @app.get("/items/{item_id}")
    def get_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/items/42")
        response = await client.get("/metrics")

    assert response.status_code == 200
    content = response.text
    assert 'http_requests_total{method="GET",path="/items/{item_id}",status="200"}' in content
    assert (
        'http_request_duration_seconds_count{method="GET",path="/items/{item_id}",status="200"}'
        in content
    )


@pytest.mark.anyio
async def test_middleware_ignores_excluded_paths() -> None:
    app = FastAPI()
    app.add_middleware(PrometheusMetricsMiddleware)
    app.include_router(metrics_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/ready")
        response = await client.get("/metrics")

    assert response.status_code == 200
    content = response.text
    assert 'http_requests_total{method="GET",path="/health"' not in content
    assert 'http_requests_total{method="GET",path="/ready"' not in content
