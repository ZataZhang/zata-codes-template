"""云沙箱测试替身:内存版控制面与执行通道。

只实现 ``e2b_control_plane`` 与 ``e2b_execution_channel`` 实际用到的协议面,但行为
按真实服务对齐——命令按形状真正执行(rm/mv/find/mkdir)、文件按路径真正存取,因此
"整体替换运行资产"这类断言检查的是真实语义而不是调用次数。

不联网、不需要凭据;真实云沙箱验收见 ``tests/backend/test_cloud_sandbox_e2b_live.py``。
"""

from __future__ import annotations

import base64
import json
import re
import shlex
import struct
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import httpx

from backend.infrastructure.sandbox.e2b_protocol import (
    CONNECT_END_STREAM_FLAG,
    encode_connect_frame,
)

DEFAULT_SANDBOX_ID = "sb-0000000000000001"
DEFAULT_ACCESS_TOKEN = "envd-token-should-not-leak"
DEFAULT_DOMAIN = "sandbox.example.test"

# provider 与 session 会发出的固定命令形状。
WORKSPACE_SETUP_COMMAND_PREFIX = "mkdir -p /workspace/inputs /workspace/outputs"
LIST_FILES_COMMAND_PREFIX = "find "

# 每条命令都由 provider 包上身份自校验。这里按形状解析而不是写死标记文本:标记与
# 退出码从命令本身取回,替身因此不会与实现漂移。
_IDENTITY_PATH_INFIX = "/.zata-sandbox-identity-"
_IDENTITY_GUARD_PATTERN = re.compile(
    r'^if \[ "\$\(cat (?P<path>.+?) 2>/dev/null\)" != (?P<nonce>.+?) \]; '
    r"then echo (?P<marker>.+?); exit (?P<exit_code>\d+); fi\n(?P<command>.*)$",
    re.DOTALL,
)


