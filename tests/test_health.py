"""Tests for health, readiness, and liveness endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.health_router import health_router
from backend.main import create_app


@pytest.mark.anyio
async def test_health_endpoints_return_ok() -> None:
    app = create_app()
    app.include_router(health_router)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health_response = await client.get("/health")
        ready_response = await client.get("/ready")
        live_response = await client.get("/live")

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ok"}
    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}
