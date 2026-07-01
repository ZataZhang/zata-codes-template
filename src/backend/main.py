"""后端应用入口。"""

from __future__ import annotations

import os
import uuid

import uvicorn
from fastapi import FastAPI

from alembic import command
from alembic.config import Config
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
from backend.core.auth.directory import PublicUserDirectory
from backend.core.auth.models import AuthDomain
from backend.core.auth.service import AuthService
from backend.core.shared.models.user_account import UserAccount
from backend.engines.skills.registry.tool_registry import ToolRegistryImpl
from backend.infrastructure.auth.bcrypt_password_hasher import BcryptPasswordHasher
from backend.infrastructure.auth.redis_client import create_redis_client
from backend.infrastructure.auth.redis_session_store import RedisSessionStore
from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import logger
from backend.infrastructure.models.llm_client import LangChainLLMClient
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.admin_user import AdminUserModel
from backend.infrastructure.persistence.models.public_user import PublicUserModel
from backend.infrastructure.persistence.models.tool import ToolModel
from backend.infrastructure.persistence.repos.agent_repo import (
    SqlAlchemyAgentRepository,
)
from backend.infrastructure.persistence.repos.session_repo import (
    SqlAlchemySessionRepository,
)
from backend.infrastructure.persistence.repos.tool_repo import SqlAlchemyToolRepository
from backend.infrastructure.persistence.repos.user_account_repo import (
    SqlAlchemyUserAccountRepository,
)
from backend.infrastructure.persistence.repos.workflow_repo import (
    SqlAlchemyWorkflowRepository,
)

_PUBLIC_SESSION_PREFIX: str = "public:session:"
_ADMIN_SESSION_PREFIX: str = "admin:session:"


def _run_migrations() -> None:
    """启动时自动执行 Alembic 迁移到最新版本。"""
    alembic_ini_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "alembic.ini",
    )
    alembic_cfg = Config(alembic_ini_path)
    command.upgrade(alembic_cfg, "head")


def _seed_tools() -> None:
    """MVP 阶段预置工具种子数据。"""
    db_session = SessionLocal()
    try:
        existing = db_session.query(ToolModel).first()
        if existing is not None:
            return

        seed_tools = [
            ToolModel(
                id="web_search",
                name="网页搜索",
                description="通过关键词搜索网页并返回摘要结果。",
                handler_path="backend.engines.skills.tools.web_search",
                schema={
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "搜索关键词"}},
                    "required": ["query"],
                },
            ),
            ToolModel(
                id="code_runner",
                name="代码执行",
                description="执行一段代码并返回运行结果。",
                handler_path="backend.engines.skills.tools.code_runner",
                schema={
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "代码内容"},
                        "language": {"type": "string", "description": "编程语言"},
                    },
                    "required": ["code"],
                },
            ),
        ]
        for tool in seed_tools:
            db_session.add(tool)
        db_session.commit()
    finally:
        db_session.close()


def _seed_admin_user(
    admin_repository: SqlAlchemyUserAccountRepository,
    password_hasher: BcryptPasswordHasher,
) -> None:
    """根据环境变量幂等创建初始管理员。

    仅当配置了 ``AUTH_ADMIN_BOOTSTRAP_USERNAME`` 与 ``AUTH_ADMIN_BOOTSTRAP_PASSWORD``
    且该用户名尚不存在时创建；凭据来自环境变量，库中只保存 bcrypt 哈希。

    Args:
        admin_repository (SqlAlchemyUserAccountRepository): admin 域用户仓库。
        password_hasher (BcryptPasswordHasher): 密码哈希实现。
    """
    bootstrap_username: str = config.auth.admin_bootstrap_username.strip()
    bootstrap_password: str = config.auth.admin_bootstrap_password.get_secret_value()
    if not bootstrap_username or not bootstrap_password:
        logger.info("未配置 AUTH_ADMIN_BOOTSTRAP_*，跳过初始管理员种子。")
        return

    normalized_username: str = bootstrap_username.lower()
    if admin_repository.find_by_identifier(normalized_username) is not None:
        return

    admin_repository.create(
        UserAccount(
            id=uuid.uuid4().hex,
            identifier=normalized_username,
            display_name=bootstrap_username,
            password_hash=password_hasher.hash(bootstrap_password),
            is_active=True,
        )
    )
    logger.info("已创建初始管理员：%s", normalized_username)


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    _run_migrations()

    app = FastAPI(title="Zata Agent Platform API", version="0.2.0")

    # 业务与认证复用同一数据库会话（与既有装配一致）
    db_session = SessionLocal()

    # --- 认证：两域独立装配（独立用户表 + 独立 Redis 会话命名空间）---
    redis_client = create_redis_client(config.redis.url)
    password_hasher = BcryptPasswordHasher()

    public_user_repository = SqlAlchemyUserAccountRepository(
        session=db_session,
        model_class=PublicUserModel,
        identifier_attr="email",
    )
    admin_user_repository = SqlAlchemyUserAccountRepository(
        session=db_session,
        model_class=AdminUserModel,
        identifier_attr="username",
    )
    public_session_store = RedisSessionStore(
        redis_client=redis_client,
        key_prefix=_PUBLIC_SESSION_PREFIX,
        sliding_window_days=config.auth.session_sliding_days,
        absolute_max_days=config.auth.session_absolute_days,
    )
    admin_session_store = RedisSessionStore(
        redis_client=redis_client,
        key_prefix=_ADMIN_SESSION_PREFIX,
        sliding_window_days=config.auth.session_sliding_days,
        absolute_max_days=config.auth.session_absolute_days,
    )
    app.state.public_auth_service = AuthService(
        domain=AuthDomain.PUBLIC,
        repository=public_user_repository,
        session_store=public_session_store,
        password_hasher=password_hasher,
        allow_registration=True,
    )
    app.state.admin_auth_service = AuthService(
        domain=AuthDomain.ADMIN,
        repository=admin_user_repository,
        session_store=admin_session_store,
        password_hasher=password_hasher,
        allow_registration=False,
    )
    app.state.public_user_directory = PublicUserDirectory(public_repository=public_user_repository)

    # --- 业务仓库与能力（复用同一会话）---
    app.state.agent_repository = SqlAlchemyAgentRepository(db_session)
    app.state.session_repository = SqlAlchemySessionRepository(db_session)
    app.state.workflow_repository = SqlAlchemyWorkflowRepository(db_session)
    app.state.tool_metadata_repository = SqlAlchemyToolRepository(db_session)
    app.state.tool_registry = ToolRegistryImpl(tool_repository=SqlAlchemyToolRepository(db_session))
    app.state.llm_client = LangChainLLMClient()

    _seed_tools()
    _seed_admin_user(admin_user_repository, password_hasher)

    app.include_router(auth_router)
    app.include_router(admin_auth_router)
    app.include_router(admin_user_router)
    app.include_router(agent_router)
    app.include_router(session_router)
    app.include_router(workflow_router)
    app.include_router(tool_router)
    app.include_router(health_router)

    observability = config.observability
    if observability.enabled:
        if observability.request_id_enabled:
            app.add_middleware(RequestContextMiddleware, logger=logger.get_logger())
        if observability.metrics_enabled:
            app.add_middleware(PrometheusMetricsMiddleware)
            app.include_router(metrics_router)

    return app


app: FastAPI = create_app()


def main() -> None:
    """运行后端入口。"""
    backend_port: int = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=backend_port, reload=True)


if __name__ == "__main__":
    main()
