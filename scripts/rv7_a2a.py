"""rv-7：官方 A2A 1.0 客户端/服务端双向互通、隔离与失败闭合。"""

from __future__ import annotations

import argparse
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402
import rv_ui as ui_runner  # noqa: E402

OFFICIAL_PACKAGE = "a2a-sdk[all]==1.0.0"
OFFICIAL_SERVER_PACKAGES = ("uvicorn==0.47.0", "fastapi==0.136.1")
PEER_ENV_ALIAS = "RV58_PEER_A_TOKEN"
PEER_TOKEN = "rv58-peer-a-token"
OPERATION_BUDGET_SECONDS = 270


def mutant_src() -> Path:
    """在临时 src 副本放宽 A2A Task scope，证明跨组织负控会失败。"""
    temporary_root = Path(tempfile.mkdtemp(prefix="rv58-rv7-mutant-"))
    source_root = temporary_root / "src"
    shutil.copytree(stack.WORKTREE / "src", source_root)
    shutil.copytree(stack.WORKTREE / "alembic", temporary_root / "alembic")
    shutil.copy2(stack.WORKTREE / "alembic.ini", temporary_root / "alembic.ini")

    support_path = source_root / "backend/api/a2a_support.py"
    support_text = support_path.read_text(encoding="utf-8")
    support_start = support_text.index("    credential = catalog.resolve_a2a_credential(token)\n")
    support_end = support_text.index("    return credential\n", support_start) + len("    return credential\n")
    support_text = support_text[:support_start] + (
        "    credential = catalog.resolve_a2a_credential(token)\n"
        "    if credential is None:\n"
        "        raise HTTPException(status_code=404, detail=\"agent_not_found\")\n"
        "    return credential\n"
    ) + support_text[support_end:]
    support_path.write_text(support_text, encoding="utf-8")

    runs_path = source_root / "backend/core/agent/runs.py"
    runs_text = runs_path.read_text(encoding="utf-8")
    scope_guard = (
        "        if (\n"
        "            run is None\n"
        "            or run.organization_id != organization_id\n"
        "            or run.subject_id != agent_id\n"
        "            or run.owner_id != f\"a2a:{credential_id}\"\n"
        "        ):\n"
    )
    if scope_guard not in runs_text:
        shutil.rmtree(temporary_root, ignore_errors=True)
        raise RuntimeError("A2A Task scope mutation anchor missing")
    runs_path.write_text(runs_text.replace(scope_guard, "        if run is None:\n", 1), encoding="utf-8")
    return source_root


