"""FastAPI 应用 composition root。"""

from __future__ import annotations

import asyncio
import tomllib
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI
from mcp.server.transport_security import TransportSecuritySettings
from zata_oidc import HttpOidcClient, OidcAuthenticationError, OidcClientSettings

from backend.api.a2a_router import router as a2a_router
from backend.api.admin import (
    admin_auth_router,
    admin_directory_router,
    admin_user_router,
    agent_admin_router,
    organization_router,
    registration_policy_router,
    run_trace_router,
)
from backend.api.agent_router import router as agent_router
from backend.api.auth_router import router as auth_router
from backend.api.health_router import health_router
from backend.api.metrics_router import metrics_router
from backend.api.middleware.api_rate_limit import ApiRateLimitMiddleware
from backend.api.middleware.prometheus_metrics import PrometheusMetricsMiddleware
from backend.api.middleware.request_body_limit import RequestBodyLimitMiddleware
from backend.api.middleware.request_context import RequestContextMiddleware
from backend.api.security.rate_limiter import ApiRateLimitConfig, ApiRateLimiter
from backend.composition.agent_wiring import build_agent_components
from backend.composition.auth_wiring import build_auth_components
from backend.composition.bootstrap import run_migrations, seed_admin_user, seed_public_user
from backend.composition.run_tracing_wiring import build_run_tracing_components
from backend.core.auth.admin_directory import AdminDirectory
from backend.core.auth.organization_directory import OrganizationDirectory
from backend.engines.mcp.server import create_mcp_server
from backend.infrastructure.auth.redis_client import create_redis_client
from backend.infrastructure.auth.redis_oidc_transaction_store import (
    RedisOidcTransactionStore,
)
from backend.infrastructure.config.providers import (
    build_config_provider,
)
from backend.infrastructure.config.settings import config, startup_runtime_config
from backend.infrastructure.logger import logger
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.security.redis_rate_limit_store import RedisRateLimitStore


