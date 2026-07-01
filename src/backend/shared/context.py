"""横切上下文变量。

本模块位于严格分层架构之外，使 HTTP 中间件（``api/``）和基础设施工具
（``infrastructure/``）都能共享请求级标识，同时避免层间产生循环或反向依赖。
"""

from __future__ import annotations

import contextvars

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)

__all__ = [
    "request_id_var",
    "span_id_var",
    "trace_id_var",
]
