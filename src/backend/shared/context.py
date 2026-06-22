"""Cross-cutting context variables.

This module sits outside the strict layered architecture so that both HTTP
middleware (``api/``) and infrastructure utilities (``infrastructure/``) can
share request-scoped identifiers without creating a circular or reverse
dependency between layers.
"""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id", default=None
)
span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "span_id", default=None
)

__all__ = [
    "request_id_var",
    "span_id_var",
    "trace_id_var",
]
