"""Backend application entrypoint."""

from __future__ import annotations

import os

import uvicorn
from fastapi import FastAPI

from backend.api.auth_router import router as auth_router
from backend.core.use_cases.auth import AuthUseCase
from backend.infrastructure.auth.memory_session_store import InMemorySessionStore


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用。"""
    app = FastAPI(title="Zata Codes Template API", version="0.1.0")

    session_store = InMemorySessionStore()
    auth_use_case = AuthUseCase(session_store=session_store)
    app.state.auth_use_case = auth_use_case

    app.include_router(auth_router)
    return app


app: FastAPI = create_app()


def main() -> None:
    """Run the backend entrypoint."""
    backend_port: int = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host="0.0.0.0", port=backend_port, reload=True)


if __name__ == "__main__":
    main()
