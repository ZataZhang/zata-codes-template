"""rv-1：两组织真实会话越权负控、迁移对账与成员调组织后的数据归属。

用法（仓库根目录）：
  uv run --no-sync python tasks/evidence/<stem>/scripts/rv1_org_isolation.py --db pg
  uv run --no-sync python tasks/evidence/<stem>/scripts/rv1_org_isolation.py --db mysql
  uv run --no-sync python tasks/evidence/<stem>/scripts/rv1_org_isolation.py --db pg --mutant
--mutant 把 src/ 复制到临时目录并删除 AgentRunUseCase.get_scoped_run 的组织/owner 过滤，
用同一套探针证明断言会变红（变异只存在于临时副本，生产代码不含任何故障开关）。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

import bcrypt
import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rv_stack as stack  # noqa: E402

LEGACY_EMAIL = "legacy-owner@example.test"
SECRET_A = "ORG-A-PRIVATE-PAYLOAD-7f3c"
MOVER_SECRET = "MOVER-A-PERIOD-NOTE-91d2"


def seed_legacy(database: stack.TempDatabase, password: str) -> dict[str, str]:
    """在 Agent 迁移之前写入一条存量 public 用户、Run 与两条事件。"""
    engine = sa.create_engine(database.url)
    now = datetime.now(UTC).replace(tzinfo=None)
    user_id = str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    snapshot = {
        "subject_type": "legacy",
        "subject_id": "legacy-subject",
        "subject_name": "Legacy",
        "snapshot_checksum": "0" * 64,
    }
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "INSERT INTO public_user (id, email, display_name, password_hash, is_active,"
                " organization_id) VALUES (:id, :email, 'legacy', :hash, :active, 'default')"
            ),
            {
                "id": user_id,
                "email": LEGACY_EMAIL,
                "hash": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                "active": True,
            },
        )
        connection.execute(
            sa.text(
                "INSERT INTO run (id, subject_id, subject_type, subject_name, subject_snapshot,"
                " subject_snapshot_checksum, owner_id, status, last_event_seq,"
                " idempotency_key_hash, request_checksum, created_at, finished_at)"
                " VALUES (:id, 'legacy-subject', 'legacy', 'Legacy', :snap, :c64, :owner,"
                " 'succeeded', 2, :c64, :c64, :now, :now)"
            ),
            {"id": run_id, "snap": json.dumps(snapshot), "c64": "0" * 64, "owner": user_id, "now": now},
        )
        for seq, event_type, payload in (
            (1, "input.accepted", {"content": "legacy hello"}),
            (2, "message.completed", {"content": "legacy answer"}),
        ):
            connection.execute(
                sa.text(
                    "INSERT INTO run_event (run_id, seq, schema_version, event_type, occurred_at,"
                    " recorded_at, subject_id, subject_snapshot_checksum, payload,"
                    " payload_checksum, provenance) VALUES (:run, :seq, 1, :type, :now, :now,"
                    " 'legacy-subject', :c64, :payload, :c64, :prov)"
                ),
                {
                    "run": run_id,
                    "seq": seq,
                    "type": event_type,
                    "now": now,
                    "c64": "0" * 64,
                    "payload": json.dumps(payload),
                    "prov": json.dumps({"source": "rv-1-legacy-seed"}),
                },
            )
    engine.dispose()
    return {"user_id": user_id, "run_id": run_id}


def table_counts(database: stack.TempDatabase) -> dict[str, object]:
    engine = sa.create_engine(database.url)
    with engine.connect() as connection:
        counts = {
            "run": connection.execute(sa.text("SELECT COUNT(*) FROM run")).scalar_one(),
            "run_event": connection.execute(sa.text("SELECT COUNT(*) FROM run_event")).scalar_one(),
            "orphan_events": connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM run_event e LEFT JOIN run r ON r.id = e.run_id"
                    " WHERE r.id IS NULL"
                )
            ).scalar_one(),
        }
        columns = {column["name"] for column in sa.inspect(connection).get_columns("run")}
        if "organization_id" in columns:
            counts["run_by_org"] = dict(
                connection.execute(
                    sa.text("SELECT organization_id, COUNT(*) FROM run GROUP BY organization_id")
                ).all()
            )
    engine.dispose()
    return counts


def mutant_src() -> Path:
    """复制 src 并去掉 get_scoped_run 的组织/owner 过滤（仅临时副本）。"""
    root = Path(tempfile.mkdtemp(prefix="rv58-mutant-"))
    shutil.copytree(stack.WORKTREE / "src", root / "src")
    shutil.copytree(stack.WORKTREE / "alembic", root / "alembic")
    shutil.copy2(stack.WORKTREE / "alembic.ini", root / "alembic.ini")
    target = root / "src/backend/core/agent/runs.py"
    text = target.read_text(encoding="utf-8")
    original = (
        "            run is None\n"
        "            or run.organization_id != organization_id\n"
        "            or (owner_id is not None and run.owner_id != owner_id)\n"
    )
    assert original in text, "mutation anchor missing"
    target.write_text(text.replace(original, "            run is None\n", 1), encoding="utf-8")
    return root / "src"


def assert_hidden(report: stack.Report, label: str, response, forbidden: list[str]) -> None:
    body = response.text
    leaked = [value for value in forbidden if value and value in body]
    ok = response.status_code in (403, 404) and not leaked
    report(f"  [{'OK' if ok else 'LEAK'}] {label}: HTTP {response.status_code} leaked={leaked}")
    if not ok:
        raise AssertionError(f"cross-organization exposure: {label} -> {response.status_code}")


def run_scenario(kind: str, mutant: bool) -> None:
    suffix = "-mutant" if mutant else ""
    evidence_name = f"rv-1-negative-control-{kind}.txt" if mutant else f"rv-1-org-isolation-{kind}.txt"
    report = stack.Report(stack.EVIDENCE_DIR / evidence_name)
    report(f"# rv-1 organization isolation ({kind}{suffix}) at {datetime.now(UTC).isoformat()}")
    report("identity:", json.dumps(stack.git_identity()))
    src_path = mutant_src() if mutant else None
    if mutant:
        report("MUTANT: get_scoped_run organization/owner filter removed in a temp copy of src/")
    database = stack.create_database(kind, "rv1")
    model = stack.ModelStub(delay_seconds=0.2)
    backend = None
    legacy_password = "Legacy-" + uuid.uuid4().hex[:10]
    member_password = "Member-" + uuid.uuid4().hex[:10]
    try:
        # ---------- 迁移：存量 Run/Event 回填、计数与降级往返 ----------
        report("\n## migration with pre-existing data")
        stack.alembic(database, "upgrade", stack.PRE_AGENT_REVISION, src_path=src_path)
        legacy = seed_legacy(database, legacy_password)
        before = table_counts(database)
        report("before upgrade:", before)
        upgrade_log = stack.alembic(database, "upgrade", "head", src_path=src_path)
        backfill_lines = [line for line in upgrade_log.splitlines() if "organization backfill" in line]
        report("migration log:", backfill_lines[-1].split("] ")[-1] if backfill_lines else "MISSING")
        after = table_counts(database)
        report("after upgrade:", after)
        assert backfill_lines, "migration did not log backfill counts"
        assert after["run"] == before["run"] and after["run_event"] == before["run_event"]
        assert after["orphan_events"] == 0 and after["run_by_org"] == {"default": before["run"]}
        stack.alembic(database, "downgrade", stack.PRE_AGENT_REVISION, src_path=src_path)
        report(f"after downgrade {stack.PRE_AGENT_REVISION}:", table_counts(database))
        stack.alembic(database, "upgrade", "head", src_path=src_path)
        heads = [
            line for line in stack.alembic(database, "current", src_path=src_path).splitlines()
            if "(head)" in line
        ]
        report("re-upgraded current revision:", heads)
        assert heads, "database not at single head"
        assert table_counts(database)["run_event"] == before["run_event"]

        backend = stack.start_backend(
            database,
            model_base_url=model.base_url,
            src_path=src_path,
            log_name=f"rv1-{kind}{suffix}",
        )
        report(f"\n## real backend on {backend.base_url} (uvicorn backend.main:app)")
        platform = stack.admin_login(backend, backend.admin_username, backend.admin_password)
        token = uuid.uuid4().hex[:6]
        org_a = platform.call("POST", "/admin/organizations", (200, 201), json={"name": f"Org-A-{token}"}).json()
        org_b = platform.call("POST", "/admin/organizations", (200, 201), json={"name": f"Org-B-{token}"}).json()
        report("organizations created via API:", org_a["id"], org_b["id"])
        admin_passwords: dict[str, str] = {}
        for label, org in (("a", org_a), ("b", org_b)):
            admin_passwords[label] = "OrgAdm-" + uuid.uuid4().hex[:10]
            platform.call(
                "POST",
                "/admin/admins",
                (200, 201),
                json={
                    "username": f"rv1-admin-{label}-{token}",
                    "email": f"rv1-admin-{label}-{token}@example.test",
                    "role": "org",
                    "organization_id": org["id"],
                    "password": admin_passwords[label],
                },
            )
        users: dict[str, str] = {}
        for label, org in (("member_a", org_a), ("member_b", org_b), ("mover", org_a)):
            email = f"rv1-{label}-{token}@example.test"
            _, user_id = stack.public_register(backend, email, member_password)
            platform.call(
                "PATCH", f"/admin/users/{user_id}/organization", 200, json={"organization_id": org["id"]}
            )
            users[label] = email
        admin_a = stack.admin_login(backend, f"rv1-admin-a-{token}", admin_passwords["a"])
        admin_b = stack.admin_login(backend, f"rv1-admin-b-{token}", admin_passwords["b"])
        member_a = stack.public_login(backend, users["member_a"], member_password)
        member_b = stack.public_login(backend, users["member_b"], member_password)
        mover = stack.public_login(backend, users["mover"], member_password)

        skill_a = admin_a.call(
            "POST", "/admin/skills", 201, json={"name": f"Skill-A-{token}", "body": f"Skill A body {SECRET_A}"}
        ).json()
        agent_a = admin_a.call(
            "POST",
            "/admin/agents",
            201,
            json={"name": f"Agent-A-{token}", "instructions": "Be brief.", "skill_id": skill_a["id"]},
        ).json()
        admin_a.call("POST", f"/admin/agents/{agent_a['id']}/publish", 200)
        agent_b = admin_b.call(
            "POST", "/admin/agents", 201, json={"name": f"Agent-B-{token}", "instructions": "B"}
        ).json()
        admin_b.call("POST", f"/admin/agents/{agent_b['id']}/publish", 200)
        credential_a = admin_a.call(
            "POST", f"/admin/agents/{agent_a['id']}/a2a-credentials", (200, 201), json={"name": "rv1"}
        ).json()

        run_a = member_a.call(
            "POST", "/agent-runs", 202, json={"agent_id": agent_a["id"], "message": f"hello {SECRET_A}"}
        ).json()
        run_a = stack.wait_run(member_a, run_a["id"])
        mover_run = mover.call(
            "POST", "/agent-runs", 202, json={"agent_id": agent_a["id"], "message": MOVER_SECRET}
        ).json()
        mover_run = stack.wait_run(mover, mover_run["id"])
        report("org A run:", run_a["id"], run_a["status"], "| mover run:", mover_run["id"], mover_run["status"])
        assert run_a["status"] == "succeeded" and SECRET_A in run_a["input_message"]

        forbidden = [org_a["name"], agent_a["name"], skill_a["name"], SECRET_A, MOVER_SECRET]
        report("\n## organization B member -> organization A resources (exact IDs from A responses)")
        assert_hidden(report, "GET /agent-runs/{A run}", member_b.call("GET", f"/agent-runs/{run_a['id']}"), forbidden)
        assert_hidden(report, "GET /agent-runs/{A run}/events", member_b.call("GET", f"/agent-runs/{run_a['id']}/events"), forbidden)
        assert_hidden(report, "GET /agent-runs/{A run}/assets", member_b.call("GET", f"/agent-runs/{run_a['id']}/assets"), forbidden)
        assert_hidden(report, "POST /agent-runs/{A run}/cancel", member_b.call("POST", f"/agent-runs/{run_a['id']}/cancel"), forbidden)
        assert_hidden(
            report,
            "POST /agent-runs agent_id={A agent}",
            member_b.call("POST", "/agent-runs", json={"agent_id": agent_a["id"], "message": "x"}),
            forbidden,
        )
        b_agents = member_b.call("GET", "/agents", 200)
        b_runs = member_b.call("GET", "/agent-runs", 200)
        listed_ok = agent_a["id"] not in b_agents.text and run_a["id"] not in b_runs.text
        report(f"  [{'OK' if listed_ok else 'LEAK'}] B /agents and /agent-runs lists exclude A ids")
        assert listed_ok

        report("\n## organization B admin -> organization A resources")
        for method, path, body in (
            ("PUT", f"/admin/agents/{agent_a['id']}", {"name": "steal", "instructions": "x"}),
            ("POST", f"/admin/agents/{agent_a['id']}/publish", None),
            ("POST", f"/admin/agents/{agent_a['id']}/unpublish", None),
            ("GET", f"/admin/agents/{agent_a['id']}/a2a-credentials", None),
            ("DELETE", f"/admin/a2a-credentials/{credential_a['id']}", None),
            ("GET", f"/admin/skills/{skill_a['id']}/versions", None),
            ("POST", f"/admin/skills/{skill_a['id']}/versions", {"body": "overwrite"}),
            ("GET", f"/admin/skills/{skill_a['id']}/compare?from_version=1&to_version=1", None),
            ("POST", f"/admin/skills/{skill_a['id']}/restore/1", None),
            ("GET", f"/admin/agent-runs/{run_a['id']}/events", None),
        ):
            assert_hidden(report, f"{method} {path.split('?')[0]}", admin_b.call(method, path, json=body), forbidden)
        b_admin_lists = " ".join(
            admin_b.call("GET", path, 200).text for path in ("/admin/agents", "/admin/skills", "/admin/agent-runs")
        )
        lists_ok = all(value not in b_admin_lists for value in (agent_a["id"], skill_a["id"], run_a["id"]))
        report(f"  [{'OK' if lists_ok else 'LEAK'}] B admin /admin/agents|skills|agent-runs lists exclude A ids")
        assert lists_ok

        report("\n## existence oracle: real A id vs random id give identical responses")
        random_id = str(uuid.uuid4())
        real = member_b.call("GET", f"/agent-runs/{run_a['id']}")
        fake = member_b.call("GET", f"/agent-runs/{random_id}")
        same = (real.status_code, real.json()) == (fake.status_code, fake.json())
        report(f"  [{'OK' if same else 'LEAK'}] member: {real.status_code} {real.text} == {fake.status_code} {fake.text}")
        assert same
        real = admin_b.call("GET", f"/admin/agent-runs/{run_a['id']}/events")
        fake = admin_b.call("GET", f"/admin/agent-runs/{random_id}/events")
        same = (real.status_code, real.json()) == (fake.status_code, fake.json())
        report(f"  [{'OK' if same else 'LEAK'}] admin: {real.status_code} {real.text} == {fake.status_code} {fake.text}")
        assert same

        report("\n## platform admin has no default access to member content")
        assert_hidden(report, "platform GET /admin/agent-runs/{A run}/events", platform.call("GET", f"/admin/agent-runs/{run_a['id']}/events"), forbidden)
        assert_hidden(report, "platform GET /admin/run-traces/{A run}/export", platform.call("GET", f"/admin/run-traces/{run_a['id']}/export"), forbidden)

        report("\n## request body cannot choose organization")
        spoof = member_b.call(
            "POST",
            "/agent-runs",
            json={"agent_id": agent_a["id"], "message": "x", "organization_id": org_a["id"]},
        )
        assert_hidden(report, "POST /agent-runs with organization_id=A in body", spoof, forbidden)

        report("\n## legacy owner still reads migrated history (fresh login)")
        legacy_session = stack.public_login(backend, LEGACY_EMAIL, legacy_password)
        legacy_run = legacy_session.call("GET", f"/agent-runs/{legacy['run_id']}", 200).json()
        report("  legacy run:", legacy_run["id"], legacy_run["status"], repr(legacy_run["input_message"]), repr(legacy_run["assistant_message"]))
        assert legacy_run["assistant_message"] == "legacy answer"

        report("\n## platform admin moves member from A to B; data stays with A")
        mover_conversation = mover_run["conversation_id"]
        mover_user_id = mover.call("GET", "/auth/me", 200).json()["user_id"]
        platform.call(
            "PATCH", f"/admin/users/{mover_user_id}/organization", 200, json={"organization_id": org_b["id"]}
        )
        moved = stack.public_login(backend, users["mover"], member_password)
        assert_hidden(report, "moved member GET own A-period run", moved.call("GET", f"/agent-runs/{mover_run['id']}"), forbidden)
        assert_hidden(report, "moved member GET own A-period events", moved.call("GET", f"/agent-runs/{mover_run['id']}/events"), forbidden)
        moved_list = moved.call("GET", "/agent-runs", 200).text
        report(f"  [{'OK' if mover_run['id'] not in moved_list else 'LEAK'}] moved member history list excludes A-period run")
        assert mover_run["id"] not in moved_list
        append = moved.call(
            "POST",
            "/agent-runs",
            json={"agent_id": agent_b["id"], "message": "append", "conversation_id": mover_conversation},
        )
        assert_hidden(report, "moved member append to A-period conversation", append, forbidden)
        fresh_admin_b = stack.admin_login(backend, f"rv1-admin-b-{token}", admin_passwords["b"])
        b_view = fresh_admin_b.call("GET", "/admin/agent-runs", 200).text
        report(f"  [{'OK' if mover_run['id'] not in b_view else 'LEAK'}] B admin view excludes moved member A-period run")
        assert mover_run["id"] not in b_view
        fresh_admin_a = stack.admin_login(backend, f"rv1-admin-a-{token}", admin_passwords["a"])
        a_view = fresh_admin_a.call("GET", "/admin/agent-runs", 200).json()
        a_events = fresh_admin_a.call("GET", f"/admin/agent-runs/{mover_run['id']}/events", 200).json()
        a_ok = any(item["id"] == mover_run["id"] for item in a_view["items"])
        no_body = MOVER_SECRET not in json.dumps(a_events)
        report(f"  [{'OK' if a_ok else 'MISSING'}] A admin still lists moved member A-period run; events={len(a_events['items'])}; low-sensitive (no message body)={no_body}")
        assert a_ok and no_body

        report("\n## fresh-state probe: new clients and direct SQL")
        fresh_member_a = stack.public_login(backend, users["member_a"], member_password)
        reread = fresh_member_a.call("GET", f"/agent-runs/{run_a['id']}", 200).json()
        report("  member A fresh re-read:", reread["id"], reread["status"], "reply present:", bool(reread["assistant_message"]))
        engine = sa.create_engine(database.url)
        with engine.connect() as connection:
            rows = connection.execute(
                sa.text("SELECT id, organization_id, status FROM run WHERE id IN (:a, :m) ORDER BY id"),
                {"a": run_a["id"], "m": mover_run["id"]},
            ).all()
        engine.dispose()
        report("  SQL run rows:", [tuple(row) for row in rows])
        assert all(row[1] == org_a["id"] for row in rows)
        report("  final counts:", table_counts(database))
        report("\nRV_RESULT: PASS rv-1", kind)
    except Exception as error:
        report(f"\nRV_RESULT: FAIL rv-1 {kind}{suffix}: {type(error).__name__}: {error}")
        raise
    finally:
        report.save()
        if backend is not None:
            backend.stop()
        model.close()
        database.drop()
        if src_path is not None:
            shutil.rmtree(src_path.parent, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", action="append", choices=["pg", "mysql"], required=True)
    parser.add_argument("--mutant", action="store_true")
    arguments = parser.parse_args()
    for kind in arguments.db:
        run_scenario(kind, arguments.mutant)


if __name__ == "__main__":
    stack.main_guard(main)