def start_admin_frontend(backend: stack.Backend) -> tuple[int, subprocess.Popen[bytes]]:
    """启动连接真实 API 的管理端 Vite 页面。"""
    port = stack.free_port()
    environment = {
        **os.environ,
        "BACKEND_PORT": str(backend.port),
        "FRONTEND_ADMIN_PORT": str(port),
        "PLAYWRIGHT_REMOTE_BROWSER_WS": "rv7-real-admin-ui",
    }
    process = subprocess.Popen(
        ["pnpm", "dev", "--host", "0.0.0.0", "--port", str(port)],
        cwd=stack.WORKTREE / "frontend-admin",
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("admin frontend exited before becoming ready")
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/sign-in", timeout=1)
            if response.status_code == 200:
                return port, process
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    process.terminate()
    raise RuntimeError("admin frontend did not become ready")


def configure_a2a_from_admin_ui(
    backend: stack.Backend,
    official_endpoint: str,
    organization_admin_username: str,
    organization_admin_password: str,
) -> dict[str, str]:
    """通过生产管理页面创建 Agent、签发凭据、登记并审批 A2A 对端。"""
    operation_started_at = time.monotonic()
    admin_port, frontend_process = start_admin_frontend(backend)
    result_path = stack.EVIDENCE_DIR / "scripts" / ".rv7-ui-result.json"
    result_path.unlink(missing_ok=True)
    browser_container: str | None = None
    browser_endpoint_file = stack.EVIDENCE_DIR / "scripts" / ".rv58-browser-endpoint"
    try:
        browser_container, _, browser_endpoint = ui_runner.start_remote_chromium(
            admin_port,
            admin_port,
            started_at=time.monotonic(),
        )
        node_environment = {
            **os.environ,
            "PLAYWRIGHT_REMOTE_BROWSER_WS": browser_endpoint,
            "RV7_ADMIN_BASE_URL": f"http://host.docker.internal:{admin_port}",
            "RV7_ADMIN_UI_OUTPUT": str(result_path),
            "RV7_ORG_ADMIN_USERNAME": organization_admin_username,
            "RV7_ORG_ADMIN_PASSWORD": organization_admin_password,
            "RV7_PLATFORM_ADMIN_USERNAME": backend.admin_username,
            "RV7_PLATFORM_ADMIN_PASSWORD": backend.admin_password,
            "RV7_OFFICIAL_A2A_ENDPOINT": official_endpoint,
            "RV7_PEER_CREDENTIAL_ALIAS": PEER_ENV_ALIAS,
            "RV7_EVIDENCE_DIR": str(stack.EVIDENCE_DIR),
        }
        timeout = max(1, min(150, int(OPERATION_BUDGET_SECONDS - (time.monotonic() - operation_started_at))))
        completed = subprocess.run(
            ["node", str(stack.EVIDENCE_DIR / "scripts" / "rv7_admin_ui.mjs")],
            cwd=stack.WORKTREE,
            env=node_environment,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"admin UI workflow failed:\n{completed.stdout[-5000:]}\n{completed.stderr[-5000:]}"
            )
        if not result_path.is_file():
            raise RuntimeError("admin UI workflow did not save transient setup data")
        setup = json.loads(result_path.read_text(encoding="utf-8"))
        if not setup.get("agentId") or not setup.get("inboundToken") or not setup.get("peerName"):
            raise RuntimeError("admin UI workflow returned incomplete setup")
        print("\n## real admin interface", completed.stdout.strip())
        print("isolated Linux Chromium configured the Agent and peer through real admin pages")
        return setup
    finally:
        result_path.unlink(missing_ok=True)
        if browser_container is not None:
            ui_runner.cleanup_command(["docker", "rm", "-f", browser_container], timeout=10)
        browser_endpoint_file.unlink(missing_ok=True)
        if frontend_process.poll() is None:
            frontend_process.terminate()
            try:
                frontend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                frontend_process.kill()
                frontend_process.wait(timeout=5)


def create_organization(backend: stack.Backend, platform: stack.Http, label: str, token: str):
    organization = platform.call(
        "POST", "/admin/organizations", (200, 201), json={"name": f"RV7-{label}-{token}"}
    ).json()
    password = f"Rv7-{label}-{token}-pass"
    platform.call(
        "POST",
        "/admin/admins",
        (200, 201),
        json={
            "username": f"rv7-admin-{label}-{token}",
            "email": f"rv7-admin-{label}-{token}@example.test",
            "role": "org",
            "organization_id": organization["id"],
            "password": password,
        },
    )
    email = f"rv7-member-{label}-{token}@example.test"
    _, user_id = stack.public_register(backend, email, password)
    platform.call(
        "PATCH",
        f"/admin/users/{user_id}/organization",
        200,
        json={"organization_id": organization["id"]},
    )
    return organization, password, email, password


def start_official_server(port: int):
    log_path = stack.EVIDENCE_DIR / "rv-7-official-server.log"
    server_command = ["uvx", "--from", OFFICIAL_PACKAGE]
    for package_name in OFFICIAL_SERVER_PACKAGES:
        server_command.extend(("--with", package_name))
    server_command.extend(
        (
            "python",
            str(stack.EVIDENCE_DIR / "scripts" / "official_a2a_server.py"),
            "--port",
            str(port),
        )
    )
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            server_command,
            cwd=stack.WORKTREE,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    endpoint = f"http://127.0.0.1:{port}/a2a/agents/remote"
    deadline = time.time() + 90
    last_probe = "no HTTP response yet"
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"official server exited: {log_path.read_text(encoding='utf-8')[-3000:]}")
        try:
            response = httpx.get(
                endpoint,
                headers={"Authorization": f"Bearer {PEER_TOKEN}", "A2A-Version": "1.0"},
                timeout=2,
            )
            if response.status_code == 200:
                return process, endpoint, log_path
            last_probe = f"HTTP {response.status_code}: {response.text[:300]}"
        except httpx.HTTPError:
            last_probe = "connection attempt failed"
        time.sleep(0.5)
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        process.kill()
        process.wait(timeout=5)
    log_tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
    raise RuntimeError(
        f"official server did not become ready; last probe: {last_probe}; log tail: {log_tail}"
    )


