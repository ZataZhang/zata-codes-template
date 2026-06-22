"""Prometheus metrics endpoint."""

from __future__ import annotations

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

metrics_router: APIRouter = APIRouter(tags=["observability"])


@metrics_router.get("/metrics")
async def metrics(_request: Request) -> Response:
    """Return application metrics in Prometheus exposition format.

    Returns:
        Response: Prometheus text format with ``Content-Type`` header.
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


__all__ = ["metrics_router"]
