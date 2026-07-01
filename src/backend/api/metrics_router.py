"""Prometheus 指标端点。"""

from __future__ import annotations

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

metrics_router: APIRouter = APIRouter(tags=["observability"])


@metrics_router.get("/metrics")
async def metrics(_request: Request) -> Response:
    """返回 Prometheus  exposition 格式的应用指标。

    Returns:
        Response: Prometheus 文本格式，附带 ``Content-Type`` 头。
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


__all__ = ["metrics_router"]
