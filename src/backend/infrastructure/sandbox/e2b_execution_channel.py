"""E2B 执行通道客户端:命令执行与文件读写。

执行通道经 envd 网关访问,鉴权使用创建响应中的 ``envdAccessToken``。云端通过
沙箱域名直连;E2B Embed 则经 client-proxy 并附带沙箱 ID 和 envd 端口路由头。

经实测确认的契约(2026-09-21):

* 命令执行走 Connect RPC ``POST /process.Process/Start``,``Content-Type:
  application/connect+json``,5 字节分帧;响应事件里 stdout/stderr 是 base64,
  ``end.exitCode`` 给退出码,终止帧载荷为 ``{}``。
* 文件读写**不在** Connect 服务里:用 REST ``GET/POST /files?path=&username=``,
  写用 multipart 的 ``file`` 字段。父目录会被自动创建,内容二进制安全。
* ``GET /health`` 返回 ``{"status":"ok"}``,但**不能**当作存活判据:实测沙箱被销毁后
  它仍返回 200,因此存活判定由 :mod:`e2b_provider` 的沙箱身份校验承担。

命令超时用沙箱内的 ``timeout`` 包裹,而不是依赖客户端超时:客户端超时只会放弃
等待,命令仍在沙箱里跑。
"""

from __future__ import annotations

import base64
import json
import shlex
from pathlib import PurePosixPath

import httpx

from backend.infrastructure.sandbox.e2b_protocol import (
    CONNECT_END_STREAM_FLAG,
    ENVD_PORT,
    E2bExecOutcome,
    E2bProtocolError,
    E2bSandboxHandle,
    E2bSandboxNotFoundError,
    build_status_error,
    build_transport_error,
    decode_connect_frames,
    encode_connect_frame,
)

_EXEC_PATH = "/process.Process/Start"
_FILES_PATH = "/files"
_CONNECT_CONTENT_TYPE = "application/connect+json"
_ACCESS_TOKEN_HEADER = "X-Access-Token"
_EXEC_TIMEOUT_MARGIN_SECONDS = 30.0
_SANDBOX_MISSING_CODES = ("not_found", "sandbox_not_found")