def _close_oidc_gateways(fastapi_app: FastAPI) -> None:
    """关闭应用装配的 OIDC HTTP 客户端。"""
    for state_attribute in ("admin_oidc_gateway", "public_oidc_gateway"):
        oidc_gateway = getattr(fastapi_app.state, state_attribute, None)
        close_gateway = getattr(oidc_gateway, "close", None)
        if callable(close_gateway):
            close_gateway()


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
    mcp_server = (
        create_mcp_server(app_name=config.app_name, app_version=project_version)
        if config.mcp.enabled
        else None
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        """在应用生命周期内暴露启动快照并启动 MCP 管理器。"""
        if config.config_provider.provider == "nacos" or config.config_provider.nacos_server_addr:
            _app.state.runtime_config = dict(startup_runtime_config)
        else:
            config_provider = build_config_provider(
                config.config_provider,
                config_file_path=config.base_dir / "config.toml",
            )
            try:
                _app.state.runtime_config = dict(await config_provider.load())
            finally:
                await config_provider.close()
        async def monitor_agent_runs() -> None:
            """恢复过期 Run 队列并收敛已失去执行租约的 Run。"""
            while True:
                agent_components.runs.recover_expired_runs()
                await asyncio.sleep(5)

        run_monitor_task = asyncio.create_task(monitor_agent_runs())
        if mcp_server is not None:
            try:
                async with mcp_server.session_manager.run():
                    yield
            finally:
                run_monitor_task.cancel()
                try:
                    await run_monitor_task
                except asyncio.CancelledError:
                    pass
                _close_oidc_gateways(_app)
        else:
            try:
                yield
            finally:
                run_monitor_task.cancel()
                try:
                    await run_monitor_task
                except asyncio.CancelledError:
                    pass
                _close_oidc_gateways(_app)

    fastapi_app = FastAPI(
        title=config.app_name,
        version=project_version,
        lifespan=lifespan,
    )
    fastapi_app.state.runtime_config = {}
    fastapi_app.state.auth_cookie_secure = config.auth.cookie_secure
    session_factory = SessionLocal
    redis_client = redis_client_factory(config.redis.url)
    auth_components = build_auth_components(
        session_factory,
        redis_client,
    )
    api_rate_limiter = ApiRateLimiter(
        rate_limit_store=RedisRateLimitStore(redis_client),
        config=ApiRateLimitConfig(
            enabled=config.security.rate_limit_enabled,
            api_requests_per_minute=config.security.api_requests_per_minute,
            public_login_ip_attempts=config.security.public_login_ip_attempts,
            public_login_identifier_attempts=config.security.public_login_identifier_attempts,
            admin_login_ip_attempts=config.security.admin_login_ip_attempts,
            admin_login_identifier_attempts=config.security.admin_login_identifier_attempts,
            login_ip_window_seconds=config.security.login_ip_window_seconds,
            login_identifier_window_seconds=config.security.login_identifier_window_seconds,
            register_ip_attempts=config.security.register_ip_attempts,
            register_window_seconds=config.security.register_window_seconds,
        ),
    )
    fastapi_app.state.api_rate_limiter = api_rate_limiter
    fastapi_app.add_middleware(
        RequestBodyLimitMiddleware,
        max_body_bytes=config.security.request_body_max_bytes,
    )
    fastapi_app.add_middleware(ApiRateLimitMiddleware, rate_limiter=api_rate_limiter)

    fastapi_app.state.public_auth_service = auth_components.public_auth_service
    fastapi_app.state.admin_auth_service = auth_components.admin_auth_service
    fastapi_app.state.public_user_directory = auth_components.public_user_directory
    fastapi_app.state.registration_policy_service = auth_components.registration_policy_service
    fastapi_app.state.admin_user_repository = auth_components.admin_user_repository
    fastapi_app.state.public_user_repository = auth_components.public_user_repository
    fastapi_app.state.admin_session_store = auth_components.admin_session_store
    fastapi_app.state.public_session_store = auth_components.public_session_store
    fastapi_app.state.password_hasher = auth_components.password_hasher
    fastapi_app.state.admin_oidc_transaction_store = RedisOidcTransactionStore(
        redis_client=redis_client,
        key_prefix="oidc:txn:admin:",
    )
    fastapi_app.state.public_oidc_transaction_store = RedisOidcTransactionStore(
        redis_client=redis_client,
        key_prefix="oidc:txn:public:",
    )
    admin_oidc_gateway = None
    if config.admin_oidc.is_configured:
        try:
            admin_oidc_gateway = HttpOidcClient(
                OidcClientSettings(
                    issuer=config.admin_oidc.issuer,
                    client_id=config.admin_oidc.client_id,
                    client_secret=config.admin_oidc.client_secret.get_secret_value(),
                    callback_uri=config.admin_oidc.callback_uri,
                )
            )
        except OidcAuthenticationError as oidc_error:
            logger.warning(
                "auth.oidc outcome=unavailable portal=admin reason=%s",
                oidc_error.reason.value,
            )
    else:
        logger.info("auth.oidc outcome=unavailable portal=admin reason=configuration_incomplete")
    fastapi_app.state.admin_oidc_gateway = admin_oidc_gateway
    fastapi_app.state.admin_oidc_enabled = admin_oidc_gateway is not None

    public_oidc_gateway = None
    if config.user_oidc.is_configured:
        try:
            public_oidc_gateway = HttpOidcClient(
                OidcClientSettings(
                    issuer=config.user_oidc.issuer,
                    client_id=config.user_oidc.client_id,
                    client_secret=config.user_oidc.client_secret.get_secret_value(),
                    callback_uri=config.user_oidc.callback_uri,
                )
            )
        except OidcAuthenticationError as oidc_error:
            logger.warning(
                "auth.oidc outcome=unavailable portal=public reason=%s",
                oidc_error.reason.value,
            )
    else:
        logger.info("auth.oidc outcome=unavailable portal=public reason=configuration_incomplete")
    fastapi_app.state.public_oidc_gateway = public_oidc_gateway
    fastapi_app.state.public_oidc_enabled = public_oidc_gateway is not None
    fastapi_app.state.registration_policy_service = auth_components.registration_policy_service
    fastapi_app.state.system_setting_repository = auth_components.system_setting_repository

    organization_repository = auth_components.organization_repository
    fastapi_app.state.organization_directory = OrganizationDirectory(organization_repository)
    fastapi_app.state.admin_directory = AdminDirectory(
        admin_repository=auth_components.admin_user_repository,
        organization_repository=organization_repository,
        password_hasher=auth_components.password_hasher,
        oidc_enabled=admin_oidc_gateway is not None,
    )

    run_tracing_components = build_run_tracing_components(session_factory)
    fastapi_app.state.run_trace_use_case = run_tracing_components.run_trace_use_case
    agent_components = build_agent_components(
        session_factory,
        run_tracing_components.run_repository,
    )
    fastapi_app.state.agent_catalog_use_case = agent_components.catalog
    fastapi_app.state.skill_use_case = agent_components.skills
    fastapi_app.state.agent_run_use_case = agent_components.runs

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
        admin_directory_router,
        admin_user_router,
        organization_router,
        registration_policy_router,
        run_trace_router,
        agent_admin_router,
        agent_router,
        a2a_router,
        health_router,
    ):
        fastapi_app.include_router(api_router)

    if mcp_server is not None:
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
