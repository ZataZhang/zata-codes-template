"""启动配置优先级、失败隔离及真实 Settings 导入验证。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from backend.infrastructure.config.startup import build_startup_environment


def test_startup_environment_preserves_strings_and_json_types() -> None:
    """字符串不展开，布尔、数字、列表保持可供 Settings 校验的表示。"""
    assert build_startup_environment(
        {
            "APP_NAME": "${UNCHANGED}",
            "DB_PORT": 5544,
            "OBSERVABILITY_ENABLED": False,
            "MCP_ALLOWED_HOSTS": ["example.com"],
            "runtime_config": {"enabled": True},
        },
        credential_names=("READER_USER", "READER_PASSWORD"),
    ) == {
        "APP_NAME": "${UNCHANGED}",
        "DB_PORT": "5544",
        "OBSERVABILITY_ENABLED": "false",
        "MCP_ALLOWED_HOSTS": '["example.com"]',
    }


@pytest.mark.parametrize(
    "invalid_document",
    [
        {"NACOS_SERVER_ADDR": "http://other"},
        {"READER_PASSWORD": "secret"},
        {"CONFIG_PROVIDER": {}},
        {"app_name": "bad"},
        {"DB_PORT": None},
        {"DB_PORT": float("nan")},
        {"runtime_config": []},
    ],
)
def test_startup_environment_rejects_invalid_documents(invalid_document: dict[str, object]) -> None:
    """非法文档整体拒绝，错误消息不包含配置值。"""
    with pytest.raises(ValueError) as config_error:
        build_startup_environment(
            invalid_document, credential_names=("READER_USER", "READER_PASSWORD")
        )
    assert "secret" not in str(config_error.value)


@pytest.fixture
def nacos_server() -> Iterator[tuple[ThreadingHTTPServer, dict[str, object]]]:
    """通过真实 HTTP 传输提供已核对的 Nacos Client API 响应结构。"""
    server_state: dict[str, object] = {"content": "{}", "requests": []}

    class NacosHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            """校验真实客户端提交的登录表单。"""
            body = self.rfile.read(int(self.headers["Content-Length"])).decode()
            assert parse_qs(body) == {"username": ["reader"], "password": ["test-password"]}
            self._reply({"accessToken": "test-access-token", "tokenTtl": 3600})

        def do_GET(self) -> None:  # noqa: N802
            """返回官方 Client API 的 content 外层结构，正文由用例控制。"""
            assert self.headers["accessToken"] == "test-access-token"
            query = parse_qs(urlsplit(self.path).query)
            assert query == {
                "dataId": ["settings.json"],
                "groupName": ["TEST"],
                "namespaceId": ["staging"],
            }
            requests = server_state["requests"]
            assert isinstance(requests, list)
            requests.append(self.path)
            self._reply(
                {
                    "code": 0,
                    "data": {
                        "resultCode": 200,
                        "content": server_state["content"],
                        "md5": "fixture-md5",
                    },
                }
            )

        def _reply(self, payload: dict[str, object]) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode())

        def log_message(self, format: str, *args: object) -> None:
            """避免测试 HTTP 服务写访问日志。"""

    server = ThreadingHTTPServer(("127.0.0.1", 0), NacosHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        yield server, server_state
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


@pytest.fixture
def startup_project(tmp_path: Path) -> Path:
    """复制真实后端代码到无开发者凭据的隔离项目目录。"""
    repository_root = Path(__file__).resolve().parents[2]
    shutil.copytree(
        repository_root / "src/backend",
        tmp_path / "src/backend",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "config.toml").write_text(
        '[app]\napp_name="toml-name"\n[database]\nhost="toml-db"\n'
        '[redis]\nurl="redis://toml-redis:6379/0"\n',
        encoding="utf-8",
    )
    return tmp_path


def run_settings_process(
    project_path: Path, process_environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    """由独立进程导入真实 Settings 和数据库引擎，避免全局配置缓存干扰。"""
    return subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; "
            "from backend.infrastructure.config.settings import config, startup_runtime_config; "
            "from backend.infrastructure.persistence.database import engine; "
            "print(json.dumps([config.app_name, config.database.host, config.database.port, "
            "config.observability.enabled, config.redis.url, "
            "config.postgres_password.get_secret_value(), str(engine.url), "
            "startup_runtime_config]))",
        ],
        cwd=project_path,
        env={"PYTHONPATH": str(project_path / "src"), **process_environment},
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def test_settings_and_database_use_remote_config_before_initialization(
    startup_project: Path,
    nacos_server: tuple[ThreadingHTTPServer, dict[str, object]],
) -> None:
    """进程、两份 dotenv、Nacos、TOML 按约定覆盖，数据库初始化使用远端 URL。"""
    server, state = nacos_server
    state["content"] = json.dumps(
        {
            "APP_NAME": "remote-name",
            "DB_HOST": "remote-db",
            "DB_PORT": 5555,
            "OBSERVABILITY_ENABLED": False,
            "POSTGRES_PASSWORD": "remote-secret",
            "DATABASE_URL": "sqlite:///:memory:",
            "runtime_config": {"feature_enabled": True},
        }
    )
    (startup_project / ".env").write_text("DB_PORT=5444\nAPP_NAME=dotenv-name\n", encoding="utf-8")
    (startup_project / ".env.local").write_text(
        "DB_HOST=local-db\nAPP_NAME=local-name\n", encoding="utf-8"
    )
    completed = run_settings_process(
        startup_project,
        {
            "NACOS_SERVER_ADDR": f"http://127.0.0.1:{server.server_port}",
            "NACOS_USERNAME": "reader",
            "NACOS_PASSWORD": "test-password",
            "NACOS_NAMESPACE_ID": "staging",
            "NACOS_GROUP": "TEST",
            "NACOS_DATA_ID": "settings.json",
            "APP_NAME": "process-name",
            "POSTGRES_PASSWORD": "",
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == [
        "process-name",
        "local-db",
        5444,
        False,
        "redis://toml-redis:6379/0",
        "",
        "sqlite:///:memory:",
        {"feature_enabled": True},
    ]
    assert len(state["requests"]) == 1


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"DB_PORT":null}',
        '{"DB_PORT":"secret-wrong-integer"}',
        '{"NACOS_PASSWORD":"secret"}',
    ],
)
def test_invalid_remote_document_stops_settings_import(
    startup_project: Path,
    nacos_server: tuple[ThreadingHTTPServer, dict[str, object]],
    content: str,
) -> None:
    """无效远端配置在数据库初始化前失败，异常不回显配置正文。"""
    server, state = nacos_server
    state["content"] = content
    completed = run_settings_process(
        startup_project,
        {
            "NACOS_SERVER_ADDR": f"http://127.0.0.1:{server.server_port}",
            "NACOS_USERNAME": "reader",
            "NACOS_PASSWORD": "test-password",
            "NACOS_NAMESPACE_ID": "staging",
            "NACOS_GROUP": "TEST",
            "NACOS_DATA_ID": "settings.json",
        },
    )
    assert completed.returncode != 0
    assert "create_database_engine" not in completed.stderr
    assert content not in completed.stderr
    assert "secret-wrong-integer" not in completed.stderr


def test_local_mode_needs_no_nacos(startup_project: Path) -> None:
    """未配置 Nacos 时，本地 dotenv 和 TOML 保持可用。"""
    (startup_project / ".env").write_text("APP_NAME=dotenv-name\n", encoding="utf-8")
    (startup_project / ".env.local").write_text(
        "APP_NAME=local-name\nDATABASE_URL=sqlite:///:memory:\n",
        encoding="utf-8",
    )
    completed = run_settings_process(startup_project, {})
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip().splitlines()[-1])[:2] == ["local-name", "toml-db"]
