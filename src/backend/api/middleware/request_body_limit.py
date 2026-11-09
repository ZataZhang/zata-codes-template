"""限制 HTTP 请求体大小的 ASGI 中间件。"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_BODY_TOO_LARGE_RESPONSE: bytes = b'{"detail":"Request body too large"}'
_INVALID_LENGTH_RESPONSE: bytes = b'{"detail":"Invalid Content-Length"}'


class RequestBodyLimitMiddleware:
    """在读取请求体时限制内存与解析器可接收的数据量。"""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        """初始化请求体大小中间件。

        Args:
            app (ASGIApp): 下游 ASGI 应用。
            max_body_bytes (int): 单个请求允许的最大请求体字节数。
        """
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """先在有界缓冲区内读取请求体，再交给下游 ASGI 应用。

        Args:
            scope (Scope): ASGI 连接作用域。
            receive (Receive): ASGI 请求消息接收器。
            send (Send): ASGI 响应消息发送器。
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        content_length_header: bytes | None = next(
            (
                header_value
                for header_name, header_value in scope.get("headers", [])
                if header_name.lower() == b"content-length"
            ),
            None,
        )
        if content_length_header is not None:
            try:
                declared_body_bytes: int = int(content_length_header)
            except ValueError:
                await self._send_error(send, status_code=400, body=_INVALID_LENGTH_RESPONSE)
                return
            if declared_body_bytes < 0:
                await self._send_error(send, status_code=400, body=_INVALID_LENGTH_RESPONSE)
                return
            if declared_body_bytes > self._max_body_bytes:
                await self._send_error(send, status_code=413, body=_BODY_TOO_LARGE_RESPONSE)
                return

        request_body_buffer: bytearray = bytearray()
        while True:
            request_message: Message = await receive()
            if request_message["type"] == "http.disconnect":
                return
            if request_message["type"] != "http.request":
                continue

            body_chunk: bytes = request_message.get("body", b"")
            if len(request_body_buffer) + len(body_chunk) > self._max_body_bytes:
                await self._send_error(send, status_code=413, body=_BODY_TOO_LARGE_RESPONSE)
                return
            request_body_buffer.extend(body_chunk)
            if not request_message.get("more_body", False):
                break

        body_delivered: bool = False

        async def receive_buffered_body() -> Message:
            nonlocal body_delivered
            if not body_delivered:
                body_delivered = True
                return {
                    "type": "http.request",
                    "body": bytes(request_body_buffer),
                    "more_body": False,
                }
            return await receive()

        await self._app(scope, receive_buffered_body, send)

    @staticmethod
    async def _send_error(send: Send, *, status_code: int, body: bytes) -> None:
        """发送简短错误响应，不把请求内容复制进错误信息。"""
        await send(
            {
                "type": "http.response.start",
                "status": status_code,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body, "more_body": False})


__all__ = ["RequestBodyLimitMiddleware"]
