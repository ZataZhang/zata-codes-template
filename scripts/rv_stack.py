"""RV 共享隔离场景：一次性数据库、模型替身与真实后端进程。

只供 tasks/evidence/<prd-stem>/scripts/ 下的 RV 脚本使用，不进入代码 diff。
- 数据库：在本机测试 PostgreSQL / MySQL 中新建一次性库，结束后删除。
- 模型：本进程内的 OpenAI-compatible 替身（PRD 允许替换付费模型传输）。
- 后端：真实 `backend.main:app`（uvicorn 子进程），认证、Redis、路由、迁移、仓库全部真实。
凭据只在运行时从 .env.local / 容器环境读取，不打印、不写入证据。
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx
import sqlalchemy as sa

WORKTREE = Path(__file__).resolve().parents[4]
EVIDENCE_DIR = Path(__file__).resolve().parents[1]
PRE_AGENT_REVISION = "b93aa5cf0228"
MODEL_API_KEY_MARKER = "rv58-fake-model-key-not-a-secret"


def free_port() -> int:
    """向内核申请一个空闲端口。"""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _dotenv_value(name: str) -> str:
    """读取 .env.local 中最后一次出现的值（与 dotenv 覆盖语义一致）。"""
    found = None
    for line in (WORKTREE / ".env.local").read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            found = line.split("=", 1)[1].strip()
    if found is None:
        raise RuntimeError(f"{name} missing in .env.local")
    return found


def server_url(kind: str) -> str:
    """返回测试数据库服务器的管理连接（不含库名）。"""
    if kind == "pg":
        parts = urlsplit(_dotenv_value("DATABASE_URL"))
        return urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))
    if kind == "mysql":
        root_password = subprocess.run(
            ["docker", "exec", "test-mysql-app", "printenv", "MYSQL_ROOT_PASSWORD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        return f"mysql+pymysql://root:{root_password}@127.0.0.1:3306/mysql?charset=utf8mb4"
    raise ValueError(kind)


@dataclass
class TempDatabase:
    """一次性数据库。"""

    kind: str
    name: str
    url: str
    admin_url: str

    def drop(self) -> None:
        engine = sa.create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as connection:
            if self.kind == "pg":
                connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": self.name},
                )
                connection.execute(sa.text(f'DROP DATABASE IF EXISTS "{self.name}"'))
            else:
                connection.execute(sa.text(f"DROP DATABASE IF EXISTS `{self.name}`"))
        engine.dispose()


def create_database(kind: str, label: str) -> TempDatabase:
    admin_url = server_url(kind)
    name = f"rv58_{label}_{kind}_{secrets.token_hex(3)}"
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        if kind == "pg":
            connection.execute(sa.text(f'CREATE DATABASE "{name}"'))
        else:
            connection.execute(
                sa.text(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            )
    engine.dispose()
    parts = urlsplit(admin_url)
    url = urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, ""))
    return TempDatabase(kind=kind, name=name, url=url, admin_url=admin_url)


def alembic(database: TempDatabase, *arguments: str, src_path: Path | None = None) -> str:
    """在真实 alembic 入口执行迁移命令，返回输出。"""
    env = {**os.environ, "DATABASE_URL": database.url}
    if src_path is not None:
        env["PYTHONPATH"] = str(src_path)
    completed = subprocess.run(
        ["uv", "run", "--no-sync", "alembic", *arguments],
        cwd=WORKTREE,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"alembic {arguments} failed:\n{completed.stderr[-4000:]}")
    return completed.stdout + completed.stderr


class ModelStub:
    """OpenAI-compatible Chat Completions 替身，支持 SSE 流式返回并记录请求。"""

    def __init__(
        self,
        delay_seconds: float = 1.0,
        malformed_response: bool = False,
        chunk_delay_seconds: float = 0.35,
        chunk_size: int = 12,
    ) -> None:
        self.requests: list[dict[str, Any]] = []
        self.delay_seconds = delay_seconds
        self.malformed_response = malformed_response
        self.chunk_delay_seconds = chunk_delay_seconds
        self.chunk_size = max(chunk_size, 1)
        self.port = free_port()
        stub = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                request_messages = body.get("messages", [])
                last_user_message = next(
                    (
                        message
                        for message in reversed(request_messages)
                        if isinstance(message, dict) and message.get("role") == "user"
                    ),
                    {},
                )
                request_text = str(last_user_message.get("content", ""))
                immediate_response = "RV2_FAST_" in request_text
                malformed_response = stub.malformed_response or "RV2_FAST_FAILURE" in request_text
                stub.requests.append(
                    {
                        "path": self.path,
                        "authorization_ok": self.headers.get("Authorization")
                        == f"Bearer {MODEL_API_KEY_MARKER}",
                        "body": body,
                    }
                )
                time.sleep(0 if immediate_response else stub.delay_seconds)
                document = stub.respond(body, malformed_response=malformed_response)
                if body.get("stream"):
                    try:
                        self._write_stream(
                            document,
                            chunk_delay_seconds=0 if immediate_response else stub.chunk_delay_seconds,
                        )
                    except (BrokenPipeError, ConnectionResetError):
                        # 真实取消会关闭 SSE 客户端；这属于正常断连。
                        return
                    return
                encoded = json.dumps(document).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def _write_stream(
                self,
                document: dict[str, Any],
                *,
                chunk_delay_seconds: float,
            ) -> None:
                """按 SSE 分片写出同一份响应内容，并在片段之间停顿。"""
                chunk_documents = stub.stream_chunks(document)
                payload = b"".join(
                    f"data: {json.dumps(chunk_document)}\n\n".encode()
                    for chunk_document in chunk_documents
                ) + b"data: [DONE]\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                for chunk_document in chunk_documents:
                    self.wfile.write(f"data: {json.dumps(chunk_document)}\n\n".encode())
                    self.wfile.flush()
                    time.sleep(chunk_delay_seconds)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def stream_chunks(self, document: dict[str, Any]) -> list[dict[str, Any]]:
        """把一次性响应文档拆成 OpenAI 流式 ``delta`` 分片。"""
        choices = document.get("choices")
        if not isinstance(choices, list) or not choices:
            return [{"choices": []}]
        choice_document = choices[0]
        message_document = choice_document.get("message", {})
        chunk_documents: list[dict[str, Any]] = []
        tool_calls = message_document.get("tool_calls")
        if tool_calls:
            chunk_documents.append(
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "tool_calls": [
                                    {
                                        "index": tool_call_index,
                                        "id": tool_call.get("id"),
                                        "type": "function",
                                        "function": tool_call.get("function"),
                                    }
                                    for tool_call_index, tool_call in enumerate(tool_calls)
                                ]
                            },
                            "finish_reason": "tool_calls",
                        }
                    ]
                }
            )
            return chunk_documents
        content = str(message_document.get("content") or "")
        for index in range(0, len(content), self.chunk_size):
            chunk_documents.append(
                {"choices": [{"index": 0, "delta": {"content": content[index : index + self.chunk_size]}}]}
            )
        chunk_documents.append(
            {
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": choice_document.get("finish_reason", "stop"),
                    }
                ]
            }
        )
        return chunk_documents

        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def respond(
        self,
        body: dict[str, Any],
        *,
        malformed_response: bool | None = None,
    ) -> dict[str, Any]:
        if self.malformed_response if malformed_response is None else malformed_response:
            return {"choices": []}
        messages = body.get("messages", [])
        last = messages[-1] if messages else {}
        tools = body.get("tools") or []
        system_text = str(messages[0].get("content", "")) if messages else ""
        if last.get("role") == "tool":
            content = f"peer-result: {last.get('content')}"
        elif tools and "ASK_PEER" in str(last.get("content", "")):
            peer_ids = tools[0]["function"]["parameters"]["properties"]["peer_id"]["enum"]
            requested = str(last.get("content", "")).split("ASK_PEER:", 1)
            peer_id = requested[1].split()[0] if len(requested) > 1 else peer_ids[0]
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "call_a2a_peer",
                                        "arguments": json.dumps(
                                            {"peer_id": peer_id, "message": "remote please echo"}
                                        ),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        elif "RUN_SHELL" in str(last.get("content", "")):
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call-x",
                                    "type": "function",
                                    "function": {
                                        "name": "run_shell",
                                        "arguments": json.dumps({"cmd": "touch /tmp/rv58-pwned"}),
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ]
            }
        else:
            skill_marker = ""
            if "Skill reference:" in system_text:
                skill_marker = " skill=" + system_text.split("Skill reference:\n", 1)[1][:40]
            content = f"stub-reply to: {last.get('content')}{skill_marker}"
        return {
            "choices": [
                {"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
        }

    def close(self) -> None:
        self._server.shutdown()


@dataclass
class Backend:
    """真实后端子进程。"""

    port: int
    process: subprocess.Popen[bytes]
    log_path: Path
    admin_username: str
    admin_password: str
    extra_env: dict[str, str] = field(default_factory=dict)
    redis_container_name: str | None = None

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        if self.redis_container_name is not None:
            subprocess.run(
                ["docker", "rm", "--force", self.redis_container_name],
                capture_output=True,
                timeout=10,
                check=False,
            )


def start_backend(
    database: TempDatabase,
    *,
    model_base_url: str | None,
    extra_env: dict[str, str] | None = None,
    src_path: Path | None = None,
    log_name: str = "backend",
) -> Backend:
    """以一次性数据库和 Redis 启动真实后端并等待 /health。"""
    port = free_port()
    redis_port = free_port()
    redis_container_name = f"rv58-isolated-redis-{port}"
    redis_created = False
    backend: Backend | None = None
    admin_password = "Rv58-" + secrets.token_urlsafe(12)
    try:
        redis_start = subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                redis_container_name,
                "--publish",
                f"127.0.0.1:{redis_port}:6379",
                "redis:7-alpine",
                "redis-server",
                "--save",
                "",
                "--appendonly",
                "no",
            ],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=20,
        )
        if redis_start.returncode != 0:
            raise RuntimeError("isolated Redis container failed to start")
        redis_created = True
        import redis

        redis_client = redis.Redis(
            host="127.0.0.1",
            port=redis_port,
            db=0,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_deadline = time.monotonic() + 20
        redis_ready = False
        while time.monotonic() < redis_deadline:
            try:
                redis_ready = bool(redis_client.ping())
                if redis_ready:
                    break
            except redis.RedisError:
                time.sleep(0.5)
        redis_client.close()
        if not redis_ready:
            raise RuntimeError("isolated Redis container did not become ready")

        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith(("MODEL_", "A2A_", "AUTH_", "SECURITY_"))
        }
        env.update(
            {
                "DATABASE_URL": database.url,
                "REDIS_URL": f"redis://127.0.0.1:{redis_port}/0",
                "AUTH_ADMIN_BOOTSTRAP_USERNAME": "rv58-platform",
                "AUTH_ADMIN_BOOTSTRAP_PASSWORD": admin_password,
                "AUTH_COOKIE_SECURE": "false",
                "SECURITY_API_REQUESTS_PER_MINUTE": "5000",
                "SECURITY_ADMIN_LOGIN_IP_ATTEMPTS": "500",
                "SECURITY_PUBLIC_LOGIN_IP_ATTEMPTS": "500",
                "SECURITY_REGISTER_IP_ATTEMPTS": "500",
                "A2A_PUBLIC_BASE_URL": f"http://127.0.0.1:{port}",
                "A2A_ALLOW_LOOPBACK_FOR_DEV": "true",
                "PORT": str(port),
            }
        )
        if model_base_url:
            env.update(
                {
                    "MODEL_BASE_URL": model_base_url,
                    "MODEL_API_KEY": MODEL_API_KEY_MARKER,
                    "MODEL_NAME": "rv58-stub-model",
                }
            )
        else:
            env.update({"MODEL_BASE_URL": "", "MODEL_API_KEY": "", "MODEL_NAME": ""})
        if src_path is not None:
            env["PYTHONPATH"] = str(src_path)
        env.update(extra_env or {})
        log_path = Path(f"/tmp/rv58-{log_name}-{port}.log")
        log_file = log_path.open("wb")
        process = subprocess.Popen(
            [
                "uv",
                "run",
                "--no-sync",
                "uvicorn",
                "backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=WORKTREE,
            env=env,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        backend = Backend(
            port,
            process,
            log_path,
            "rv58-platform",
            admin_password,
            extra_env or {},
            redis_container_name,
        )
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"backend exited: {log_path.read_text(errors='replace')[-3000:]}")
            try:
                if httpx.get(f"{backend.base_url}/health", timeout=2).status_code == 200:
                    return backend
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        raise RuntimeError("backend did not become healthy")
    except Exception:
        if backend is not None:
            backend.stop()
        elif redis_created:
            subprocess.run(
                ["docker", "rm", "--force", redis_container_name],
                capture_output=True,
                timeout=10,
                check=False,
            )
        raise


class Http:
    """带独立 Cookie 罐的 HTTP 客户端（每个身份一个新客户端）。"""

    def __init__(self, base_url: str) -> None:
        self.client = httpx.Client(base_url=base_url, timeout=30)

    def call(self, method: str, path: str, expect: int | tuple[int, ...] | None = None, **kw: Any):
        if method == "POST" and path == "/agent-runs":
            headers = dict(kw.pop("headers", None) or {})
            headers.setdefault("Idempotency-Key", secrets.token_hex(8))
            kw["headers"] = headers
        response = self.client.request(method, path, **kw)
        if expect is not None:
            expected = (expect,) if isinstance(expect, int) else expect
            if response.status_code not in expected:
                raise AssertionError(
                    f"{method} {path} -> {response.status_code} (expected {expected}): "
                    f"{response.text[:400]}"
                )
        return response


def admin_login(backend: Backend, username: str, password: str) -> Http:
    session = Http(backend.base_url)
    session.call(
        "POST", "/admin/auth/login", 200, json={"identifier": username, "password": password}
    )
    return session


def public_register(backend: Backend, email: str, password: str) -> tuple[Http, str]:
    """经正式注册入口创建 public 用户，返回会话与 user_id。"""
    session = Http(backend.base_url)
    response = session.call(
        "POST",
        "/auth/register",
        201,
        json={"display_name": email.split("@")[0], "email": email, "password": password},
    )
    return session, response.json()["user_id"]


def public_login(backend: Backend, email: str, password: str) -> Http:
    session = Http(backend.base_url)
    session.call("POST", "/auth/login", 200, json={"identifier": email, "password": password})
    return session


def wait_run(session: Http, run_id: str, timeout: float = 60) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = session.call("GET", f"/agent-runs/{run_id}", 200).json()
        if run["status"] in {"succeeded", "failed", "cancelled", "interrupted"}:
            return run
        time.sleep(0.4)
    raise AssertionError(f"run {run_id} did not finish")


def git_identity() -> dict[str, str]:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=WORKTREE, capture_output=True, text=True
    ).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="rv58-index-", dir="/private/tmp") as index_directory:
        index_path = Path(index_directory) / "index"
        env = {**os.environ, "GIT_INDEX_FILE": str(index_path)}
        subprocess.run(["git", "read-tree", "HEAD"], cwd=WORKTREE, env=env, check=True)
        excluded_paths = (
            "tasks/evidence/",
            "tasks/pending/",
            "tasks/archive/",
            "tests/playwright-e2e/tests/rv58-workflows/",
            "tests/playwright-e2e/tests/.rv58-workflows/",
            ".pnpm-store/",
        )
        subprocess.run(
            ["git", "rm", "--cached", "-r", "--ignore-unmatch", "--", *excluded_paths],
            cwd=WORKTREE,
            env=env,
            capture_output=True,
            check=True,
        )
        changed_paths = subprocess.run(
            ["git", "diff", "--name-only", "-z", "HEAD"],
            cwd=WORKTREE,
            capture_output=True,
            check=True,
        ).stdout.decode().split("\0")
        untracked_paths = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=WORKTREE,
            capture_output=True,
            check=True,
        ).stdout.decode().split("\0")
        snapshot_paths = sorted({path for path in changed_paths + untracked_paths if path})
        for relative_path in snapshot_paths:
            if relative_path.startswith(
                (
                    "tasks/evidence/",
                    "tasks/pending/",
                    "tasks/archive/",
                    "tests/playwright-e2e/tests/rv58-workflows/",
                    "tests/playwright-e2e/tests/.rv58-workflows/",
                    ".pnpm-store/",
                )
            ):
                continue
            absolute_path = WORKTREE / relative_path
            if not absolute_path.exists() and not absolute_path.is_symlink():
                subprocess.run(
                    ["git", "update-index", "--force-remove", "--", relative_path],
                    cwd=WORKTREE,
                    env=env,
                    check=False,
                )
                continue
            if absolute_path.is_symlink():
                file_mode = "120000"
                file_content = os.readlink(absolute_path).encode("utf-8")
            else:
                indexed = subprocess.run(
                    ["git", "ls-files", "--stage", "--", relative_path],
                    cwd=WORKTREE,
                    capture_output=True,
                    text=True,
                    check=True,
                ).stdout
                indexed_mode = indexed.split(maxsplit=1)[0] if indexed else ""
                file_mode = indexed_mode or (
                    "100755" if absolute_path.stat().st_mode & stat.S_IXUSR else "100644"
                )
                file_content = absolute_path.read_bytes()
            file_hash = subprocess.run(
                ["git", "hash-object", "-w", f"--path={relative_path}", "--stdin"],
                cwd=WORKTREE,
                input=file_content,
                capture_output=True,
                check=True,
            ).stdout.decode().strip()
            subprocess.run(
                [
                    "git",
                    "update-index",
                    "--add",
                    "--cacheinfo",
                    f"{file_mode},{file_hash},{relative_path}",
                ],
                cwd=WORKTREE,
                env=env,
                check=True,
            )
        tree = subprocess.run(
            ["git", "write-tree"], cwd=WORKTREE, env=env, capture_output=True, text=True, check=True
        ).stdout.strip()
    return {"head": head, "working_tree_excluding_delivery_records": tree}


class Report:
    """把一个 RV 项的输出写到 stdout 与该项专属证据文件。"""

    def __init__(self, path: Path | None) -> None:
        self.lines: list[str] = []
        self.path = path

    def __call__(self, *parts: object) -> None:
        line = " ".join(str(part) for part in parts)
        print(line, flush=True)
        self.lines.append(line)

    def save(self) -> None:
        if self.path is not None:
            self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


def main_guard(function: Any) -> None:
    try:
        function()
    except Exception as error:  # noqa: BLE001
        print(f"RV_RESULT: FAIL {type(error).__name__}: {error}", flush=True)
        sys.exit(1)