@dataclass
class FakeCloudSandboxService:
    """内存版云沙箱服务。

    Attributes:
        sandboxes (dict[str, dict[str, object]]): 沙箱标识到元数据的映射。
        files (dict[str, dict[str, bytes]]): 沙箱标识到"路径 -> 内容"的映射。
        executed_commands (list[str]): 收到过的内层命令。
        bounded_commands (list[str]): 收到过的外层命令;用于断言沙箱内超时包装。
        renewed_timeouts (list[int]): 每次续期请求声明的存活窗口。
        destroyed_sandbox_ids (list[str]): 收到过销毁请求的沙箱标识。
        workspace_writable (bool): 工作区是否可写;为假时演练"执行模板不合格"。
        control_plane_forgotten_sandbox_ids (set[str]): 控制面"已忘记"的沙箱标识;
            用于演练"控制面报 404 但 envd 仍在服务"这一实测形态。
        probe_status_code (int): 控制面探测返回的状态码。
        exec_rejection_status (int | None): 非空时执行通道对该状态码直接拒绝请求;
            用于演练"模板没有约定工作目录"这类执行前就被服务端挡下的情况。
        command_responder (Callable[[str], tuple[str, str, int]] | None): 对未被内建
            形状识别的命令给出 (stdout, stderr, exit_code);``None`` 表示空成功输出。
    """

    sandboxes: dict[str, dict[str, object]] = field(default_factory=dict)
    files: dict[str, dict[str, bytes]] = field(default_factory=dict)
    executed_commands: list[str] = field(default_factory=list)
    bounded_commands: list[str] = field(default_factory=list)
    renewed_timeouts: list[int] = field(default_factory=list)
    destroyed_sandbox_ids: list[str] = field(default_factory=list)
    workspace_writable: bool = True
    control_plane_forgotten_sandbox_ids: set[str] = field(default_factory=set)
    probe_status_code: int = 200
    exec_rejection_status: int | None = None
    command_responder: Callable[[str], tuple[str, str, int]] | None = None
    _created_counter: int = 0

    def create_client(self) -> httpx.Client:
        """返回一个把全部请求交给本替身的 HTTP 客户端。"""
        return httpx.Client(transport=httpx.MockTransport(self.handle_request), timeout=5.0)

    def forget_sandbox_in_control_plane(self, sandbox_id: str) -> None:
        """让控制面不再认识该沙箱,但 envd 与文件系统照旧服务。

        这还原了实测形态:销毁后 ``GET /sandboxes/{id}`` 立刻 404,而执行通道仍以
        200 返回另一个环境的结果。
        """
        self.control_plane_forgotten_sandbox_ids.add(sandbox_id)

    def files_of(self, sandbox_id: str) -> dict[str, bytes]:
        """返回某个沙箱当前的文件快照。"""
        return dict(self.files.get(sandbox_id, {}))

    def replace_files_keeping_identity(
        self, sandbox_id: str, replacement_files: dict[str, bytes]
    ) -> None:
        """替换沙箱文件内容,但保留身份标记。

        身份标记是会话凭据而不是业务文件;只清业务文件才能演练"目录里内容变了"
        而沙箱仍属于本会话的场景。
        """
        identity_files = {
            stored_path: stored_content
            for stored_path, stored_content in self.files.get(sandbox_id, {}).items()
            if _IDENTITY_PATH_INFIX in stored_path
        }
        self.files[sandbox_id] = {**identity_files, **replacement_files}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """按请求路径分派到控制面或执行通道。

        Args:
            request (httpx.Request): 待处理请求。

        Returns:
            httpx.Response: 替身响应。
        """
        if request.url.path == "/templates":
            return httpx.Response(self.probe_status_code, json={"templates": []})
        if request.url.path == "/sandboxes" and request.method == "POST":
            return self._create_sandbox()
        if request.url.path == "/sandboxes" and request.method == "GET":
            # 实测形状:裸数组,不是 {"sandboxes": [...]}。
            return httpx.Response(200, json=[{"sandboxID": key} for key in self.sandboxes])
        if request.url.path.startswith("/sandboxes/"):
            return self._handle_sandbox_operation(request)
        return self._handle_envd_request(request)

    def _create_sandbox(self) -> httpx.Response:
        """创建沙箱并返回与真实服务同形的 201 响应。"""
        self._created_counter += 1
        sandbox_id = f"sb-{self._created_counter:016d}"
        self.sandboxes[sandbox_id] = {"sandboxID": sandbox_id}
        self.files[sandbox_id] = {}
        return httpx.Response(
            201,
            json={
                "sandboxID": sandbox_id,
                "envdAccessToken": DEFAULT_ACCESS_TOKEN,
                "envdVersion": "0.5.2",
                "domain": DEFAULT_DOMAIN,
                "templateID": "zata-sandbox",
            },
        )

    def _handle_sandbox_operation(self, request: httpx.Request) -> httpx.Response:
        """处理续期与销毁。"""
        path_parts = request.url.path.strip("/").split("/")
        sandbox_id = path_parts[1]
        if (
            sandbox_id not in self.sandboxes
            or sandbox_id in self.control_plane_forgotten_sandbox_ids
        ):
            return httpx.Response(404, text="not found")
        if request.method == "GET":
            return httpx.Response(200, json={"sandboxID": sandbox_id, "state": "running"})
        if request.method == "DELETE":
            self.destroyed_sandbox_ids.append(sandbox_id)
            self.sandboxes.pop(sandbox_id, None)
            self.files.pop(sandbox_id, None)
            return httpx.Response(204)
        if request.method == "POST" and path_parts[-1] == "timeout":
            request_body = json.loads(request.content.decode("utf-8"))
            self.renewed_timeouts.append(int(request_body["timeout"]))
            return httpx.Response(204)
        return httpx.Response(405, text="method not allowed")

    def _handle_envd_request(self, request: httpx.Request) -> httpx.Response:
        """处理执行通道请求。"""
        sandbox_id = _sandbox_id_from_envd_host(request.url.host, request.url.port)
        if sandbox_id is None or sandbox_id not in self.sandboxes:
            return httpx.Response(404, text="sandbox not found")
        if request.url.path == "/files":
            return self._handle_file_request(request, sandbox_id)
        if request.url.path == "/process.Process/Start":
            return self._handle_exec_request(request, sandbox_id)
        return httpx.Response(404, text="not found")

    def _handle_file_request(self, request: httpx.Request, sandbox_id: str) -> httpx.Response:
        """处理文件读写。"""
        sandbox_path = str(request.url.params.get("path") or "")
        sandbox_files = self.files.setdefault(sandbox_id, {})
        if request.method == "GET":
            if sandbox_path not in sandbox_files:
                return httpx.Response(404, text="file not found")
            return httpx.Response(
                200,
                content=sandbox_files[sandbox_path],
                headers={"Content-Type": "application/octet-stream"},
            )
        uploaded_content = _extract_multipart_content(request.content)
        if uploaded_content is None:
            return httpx.Response(400, text="missing file field")
        sandbox_files[sandbox_path] = uploaded_content
        return httpx.Response(201, json=[{"name": sandbox_path, "path": sandbox_path, "type": 1}])

    def _handle_exec_request(self, request: httpx.Request, sandbox_id: str) -> httpx.Response:
        """解码命令、按形状执行并编码响应事件。"""
        if self.exec_rejection_status is not None:
            return httpx.Response(
                self.exec_rejection_status, text="cwd '/workspace' does not exist"
            )
        command = _decode_exec_command(request.content)
        self.bounded_commands.append(command)
        inner_command = _unwrap_bounded_command(command)
        sandbox_files = self.files.setdefault(sandbox_id, {})
        identity_path, identity_nonce, identity_marker, identity_exit_code, command = (
            _split_identity_guard(inner_command)
        )
        self.executed_commands.append(command)
        if sandbox_files.get(identity_path) != identity_nonce.encode("utf-8"):
            # 真实服务在沙箱被销毁后就是这个表现:不报错,而是给出另一个干净环境的
            # 成功结果。替身把它还原成身份校验失败。
            return _build_exec_response(
                stdout=f"{identity_marker}\n", stderr="", exit_code=identity_exit_code
            )
        if command.startswith(WORKSPACE_SETUP_COMMAND_PREFIX):
            exit_code = 0 if self.workspace_writable else 1
            return _build_exec_response(stdout="", stderr="", exit_code=exit_code)
        if command.startswith("rm -rf -- "):
            return _build_exec_response(*self._run_remove(command, sandbox_files))
        if command.startswith(LIST_FILES_COMMAND_PREFIX):
            directory = command.split(" ", 2)[1]
            listed_paths = sorted(
                path for path in sandbox_files if _is_within(path, directory.strip("'"))
            )
            return _build_exec_response(stdout="\0".join(listed_paths), stderr="", exit_code=0)
        if self.command_responder is not None:
            return _build_exec_response(*self.command_responder(command))
        return _build_exec_response(stdout="", stderr="", exit_code=0)

    def _run_remove(self, command: str, sandbox_files: dict[str, bytes]) -> tuple[str, str, int]:
        """执行 ``rm -rf -- <path>`` 或 ``rm -rf -- <path> && mv -- a b``。"""
        rm_target, mv_targets = _split_remove_and_move(command)
        for stored_path in [path for path in sandbox_files if _is_within(path, rm_target)]:
            sandbox_files.pop(stored_path, None)
        if mv_targets is None:
            return "", "", 0
        move_source, move_destination = mv_targets
        for stored_path in [path for path in sandbox_files if _is_within(path, move_source)]:
            moved_content = sandbox_files.pop(stored_path)
            sandbox_files[move_destination + stored_path[len(move_source) :]] = moved_content
        return "", "", 0


