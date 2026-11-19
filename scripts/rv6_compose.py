"""rv-6：三服务生产容器、双前端同源代理与模型密钥边界。"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
import redis

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv6_mirror_lock  # noqa: E402
import rv_stack as stack  # noqa: E402

OPERATION_BUDGET_SECONDS = 280


def remaining_timeout(started_at: float, ceiling: int) -> int:
    """按单次证据门禁的总时限返回有界子进程超时。"""
    remaining = OPERATION_BUDGET_SECONDS - (time.monotonic() - started_at)
    if remaining <= 0:
        raise TimeoutError("rv-6 validation exceeded its 280-second operation budget")
    return max(1, min(ceiling, int(remaining)))


def compose_up_with_port_retry(
    compose: list[str],
    environment: dict[str, str],
    started_at: float,
    report: stack.Report,
) -> tuple[subprocess.CompletedProcess[str], dict[str, int]]:
    """遇到短暂宿主机端口争用时重新分配端口并重试 Compose。"""
    port_environment_key = {
        "backend": "BACKEND_PORT",
        "admin": "FRONTEND_ADMIN_PORT",
        "public": "FRONTEND_PUBLIC_PORT",
    }
    completed: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, 4):
        selected_port_by_service = {
            service_name: stack.free_port() for service_name in port_environment_key
        }
        for service_name, environment_key in port_environment_key.items():
            environment[environment_key] = str(selected_port_by_service[service_name])
        environment["A2A_PUBLIC_BASE_URL"] = (
            f"http://127.0.0.1:{selected_port_by_service['backend']}"
        )
        try:
            completed = subprocess.run(
                [*compose, "up", "-d", "--build"],
                cwd=stack.WORKTREE,
                env=environment,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=remaining_timeout(started_at, 235),
            )
        except subprocess.TimeoutExpired as error:
            captured_stdout = error.stdout or ""
            captured_stderr = error.stderr or ""
            if isinstance(captured_stdout, bytes):
                captured_stdout = captured_stdout.decode("utf-8", errors="replace")
            if isinstance(captured_stderr, bytes):
                captured_stderr = captured_stderr.decode("utf-8", errors="replace")
            report("docker compose up partial output:\n" + captured_stdout[-9000:])
            report("docker compose up partial errors:\n" + captured_stderr[-3000:])
            raise
        if completed.returncode == 0:
            return completed, selected_port_by_service
        output = f"{completed.stdout}\n{completed.stderr}"
        transient_port_conflict = any(
            marker in output.lower()
            for marker in ("address already in use", "port is already allocated")
        )
        if not transient_port_conflict or attempt == 3:
            return completed, selected_port_by_service
        report(
            "Compose host port collision on attempt:",
            attempt,
            "; selecting new ports and retrying.",
        )
        subprocess.run(
            [*compose, "down", "--remove-orphans", "--timeout", "5"],
            cwd=stack.WORKTREE,
            env=environment,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=remaining_timeout(started_at, 10),
            check=False,
        )
    if completed is None:
        raise RuntimeError("Compose startup did not run")
    return completed, selected_port_by_service


def copy_runtime_package(
    compose: list[str],
    environment: dict[str, str],
    service_name: str,
    container_path: str,
    destination_root: Path,
    started_at: float,
    report: stack.Report,
) -> Path:
    """从正在运行的生产容器复制实际交付目录，供密钥探针扫描。"""
    container_result = subprocess.run(
        [*compose, "ps", "-q", service_name],
        cwd=stack.WORKTREE,
        env=environment,
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
        timeout=remaining_timeout(started_at, 8),
    )
    container_id = container_result.stdout.strip().splitlines()[0]
    image_result = subprocess.run(
        ["docker", "inspect", "--format", "{{.Image}}", container_id],
        cwd=stack.WORKTREE,
        capture_output=True,
        text=True,
        errors="replace",
        check=True,
        timeout=remaining_timeout(started_at, 8),
    )
    image_id = image_result.stdout.strip()
    destination_path = destination_root / service_name
    copied_package = subprocess.run(
        ["docker", "cp", f"{container_id}:{container_path}", str(destination_path)],
        cwd=stack.WORKTREE,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=remaining_timeout(started_at, 15),
    )
    if copied_package.returncode != 0:
        raise RuntimeError(
            f"failed to copy {service_name} package from image {image_id}: "
            f"{copied_package.stderr[-1000:]}"
        )
    if not destination_path.is_dir() or not any(destination_path.iterdir()):
        raise RuntimeError(f"copied package from {service_name} is empty")
    report(
        "runtime image package copied:",
        service_name,
        "image:",
        image_id,
        "path:",
        container_path,
    )
    return destination_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    arguments = parser.parse_args()
    started_at = time.monotonic()
    report_name = "rv-6-negative-control.txt" if arguments.negative_control else "rv-6-production-compose.txt"
    report = stack.Report(stack.EVIDENCE_DIR / report_name)
    report(f"# rv-6 production compose at {datetime.now(UTC).isoformat()}")
    report("identity:", json.dumps(stack.git_identity()))
    mirror_lock = rv6_mirror_lock.prepare_mirror_lock(
        remaining_timeout(started_at, 90)
    )
    report(
        "dependency lock:",
        mirror_lock.relative_to(stack.WORKTREE),
        "versions and package hashes verified against uv.lock",
    )
    database = stack.create_database("pg", "rv6")
    model = stack.ModelStub(delay_seconds=0.1)
    project_name = f"rv58-{secrets.token_hex(3)}"
    redis_port = stack.free_port()
    redis_container_name = f"{project_name}-redis"
    environment = {
        **os.environ,
        "COMPOSE_PROJECT_NAME": project_name,
        "BUILDX_CONFIG": os.environ.get("BUILDX_CONFIG", "/tmp/rv58-buildx"),
        "BACKEND_PORT": "0",
        "FRONTEND_ADMIN_PORT": "0",
        "FRONTEND_PUBLIC_PORT": "0",
        "DATABASE_URL": database.url.replace("127.0.0.1", "host.docker.internal").replace(
            "localhost", "host.docker.internal"
        ),
        "REDIS_URL": f"redis://host.docker.internal:{redis_port}/0",
        "AUTH_COOKIE_SECURE": "false",
        "AUTH_ADMIN_BOOTSTRAP_USERNAME": "rv6-platform",
        "AUTH_ADMIN_BOOTSTRAP_PASSWORD": "rv6-platform-password",
        "APP_BOOTSTRAP_EMAIL": "rv6-member@example.test",
        "APP_BOOTSTRAP_PASSWORD": "rv6-member-password",
        "MODEL_BASE_URL": model.base_url,
        "MODEL_API_KEY": stack.MODEL_API_KEY_MARKER,
        "MODEL_NAME": "rv6-stub-model",
        "API_BASE_URL": "http://zata-codes-template-backend:8000",
        "A2A_PUBLIC_BASE_URL": "http://127.0.0.1:0",
        "A2A_ALLOW_LOOPBACK_FOR_DEV": "true",
        "A2A_CREDENTIAL_ENCRYPTION_KEY": "rv6-local-encryption-not-a-secret",
        "SECURITY_API_REQUESTS_PER_MINUTE": "5000",
    }
    if arguments.negative_control:
        environment["API_BASE_URL"] += "/api"
    compose = [
        "docker",
        "compose",
        "-p",
        project_name,
        "-f",
        "docker-compose.yml",
        "-f",
        str(stack.EVIDENCE_DIR / "scripts" / "rv6-network.yml"),
    ]
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
            timeout=remaining_timeout(started_at, 20),
        )
        if redis_start.returncode != 0:
            raise RuntimeError("isolated Redis container failed to start")
        report("isolated Redis container:", "started with a disposable empty database")
        redis_client = redis.Redis(
            host="127.0.0.1",
            port=redis_port,
            db=0,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        redis_deadline = time.monotonic() + remaining_timeout(started_at, 20)
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
        completed, selected_port_by_service = compose_up_with_port_retry(
            compose,
            environment,
            started_at,
            report,
        )
        backend_port = selected_port_by_service["backend"]
        admin_port = selected_port_by_service["admin"]
        public_port = selected_port_by_service["public"]
        report("docker compose up exit:", completed.returncode)
        report(completed.stdout[-6000:] + completed.stderr[-6000:])
        if completed.returncode != 0:
            raise RuntimeError("compose build/start failed")
        backend_health = None
        deadline = time.monotonic() + remaining_timeout(started_at, 20)
        while time.monotonic() < deadline:
            try:
                backend_health = httpx.get(
                    f"http://127.0.0.1:{backend_port}/health",
                    timeout=remaining_timeout(started_at, 3),
                )
                if backend_health.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(2)
        assert backend_health is not None and backend_health.status_code == 200
        report("backend health through production container:", backend_health.json())
        for frontend_base_url, entry_path in (
            (f"http://127.0.0.1:{public_port}", "/login"),
            (f"http://127.0.0.1:{admin_port}", "/sign-in"),
        ):
            entry_response = None
            frontend_deadline = time.monotonic() + remaining_timeout(started_at, 12)
            while time.monotonic() < frontend_deadline:
                try:
                    entry_response = httpx.get(
                        frontend_base_url + entry_path,
                        timeout=remaining_timeout(started_at, 3),
                    )
                    if entry_response.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            assert entry_response is not None and entry_response.status_code == 200
            report("frontend entry ready:", frontend_base_url + entry_path)

        direct_login = httpx.post(
            f"http://127.0.0.1:{backend_port}/auth/login",
            json={"identifier": "rv6-member@example.test", "password": "rv6-member-password"},
            timeout=remaining_timeout(started_at, 8),
        )
        report("direct backend login response:", direct_login.status_code, direct_login.text[:400])
        public = httpx.Client(base_url=f"http://127.0.0.1:{public_port}", timeout=30)
        login = public.post(
            "/api/auth/login",
            json={"identifier": "rv6-member@example.test", "password": "rv6-member-password"},
            timeout=remaining_timeout(started_at, 8),
        )
        report("public login response:", login.status_code, login.text[:400])
        if arguments.negative_control:
            report("fault injection:", "production Next rewrite receives a duplicated /api upstream prefix")
            try:
                assert login.status_code == 200, "public login should survive a single /api proxy pass"
            except AssertionError as error:
                report("expected_fail:", str(error), "; observed", login.status_code)
                report("\nEXPECTED_FAIL: rv-6 proxy assertion detected the duplicated upstream prefix")
                report("RV_RESULT: NEGATIVE CONTROL DETECTED rv-6")
                return
            raise AssertionError("duplicated /api prefix unexpectedly passed production login")
        assert login.status_code == 200
        runs = public.get("/api/agent-runs", timeout=remaining_timeout(started_at, 8))
        report("public runs response:", runs.status_code, runs.text[:400])
        assert runs.status_code == 200 and runs.json()["items"] == []
        duplicated = public.get(
            "/api/api/agent-runs", timeout=remaining_timeout(started_at, 8)
        )
        report("duplicated prefix response:", duplicated.status_code, duplicated.text[:200])
        assert duplicated.status_code == 404
        admin = httpx.Client(base_url=f"http://127.0.0.1:{admin_port}", timeout=30)
        admin_login = admin.post(
            "/api/admin/auth/login",
            json={"identifier": "rv6-platform", "password": "rv6-platform-password"},
            timeout=remaining_timeout(started_at, 8),
        )
        report("admin login response:", admin_login.status_code, admin_login.text[:400])
        assert admin_login.status_code == 200
        admin_me = admin.get(
            "/api/admin/auth/me", timeout=remaining_timeout(started_at, 8)
        )
        report("admin me response:", admin_me.status_code, admin_me.text[:400])
        assert admin_me.status_code == 200
        a2a_proxy = public.get(
            "/a2a/agents/example",
            headers={"A2A-Version": "1.0"},
            timeout=remaining_timeout(started_at, 8),
        )
        report("A2A proxy response:", a2a_proxy.status_code, a2a_proxy.text[:200])
        assert a2a_proxy.status_code == 401
        report("public login + /api/agent-runs:", login.status_code, runs.status_code)
        report("admin login + /api/admin/auth/me:", admin_login.status_code, admin_me.status_code)
        report("duplicate /api/api/agent-runs:", duplicated.status_code, "A2A proxy unauthorized:", a2a_proxy.status_code)
        response_text = login.text + runs.text + admin_login.text + admin_me.text
        assert stack.MODEL_API_KEY_MARKER not in response_text
        with tempfile.TemporaryDirectory(prefix="rv6-runtime-packages-") as scan_root:
            scan_directory = Path(scan_root)
            admin_image_package = copy_runtime_package(
                compose,
                environment,
                "zata-codes-template-admin",
                "/usr/share/nginx/html",
                scan_directory,
                started_at,
                report,
            )
            public_image_package = copy_runtime_package(
                compose,
                environment,
                "zata-codes-template-public",
                "/app/frontend-public",
                scan_directory,
                started_at,
                report,
            )
            scan = subprocess.run(
                [
                    "uv",
                    "run",
                    "--no-sync",
                    "python",
                    str(stack.EVIDENCE_DIR / "scripts" / "rv6_secret_scan.py"),
                    f"admin_host={stack.WORKTREE / 'frontend-admin' / 'dist'}",
                    f"public_host={stack.WORKTREE / 'frontend-public' / '.next'}",
                    f"admin_image={admin_image_package}",
                    f"public_image={public_image_package}",
                ],
                cwd=stack.WORKTREE,
                env={**os.environ, "RV6_MARKER": stack.MODEL_API_KEY_MARKER},
                capture_output=True,
                text=True,
                check=True,
                timeout=remaining_timeout(started_at, 30),
            )
        report(scan.stdout)
        report("three production services started; browser-facing responses and static bundles contain no model key marker")
        report("\nRV_RESULT: PASS rv-6")
    except Exception as error:
        report(f"\nRV_RESULT: FAIL rv-6: {type(error).__name__}: {error}")
        raise
    finally:
        for service_name in (
            "zata-codes-template-backend",
            "zata-codes-template-public",
        ):
            try:
                service_logs = subprocess.run(
                    [*compose, "logs", "--tail=120", service_name],
                    cwd=stack.WORKTREE,
                    env=environment,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=5,
                )
                report(f"{service_name} logs before shutdown:\n" + service_logs.stdout[-6000:] + service_logs.stderr[-1000:])
            except (OSError, subprocess.TimeoutExpired):
                report(f"{service_name} logs omitted to preserve the validation deadline")
        try:
            down = subprocess.run(
                [*compose, "down", "--remove-orphans", "--timeout", "10"],
                cwd=stack.WORKTREE,
                env=environment,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=25,
            )
            report("docker compose down exit:", down.returncode)
            if down.returncode != 0:
                subprocess.run(
                    [*compose, "kill"],
                    cwd=stack.WORKTREE,
                    env=environment,
                    capture_output=True,
                    timeout=8,
                    check=False,
                )
        except (OSError, subprocess.TimeoutExpired) as error:
            report("docker compose cleanup result:", type(error).__name__)
        finally:
            try:
                redis_cleanup = subprocess.run(
                    ["docker", "rm", "--force", redis_container_name],
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=8,
                    check=False,
                )
                report("isolated Redis cleanup exit:", redis_cleanup.returncode)
            except (OSError, subprocess.TimeoutExpired) as error:
                report("isolated Redis cleanup result:", type(error).__name__)
            finally:
                report.save()
                model.close()
                database.drop()


if __name__ == "__main__":
    stack.main_guard(main)
