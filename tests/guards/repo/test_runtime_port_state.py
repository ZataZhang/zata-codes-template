"""守护本地主机运行端口单一来源的守卫测试（guard test）。

本文件位于 ``tests/guards/``，失败意味着 just 入口或本地 Compose 配置绕过了
``.env.run-state``。正确做法是修复触发失败的运行脚本或配置，而不是放宽本测试。
详见 ``docs/ai-standards/testing.md`` 的 Guard Tests 小节。
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from pathlib import Path

import pytest
import yaml

_PROJECT_ROOT_PATH = Path(__file__).resolve().parents[3]
_JUSTFILE_PATH = _PROJECT_ROOT_PATH / "justfile"
_LOCAL_COMPOSE_PATH = _PROJECT_ROOT_PATH / "docker-compose.yml"


@pytest.mark.skipif(shutil.which("just") is None, reason="需要 just 验证真实运行入口")
def test_run_recipe_persists_and_reuses_runtime_ports(tmp_path: Path) -> None:
    """端口参数应写入 run-state，后续启动应自动复用。"""
    isolated_justfile_path = tmp_path / "justfile"
    isolated_justfile_path.write_text(
        _JUSTFILE_PATH.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "justfile.shared").write_text(
        "_check-completion:\n    @true\n",
        encoding="utf-8",
    )

    with socket.socket() as available_port_socket:
        available_port_socket.bind(("127.0.0.1", 0))
        selected_backend_port = available_port_socket.getsockname()[1]

    first_run_process = subprocess.run(
        [
            "just",
            "run",
            "backend",
            f"backend_port={selected_backend_port}",
            "backend_cmd=env",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    second_run_process = subprocess.run(
        ["just", "run", "backend", "backend_cmd=env"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    expected_port_line = f"PORT={selected_backend_port}"
    run_state_text = (tmp_path / ".env.run-state").read_text(encoding="utf-8")
    assert expected_port_line in first_run_process.stdout
    assert expected_port_line in second_run_process.stdout
    assert f"BACKEND_PORT={selected_backend_port}" in run_state_text


def test_local_host_entrypoints_consume_runtime_port_state() -> None:
    """本地主机入口应消费 run-state，copy 不应把随机端口写进源码。"""
    justfile_text = _JUSTFILE_PATH.read_text(encoding="utf-8")
    frontend_recipe_start = justfile_text.index('frontend action="dev":')
    public_recipe_start = justfile_text.index('frontend-public action="dev":')
    copy_recipe_start = justfile_text.index("copy name force='':")
    frontend_recipe_text = justfile_text[frontend_recipe_start:public_recipe_start]
    public_recipe_text = justfile_text[public_recipe_start:copy_recipe_start]
    copy_recipe_text = justfile_text[copy_recipe_start:]

    with open(_LOCAL_COMPOSE_PATH, "r", encoding="utf-8") as compose_handle:
        local_compose_doc = yaml.safe_load(compose_handle)

    local_service_by_name = local_compose_doc["services"]
    assert local_service_by_name["zata-codes-template-backend"]["ports"] == [
        "${BACKEND_PORT:-8000}:8000"
    ]
    assert local_service_by_name["zata-codes-template-admin"]["ports"] == [
        "${FRONTEND_ADMIN_PORT:-5173}:80"
    ]
    assert local_service_by_name["zata-codes-template-public"]["ports"] == [
        "${FRONTEND_PUBLIC_PORT:-3000}:3000"
    ]
    assert local_service_by_name["zata-codes-template-public"]["environment"] == [
        "API_BASE_URL=${API_BASE_URL:-http://zata-codes-template-backend:8000}"
    ]
    assert 'env_file_args+=(--env-file "$run_state_file")' in justfile_text
    assert 'BACKEND_PORT="$backend_port"' in justfile_text
    assert 'FRONTEND_ADMIN_PORT="$frontend_admin_port"' in justfile_text
    assert 'FRONTEND_PUBLIC_PORT="$frontend_public_port"' in justfile_text
    assert "just run frontend" in frontend_recipe_text
    assert "just run frontend-public" in public_recipe_text
    assert '.replace("${BACKEND_PORT:-8000}"' not in copy_recipe_text
    assert "printf 'BACKEND_PORT=%s\\n'" in copy_recipe_text
    assert "process.env.API_BASE_URL" in (
        _PROJECT_ROOT_PATH / "frontend-public" / "next.config.ts"
    ).read_text(encoding="utf-8")
