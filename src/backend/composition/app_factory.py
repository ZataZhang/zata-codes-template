"""FastAPI 应用 composition root。"""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings

from backend.api.admin import admin_auth_router, admin_user_router, run_trace_router
from backend.api.auth_router import router as auth_router
from backend.api.health_router import health_router
from backend.api.metrics_router import metrics_router
from backend.api.middleware.prometheus_metrics import PrometheusMetricsMiddleware
from backend.api.middleware.request_context import RequestContextMiddleware
from backend.composition.auth_wiring import build_auth_components
from backend.composition.bootstrap import run_migrations, seed_admin_user, seed_public_user
from backend.composition.run_tracing_wiring import build_run_tracing_components
from backend.engines.mcp.server import create_mcp_server
from backend.infrastructure.auth.redis_client import create_redis_client
from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import logger
from backend.infrastructure.persistence.database import SessionLocal


def _load_project_version() -> str:
    """从 pyproject.toml 读取项目版本号（版本单一来源，避免在代码中重复维护）。"""

    pyproject_path: Path = Path(__file__).resolve().parents[3] / "pyproject.toml"
    try:
        with open(pyproject_path, "rb") as pyproject_file:
            pyproject_data: dict[str, Any] = tomllib.load(pyproject_file)
        project_section: Any = pyproject_data.get("project", {})
        if isinstance(project_section, dict) and project_section.get("version"):
            return str(project_section["version"])
    except (OSError, tomllib.TOMLDecodeError):
        pass
    return "0.0.0"


def create_app(
    redis_client_factory: Callable[[str], Any] = create_redis_client,
) -> FastAPI:
    """创建并配置 FastAPI 应用。

    Args:
        redis_client_factory: Redis 客户端工厂，测试可注入进程内替身。

    Returns:
        完成路由、中间件和运行依赖装配的 FastAPI 应用。
    """

    run_migrations()
    project_version = _load_project_version()
    mcp_server = create_mcp_server(app_name=config.app_name, app_version=project_version)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """在应用生命周期内启动 MCP Streamable HTTP 管理器。"""

        async with mcp_server.session_manager.run():
            yield

    fastapi_app = FastAPI(
        title=config.app_name,
        version=project_version,
        lifespan=lifespan,
    )
    session_factory = SessionLocal
    auth_components = build_auth_components(
        session_factory,
        redis_client_factory,
    )

    fastapi_app.state.public_auth_service = auth_components.public_auth_service
    fastapi_app.state.admin_auth_service = auth_components.admin_auth_service
    fastapi_app.state.public_user_directory = auth_components.public_user_directory

    run_tracing_components = build_run_tracing_components(session_factory)
    fastapi_app.state.run_trace_use_case = run_tracing_components.run_trace_use_case

    seed_admin_user(
        auth_components.admin_user_repository,
        auth_components.password_hasher,
    )
    seed_public_user(
        auth_components.public_user_repository,
        auth_components.password_hasher,
    )

    for api_router in (
        auth_router,
        admin_auth_router,
        admin_user_router,
        run_trace_router,
        health_router,
    ):
        fastapi_app.include_router(api_router)

    fastapi_app.mount(
        "/api/mcp",
        mcp_server.streamable_http_app(
            streamable_http_path="/",
            json_response=True,
            stateless_http=True,
            transport_security=TransportSecuritySettings(
                allowed_hosts=config.mcp.allowed_hosts,
                allowed_origins=config.mcp.allowed_origins,
            ),
        ),
        name="mcp",
    )

    observability_settings = config.observability
    if observability_settings.enabled:
        if observability_settings.request_id_enabled:
            fastapi_app.add_middleware(
                RequestContextMiddleware,
                logger=logger.get_logger(),
            )
        if observability_settings.metrics_enabled:
            fastapi_app.add_middleware(PrometheusMetricsMiddleware)
            fastapi_app.include_router(metrics_router)

    return fastapi_app


__all__ = ["create_app"]
