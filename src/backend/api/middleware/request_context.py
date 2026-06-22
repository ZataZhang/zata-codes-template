"""Request context middleware.

Provides a unique ``request_id`` for every incoming HTTP request and injects it
into the logging context so that all log records emitted during the request
share the same identifier.
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
    """Generate a short, unique request identifier."""
    return uuid.uuid4().hex[:16]


@contextmanager
def _request_context(request_id: str):
    """Bind ``request_id`` to the current async context."""
    token = request_id_var.set(request_id)
    try:
        yield
    finally:
        request_id_var.reset(token)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware that assigns a ``request_id`` per request."""

    def __init__(
        self,
        app,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the middleware with an optional logger.

        Args:
            app: The ASGI application to wrap.
            logger: Logger used to emit the per-request access log. Defaults to
                a standard library logger named after this module.
        """
        super().__init__(app)
        self._logger: logging.Logger = logger or logging.getLogger(__name__)

    async def dispatch(self, request: "Request", call_next) -> "Response":
        request_id: str = (
            request.headers.get(_REQUEST_ID_HEADER) or _generate_request_id()
        )
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
    """Return the ``request_id`` bound to the request, if any.

    Args:
        request: The current HTTP request.

    Returns:
        str | None: The request identifier or ``None`` if not set.
    """
    return getattr(request.state, "request_id", None)


__all__ = [
    "RequestContextMiddleware",
    "_REQUEST_ID_HEADER",
    "get_request_id",
]
