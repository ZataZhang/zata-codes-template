"""健康、就绪和存活探针端点。"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.requests import Request

health_router: APIRouter = APIRouter(tags=["observability"])


@health_router.get("/health")
async def health(_request: Request) -> dict[str, str]:
    """存活探针：进程正在运行并可响应请求。

    Returns:
        dict[str, str]: 简单状态负载。
    """
    return {"status": "ok"}


@health_router.get("/ready")
async def ready(_request: Request) -> dict[str, str]:
    """就绪探针：进程已准备好对外提供服务。

    当前基础实现直接返回 OK。后续可在此检查数据库连接等关键依赖。

    Returns:
        dict[str, str]: 简单状态负载。
    """
    return {"status": "ok"}


@health_router.get("/live")
async def live(_request: Request) -> dict[str, str]:
    """替代存活探针，与 ``/health`` 行为一致。

    Returns:
        dict[str, str]: 简单状态负载。
    """
    return {"status": "ok"}


__all__ = ["health_router"]
