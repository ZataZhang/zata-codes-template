"""FastAPI 应用 composition root。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI

from backend.api.admin import admin_auth_router, admin_user_router
from backend.api.agent_router import router as agent_router
from backend.api.auth_router import router as auth_router
from backend.api.health_router import health_router
from backend.api.metrics_router import metrics_router
from backend.api.middleware.prometheus_metrics import PrometheusMetricsMiddleware
from backend.api.middleware.request_context import RequestContextMiddleware
from backend.api.session_router import router as session_router
from backend.api.tool_router import router as tool_router
from backend.api.workflow_router import router as workflow_router
from backend.composition.auth_wiring import build_auth_components
from backend.composition.bootstrap import (
    run_migrations,
    seed_admin_user,
    seed_public_user,
    seed_tools,
)
from backend.composition.runtime_wiring import build_runtime_components
from backend.infrastructure.auth.redis_client import create_redis_client
from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import logger
from backend.infrastructure.persistence.database import SessionLocal


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
    fastapi_app = FastAPI(title="Zata Agent Platform API", version="0.2.0")
    database_session = SessionLocal()
    auth_components = build_auth_components(
        database_session,
        redis_client_factory,
    )
    runtime_components = build_runtime_components(database_session)

    fastapi_app.state.public_auth_service = auth_components.public_auth_service
    fastapi_app.state.admin_auth_service = auth_components.admin_auth_service
    fastapi_app.state.public_user_directory = auth_components.public_user_directory
    fastapi_app.state.agent_repository = runtime_components.agent_repository
    fastapi_app.state.session_repository = runtime_components.session_repository
    fastapi_app.state.workflow_repository = runtime_components.workflow_repository
    fastapi_app.state.tool_metadata_repository = runtime_components.tool_metadata_repository
    fastapi_app.state.tool_registry = runtime_components.tool_registry
    fastapi_app.state.llm_client = runtime_components.llm_client

    seed_tools()
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
        agent_router,
        session_router,
        workflow_router,
        tool_router,
        health_router,
    ):
        fastapi_app.include_router(api_router)

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
