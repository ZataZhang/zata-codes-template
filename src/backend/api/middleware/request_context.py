"""请求上下文中间件。

为每个入站 HTTP 请求分配唯一的 ``request_id``，并将其注入日志上下文，
使请求期间输出的所有日志共享同一标识。
"""

from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware

from backend.shared.context import request_id_var

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

_REQUEST_ID_HEADER: str = "X-Request-ID"


def _generate_request_id() -> str:
    """生成一个简短的唯一请求标识符。"""
    return uuid.uuid4().hex[:16]


@contextmanager
def _request_context(request_id: str):
    """将 ``request_id`` 绑定到当前异步上下文。"""
    token = request_id_var.set(request_id)
    try:
        yield
    finally:
        request_id_var.reset(token)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """为每个请求分配 ``request_id`` 的 FastAPI/Starlette 中间件。"""

    def __init__(
        self,
        app,
        logger: logging.Logger | None = None,
    ) -> None:
        """使用可选日志记录器初始化中间件。

        Args:
            app: 待包装的 ASGI 应用。
            logger: 用于输出每次请求访问日志的记录器。默认使用以本模块命名的
                标准库记录器。
        """
        super().__init__(app)
        self._logger: logging.Logger = logger or logging.getLogger(__name__)

    async def dispatch(self, request: "Request", call_next) -> "Response":
        """附加或透传请求 ID 到整个请求生命周期。"""
        request_id: str = request.headers.get(_REQUEST_ID_HEADER) or _generate_request_id()
        request.state.request_id = request_id

        with _request_context(request_id):
            response: "Response" = await call_next(request)
            response.headers[_REQUEST_ID_HEADER] = request_id
            self._logger.info(
                "request handled",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                },
            )
            return response


def get_request_id(request: "Request") -> str | None:
    """返回当前请求绑定的 ``request_id``，若未设置则返回 ``None``。

    Args:
        request: 当前 HTTP 请求。

    Returns:
        str | None: 请求标识符；未设置时为 ``None``。
    """
    return getattr(request.state, "request_id", None)


__all__ = [
    "RequestContextMiddleware",
    "_REQUEST_ID_HEADER",
    "get_request_id",
]
