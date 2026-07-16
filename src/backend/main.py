"""后端进程启动与历史兼容入口。"""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from backend.composition import create_app as _create_composed_app
from backend.infrastructure.auth.redis_client import create_redis_client


def create_app() -> FastAPI:
    """通过 composition root 创建 FastAPI 应用。

    Returns:
        完成依赖装配的 FastAPI 应用。
    """

    return _create_composed_app(redis_client_factory=create_redis_client)


app: FastAPI = create_app()


def main() -> None:
    """运行后端入口。"""

    backend_port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=backend_port,
        reload=True,
    )


__all__ = ["app", "create_app", "main"]


if __name__ == "__main__":
    main()
