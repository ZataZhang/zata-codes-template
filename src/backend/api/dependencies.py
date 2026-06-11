"""FastAPI 依赖注入。"""

from __future__ import annotations

from fastapi import Request

from backend.core.use_cases.auth import AuthUseCase


def get_auth_use_case(request: Request) -> AuthUseCase:
    """从应用状态中获取认证用例实例。"""
    return request.app.state.auth_use_case


def get_session_token(request: Request) -> str | None:
    """从请求 Cookie 中提取 session token。"""
    return request.cookies.get("session_id")
