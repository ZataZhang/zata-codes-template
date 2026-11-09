"""本机文件与改动查看器的服务端实现。

由 ``scripts/shared/view/launch.py`` 以子进程方式拉起，不作为包被 import。服务只绑
本机回环地址、路由白名单固定；所有路径参数在 :mod:`workspace` 里解析成绝对路径后断言仍在
仓库根之下。

**写边界**：仓库侧的写操作是显式保存文本文件（``POST /api/file/save``）、从 Markdown 预览
切换任务项（``POST /api/file/toggle-task``）和暂存（``POST /api/stage``，只做 ``git add``）。
另有一条不写仓库的写路由 ``POST /api/open``：
把仓库内的文件交给系统默认应用打开（macOS ``open`` / Windows ``startfile`` / 其它
``xdg-open``），但在用户机器上有副作用。所有写路由都要求 ``Content-Type: application/json``：
跨站表单式 POST 是「简单请求」，浏览器会直接发出去，而 JSON 类型会强制预检、预检又必然
失败。查看器首页使用每次请求生成的 CSP 脚本 nonce；仓库原始 HTML/SVG 由 ``/raw/`` 返回时
禁用脚本，避免仓库内容借同源执行代码触发保存。其余写方法（PUT / DELETE / PATCH）仍一律
405。边界说明见 :mod:`workspace` 的模块 docstring。

空闲回收：服务按「最后一次请求时间」计时，超过时限即优雅退出并清理登记文件。页面
刻意不做心跳轮询，因此「关掉标签页」即等同于进入空闲——这是自动回收路径成立的前提，
给这个页面加轮询会让自动回收静默失效。
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import sys
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import file_edit
import instance
import rendering
import workspace
import workspace_read

#: 服务只绑本机回环地址，常量与客户端入口共用同一份定义。
VIEWER_HOST = instance.LOOPBACK_HOST

_ASSETS_DIRECTORY_PATH = Path(__file__).resolve().parent / "assets"
_ASSET_ROUTE_PREFIX = "/assets/"

_STATIC_CONTENT_TYPES_BY_FILENAME = {
    "index.html": "text/html; charset=utf-8",
    "viewer.css": "text/css; charset=utf-8",
    "history-view.js": "application/javascript; charset=utf-8",
    "viewer.js": "application/javascript; charset=utf-8",
    # 第三方产物（mermaid 的官方压缩包），只在页面真的遇到 mermaid 围栏时才按需取。
    # 版本、来源与校验和见 assets/viewer.js 顶部的说明。
    "mermaid.min.js": "application/javascript; charset=utf-8",
}

_READ_METHOD_HANDLER_PREFIX = "do_"

#: 写方法入口只有 ``POST`` 一个；具体写操作由白名单路由分发（见
#: :meth:`ViewerRequestHandler.do_POST`）。
_WRITE_METHOD_HANDLER_NAME = "do_POST"
_STAGE_ROUTE_PATH = "/api/stage"
_OPEN_ROUTE_PATH = "/api/open"
_FILE_SOURCE_ROUTE_PATH = "/api/file/source"
_FILE_SAVE_ROUTE_PATH = "/api/file/save"
_FILE_TOGGLE_TASK_ROUTE_PATH = "/api/file/toggle-task"
_SCRIPT_NONCE_PLACEHOLDER = "__LOCAL_VIEW_SCRIPT_NONCE__"

#: 通用写请求体的长度上限。文件保存有单独的上限，足以容纳 256 KiB 文本转成 JSON。
_MAX_WRITE_BODY_BYTES = 64 * 1024
_MAX_FILE_SAVE_BODY_BYTES = workspace.MAX_FILE_BYTES * 6 + 4096

_IDLE_CHECK_INTERVAL_SECONDS = 5.0
_MIN_IDLE_CHECK_INTERVAL_SECONDS = 0.1
_SERVE_POLL_INTERVAL_SECONDS = 0.2


@dataclass(frozen=True)
class ServerConfiguration:
    """一次服务进程的启动配置。

    Attributes:
        repository_root (Path): 被查看目录的根绝对路径。
        port (int): 监听端口，由客户端入口选定。
        idle_timeout_seconds (float): 空闲回收时限；非正数表示关闭自动回收。
        git_available (bool): 目标目录是否在 Git 工作区内。
    """

    repository_root: Path
    port: int
    idle_timeout_seconds: float
    git_available: bool = True


class ViewerHTTPServer(ThreadingHTTPServer):
    """本机文件与改动查看器服务：绑定回环地址并持有空闲计时状态。

    Attributes:
        configuration (ServerConfiguration): 本次启动配置。
    """

    # 请求线程是守护线程：退出时不必等浏览器持有的 keep-alive 连接自行断开。
    daemon_threads = True
    # 端口被占用时明确失败，不做地址复用——复用会让新旧实例静默抢同一个端口。
    allow_reuse_address = False

    def __init__(
        self,
        configuration: ServerConfiguration,
        request_handler_class: type[BaseHTTPRequestHandler],
    ) -> None:
        """绑定回环地址并初始化空闲计时。

        Args:
            configuration (ServerConfiguration): 本次启动配置。
            request_handler_class (type[BaseHTTPRequestHandler]): 请求处理器类。
        """
        self.configuration = configuration
        self._activity_lock = threading.Lock()
        self._last_request_monotonic = time.monotonic()
        super().__init__((VIEWER_HOST, configuration.port), request_handler_class)

    @property
    def repository_root(self) -> Path:
        """本实例所服务的仓库根绝对路径。"""
        return self.configuration.repository_root

    @property
    def git_available(self) -> bool:
        """本实例是否连接到 Git 仓库。"""
        return self.configuration.git_available

    def mark_request_served(self) -> None:
        """刷新空闲计时的起点；被拒绝的请求同样算「有请求」。"""
        with self._activity_lock:
            self._last_request_monotonic = time.monotonic()

    def seconds_since_last_request(self) -> float:
        """给出距离最近一次请求经过的秒数。"""
        with self._activity_lock:
            return time.monotonic() - self._last_request_monotonic


class ViewerRequestHandler(BaseHTTPRequestHandler):
    """本机查看器的请求处理器：固定读取路由与少量 JSON 写入路由。"""

    server: ViewerHTTPServer

    server_version = "LocalViewServer/1.0"
    sys_version = ""
    # HTTP/1.1 让浏览器复用连接：文件树一次要发若干请求，省掉重复握手。
    protocol_version = "HTTP/1.1"

    def __getattr__(self, attribute_name: str) -> object:
        """把 ``do_<方法>`` 名字解析成对应的处理器：``POST`` 走写口，其余一律拒绝。

        这里刻意不逐个定义写方法（PUT / DELETE / PATCH）对应的处理器名字：写边界的可审查性
        依赖「所有写操作都由一个 POST 入口按路由白名单分发」这一事实，逐个定义同名方法会让
        「``scripts/shared/view/`` 下搜不到写方法处理器」这类静态断言失去判别力。
        ``http.server`` 的分发正是 ``hasattr(self, "do_" + command)`` 加 ``getattr``，因此按
        前缀返回同一个拒绝处理器即可覆盖其余非读取方法。

        Args:
            attribute_name (str): 被查找的属性名。

        Returns:
            object: 写入口（``POST``）或非读取方法的拒绝处理器。

        Raises:
            AttributeError: 属性名不带 ``do_`` 前缀且确实不存在。
        """
        if attribute_name == _WRITE_METHOD_HANDLER_NAME:
            return self.do_POST
        if attribute_name.startswith(_READ_METHOD_HANDLER_PREFIX):
            return self._refuse_non_read_method
        raise AttributeError(attribute_name)

    def do_GET(self) -> None:  # noqa: N802 - http.server 靠 do_<METHOD> 这个名字分发
        """唯一的读取入口：先刷新空闲计时，再按路由白名单分发。"""
        self.server.mark_request_served()
        try:
            self._dispatch_read_request()
        except workspace.WorkspaceCommandError as read_error:
            self._send_json_payload(500, {"error": f"读取仓库失败：{read_error}"})

    def do_POST(self) -> None:  # noqa: N802 - http.server 靠 do_<METHOD> 这个名字分发
        """唯一的写方法入口：按路由分发给保存、切换任务、暂存或在系统中打开。

        只接受 JSON 请求体。

        要求 ``Content-Type: application/json`` 不是为了讲究，而是这里唯一说得通的防线：
        跨站表单式 POST 属于「简单请求」，浏览器会直接发出去（恶意页面读不到响应，但**副作用
        已经发生**）。JSON 类型会强制浏览器先发预检，而本服务不返回任何 CORS 头，预检必然
        失败。首页 CSP nonce 与 ``/raw/`` 禁用脚本共同阻止仓库内容借同源脚本触发保存。非 JSON
        一律 415，绝不「宽容地」处理。
        """
        self.server.mark_request_served()
        requested_route_path = urlsplit(self.path).path
        try:
            self._dispatch_write_request(requested_route_path)
        except workspace.WorkspaceCommandError as write_error:
            # 具体操作把常见失败都转成拒绝应答；标签仍按路由区分，避免异常时误报操作。
            failure_label = {
                _OPEN_ROUTE_PATH: "打开",
                _FILE_SAVE_ROUTE_PATH: "保存",
                _FILE_TOGGLE_TASK_ROUTE_PATH: "更新任务",
            }.get(requested_route_path, "暂存")
            self._send_json_payload(500, {"error": f"{failure_label}失败：{write_error}"})

    def _refuse_non_read_method(self) -> None:
        """拒绝不支持的 HTTP 方法：本服务只接受 GET 与白名单里的 POST 路由。"""
        self.server.mark_request_served()
        self._send_json_payload(
            405,
            {
                "error": "拒绝：本服务只接受 GET 请求与白名单操作用的 JSON POST，"
                "不提供提交、撤销暂存或丢弃改动接口。",
                "method": self.command,
            },
        )

    def _dispatch_read_request(self) -> None:
        """按固定白名单分发读取路由；白名单之外一律 404。"""
        parsed_request_target = urlsplit(self.path)
        route_path = parsed_request_target.path
        query_parameters = parse_qs(parsed_request_target.query)
        repository_root = self.server.repository_root

        if route_path == "/":
            self._serve_static_asset("index.html")
        elif route_path.startswith(_ASSET_ROUTE_PREFIX):
            self._serve_static_asset(route_path.removeprefix(_ASSET_ROUTE_PREFIX))
        elif route_path == "/api/info":
            self._serve_workspace_payload(
                workspace.build_info_payload(
                    repository_root, git_available=self.server.git_available
                )
            )
        elif route_path == "/api/tree":
            include_ignored = self._read_query_parameter(query_parameters, "include_ignored") == "1"
            self._serve_workspace_payload(
                workspace.build_tree_payload(
                    repository_root,
                    include_ignored=include_ignored,
                    git_available=self.server.git_available,
                )
            )
        elif route_path == "/api/file":
            self._serve_workspace_payload(
                workspace.build_file_payload(
                    repository_root,
                    self._read_query_parameter(query_parameters, "path"),
                )
            )
        elif route_path == _FILE_SOURCE_ROUTE_PATH:
            self._serve_workspace_payload(
                file_edit.build_editable_source_payload(
                    repository_root,
                    self._read_query_parameter(query_parameters, "path"),
                )
            )
        elif route_path == "/api/changes":
            if not self.server.git_available:
                self._send_json_payload(404, {"error": "该目录不在 Git 仓库中，没有改动列表。"})
                return
            self._serve_workspace_payload(workspace.build_changes_payload(repository_root))
        elif route_path in {
            "/api/log",
            "/api/log/commit",
            "/api/log/diff",
        }:
            if not self.server.git_available:
                self._send_json_payload(404, {"error": "该目录不在 Git 仓库中，没有提交历史。"})
                return
            # 历史模块只在首次请求 Git Log 时导入，保持默认视图的常驻开销较低。
            # 服务端 RSS 软预算（不含浏览器）：未访问历史时 ≤50 MiB，访问历史后 ≤80 MiB；
            # 稳定超过 100 MiB 时排查。这是维护目标，不是运行时硬限制。
            import history

            if route_path == "/api/log":
                offset_text = self._read_query_parameter(query_parameters, "offset") or "0"
                limit_text = self._read_query_parameter(query_parameters, "limit") or str(
                    history.DEFAULT_HISTORY_PAGE_SIZE
                )
                try:
                    history_offset = int(offset_text)
                    history_limit = int(limit_text)
                except ValueError:
                    self._send_json_payload(400, {"error": "拒绝：Git 历史分页参数必须是整数。"})
                    return
                self._serve_workspace_payload(
                    history.build_git_history_payload(
                        repository_root,
                        offset=history_offset,
                        limit=history_limit,
                    )
                )
            elif route_path == "/api/log/commit":
                self._serve_workspace_payload(
                    history.build_git_commit_payload(
                        repository_root,
                        self._read_query_parameter(query_parameters, "hash"),
                    )
                )
            elif route_path == "/api/log/diff":
                self._serve_workspace_payload(
                    history.build_git_commit_diff_payload(
                        repository_root,
                        self._read_query_parameter(query_parameters, "hash"),
                        self._read_query_parameter(query_parameters, "path"),
                    )
                )
        elif route_path == "/api/diff":
            if not self.server.git_available:
                self._send_json_payload(404, {"error": "该目录不在 Git 仓库中，没有改动 diff。"})
                return
            self._serve_workspace_payload(
                workspace.build_diff_payload(
                    repository_root,
                    self._read_query_parameter(query_parameters, "path"),
                    self._read_query_parameter(query_parameters, "section"),
                )
            )
        elif route_path == "/api/markdown":
            self._serve_workspace_payload(
                workspace.build_markdown_payload(
                    repository_root,
                    self._read_query_parameter(query_parameters, "path"),
                )
            )
        elif route_path.startswith(workspace.RAW_ROUTE_PREFIX):
            self._serve_raw_file(
                route_path.removeprefix(workspace.RAW_ROUTE_PREFIX),
                self._read_query_parameter(
                    query_parameters, workspace.RAW_REVISION_QUERY_PARAMETER
                ),
            )
        else:
            # 不回声请求路径：未知路由的应答里没有任何来自请求的可控内容。
            self._send_json_payload(
                404, {"error": "未知路由：本服务只提供白名单内的文件查看接口。"}
            )

    def _dispatch_write_request(self, requested_route_path: str) -> None:
        """按固定白名单分发写路由；白名单之外一律 405。

        写路由都要求是 JSON 对象：``POST /api/file/save`` 保存已有 UTF-8 文本并校验读取版本；
        ``POST /api/file/toggle-task`` 只切换 Markdown 预览中已定位的任务复选框，并校验预览版本；
        ``POST /api/stage`` 的 ``scope`` 取值是封闭枚举（``path`` 或 ``all``）；
        ``POST /api/open`` 的 ``path`` 是仓库相对路径，越界与不存在都在
        :func:`workspace.open_path_in_system` 里按拒绝应答处理。路径会先在服务端校验，参数不会被
        当作任意 ``git`` 选项或 shell 命令执行。
        """
        if requested_route_path == _FILE_TOGGLE_TASK_ROUTE_PATH:
            task_toggle_request, failure_payload = self._read_write_request_body()
            if failure_payload is not None:
                self._send_json_payload(failure_payload.status_code, failure_payload.payload)
                return

            requested_path = task_toggle_request.get("path")
            expected_revision = task_toggle_request.get("revision")
            checkbox_index = task_toggle_request.get("checkbox_index")
            is_checked = task_toggle_request.get("checked")
            if (
                not isinstance(requested_path, str)
                or not isinstance(expected_revision, str)
                or type(checkbox_index) is not int
                or not isinstance(is_checked, bool)
            ):
                self._send_json_payload(
                    400,
                    {
                        "error": "拒绝：任务切换需要字符串 path、revision、整数 checkbox_index "
                        "和布尔 checked。"
                    },
                )
                return
            self._serve_workspace_payload(
                file_edit.toggle_markdown_task_checkbox(
                    self.server.repository_root,
                    file_edit.MarkdownTaskToggleRequest(
                        path=requested_path,
                        expected_revision=expected_revision,
                        checkbox_index=checkbox_index,
                        is_checked=is_checked,
                    ),
                )
            )
            return

        if requested_route_path == _FILE_SAVE_ROUTE_PATH:
            file_save_request, failure_payload = self._read_write_request_body(
                max_body_bytes=_MAX_FILE_SAVE_BODY_BYTES
            )
            if failure_payload is not None:
                self._send_json_payload(failure_payload.status_code, failure_payload.payload)
                return

            requested_path = file_save_request.get("path")
            source_text = file_save_request.get("source")
            expected_revision = file_save_request.get("revision")
            line_ending = file_save_request.get("line_ending")
            if not all(
                isinstance(field_value, str)
                for field_value in (requested_path, source_text, expected_revision, line_ending)
            ):
                self._send_json_payload(
                    400,
                    {"error": "拒绝：保存需要字符串 path、source、revision 和 line_ending。"},
                )
                return
            assert isinstance(requested_path, str)
            assert isinstance(source_text, str)
            assert isinstance(expected_revision, str)
            assert isinstance(line_ending, str)
            self._serve_workspace_payload(
                file_edit.save_file_content(
                    self.server.repository_root,
                    file_edit.FileEditRequest(
                        path=requested_path,
                        source_text=source_text,
                        expected_revision=expected_revision,
                        line_ending=line_ending,
                    ),
                )
            )
            return

        if requested_route_path == _STAGE_ROUTE_PATH:
            if not self.server.git_available:
                self._send_json_payload(405, {"error": "该目录不在 Git 仓库中，不能暂存文件。"})
                return
            stage_request, failure_payload = self._read_write_request_body()
            if failure_payload is not None:
                self._send_json_payload(failure_payload.status_code, failure_payload.payload)
                return

            scope = stage_request.get("scope")
            repository_root = self.server.repository_root
            if scope == workspace.STAGE_SCOPE_ALL:
                self._serve_workspace_payload(workspace.stage_all_changes(repository_root))
                return
            if scope == workspace.STAGE_SCOPE_PATH:
                requested_path = stage_request.get("path")
                if not isinstance(requested_path, str):
                    self._send_json_payload(
                        400, {"error": "拒绝：scope 为 path 时必须给出字符串 path。"}
                    )
                    return
                self._serve_workspace_payload(
                    workspace.stage_changes(repository_root, requested_path)
                )
                return
            self._send_json_payload(
                400,
                {
                    "error": "拒绝：scope 不是可用的暂存范围，"
                    f"请选择「{'」「'.join(sorted(workspace.KNOWN_STAGE_SCOPES))}」。"
                },
            )
            return

        if requested_route_path == _OPEN_ROUTE_PATH:
            open_request, failure_payload = self._read_write_request_body()
            if failure_payload is not None:
                self._send_json_payload(failure_payload.status_code, failure_payload.payload)
                return

            requested_path = open_request.get("path")
            if not isinstance(requested_path, str):
                self._send_json_payload(400, {"error": "拒绝：打开必须给出字符串 path。"})
                return
            self._serve_workspace_payload(
                workspace.open_path_in_system(self.server.repository_root, requested_path)
            )
            return

        self._refuse_non_read_method()

    def _read_write_request_body(
        self,
        *,
        max_body_bytes: int = _MAX_WRITE_BODY_BYTES,
    ) -> tuple[dict[str, object], workspace_read.WorkspacePayload | None]:
        """读取并校验写请求的 JSON 对象体。

        两道门槛都是必须的，而不是讲究：**类型必须是 JSON**（跨站表单式 POST 是「简单请求」，
        浏览器会直接发出，而 JSON 会强制预检、预检必然失败），**长度设上限**（一句话就能让服务
        端在读取时分配内存）。

        Returns:
            tuple[dict[str, object], WorkspacePayload | None]: 解析出的对象，以及失败时的拒绝
                应答（成功时为 ``None``）。
        """
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";")[0].strip().lower() != "application/json":
            return {}, workspace_read.build_refusal_payload(
                415,
                "拒绝：写接口只接受 application/json 请求体"
                "（跨站表单式 POST 会被浏览器直接发出，因此这里用类型强制预检）。",
            )

        try:
            content_length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            return {}, workspace_read.build_refusal_payload(400, "拒绝：Content-Length 不合法。")
        if content_length <= 0:
            return {}, workspace_read.build_refusal_payload(400, "拒绝：请求体为空。")
        if content_length > max_body_bytes:
            # 刻意不读这段正文，因此这条连接必须关掉：HTTP/1.1 连接要被复用，留着一段没读完的
            # 正文会让下一次请求读到它的残余。
            self.close_connection = True
            return {}, workspace_read.build_refusal_payload(
                413, f"拒绝：请求体超过 {max_body_bytes} 字节的上限。"
            )

        try:
            parsed_body = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}, workspace_read.build_refusal_payload(400, "拒绝：请求体不是合法的 JSON。")
        if not isinstance(parsed_body, dict):
            return {}, workspace_read.build_refusal_payload(400, "拒绝：请求体必须是 JSON 对象。")
        return parsed_body, None

    def _read_query_parameter(
        self,
        query_parameters: dict[str, list[str]],
        parameter_name: str,
    ) -> str:
        """取单个查询参数；缺失或重复给出时取第一个。"""
        parameter_values = query_parameters.get(parameter_name)
        return parameter_values[0] if parameter_values else ""

    def _serve_workspace_payload(self, workspace_payload: workspace_read.WorkspacePayload) -> None:
        """返回一个工作区读取结果。"""
        self._send_json_payload(workspace_payload.status_code, workspace_payload.payload)

    def _serve_static_asset(self, asset_name: str) -> None:
        """按固定文件名白名单返回静态资源。

        资源名来自请求路径，因此这里用白名单而不是拼接路径：没有可以拼接的路径，就
        没有可以逃逸的路径。查看器自己的页面资源是手写的三个文件，加上一份第三方
        产物（mermaid，见 :data:`_STATIC_CONTENT_TYPES_BY_FILENAME`），数量固定，
        所以白名单足够；仓库内文件的按路径取用走另一条路由（见
        :meth:`_serve_raw_file`），那里的防护是解析成绝对路径之后再断言。
        """
        content_type = _STATIC_CONTENT_TYPES_BY_FILENAME.get(asset_name)
        if content_type is None:
            self._send_json_payload(404, {"error": "未知的静态资源。"})
            return

        asset_bytes = (_ASSETS_DIRECTORY_PATH / asset_name).read_bytes()
        script_nonce = ""
        if asset_name == "index.html":
            script_nonce = secrets.token_urlsafe(18)
            asset_bytes = asset_bytes.replace(
                _SCRIPT_NONCE_PLACEHOLDER.encode("ascii"), script_nonce.encode("ascii")
            )
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if asset_name == "index.html":
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; "
                f"script-src 'nonce-{script_nonce}' 'strict-dynamic'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: blob:; font-src 'self' data:; "
                "connect-src 'self'; worker-src 'self' blob:; object-src 'none'; "
                "base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
            )
        self.send_header("Content-Length", str(len(asset_bytes)))
        # 本地开发工具不缓存：改了页面就应该立刻看到。
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(asset_bytes)

    def _serve_raw_file(self, encoded_relative_path: str, revision_name: str) -> None:
        """返回仓库内的原始文件字节，供 HTML 文件在新标签页里加载、供图片在内容区显示。

        这是唯一一条保持路径原样的路由，而且必须保持：HTML 文档里的相对引用要能解析
        回同一路由、真的加载出来。替代的防护是 ``resolve()`` 之后再断言仍在仓库根之下
        （见 :func:`workspace.resolve_repository_path`），越界一律拒绝。路径段先解码再
        交给解析器——带 ``%00`` 之类的畸形输入解码后同样落在那条断言上，而不是穿透成
        无应答。

        ``revision_name`` 为空表示工作区当前版本（默认）；给了则是 HEAD / 索引里的历史
        版本，供改动视图做旧新对比。取值是封闭枚举，两种来源走的是同一条边界断言。

        Args:
            encoded_relative_path (str): ``/raw/`` 之后、尚未解码的路径。
            revision_name (str): 历史版本取值；空串表示工作区当前版本。
        """
        if revision_name and not self.server.git_available:
            self._send_json_payload(404, {"error": "该目录不在 Git 仓库中，没有历史版本。"})
            return
        decoded_relative_path = unquote(encoded_relative_path)
        raw_file_result = (
            workspace.build_revision_file_payload(
                self.server.repository_root, decoded_relative_path, revision_name
            )
            if revision_name
            else workspace.build_raw_file_payload(
                self.server.repository_root, decoded_relative_path
            )
        )
        if isinstance(raw_file_result, workspace_read.WorkspacePayload):
            self._send_json_payload(raw_file_result.status_code, raw_file_result.payload)
            return

        self.send_response(raw_file_result.status_code)
        self.send_header("Content-Type", raw_file_result.content_type)
        self.send_header("Content-Length", str(len(raw_file_result.body_bytes)))
        # 表外后缀是二进制流。不声明 nosniff 时浏览器会按内容嗅探，把一个 .txt 当 HTML
        # 执行——即使它从来没有以 text/html 供出过。
        self.send_header("X-Content-Type-Options", "nosniff")
        if raw_file_result.content_type.startswith(("text/html", "image/svg+xml")):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self' data: blob:; script-src 'none'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
                "font-src 'self' data:; object-src 'none'; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'",
            )
        # 与其它读取路径一致：本地开发工具不缓存，改了文件就应该立刻看到。
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw_file_result.body_bytes)

    def _send_json_payload(self, status_code: int, payload: dict[str, object]) -> None:
        """返回一条 JSON 应答。"""
        response_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(response_bytes)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(response_bytes)


def run_server(configuration: ServerConfiguration) -> int:
    """启动服务并阻塞到退出，退出前清理本实例的登记记录。

    Args:
        configuration (ServerConfiguration): 本次启动配置。

    Returns:
        int: 进程退出码；端口无法绑定时为 ``1``。
    """
    try:
        viewer_server = ViewerHTTPServer(configuration, ViewerRequestHandler)
    except OSError as bind_error:
        print(
            f"查看器服务无法绑定 {VIEWER_HOST}:{configuration.port}：{bind_error}",
            file=sys.stderr,
            flush=True,
        )
        return 1

    _register_termination_signal_handlers(viewer_server)
    _start_highlight_prewarm_thread()
    _start_idle_reaper_thread(viewer_server)
    print(
        f"查看器服务已监听 http://{VIEWER_HOST}:{configuration.port}/"
        f"（仓库 {configuration.repository_root.name}，"
        f"空闲时限 {configuration.idle_timeout_seconds:.0f} 秒）",
        file=sys.stderr,
        flush=True,
    )

    try:
        viewer_server.serve_forever(poll_interval=_SERVE_POLL_INTERVAL_SECONDS)
    finally:
        viewer_server.server_close()
        instance.clear_instance_record(
            configuration.repository_root,
            expected_process_id=os.getpid(),
        )
    return 0


def _register_termination_signal_handlers(viewer_server: ViewerHTTPServer) -> None:
    """把 SIGINT / SIGTERM 接到优雅退出上，让登记清理在两条路径都成立。

    处理器必须把 ``shutdown()`` 交给另一个线程：信号处理器跑在主线程里，而主线程
    此刻正阻塞在 ``serve_forever()``，直接调用等于自己等自己。

    Args:
        viewer_server (ViewerHTTPServer): 待停止的服务实例。
    """

    def handle_termination_signal(_signal_number: int, _stack_frame: object) -> None:
        threading.Thread(target=viewer_server.shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, handle_termination_signal)
    signal.signal(signal.SIGTERM, handle_termination_signal)


def _start_highlight_prewarm_thread() -> threading.Thread:
    """在后台线程预热语法高亮，使首个文件请求不为这段导入付费。

    Returns:
        threading.Thread: 已启动的预热线程。
    """
    prewarm_thread = threading.Thread(
        target=rendering.prewarm_highlighting,
        daemon=True,
        name="view-highlight-prewarm",
    )
    prewarm_thread.start()
    return prewarm_thread


def _start_idle_reaper_thread(viewer_server: ViewerHTTPServer) -> threading.Thread | None:
    """启动空闲回收线程；时限非正数时关闭该行为。

    Args:
        viewer_server (ViewerHTTPServer): 被监视的服务实例。

    Returns:
        threading.Thread | None: 已启动的回收线程；关闭自动回收时为 ``None``。
    """
    idle_timeout_seconds = viewer_server.configuration.idle_timeout_seconds
    if idle_timeout_seconds <= 0:
        return None
    check_interval_seconds = max(
        _MIN_IDLE_CHECK_INTERVAL_SECONDS,
        min(_IDLE_CHECK_INTERVAL_SECONDS, idle_timeout_seconds / 4),
    )

    def reap_when_idle() -> None:
        while True:
            time.sleep(check_interval_seconds)
            idle_seconds = viewer_server.seconds_since_last_request()
            if idle_seconds >= idle_timeout_seconds:
                print(
                    f"查看器已闲置 {idle_seconds:.0f} 秒（上限 "
                    f"{idle_timeout_seconds:.0f} 秒），退出并清理登记。",
                    file=sys.stderr,
                    flush=True,
                )
                viewer_server.shutdown()
                return

    idle_reaper_thread = threading.Thread(
        target=reap_when_idle,
        daemon=True,
        name="view-idle-reaper",
    )
    idle_reaper_thread.start()
    return idle_reaper_thread


def main(argv: list[str] | None = None) -> int:
    """解析命令行参数并运行服务。

    Args:
        argv (list[str] | None): 命令行参数；``None`` 时取 ``sys.argv[1:]``。

    Returns:
        int: 进程退出码。
    """
    argument_parser = argparse.ArgumentParser(
        description="本机只读文件与改动查看器服务。由 `just view` 拉起，通常不直接使用。",
    )
    argument_parser.add_argument("--repo-root", required=True, help="被查看仓库的根目录")
    argument_parser.add_argument("--port", type=int, required=True, help="监听端口")
    argument_parser.add_argument(
        "--files-only",
        action="store_true",
        help="只浏览文件，不调用 Git 接口",
    )
    argument_parser.add_argument(
        "--idle-timeout",
        type=float,
        default=instance.DEFAULT_IDLE_TIMEOUT_SECONDS,
        help="空闲回收时限（秒），0 表示关闭自动回收",
    )
    parsed_arguments = argument_parser.parse_args(argv)

    return run_server(
        ServerConfiguration(
            repository_root=Path(parsed_arguments.repo_root).resolve(),
            port=parsed_arguments.port,
            idle_timeout_seconds=parsed_arguments.idle_timeout,
            git_available=not parsed_arguments.files_only,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