def _is_within(sandbox_path: str, directory_path: str) -> bool:
    """判断路径是否落在目录之下(含目录自身)。"""
    return sandbox_path == directory_path or sandbox_path.startswith(f"{directory_path}/")


def _split_remove_and_move(command: str) -> tuple[str, tuple[str, str] | None]:
    """从维护命令里解析出删除目标与可选的换名目标。"""
    remove_part = command.split("rm -rf -- ", 1)[1]
    if " && mv -- " not in remove_part:
        return remove_part.strip().strip("'"), None
    rm_target, move_part = remove_part.split(" && mv -- ", 1)
    move_source, move_destination = move_part.split(" ", 1)
    return (
        rm_target.strip().strip("'"),
        (move_source.strip().strip("'"), move_destination.strip().strip("'")),
    )


def _sandbox_id_from_envd_host(host: str | None, port: int | None) -> str | None:
    """从 envd 主机名里取回裸沙箱标识。"""
    if port is not None or host is None or not host.startswith("49983-"):
        return None
    return host[len("49983-") :].split(".", 1)[0]


def _extract_multipart_content(request_body: bytes) -> bytes | None:
    """从 multipart 请求体里取出 ``file`` 字段的内容。"""
    marker = b'name="file"; filename="'
    marker_offset = request_body.find(marker)
    if marker_offset < 0:
        return None
    content_start_offset = request_body.find(b"\r\n\r\n", marker_offset)
    if content_start_offset < 0:
        return None
    content_start_offset += 4
    content_end_offset = request_body.find(b"\r\n--", content_start_offset)
    if content_end_offset < 0:
        return None
    return request_body[content_start_offset:content_end_offset]