def run_official_client(agent_url: str, token: str):
    output_path = stack.EVIDENCE_DIR / "rv-7-official-client.json"
    completed = subprocess.run(
        [
            "uvx",
            "--from",
            OFFICIAL_PACKAGE,
            "python",
            str(stack.EVIDENCE_DIR / "scripts" / "official_a2a_client.py"),
            "--agent-url",
            agent_url,
            "--token",
            token,
            "--output",
            str(output_path),
        ],
        cwd=stack.WORKTREE,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"official client failed:\n{completed.stdout}\n{completed.stderr}")
    return json.loads(output_path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.add_argument("--mutant", action="store_true")
    arguments = parser.parse_args()
    if arguments.mutant and not arguments.negative_control:
        parser.error("--mutant can only be combined with --negative-control")
    report_name = "rv-7-negative-control.txt" if arguments.negative_control else "rv-7-a2a-bidirectional.txt"
    report = stack.Report(stack.EVIDENCE_DIR / report_name)
    report(f"# rv-7 A2A bidirectional at {datetime.now(UTC).isoformat()}")
    report("identity:", json.dumps(stack.git_identity()))
    report("official compatibility:", OFFICIAL_PACKAGE)
    database = stack.create_database("pg", "rv7")
    model = stack.ModelStub(delay_seconds=3.0)
    mutant_source = mutant_src() if arguments.mutant else None
    official_process = None
    backend = None
    no_model_backend = None
    official_log_path = None
    try:
        official_port = stack.free_port()
        official_process, official_endpoint, official_log_path = start_official_server(official_port)
        backend = stack.start_backend(
            database,
            model_base_url=model.base_url,
            src_path=mutant_source,
            extra_env={
                "A2A_CREDENTIAL_ENCRYPTION_KEY": "rv58-local-encryption-not-a-secret",
                PEER_ENV_ALIAS: PEER_TOKEN,
            },
            log_name="rv7",
        )
        platform = stack.admin_login(backend, backend.admin_username, backend.admin_password)
        suffix = uuid.uuid4().hex[:6]
        org_a, admin_a_password, member_a_email, member_a_password = create_organization(
            backend, platform, "a", suffix
        )
        org_b, admin_b_password, member_b_email, member_b_password = create_organization(
            backend, platform, "b", suffix
        )
        platform_password = backend.admin_password
        backend.stop()
        backend = stack.start_backend(
            database,
            model_base_url=model.base_url,
            src_path=mutant_source,
            extra_env={
                "A2A_CREDENTIAL_ENCRYPTION_KEY": "rv58-local-encryption-not-a-secret",
                PEER_ENV_ALIAS: PEER_TOKEN,
                "AUTH_ADMIN_BOOTSTRAP_PASSWORD": platform_password,
                "A2A_CREDENTIAL_BINDINGS": json.dumps({
                    org_a["id"]: {official_endpoint: [PEER_ENV_ALIAS]}
                }),
            },
            log_name="rv7-scoped",
        )
        backend.admin_password = platform_password
        platform = stack.admin_login(backend, backend.admin_username, platform_password)
        admin_a = stack.admin_login(backend, f"rv7-admin-a-{suffix}", admin_a_password)
        admin_b = stack.admin_login(backend, f"rv7-admin-b-{suffix}", admin_b_password)
        member_a = stack.public_login(backend, member_a_email, member_a_password)
        member_b = stack.public_login(backend, member_b_email, member_b_password)

        admin_ui_setup = configure_a2a_from_admin_ui(
            backend,
            official_endpoint,
            f"rv7-admin-a-{suffix}",
            admin_a_password,
        )
        for denied_alias in ("MODEL_API_KEY", PEER_ENV_ALIAS):
            rejected_reference = admin_b.call(
                "POST", "/admin/a2a-peers", 422,
                json={"name": "denied-reference", "card_url": official_endpoint,
                      "endpoint_url": official_endpoint, "credential_env_alias": denied_alias},
            )
            assert "secret_reference_not_authorized" in rejected_reference.text
        report("credential reference scope: B cannot read platform or A peer aliases; HTTP 422 before persistence")
        agent_a_items = admin_a.call("GET", "/admin/agents", 200).json()["items"]
        agent_a = next(item for item in agent_a_items if item["id"] == admin_ui_setup["agentId"])
        assert admin_ui_setup["peerId"] in agent_a["allowed_peer_ids"]
        report("admin UI selected peer persisted on Agent:", admin_ui_setup["peerId"])
        inbound_token = admin_ui_setup["inboundToken"]
        agent_b = admin_b.call(
            "POST", "/admin/agents", 201, json={"name": f"RV7-Agent-B-{suffix}", "instructions": "Be concise."}
        ).json()
        admin_b.call("POST", f"/admin/agents/{agent_b['id']}/publish", 200)
        credential_b = admin_b.call(
            "POST", f"/admin/agents/{agent_b['id']}/a2a-credentials", 201, json={"name": "official-b"}
        ).json()
        agent_url = f"{backend.base_url}/a2a/agents/{agent_a['id']}"
        official_summary = run_official_client(agent_url, inbound_token)
        report("\n## official client inbound", json.dumps(official_summary, sort_keys=True))
        inbound_task_id = official_summary["first_task_id"]

        cross_org = httpx.get(
            f"{agent_url}/tasks/{inbound_task_id}",
            headers={"Authorization": f"Bearer {credential_b['token']}", "A2A-Version": "1.0"},
            timeout=10,
        )
        task_input_leaked = "hello from official SDK" in cross_org.text
        report("organization B credential reads A Task:", cross_org.status_code, "A task input exposed:", task_input_leaked)
        if arguments.negative_control:
            if cross_org.status_code == 200 and task_input_leaked:
                report("fault injection: temporary src copy bypassed credential and A2A Task organization/owner checks")
                report("expected_fail:", "B credential read A Task and the response exposed A's input")
                report("\nEXPECTED_FAIL: rv-7 cross-organization Task disclosure detected")
                report("RV_RESULT: NEGATIVE CONTROL DETECTED rv-7")
                return
            raise AssertionError("the A2A scope mutant did not expose the target Task")
        assert cross_org.status_code == 404 and not task_input_leaked
        wrong_agent = httpx.get(
            f"{backend.base_url}/a2a/agents/{agent_b['id']}/tasks/{inbound_task_id}",
            headers={"Authorization": f"Bearer {credential_b['token']}", "A2A-Version": "1.0"},
            timeout=10,
        )
        assert wrong_agent.status_code == 404

        report("\n## Skill write retry idempotency")
        skill = admin_a.call(
            "POST", "/admin/skills", 201, json={"name": f"RV7-Skill-{suffix}", "body": "v1"}
        ).json()
        headers = {"Idempotency-Key": "rv7-version-retry"}
        first = admin_a.call("POST", f"/admin/skills/{skill['id']}/versions", 200, json={"body": "v2"}, headers=headers).json()
        retry = admin_a.call("POST", f"/admin/skills/{skill['id']}/versions", 200, json={"body": "v2"}, headers=headers).json()
        assert first["id"] == retry["id"] and first["version"] == 2
        restore_headers = {"Idempotency-Key": "rv7-restore-retry"}
        restored = admin_a.call("POST", f"/admin/skills/{skill['id']}/restore/1", 200, headers=restore_headers).json()
        restored_retry = admin_a.call("POST", f"/admin/skills/{skill['id']}/restore/1", 200, headers=restore_headers).json()
        assert restored["id"] == restored_retry["id"] and restored["version"] == 3
        versions = admin_a.call("GET", f"/admin/skills/{skill['id']}/versions", 200).json()["items"]
        assert [item["version"] for item in versions] == [1, 2, 3]
        conflict = admin_a.call("POST", f"/admin/skills/{skill['id']}/versions", json={"body": "different"}, headers=headers)
        assert conflict.status_code == 422
        report("version retry IDs:", first["id"], "restore retry IDs:", restored["id"], "history:", [1, 2, 3])

        report("\n## outbound through official independent server")
        peer_items = admin_a.call("GET", "/admin/a2a-peers", 200).json()["items"]
        peer = next(item for item in peer_items if item["name"] == admin_ui_setup["peerName"])
        assert peer["is_approved"] is True
        assert peer["id"] in agent_a["allowed_peer_ids"]
        run = member_a.call(
            "POST", "/agent-runs", 202, json={"agent_id": agent_a["id"], "message": f"ASK_PEER:{peer['id']}"}
        ).json()
        run = stack.wait_run(member_a, run["id"], timeout=90)
        assert run["status"] == "succeeded" and "official-remote" in run["assistant_message"]
        events = member_a.call("GET", f"/agent-runs/{run['id']}/events", 200).json()["items"]
        remote_ids = [event["payload"].get("remote_task_id") for event in events if event["payload"].get("remote_task_id")]
        assert remote_ids
        report("parent Run:", run["id"], "remote Task IDs:", remote_ids, "reply:", run["assistant_message"])

        unselected_peer = admin_a.call(
            "POST",
            "/admin/a2a-peers",
            (200, 201),
            json={
                "name": f"RV7-unselected-{suffix}",
                "card_url": official_endpoint,
                "endpoint_url": official_endpoint,
                "credential_env_alias": PEER_ENV_ALIAS,
            },
        ).json()
        platform.call("POST", f"/admin/a2a-peers/{unselected_peer['id']}/approve", 200)
        official_requests_before_unselected_run = [
            line
            for line in official_log_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("OFFICIAL_REQUEST ")
        ]
        unselected_run = member_a.call(
            "POST",
            "/agent-runs",
            202,
            json={
                "agent_id": agent_a["id"],
                "message": f"ASK_PEER:{unselected_peer['id']}",
            },
        ).json()
        unselected_run = stack.wait_run(member_a, unselected_run["id"], timeout=60)
        official_requests_after_unselected_run = [
            line
            for line in official_log_path.read_text(encoding="utf-8").splitlines()
            if line.startswith("OFFICIAL_REQUEST ")
        ]
        assert unselected_run["status"] == "failed"
        assert official_requests_after_unselected_run == official_requests_before_unselected_run
        report(
            "approved but unbound peer rejected before HTTP:",
            unselected_peer["id"],
            "request count unchanged:",
            len(official_requests_after_unselected_run),
        )

        history_before = member_a.call("GET", "/agent-runs", 200).json()["total"]
        shell_run = member_a.call(
            "POST", "/agent-runs", 202, json={"agent_id": agent_a["id"], "message": "RUN_SHELL"}
        ).json()
        shell_run = stack.wait_run(member_a, shell_run["id"], timeout=60)
        shell_events = member_a.call("GET", f"/agent-runs/{shell_run['id']}/events", 200).json()["items"]
        assert shell_run["status"] == "failed"
        assert all(event["event_type"] != "run.completed" for event in shell_events)
        unknown_run = member_a.call(
            "POST", "/agent-runs", 202, json={"agent_id": agent_a["id"], "message": "ASK_PEER:not-registered"}
        ).json()
        unknown_run = stack.wait_run(member_a, unknown_run["id"], timeout=60)
        assert unknown_run["status"] == "failed"
        report("unsafe tool and unregistered peer runs failed closed:", shell_run["id"], unknown_run["id"])

        redirect_peer = admin_a.call(
            "POST",
            "/admin/a2a-peers",
            201,
            json={
                "name": "redirect-peer",
                "card_url": f"http://127.0.0.1:{official_port}/redirect-card",
                "endpoint_url": official_endpoint,
            },
        ).json()
        platform.call("POST", f"/admin/a2a-peers/{redirect_peer['id']}/approve", 200)
        redirect_agent_update = {
            "name": agent_a["name"],
            "description": agent_a["description"],
            "instructions": agent_a["instructions"],
            "model_name": agent_a["model_name"],
            "skill_id": agent_a["skill_id"],
            "peer_ids": [redirect_peer["id"]],
            "is_enabled": True,
        }
        admin_a.call("PUT", f"/admin/agents/{agent_a['id']}", 200, json=redirect_agent_update)
        redirect_run = member_a.call(
            "POST", "/agent-runs", 202, json={"agent_id": agent_a["id"], "message": f"ASK_PEER:{redirect_peer['id']}"}
        ).json()
        redirect_run = stack.wait_run(member_a, redirect_run["id"], timeout=60)
        assert redirect_run["status"] == "failed"
        request_lines = official_log_path.read_text(encoding="utf-8").splitlines()
        assert not any("/redirect-target" in line for line in request_lines)
        report("redirect target was not followed; remote request count:", len(request_lines))
        redirect_agent_update["peer_ids"] = agent_a["allowed_peer_ids"]
        admin_a.call("PUT", f"/admin/agents/{agent_a['id']}", 200, json=redirect_agent_update)

        updated_agent = {
            "name": agent_a["name"],
            "description": agent_a["description"],
            "instructions": agent_a["instructions"],
            "model_name": agent_a["model_name"],
            "skill_id": agent_a["skill_id"],
            "peer_ids": agent_a["allowed_peer_ids"],
            "is_enabled": False,
        }
        admin_a.call("PUT", f"/admin/agents/{agent_a['id']}", 200, json=updated_agent)
        disabled = member_a.call(
            "POST", "/agent-runs", json={"agent_id": agent_a["id"], "message": "disabled"}
        )
        assert disabled.status_code == 409
        updated_agent["is_enabled"] = True
        admin_a.call("PUT", f"/admin/agents/{agent_a['id']}", 200, json=updated_agent)
        updated_agent_snapshot = next(
            item
            for item in admin_a.call("GET", "/admin/agents", 200).json()["items"]
            if item["id"] == agent_a["id"]
        )
        assert updated_agent_snapshot["allowed_peer_ids"] == agent_a["allowed_peer_ids"]
        report("disabled Agent rejected new Run without success:", disabled.status_code)

        no_model_backend = stack.start_backend(
            database,
            model_base_url=None,
            log_name="rv7-no-model",
        )
        no_model_member = stack.public_login(no_model_backend, member_a_email, member_a_password)
        no_model = no_model_member.call(
            "POST", "/agent-runs", json={"agent_id": agent_a["id"], "message": "no model"}
        )
        assert no_model.status_code == 409
        assert no_model_member.call("GET", "/agent-runs", 200).json()["total"] == history_before + 3
        no_model_backend.stop()
        no_model_backend = None
        report("missing model rejected new Run without persistence:", no_model.status_code)

        platform.call("POST", f"/admin/organizations/{org_a['id']}/disable", 200)
        inactive = member_a.call("POST", "/agent-runs", json={"agent_id": agent_a["id"], "message": "inactive"})
        inactive_a2a = httpx.post(
            f"{agent_url}/message:send",
            headers={"Authorization": f"Bearer {inbound_token}", "A2A-Version": "1.0"},
            json={"message": {"messageId": "inactive", "role": "ROLE_USER", "parts": [{"text": "inactive"}]}},
            timeout=10,
        )
        assert inactive.status_code == 401 and inactive_a2a.status_code == 404
        report("inactive organization rejected browser and A2A runs:", inactive.status_code, inactive_a2a.status_code)
        report("\nRV_RESULT: PASS rv-7")
    except Exception as error:
        report(f"\nRV_RESULT: FAIL rv-7: {type(error).__name__}: {error}")
        raise
    finally:
        report.save()
        if no_model_backend is not None:
            no_model_backend.stop()
        if backend is not None:
            backend.stop()
        if official_process is not None:
            official_process.terminate()
            try:
                official_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                official_process.kill()
        model.close()
        database.drop()
        if mutant_source is not None:
            shutil.rmtree(mutant_source.parent, ignore_errors=True)


if __name__ == "__main__":
    stack.main_guard(main)
