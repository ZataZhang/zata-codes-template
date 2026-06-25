"Backend application entrypoint."

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from backend.api.agent_router import router as agent_router
from backend.api.auth_router import router as auth_router
from backend.api.health_router import health_router
from backend.api.metrics_router import metrics_router
from backend.api.middleware.prometheus_metrics import PrometheusMetricsMiddleware
from backend.api.middleware.request_context import RequestContextMiddleware
from backend.api.session_router import router as session_router
from backend.api.tool_router import router as tool_router
from backend.api.workflow_router import router as workflow_router
from backend.core.use_cases.auth import AuthUseCase
from backend.infrastructure.auth.memory_session_store import InMemorySessionStore
from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import logger
from backend.infrastructure.models.llm_client import LangChainLLMClient
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.tool import ToolModel
from backend.infrastructure.persistence.repos.agent_repo import (
    SqlAlchemyAgentRepository,
)
from backend.infrastructure.persistence.repos.session_repo import (
    SqlAlchemySessionRepository,
)
from backend.infrastructure.persistence.repos.tool_repo import SqlAlchemyToolRepository
from backend.infrastructure.persistence.repos.workflow_repo import (
    SqlAlchemyWorkflowRepository,
)
from backend.engines.skills.registry.tool_registry import ToolRegistryImpl


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
                    "properties": {
                        "query": {"type": "string", "description": "搜索关键词"}
                    },
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


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(title="Zata Agent Platform API", version="0.2.0")

    session_store = InMemorySessionStore()
    auth_use_case = AuthUseCase(session_store=session_store)
    app.state.auth_use_case = auth_use_case

    db_session = SessionLocal()
    app.state.agent_repository = SqlAlchemyAgentRepository(db_session)
    app.state.session_repository = SqlAlchemySessionRepository(db_session)
    app.state.workflow_repository = SqlAlchemyWorkflowRepository(db_session)
    app.state.tool_metadata_repository = SqlAlchemyToolRepository(db_session)
    app.state.tool_registry = ToolRegistryImpl(
        tool_repository=SqlAlchemyToolRepository(db_session)
    )
    app.state.llm_client = LangChainLLMClient()

    _seed_tools()

    app.include_router(auth_router)
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
    """Run the backend entrypoint."""
    backend_port: int = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=backend_port, reload=True)


if __name__ == "__main__":
    main()
