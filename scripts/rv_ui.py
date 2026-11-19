"""rv-2/rv-3：用真实 just e2e 入口运行双前端流程并保存证据。

用法：uv run --no-sync python tasks/evidence/<stem>/scripts/rv_ui.py --rv 2
Playwright 流程从本目录临时复制到测试运行目录，结束后会删除，不进入代码 diff。
"""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402

OPERATION_BUDGET_SECONDS = 588


def remaining_timeout(started_at: float, ceiling: int) -> int:
    """让单条 RV 命令在 300 秒提交门禁前完成清理。"""
    remaining = OPERATION_BUDGET_SECONDS - (time.monotonic() - started_at)
    if remaining <= 0:
        raise TimeoutError("real UI validation exceeded its 280-second operation budget")
    return max(1, min(ceiling, int(remaining)))


def cleanup_command(arguments: list[str], timeout: int = 8) -> None:
    """运行有时限的清理命令，避免证据脚本遗留长驻服务。"""
    try:
        subprocess.run(arguments, capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return


def stage_workflow_spec(spec_path: str) -> Path:
    """把当前 RV 流程临时放入 Playwright 的真实运行目录。"""
    workflow_directory = stack.WORKTREE / "tests/playwright-e2e/tests/rv58-workflows"
    legacy_workflow_directory = stack.WORKTREE / "tests/playwright-e2e/tests/.rv58-workflows"
    shutil.rmtree(legacy_workflow_directory, ignore_errors=True)
    shutil.rmtree(workflow_directory, ignore_errors=True)
    workflow_directory.mkdir(parents=True, exist_ok=True)
    script_directory = Path(__file__).resolve().parent
    for file_name in ("agent-test-support.ts", Path(spec_path).name):
        source_path = script_directory / file_name
        if not source_path.is_file():
            raise FileNotFoundError(f"missing staged Playwright workflow: {source_path.name}")
        shutil.copy2(source_path, workflow_directory / file_name)
    staged_spec_path = workflow_directory / Path(spec_path).name
    if not staged_spec_path.is_file():
        raise FileNotFoundError(f"workflow was not staged: {staged_spec_path.name}")
    return workflow_directory


def start_isolated_redis(started_at: float) -> tuple[str, int]:
    """为本次流程启动专用 Redis，避免触碰共享开发数据。"""
    container_name = f"rv58-ui-redis-{os.getpid()}-{secrets.token_hex(3)}"
    port = stack.free_port()
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                container_name,
                "-p",
                f"127.0.0.1:{port}:6379",
                "redis:7-alpine",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=remaining_timeout(started_at, 30),
        )
    except (OSError, subprocess.SubprocessError):
        cleanup_command(["docker", "rm", "--force", container_name])
        raise
    redis_deadline = time.monotonic() + remaining_timeout(started_at, 15)
    while time.monotonic() < redis_deadline:
        redis_probe = subprocess.run(
            ["docker", "exec", container_name, "redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=remaining_timeout(started_at, 3),
        )
        if redis_probe.returncode == 0 and "PONG" in redis_probe.stdout:
            return container_name, port
        time.sleep(0.2)
    cleanup_command(["docker", "rm", "-f", container_name])
    raise RuntimeError("isolated Redis did not become ready")


def start_remote_chromium(
    admin_port: int,
    public_port: int,
    *,
    started_at: float,
    install_video_encoder: bool = False,
) -> tuple[str, int, str]:
    """在隔离 Linux 容器中启动 Chromium 供真实 Playwright 流程连接。"""
    container_name = f"rv58-ui-browser-{os.getpid()}-{secrets.token_hex(3)}"
    port = stack.free_port()
    browser_script_directory = stack.EVIDENCE_DIR / "scripts"
    endpoint_file = browser_script_directory / ".rv58-browser-endpoint"
    endpoint_file.unlink(missing_ok=True)
    browser_image = "rv58-playwright-browser:local"
    image_probe = subprocess.run(
        ["docker", "image", "inspect", browser_image],
        capture_output=True,
        check=False,
        timeout=remaining_timeout(started_at, 8),
    )
    if image_probe.returncode != 0:
        source_browser_probe = subprocess.run(
            ["docker", "inspect", "issue58-rv-browser"],
            capture_output=True,
            check=False,
            timeout=remaining_timeout(started_at, 8),
        )
        if source_browser_probe.returncode != 0:
            raise RuntimeError("remote Chromium image unavailable; prepare issue58-rv-browser with Chromium first")
        subprocess.run(
            ["docker", "commit", "issue58-rv-browser", browser_image],
            check=True,
            capture_output=True,
            text=True,
            timeout=remaining_timeout(started_at, 12),
        )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            container_name,
            "-p",
            f"127.0.0.1:{port}:3000",
            "--mount",
            f"type=bind,source={stack.WORKTREE},target=/work",
            "--mount",
            "type=bind,source=/Users/zata/code/zata_code_template/tests/playwright-e2e/node_modules,target=/Users/zata/code/zata_code_template/tests/playwright-e2e/node_modules,readonly",
            browser_image,
            "sleep",
            "infinity",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=remaining_timeout(started_at, 15),
    )
    try:
        if install_video_encoder:
            encoder_probe = subprocess.run(
                ["docker", "exec", container_name, "sh", "-lc", "command -v ffmpeg"],
                capture_output=True,
                text=True,
                check=False,
            )
            if encoder_probe.returncode != 0:
                encoder_install = subprocess.run(
                    ["docker", "exec", container_name, "apk", "add", "--no-cache", "ffmpeg"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=remaining_timeout(started_at, 60),
                )
                if encoder_install.returncode != 0:
                    raise RuntimeError(
                        f"remote Chromium ffmpeg install failed: {encoder_install.stderr[-2000:]}"
                    )
            playwright_ffmpeg_directory = "/root/.cache/ms-playwright/ffmpeg-1011"
            subprocess.run(
                ["docker", "exec", container_name, "mkdir", "-p", playwright_ffmpeg_directory],
                check=True,
                capture_output=True,
                text=True,
                timeout=remaining_timeout(started_at, 5),
            )
            subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "ln",
                    "-sf",
                    "/usr/bin/ffmpeg",
                    f"{playwright_ffmpeg_directory}/ffmpeg-linux",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=remaining_timeout(started_at, 5),
            )
        subprocess.run(
            [
                "docker",
                "exec",
                "-e",
                f"RV58_SECURE_LOCAL_ORIGINS=http://host.docker.internal:{admin_port},http://host.docker.internal:{public_port}",
                "-d",
                container_name,
                "sh",
                "-lc",
                "node /work/tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/remote-browser-server.mjs >/tmp/rv58-browser.log 2>&1",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=remaining_timeout(started_at, 8),
        )
        browser_deadline = time.monotonic() + remaining_timeout(started_at, 30)
        while time.monotonic() < browser_deadline:
            if endpoint_file.is_file():
                endpoint = endpoint_file.read_text(encoding="utf-8").strip()
                if endpoint:
                    host_endpoint = endpoint.replace("0.0.0.0", "127.0.0.1")
                    return container_name, port, host_endpoint.replace(":3000/", f":{port}/")
            time.sleep(0.5)
        copied_endpoint_path = endpoint_file.with_name(".rv58-browser-endpoint.copied")
        copied_endpoint = subprocess.run(
            [
                "docker",
                "cp",
                f"{container_name}:/work/tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/.rv58-browser-endpoint",
                str(copied_endpoint_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=remaining_timeout(started_at, 8),
        )
        if copied_endpoint.returncode == 0 and copied_endpoint_path.is_file():
            endpoint = copied_endpoint_path.read_text(encoding="utf-8").strip()
            copied_endpoint_path.unlink(missing_ok=True)
            if endpoint:
                host_endpoint = endpoint.replace("0.0.0.0", "127.0.0.1")
                return container_name, port, host_endpoint.replace(":3000/", f":{port}/")
        copied_endpoint_path.unlink(missing_ok=True)
        server_log = subprocess.run(
            ["docker", "exec", container_name, "cat", "/tmp/rv58-browser.log"],
            capture_output=True,
            text=True,
            check=False,
            timeout=remaining_timeout(started_at, 5),
        ).stdout
        endpoint_match = re.search(r"Remote Chromium ready: (ws://\S+)", server_log)
        if endpoint_match:
            host_endpoint = endpoint_match.group(1).replace("0.0.0.0", "127.0.0.1")
            return container_name, port, host_endpoint.replace(":3000/", f":{port}/")
        raise RuntimeError(f"isolated Chromium server did not start: {server_log[-2000:]}")
    except Exception:
        cleanup_command(["docker", "rm", "-f", container_name])
        endpoint_file.unlink(missing_ok=True)
        raise


def summarize_output(stdout: str, stderr: str, sensitive_values: list[str]) -> str:
    """仅保留关键 Playwright 行，并去掉凭据和本机绝对路径。"""
    combined_output = f"{stdout}\n{stderr}"
    for sensitive_value in sensitive_values:
        if sensitive_value:
            combined_output = combined_output.replace(sensitive_value, "[REDACTED]")
    output_lines = []
    for output_line in combined_output.splitlines():
        if (
            " tests using " in output_line
            or " ✓ " in output_line
            or " passed" in output_line
            or " failed" in output_line
            or "expect(" in output_line.lower()
            or "tocontaintext" in output_line.lower()
            or "tohavetext" in output_line.lower()
            or "tobe(" in output_line.lower()
            or "expected:" in output_line.lower()
            or "received:" in output_line.lower()
            or "received string:" in output_line.lower()
            or "call log:" in output_line.lower()
            or "Services ready on ports" in output_line
            or "E2E artifacts will be written" in output_line
            or "Starting just-run services" in output_line
            or "Shutting down just-run services" in output_line
            or "Waiting for" in output_line
            or "ERROR:" in output_line
            or "Timed out" in output_line
            or "Error:" in output_line
        ):
            output_lines.append(re.sub(r"/Users/[^ ]+", "[WORKTREE]", output_line.strip()))
    return "\n".join(output_lines)


def mutate_polling_race(source: str) -> str:
    """在临时生产构建中移除 SSE 失败后的持久化终态回读。"""
    original = """          try {
            if (await refreshRunState()) return
          } catch {
            // 持久化读取也失败时保留提示，等下一轮重连后重新判断。
          }
"""
    if source.count(original) != 1:
        raise AssertionError("SSE failure recovery mutation anchor missing or ambiguous")
    return source.replace(
        original,
        "          // RV-2 mutant: SSE failure leaves the persisted terminal state unread.\n",
        1,
    )


def wait_for_stack(
    base_url_by_service: dict[str, str],
    run_process: subprocess.Popen[bytes],
    timeout_seconds: int,
) -> bool:
    """轮询真实后端与双前端入口，等待三服务启动。"""
    health_path_by_service = {"backend": "/health", "admin": "/sign-in", "public": "/login"}
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if run_process.poll() is not None:
            return False
        all_ready = True
        for service_name, base_url in base_url_by_service.items():
            try:
                response = httpx.get(
                    base_url + health_path_by_service[service_name],
                    timeout=1.5,
                    follow_redirects=True,
                )
            except httpx.HTTPError:
                all_ready = False
                break
            if response.status_code == 404 or response.status_code >= 500:
                all_ready = False
                break
        if all_ready:
            return True
        time.sleep(1)
    return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rv", choices=["2", "3"], required=True)
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--mutant", action="store_true")
    parser.add_argument("--primary-demo", action="store_true")
    arguments = parser.parse_args()
    if arguments.mutant and (arguments.rv != "2" or not arguments.negative_control):
        raise ValueError("--mutant is only valid for the rv-2 negative control")
    if arguments.rv == "2" and arguments.negative_control and not arguments.mutant:
        raise ValueError("rv-2 negative control must reintroduce the activeRun polling race with --mutant")
    if arguments.primary_demo and (arguments.rv != "2" or arguments.negative_control):
        raise ValueError("the primary demo is a separate positive RV-2 recording")
    spec = {
        "2": "tests/rv58-workflows/agent-run.auth.spec.ts",
        "3": "tests/rv58-workflows/skill-version.auth.spec.ts",
    }[arguments.rv]
    if arguments.primary_demo:
        spec = "tests/rv58-workflows/primary-demo.auth.spec.ts"
    operation_started_at = time.monotonic()
    report_path = stack.EVIDENCE_DIR / (
        "rv-2-primary-demo.txt"
        if arguments.primary_demo
        else f"rv-{arguments.rv}-negative-control.txt"
        if arguments.negative_control
        else f"rv-{arguments.rv}-real-user-flow.txt"
    )
    if arguments.mutant:
        (stack.EVIDENCE_DIR / "rv-2-negative-terminal-probe.txt").unlink(missing_ok=True)
    playwright_artifact_directory = (
        stack.EVIDENCE_DIR / "scripts" / f".rv58-playwright-{arguments.rv}-{os.getpid()}"
    )
    playwright_results_directory = playwright_artifact_directory / "results"
    playwright_html_directory = playwright_artifact_directory / "html"
    model = stack.ModelStub(
        delay_seconds=0.8,
        chunk_delay_seconds=1.0,
        chunk_size=10,
    )
    database = stack.create_database("pg", f"rv{arguments.rv}")
    redis_container: str | None = None
    browser_container: str | None = None
    workflow_directory: Path | None = None
    run_process: subprocess.Popen[bytes] | None = None
    run_log_handle = None
    run_state_file = stack.WORKTREE / ".env.run-state"
    original_run_state = run_state_file.read_bytes() if run_state_file.exists() else None
    endpoint_file = stack.EVIDENCE_DIR / "scripts" / ".rv58-browser-endpoint"
    startup_log_path = stack.EVIDENCE_DIR / "scripts" / f".rv58-{arguments.rv}-{os.getpid()}-run.log"
    started_at = datetime.now(UTC).isoformat()
    try:
        redis_container, redis_port = start_isolated_redis(operation_started_at)
        ports: list[int] = []
        while len(ports) < 3:
            selected_port = stack.free_port()
            if selected_port not in ports:
                ports.append(selected_port)
        backend_port, admin_port, public_port = ports
        browser_container, browser_port, browser_endpoint = start_remote_chromium(
            admin_port,
            public_port,
            started_at=operation_started_at,
            install_video_encoder=arguments.primary_demo,
        )
        if arguments.rv == "2":
            browser_handshake = subprocess.run(
                [
                    "node",
                    str(stack.EVIDENCE_DIR / "scripts" / "remote-browser-client-smoke.mjs"),
                ],
                cwd=stack.WORKTREE,
                env={**os.environ, "PLAYWRIGHT_REMOTE_BROWSER_WS": browser_endpoint},
                capture_output=True,
                text=True,
                timeout=remaining_timeout(operation_started_at, 25),
                check=False,
            )
            handshake_output = browser_handshake.stdout.strip()
            handshake_evidence_path = stack.EVIDENCE_DIR / "rv-2-browser-handshake.txt"
            handshake_evidence_path.write_text(handshake_output + "\n", encoding="utf-8")
            if browser_handshake.returncode != 0:
                raise RuntimeError("remote Chromium browser handshake failed")
        workflow_directory = stage_workflow_spec(spec)
        environment = {
            **os.environ,
            "DATABASE_URL": database.url,
            "REDIS_URL": f"redis://127.0.0.1:{redis_port}/0",
            "MODEL_BASE_URL": model.base_url,
            "MODEL_API_KEY": stack.MODEL_API_KEY_MARKER,
            "MODEL_NAME": "rv58-stub-model",
            "APP_BOOTSTRAP_EMAIL": "rv-e2e-member@example.test",
            "APP_BOOTSTRAP_PASSWORD": "rv-e2e-member-password",
            "PLAYWRIGHT_IDENTIFIER": "rv-e2e-member@example.test",
            "PLAYWRIGHT_PASSWORD": "rv-e2e-member-password",
            "AUTH_ADMIN_BOOTSTRAP_USERNAME": "rv-e2e-platform",
            "AUTH_ADMIN_BOOTSTRAP_PASSWORD": "rv-e2e-platform-password",
            "PLAYWRIGHT_ADMIN_IDENTIFIER": "rv-e2e-platform",
            "PLAYWRIGHT_ADMIN_PASSWORD": "rv-e2e-platform-password",
            "SECURITY_API_REQUESTS_PER_MINUTE": "5000",
            "SECURITY_ADMIN_LOGIN_IP_ATTEMPTS": "500",
            "SECURITY_PUBLIC_LOGIN_IP_ATTEMPTS": "500",
            "SECURITY_REGISTER_IP_ATTEMPTS": "500",
            "A2A_PUBLIC_BASE_URL": f"http://127.0.0.1:{backend_port}",
            "A2A_ALLOW_LOOPBACK_FOR_DEV": "true",
            "A2A_CREDENTIAL_ENCRYPTION_KEY": "rv58-local-a2a-encryption-not-a-secret",
            "PLAYWRIGHT_EVIDENCE_DIR": str(stack.EVIDENCE_DIR),
            "PLAYWRIGHT_TEST_RESULTS_DIR": str(playwright_results_directory),
            "PLAYWRIGHT_HTML_OUTPUT_DIR": str(playwright_html_directory),
            "PLAYWRIGHT_JUNIT_OUTPUT_FILE": str(playwright_results_directory / "junit.xml"),
            "PLAYWRIGHT_RECORD_VIDEO": "1" if arguments.primary_demo else "0",
            "CI": "1" if arguments.primary_demo else os.environ.get("CI", ""),
            "RV3_MUTATE_OLD_VERSION": "1"
            if arguments.negative_control and arguments.rv == "3"
            else "0",
            "RV2_FORCE_STREAM_FAILURE": "1" if arguments.mutant else "0",
            "RV2_TERMINAL_MUTANT": "1" if arguments.mutant else "0",
            "PLAYWRIGHT_BASE_URL": f"http://127.0.0.1:{public_port}",
            "PLAYWRIGHT_ADMIN_BASE_URL": f"http://localhost:{admin_port}",
            "PLAYWRIGHT_REMOTE_BASE_URL": f"http://host.docker.internal:{public_port}",
            "PLAYWRIGHT_REMOTE_ADMIN_BASE_URL": f"http://host.docker.internal:{admin_port}",
            "PLAYWRIGHT_HEALTH_URL": f"http://127.0.0.1:{backend_port}/health",
            "PLAYWRIGHT_API_BASE_URL": f"http://127.0.0.1:{backend_port}",
            "PLAYWRIGHT_REMOTE_BROWSER_WS": browser_endpoint,
            "PLAYWRIGHT_SKIP_STACK_BOOT": "1",
            "PLAYWRIGHT_DEMO_PAUSE": "1",
        }
        public_build_environment = {
            **environment,
            "BACKEND_URL": f"http://localhost:{backend_port}",
            "NEXT_TELEMETRY_DISABLED": "1",
        }
        public_page = stack.WORKTREE / "frontend-public/app/(app)/app/agents/page.tsx"
        original_public_page = public_page.read_text(encoding="utf-8") if arguments.mutant else None
        if arguments.mutant:
            assert original_public_page is not None
            public_page.write_text(mutate_polling_race(original_public_page), encoding="utf-8")
        try:
            public_build = subprocess.run(
                ["pnpm", "build"],
                cwd=stack.WORKTREE / "frontend-public",
                env=public_build_environment,
                capture_output=True,
                text=True,
                timeout=remaining_timeout(operation_started_at, 100),
            )
        finally:
            if original_public_page is not None:
                public_page.write_text(original_public_page, encoding="utf-8")
        if public_build.returncode != 0:
            build_output = summarize_output(
                public_build.stdout,
                public_build.stderr,
                [
                    stack.MODEL_API_KEY_MARKER,
                    "rv-e2e-member-password",
                    "rv-e2e-platform-password",
                    "rv58-local-a2a-encryption-not-a-secret",
                ],
            )
            raw_build_lines = f"{public_build.stdout}\n{public_build.stderr}".splitlines()
            error_line_index = next(
                (
                    index
                    for index, output_line in enumerate(raw_build_lines)
                    if "Error:" in output_line or "error" in output_line.lower()
                ),
                max(0, len(raw_build_lines) - 40),
            )
            detail_lines = raw_build_lines[max(0, error_line_index - 8) : error_line_index + 45]
            detail_output = "\n".join(
                re.sub(r"/Users/[^ ]+", "[WORKTREE]", output_line)
                .replace(database.url, "[REDACTED]")
                .replace(stack.MODEL_API_KEY_MARKER, "[REDACTED]")
                .replace("rv-e2e-member-password", "[REDACTED]")
                .replace("rv-e2e-platform-password", "[REDACTED]")
                .replace("rv58-local-a2a-encryption-not-a-secret", "[REDACTED]")
                for output_line in detail_lines
            )
            failure_report = "\n".join(
                [
                    f"# rv-{arguments.rv} public frontend build failure at {started_at}",
                    f"identity: {stack.git_identity()}",
                    "command: pnpm build (production public frontend)",
                    f"exit_code: {public_build.returncode}",
                    build_output or "build output contained no recognized diagnostic lines",
                    detail_output,
                ]
            )
            report_path.write_text(failure_report + "\n", encoding="utf-8")
            print(failure_report)
            raise RuntimeError("production public frontend build failed")
        run_log_handle = startup_log_path.open("wb")
        run_process = subprocess.Popen(
            [
                "just",
                "run",
                "all",
                f"backend_port={backend_port}",
                f"frontend_admin_port={admin_port}",
                f"frontend_public_port={public_port}",
                "frontend_cmd=pnpm dev --host 0.0.0.0",
                "frontend_public_cmd=../tasks/evidence/P1-FEAT-20260928-115856-multi-organization-online-agent-base/scripts/start_public_production.sh",
            ],
            cwd=stack.WORKTREE,
            env=environment,
            stdout=run_log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        base_url_by_service = {
            "backend": f"http://127.0.0.1:{backend_port}",
            "admin": f"http://localhost:{admin_port}",
            "public": f"http://127.0.0.1:{public_port}",
        }
        if not wait_for_stack(
            base_url_by_service,
            run_process,
            timeout_seconds=remaining_timeout(operation_started_at, 75),
        ):
            run_log_handle.flush()
            startup_output = startup_log_path.read_text(encoding="utf-8", errors="replace")
            raise RuntimeError(
                "real just run all failed to expose all three entry points:\n"
                + summarize_output(startup_output, "", [database.url, stack.MODEL_API_KEY_MARKER])
            )
        listener_status = {}
        for service_name, service_port in zip(("backend", "admin", "public"), ports, strict=True):
            listener_probe = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{service_port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            listener_status[service_name] = listener_probe.returncode == 0
        e2e_arguments = [
            "just",
            "e2e",
            spec,
        ]
        shutil.rmtree(playwright_artifact_directory, ignore_errors=True)
        try:
            completed = subprocess.run(
                e2e_arguments,
                cwd=stack.WORKTREE,
                env=environment,
                capture_output=True,
                text=True,
                timeout=remaining_timeout(
                    operation_started_at,
                    560,
                ),
            )
        except subprocess.TimeoutExpired as timeout_error:
            timeout_stdout = timeout_error.stdout or ""
            timeout_stderr = timeout_error.stderr or ""
            if isinstance(timeout_stdout, bytes):
                timeout_stdout = timeout_stdout.decode("utf-8", errors="replace")
            if isinstance(timeout_stderr, bytes):
                timeout_stderr = timeout_stderr.decode("utf-8", errors="replace")
            timeout_output = summarize_output(
                timeout_stdout,
                timeout_stderr,
                [
                    database.url,
                    stack.MODEL_API_KEY_MARKER,
                    "rv-e2e-member-password",
                    "rv-e2e-platform-password",
                    "rv58-local-a2a-encryption-not-a-secret",
                ],
            )
            timeout_report = "\n".join(
                [
                    f"# rv-{arguments.rv} real user flow timeout at {started_at}",
                    f"identity: {stack.git_identity()}",
                    f"command: {' '.join(e2e_arguments)}",
                    f"service listener checks: {listener_status}",
                    "result: Playwright command exceeded its bounded validation window; this is infrastructure timeout, not a negative-control pass",
                    timeout_output,
                ]
            )
            report_path.write_text(timeout_report + "\n", encoding="utf-8")
            print(timeout_report)
            raise RuntimeError("just e2e did not finish within its bounded validation window") from timeout_error
        safe_output = summarize_output(
            completed.stdout,
            completed.stderr,
            [
                database.url,
                stack.MODEL_API_KEY_MARKER,
                "rv-e2e-member-password",
                "rv-e2e-platform-password",
                "rv58-local-a2a-encryption-not-a-secret",
            ],
        )
        report_title = (
            "primary demo real user flow"
            if arguments.primary_demo
            else "negative control"
            if arguments.negative_control
            else "real user flow"
        )
        negative_control_summary = (
            "temporary production build omits persisted-state refresh after an SSE failure"
            if arguments.mutant
            else "test response mutation changes the recorded v1 Skill body"
            if arguments.negative_control and arguments.rv == "3"
            else "none"
        )
        report_content = "\n".join(
            [
                f"# rv-{arguments.rv} {report_title} at {started_at}",
                f"identity: {stack.git_identity()}",
                "model boundary: local OpenAI-compatible transport stub; all UI/API/DB boundaries real",
                f"command: {' '.join(e2e_arguments)}",
                f"public/admin browser origins: host.docker.internal mapped through isolated Chromium container on port {browser_port}",
                "public frontend: production Next.js build and start; admin frontend, API, database, and Chromium browser are real",
                f"negative control: {negative_control_summary}",
                f"exit_code: {completed.returncode}",
                safe_output,
            ]
        )
        report_path.write_text(report_content + "\n", encoding="utf-8")
        print(report_content)
        if arguments.negative_control:
            combined_output = f"{completed.stdout}\n{completed.stderr}"
            expected_marker = "Status: succeeded" if arguments.rv == "2" else "RV3 skill v1: use the original answer."
            if completed.returncode == 0 or expected_marker not in combined_output:
                raise AssertionError("negative control did not trigger the expected workflow failure")
            expected_fail_lines = [
                "EXPECTED_FAIL: rv-2 terminal-state assertion detected the SSE recovery mutant"
                if arguments.rv == "2"
                else "EXPECTED_FAIL: rv-3 immutable-version assertion detected the altered history response",
                f"RV_RESULT: NEGATIVE CONTROL DETECTED rv-{arguments.rv}",
            ]
            with report_path.open("a", encoding="utf-8") as report_file:
                report_file.write("\n".join(expected_fail_lines) + "\n")
            print("\n".join(expected_fail_lines))
            return
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)
        if arguments.rv == "2" and arguments.primary_demo:
            demo_merger = Path(__file__).resolve().parent / "merge_primary_demo.py"
            demo_result = subprocess.run(
                [sys.executable, str(demo_merger)],
                cwd=stack.WORKTREE,
                capture_output=True,
                text=True,
                timeout=remaining_timeout(operation_started_at, 60),
            )
            if demo_result.returncode != 0:
                raise RuntimeError(f"primary demo assembly failed: {demo_result.stderr[-2000:]}")
            report_path.write_text(
                report_path.read_text(encoding="utf-8") + demo_result.stdout,
                encoding="utf-8",
            )
        required_artifacts = (
            [stack.EVIDENCE_DIR / "rv-2-demo-multi-organization-agent.mp4"]
            if arguments.primary_demo
            else [stack.EVIDENCE_DIR / "rv-2-agent-run.png"]
            if arguments.rv == "2"
            else [stack.EVIDENCE_DIR / "rv-3-skill-version.png"]
        )
        for artifact_path in required_artifacts:
            if not artifact_path.is_file() or artifact_path.stat().st_size == 0:
                raise RuntimeError(f"missing evidence: {artifact_path.name}")
        print(f"RV_RESULT: PASS rv-{arguments.rv}")
    finally:
        model.close()
        cleanup_command(
            ["just", "down"],
            timeout=10,
        )
        if run_process is not None:
            try:
                run_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                run_process.terminate()
                try:
                    run_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    run_process.kill()
                    run_process.wait(timeout=5)
        if run_log_handle is not None:
            run_log_handle.close()
        if workflow_directory is not None:
            shutil.rmtree(workflow_directory, ignore_errors=True)
            shutil.rmtree(
                stack.WORKTREE / "tests/playwright-e2e/tests/.rv58-workflows",
                ignore_errors=True,
            )
        if redis_container is not None:
            cleanup_command(["docker", "rm", "-f", redis_container])
        if browser_container is not None:
            cleanup_command(["docker", "rm", "-f", browser_container])
        shutil.rmtree(playwright_artifact_directory, ignore_errors=True)
        endpoint_file.unlink(missing_ok=True)
        startup_log_path.unlink(missing_ok=True)
        database.drop()
        if original_run_state is None:
            run_state_file.unlink(missing_ok=True)
        else:
            run_state_file.write_bytes(original_run_state)


if __name__ == "__main__":
    stack.main_guard(main)