class E2bExecutionChannel:
    """单个云沙箱的执行通道客户端。"""

    def __init__(
        self,
        *,
        handle: E2bSandboxHandle,
        username: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        """绑定沙箱句柄与可复用的 HTTP 客户端。

        Args:
            handle (E2bSandboxHandle): 沙箱访问句柄。
            username (str): 文件读写使用的沙箱用户名。
            http_client (httpx.Client | None): 复用的 HTTP 客户端;``None`` 时自建。
        """
        self._handle = handle
        self._username = username
        self._http_client = http_client or httpx.Client(timeout=_EXEC_TIMEOUT_MARGIN_SECONDS)

    def run_command(
        self,
        command: str,
        *,
        timeout_seconds: int,
        cwd: str,
        max_output_bytes: int,
    ) -> E2bExecOutcome:
        """在沙箱内执行命令并解码输出事件。

        Args:
            command (str): 待执行的 shell 命令。
            timeout_seconds (int): 命令超时秒数;由沙箱内的 ``timeout`` 强制生效。
            cwd (str): 命令的工作目录。
            max_output_bytes (int): 输出累计上限;超出部分被丢弃并标记截断。

        Returns:
            E2bExecOutcome: 标准输出、标准错误、退出码与截断标记。

        Raises:
            E2bProtocolError: 传输失败、沙箱不存在、响应分帧非法,或执行通道没有
                给出结束事件。这些都表示"没有拿到可信结果",不是命令自身失败。
        """
        bounded_command = (
            f"timeout --kill-after=5s {timeout_seconds}s /bin/sh -lc {shlex.quote(command)}"
        )
        request_body = json.dumps(
            {"process": {"cmd": "/bin/sh", "args": ["-lc", bounded_command], "cwd": cwd}}
        ).encode("utf-8")
        try:
            request_url, request_headers = self._request_target(_EXEC_PATH)
            exec_response = self._http_client.post(
                request_url,
                headers={**request_headers, "Content-Type": _CONNECT_CONTENT_TYPE},
                content=encode_connect_frame(request_body),
                timeout=timeout_seconds + _EXEC_TIMEOUT_MARGIN_SECONDS,
            )
        except httpx.HTTPError as transport_error:
            raise build_transport_error(
                action="执行命令", transport_error=transport_error
            ) from transport_error
        if exec_response.status_code >= 400:
            raise build_status_error(
                action="执行命令",
                status_code=exec_response.status_code,
                response_body=exec_response.text,
            )
        return _decode_exec_response(
            response_body=exec_response.content, max_output_bytes=max_output_bytes
        )

    def write_file(self, sandbox_path: str, content: bytes) -> None:
        """把单个文件写入沙箱。

        父目录由服务端自动创建,因此调用方不必先建目录。

        Args:
            sandbox_path (str): 沙箱内的绝对路径。
            content (bytes): 文件内容。

        Raises:
            E2bProtocolError: 传输失败或服务端返回非成功状态。
        """
        try:
            request_url, request_headers = self._request_target(_FILES_PATH)
            write_response = self._http_client.post(
                request_url,
                params={"path": sandbox_path, "username": self._username},
                headers=request_headers,
                files={
                    "file": (
                        PurePosixPath(sandbox_path).name,
                        content,
                        "application/octet-stream",
                    )
                },
            )
        except httpx.HTTPError as transport_error:
            raise build_transport_error(action="写入文件", transport_error=transport_error) from (
                transport_error
            )
        if write_response.status_code >= 400:
            raise build_status_error(
                action="写入文件",
                status_code=write_response.status_code,
                response_body=write_response.text,
            )

    def read_file(self, sandbox_path: str) -> bytes:
        """从沙箱读回单个文件。

        Args:
            sandbox_path (str): 沙箱内的绝对路径。

        Returns:
            bytes: 文件内容。

        Raises:
            E2bProtocolError: 传输失败、文件不存在或服务端返回非成功状态。
        """
        try:
            request_url, request_headers = self._request_target(_FILES_PATH)
            read_response = self._http_client.get(
                request_url,
                params={"path": sandbox_path, "username": self._username},
                headers=request_headers,
            )
        except httpx.HTTPError as transport_error:
            raise build_transport_error(action="读取文件", transport_error=transport_error) from (
                transport_error
            )
        if read_response.status_code >= 400:
            raise build_status_error(
                action="读取文件",
                status_code=read_response.status_code,
                response_body=read_response.text,
                missing_sandbox_on_404=False,
            )
        return read_response.content

    def _access_headers(self) -> dict[str, str]:
        """返回执行通道鉴权头;令牌只进请求头,不进日志与异常消息。"""
        return {_ACCESS_TOKEN_HEADER: self._handle.access_token}

    def _request_target(self, request_path: str) -> tuple[str, dict[str, str]]:
        """为直连或 E2B client-proxy 构造请求地址与鉴权路由头。"""
        if self._handle.sandbox_proxy_url is None:
            return f"{self._handle.envd_base_url}{request_path}", self._access_headers()
        request_headers = {
            **self._access_headers(),
            "E2b-Sandbox-Id": self._handle.sandbox_id,
            "E2b-Sandbox-Port": str(ENVD_PORT),
        }
        return f"{self._handle.sandbox_proxy_url.rstrip('/')}{request_path}", request_headers


def _decode_exec_response(*, response_body: bytes, max_output_bytes: int) -> E2bExecOutcome:
    """把执行通道响应体解码为命令结果。

    Args:
        response_body (bytes): Connect 流式响应体。
        max_output_bytes (int): 输出累计上限。

    Returns:
        E2bExecOutcome: 解码结果。

    Raises:
        E2bProtocolError: 分帧非法、终止帧带错误,或没有结束事件。
    """
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    exit_code: int | None = None
    is_truncated = False
    for frame_flag, frame_payload in decode_connect_frames(response_body):
        if frame_flag == CONNECT_END_STREAM_FLAG:
            _raise_on_end_stream_error(frame_payload)
            continue
        event_payload = _decode_json_object(frame_payload, subject="执行通道事件")
        event_body = event_payload.get("event")
        if not isinstance(event_body, dict):
            continue
        event_data = event_body.get("data")
        if isinstance(event_data, dict):
            stdout_chunk = _decode_base64_field(event_data.get("stdout"))
            stderr_chunk = _decode_base64_field(event_data.get("stderr"))
            is_truncated = (
                _append_bounded(stdout_buffer, stdout_chunk, max_output_bytes) or is_truncated
            )
            is_truncated = (
                _append_bounded(stderr_buffer, stderr_chunk, max_output_bytes) or is_truncated
            )
        event_end = event_body.get("end")
        if isinstance(event_end, dict):
            exit_code = _decode_exit_code(event_end)
    if exit_code is None:
        raise E2bProtocolError("云沙箱执行通道没有返回命令结束事件，结果不可信")
    return E2bExecOutcome(
        stdout_bytes=bytes(stdout_buffer),
        stderr_bytes=bytes(stderr_buffer),
        exit_code=exit_code,
        truncated=is_truncated,
    )


def _raise_on_end_stream_error(frame_payload: bytes) -> None:
    """终止帧带错误时抛出协议异常。

    Raises:
        E2bProtocolError: 终止帧声明了错误。
    """
    if not frame_payload.strip():
        return
    end_stream_payload = _decode_json_object(frame_payload, subject="执行通道终止帧")
    stream_error = end_stream_payload.get("error")
    if not isinstance(stream_error, dict):
        return
    error_code = str(stream_error.get("code") or "unknown")
    error_message = str(stream_error.get("message") or "")
    if error_code in _SANDBOX_MISSING_CODES:
        raise E2bSandboxNotFoundError(f"云沙箱已被回收: {error_code} {error_message}")
    raise E2bProtocolError(f"云沙箱执行通道返回错误: {error_code} {error_message}")


def _decode_exit_code(end_event: dict[str, object]) -> int:
    """从结束事件里取退出码。

    退出码缺失或事件自带错误时一律失败,不给"缺字段就当成功"留口子:那正是假成功的
    形状,而真实契约里 ``exitCode`` 是必填字段。

    Args:
        end_event (dict[str, object]): 结束事件载荷。

    Returns:
        int: 命令退出码。

    Raises:
        E2bProtocolError: 结束事件带错误,或缺少可用的 ``exitCode``。
    """
    reported_error = end_event.get("error")
    if reported_error:
        raise E2bProtocolError(f"云沙箱命令结束事件带错误: {reported_error}")
    raw_exit_code = end_event.get("exitCode")
    if raw_exit_code is None:
        raise E2bProtocolError("云沙箱命令结束事件缺少 exitCode，结果不可信")
    return int(raw_exit_code)


def _decode_json_object(payload: bytes, *, subject: str) -> dict[str, object]:
    """把一帧载荷解析为 JSON 对象。

    Raises:
        E2bProtocolError: 载荷不是 UTF-8 编码的 JSON 对象。
    """
    try:
        decoded_payload = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as decode_error:
        raise E2bProtocolError(f"云沙箱{subject}解码失败: {decode_error}") from decode_error
    if not isinstance(decoded_payload, dict):
        raise E2bProtocolError(f"云沙箱{subject}不是 JSON 对象")
    return decoded_payload


def _decode_base64_field(raw_field: object) -> bytes:
    """把事件里的 base64 字段解码为字节。

    字段缺失或为空表示该流本次没有新数据;内容非法时按协议错误处理,而不是当成
    空输出——否则输出会静默缺失。

    Returns:
        bytes: 解码后的字节。

    Raises:
        E2bProtocolError: 字段值不是字符串或不是合法 base64。
    """
    if raw_field is None or raw_field == "":
        return b""
    if not isinstance(raw_field, str):
        raise E2bProtocolError("云沙箱执行通道输出字段不是 base64 字符串")
    try:
        return base64.b64decode(raw_field, validate=True)
    except (ValueError, TypeError) as decode_error:
        raise E2bProtocolError(f"云沙箱执行通道输出字段不是合法 base64: {decode_error}") from (
            decode_error
        )


def _append_bounded(output_buffer: bytearray, output_chunk: bytes, max_output_bytes: int) -> bool:
    """在上限内追加输出片段。

    Returns:
        bool: 是否有内容因超出上限被丢弃。
    """
    remaining_bytes = max_output_bytes - len(output_buffer)
    if remaining_bytes <= 0:
        return bool(output_chunk)
    output_buffer.extend(output_chunk[:remaining_bytes])
    return len(output_chunk) > remaining_bytes


__all__ = ["E2bExecutionChannel"]
