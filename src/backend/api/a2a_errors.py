"""A2A HTTP+JSON/REST 错误响应适配。"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
)
from fastapi.exception_handlers import (
    request_validation_exception_handler as default_request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse, Response

_A2A_ERROR_REASONS = {
    "task_not_found": "TASK_NOT_FOUND",
    "task_not_subscribable": "UNSUPPORTED_OPERATION",
    "unsupported_a2a_version": "VERSION_NOT_SUPPORTED",
}

_A2A_FIELD_VIOLATIONS = {
    "invalid_page_token": [{"field": "pageToken", "description": "Must be a valid page token."}],
    "invalid_task_status": [{"field": "status", "description": "Must be a supported task state."}],
    "message_id_required": [
        {"field": "message.messageId", "description": "A non-empty message ID is required."}
    ],
    "text_message_required": [
        {"field": "message.parts", "description": "At least one supported text part is required."}
    ],
    "user_message_required": [
        {"field": "message.role", "description": "The message role must be ROLE_USER."}
    ],
}

_HTTP_TO_GOOGLE_STATUS = {
    400: "INVALID_ARGUMENT",
    401: "UNAUTHENTICATED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    405: "UNIMPLEMENTED",
    409: "ABORTED",
    413: "RESOURCE_EXHAUSTED",
    415: "INVALID_ARGUMENT",
    422: "INVALID_ARGUMENT",
    429: "RESOURCE_EXHAUSTED",
    500: "INTERNAL",
    501: "UNIMPLEMENTED",
    502: "UNAVAILABLE",
    503: "UNAVAILABLE",
    504: "UNAVAILABLE",
}


def _is_a2a_request(request: Request) -> bool:
    """判断请求是否属于独立 A2A 协议入口。"""
    return request.url.path.startswith("/a2a/")


def _error_message(http_status_code: int) -> str:
    """返回不泄露内部数据的 A2A 错误提示。"""
    return {
        400: "The A2A request is invalid or uses an unsupported protocol version.",
        401: "The A2A credentials are missing or invalid.",
        403: "The A2A client is not authorized for this operation.",
        404: "The requested resource does not exist or is not accessible.",
        409: "The Agent cannot accept this request in its current state.",
        422: "The A2A request contains invalid parameters.",
        503: "The A2A service is temporarily unavailable.",
    }.get(http_status_code, "The A2A request could not be completed.")


def _a2a_error_document(
    *,
    http_status_code: int,
    detail_code: str | None = None,
    field_violations: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """构造 A2A REST binding 规定的 google.rpc.Status JSON 文档。"""
    error_details: list[dict[str, Any]] = []
    if field_violations is None:
        field_violations = _A2A_FIELD_VIOLATIONS.get(detail_code or "")
    if field_violations:
        error_details.append(
            {
                "@type": "type.googleapis.com/google.rpc.BadRequest",
                "fieldViolations": field_violations,
            }
        )
    error_reason = _A2A_ERROR_REASONS.get(detail_code or "")
    if error_reason:
        error_details.append(
            {
                "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                "reason": error_reason,
                "domain": "a2a-protocol.org",
            }
        )

    return {
        "error": {
            "code": http_status_code,
            "status": _HTTP_TO_GOOGLE_STATUS.get(http_status_code, "UNKNOWN"),
            "message": _error_message(http_status_code),
            "details": error_details,
        }
    }


def _validation_field_violations(
    validation_errors: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """将请求校验错误转换为不包含用户输入值的字段说明。"""
    field_violations: list[dict[str, str]] = []
    for validation_error in validation_errors:
        location_parts = [
            str(location_part)
            for location_part in validation_error.get("loc", ())
            if str(location_part) not in {"body", "query", "path", "header"}
        ]
        field_violations.append(
            {
                "field": ".".join(location_parts) or "request",
                "description": "Invalid value.",
            }
        )
    return field_violations


async def handle_a2a_http_exception(
    request: Request,
    exception: StarletteHTTPException,
) -> Response:
    """为 A2A 路径返回规范错误，其余路径沿用 FastAPI 默认响应。

    Args:
        request (Request): 当前 HTTP 请求。
        exception (StarletteHTTPException): 路由或框架产生的 HTTP 错误。

    Returns:
        Response: A2A 错误文档或 FastAPI 默认错误响应。
    """
    if not _is_a2a_request(request):
        return await default_http_exception_handler(request, exception)

    detail_code = exception.detail if isinstance(exception.detail, str) else None
    response_headers = dict(exception.headers or {})
    if exception.status_code == 401:
        response_headers.setdefault("WWW-Authenticate", "Bearer")
    return JSONResponse(
        status_code=exception.status_code,
        content=_a2a_error_document(
            http_status_code=exception.status_code,
            detail_code=detail_code,
        ),
        headers=response_headers,
    )


async def handle_a2a_validation_exception(
    request: Request,
    exception: RequestValidationError,
) -> Response:
    """将 A2A 请求校验错误转换为 REST binding 错误文档。

    Args:
        request (Request): 当前 HTTP 请求。
        exception (RequestValidationError): FastAPI 收集到的输入校验错误。

    Returns:
        Response: A2A 错误文档或 FastAPI 默认错误响应。
    """
    if not _is_a2a_request(request):
        return await default_request_validation_exception_handler(request, exception)

    return JSONResponse(
        status_code=422,
        content=_a2a_error_document(
            http_status_code=422,
            field_violations=_validation_field_violations(exception.errors()),
        ),
    )


def register_a2a_error_handlers(fastapi_app: FastAPI) -> None:
    """为应用注册 A2A REST 错误适配器。

    Args:
        fastapi_app (FastAPI): 要注册错误适配器的 FastAPI 应用。

    Returns:
        None: 完成错误处理器注册。
    """
    fastapi_app.add_exception_handler(StarletteHTTPException, handle_a2a_http_exception)
    fastapi_app.add_exception_handler(RequestValidationError, handle_a2a_validation_exception)
