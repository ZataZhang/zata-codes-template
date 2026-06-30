"""Tests for request context middleware."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from backend.api.middleware.request_context import (
    _REQUEST_ID_HEADER,
    RequestContextMiddleware,
    get_request_id,
)


def test_get_request_id_returns_none_when_not_set() -> None:
    request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    assert get_request_id(request) is None


@pytest.mark.anyio
async def test_middleware_generates_request_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def handler(request: Request) -> dict[str, str | None]:
        return {"request_id": get_request_id(request)}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test")

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["request_id"]
    assert response.headers[_REQUEST_ID_HEADER] == response_data["request_id"]


@pytest.mark.anyio
async def test_middleware_propagates_request_id_from_header() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/test")
    def handler(request: Request) -> dict[str, str | None]:
        return {"request_id": get_request_id(request)}

    incoming_id = "incoming-request-id-123"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/test", headers={_REQUEST_ID_HEADER: incoming_id})

    assert response.status_code == 200
    assert response.json()["request_id"] == incoming_id
    assert response.headers[_REQUEST_ID_HEADER] == incoming_id
