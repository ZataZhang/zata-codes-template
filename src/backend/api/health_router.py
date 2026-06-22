"""Health, readiness, and liveness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

health_router: APIRouter = APIRouter(tags=["observability"])


@health_router.get("/health")
async def health(_request: Request) -> dict[str, str]:
    """Liveness probe: the process is running and can respond to requests.

    Returns:
        dict[str, str]: Simple status payload.
    """
    return {"status": "ok"}


@health_router.get("/ready")
async def ready(_request: Request) -> dict[str, str]:
    """Readiness probe: the process is ready to serve traffic.

    This basic implementation returns OK immediately. Future iterations can
    check database connectivity or other critical dependencies here.

    Returns:
        dict[str, str]: Simple status payload.
    """
    return {"status": "ok"}


@health_router.get("/live")
async def live(_request: Request) -> dict[str, str]:
    """Alternative liveness probe, identical to ``/health``.

    Returns:
        dict[str, str]: Simple status payload.
    """
    return {"status": "ok"}


__all__ = ["health_router"]