def _split_identity_guard(
    inner_command: str,
) -> tuple[str, str, str, int, str]:
    """把身份自校验前缀拆出来,返回路径、随机值、丢失标记、退出码与真实命令。

    前缀必须独占一行且命令体逐字跟在后面:任何"包裹命令体"的写法都会破坏带未加引号
    ``#`` 注释或 heredoc 的合法命令,替身因此按换行分隔的形状解析。

    Raises:
        AssertionError: 命令没有携带身份自校验——这正是本替身要守住的语义。
    """
    guard_match = _IDENTITY_GUARD_PATTERN.match(inner_command)
    if guard_match is None:
        raise AssertionError(f"命令未携带沙箱身份自校验: {inner_command}")
    return (
        shlex.split(guard_match.group("path"))[0],
        shlex.split(guard_match.group("nonce"))[0],
        shlex.split(guard_match.group("marker"))[0],
        int(guard_match.group("exit_code")),
        guard_match.group("command"),
    )


def _decode_exec_command(request_body: bytes) -> str:
    """从 Connect 请求帧里取出外层命令文本(含沙箱内超时包装)。"""
    frame_length = struct.unpack(">I", request_body[1:5])[0]
    request_payload = json.loads(request_body[5 : 5 + frame_length].decode("utf-8"))
    process_arguments = request_payload["process"]["args"]
    return str(process_arguments[-1])


def _unwrap_bounded_command(bounded_command: str) -> str:
    """剥掉 ``timeout ... /bin/sh -lc`` 包装,还原调用方真正想跑的命令。

    Raises:
        AssertionError: 命令没有被沙箱内超时包装——这正是本替身要守住的语义。
    """
    if " /bin/sh -lc " not in bounded_command:
        raise AssertionError(f"命令未经沙箱内超时包装: {bounded_command}")
    return shlex.split(bounded_command.split(" /bin/sh -lc ", 1)[1])[0]


def _build_exec_response(stdout: str, stderr: str, exit_code: int) -> httpx.Response:
    """把一次命令结果编码成 Connect 流式响应体。"""
    events: list[dict[str, object]] = [{"event": {"start": {"pid": 1}}}]
    if stdout or stderr:
        events.append(
            {
                "event": {
                    "data": {
                        "stdout": base64.b64encode(stdout.encode("utf-8")).decode("ascii"),
                        "stderr": base64.b64encode(stderr.encode("utf-8")).decode("ascii"),
                    }
                }
            }
        )
    events.append({"event": {"end": {"exitCode": exit_code, "exited": True, "status": "exited"}}})
    encoded_frames = b"".join(
        encode_connect_frame(json.dumps(event).encode("utf-8")) for event in events
    )
    end_stream_payload = b"{}"
    encoded_frames += (
        bytes([CONNECT_END_STREAM_FLAG])
        + struct.pack(">I", len(end_stream_payload))
        + end_stream_payload
    )
    return httpx.Response(
        200, content=encoded_frames, headers={"Content-Type": "application/connect+json"}
    )


def build_exec_response_body(
    *, stdout_chunks: Sequence[bytes], stderr_chunks: Sequence[bytes], exit_code: int
) -> bytes:
    """构造多帧执行响应,供分帧解码与截断用例直接使用。"""
    encoded_frames = encode_connect_frame(json.dumps({"event": {"start": {"pid": 1}}}).encode())
    for stdout_chunk, stderr_chunk in zip(stdout_chunks, stderr_chunks, strict=False):
        encoded_frames += encode_connect_frame(
            json.dumps(
                {
                    "event": {
                        "data": {
                            "stdout": base64.b64encode(stdout_chunk).decode("ascii"),
                            "stderr": base64.b64encode(stderr_chunk).decode("ascii"),
                        }
                    }
                }
            ).encode()
        )
    encoded_frames += encode_connect_frame(
        json.dumps({"event": {"end": {"exitCode": exit_code, "exited": True}}}).encode()
    )
    return encoded_frames + bytes([CONNECT_END_STREAM_FLAG]) + struct.pack(">I", 2) + b"{}"


def build_error_end_stream_body(*, code: str, message: str) -> bytes:
    """构造带错误终止帧的执行响应体。"""
    error_payload = json.dumps({"error": {"code": code, "message": message}}).encode()
    return bytes([CONNECT_END_STREAM_FLAG]) + struct.pack(">I", len(error_payload)) + error_payload


__all__ = [
    "DEFAULT_ACCESS_TOKEN",
    "DEFAULT_DOMAIN",
    "DEFAULT_SANDBOX_ID",
    "FakeCloudSandboxService",
    "build_error_end_stream_body",
    "build_exec_response_body",
]
