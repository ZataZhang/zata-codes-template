"""Admin Run 执行轨迹 API 真实入口测试。

真实边界：``SqlAlchemyRunRepository`` 事务提交 canonical 事件 → fresh 浏览器会话
→ admin 认证依赖 → Core 投影 → ``/admin/run-traces``。认证、数据库事务、投影与
序列化全真实，只用 repository 直接播种 Run 与事件（模板不内置执行器）。

同时验证低敏边界：把 canary 放进工具入参与结果，admin 响应必须只给出 checksum 与
长度，不得带出原文；public 身份不得读取 admin 诊断 API。原始事件导出端点同样在此
验证真实 HTTP 契约：终态可下载、非终态与超限必须经 router 的状态码映射被拒。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.core.run_tracing import trace_use_cases
from backend.core.shared.models.run import (
    Run,
    RunEventCandidate,
    RunStatus,
    RunSubjectSnapshot,
    derive_root_span_id,
    derive_span_id,
    derive_trace_id,
)
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.repos.run_repo import SqlAlchemyRunRepository
from tests.realdb_test_support import TrackedEntityRegistry

pytestmark = pytest.mark.realdb

# canary 放在工具入参与结果里：这两个字段属于既有 canonical payload 语义，
# 新增诊断 DTO 必须默认不扩散它们。
_CANARY_EMAIL = "canary-email-9f3a1c@example.invalid"
_CANARY_TOKEN = "canary-token-7d2b4e"
_CANARY_BODY = "canary-mail-body-3c8e1a"
_CANARY_REASONING = "canary-reasoning-6a4d2f"
_CANARY_ARGUMENT = (
    f"email={_CANARY_EMAIL}; credential={_CANARY_TOKEN}; "
    f"mail={_CANARY_BODY}; thought={_CANARY_REASONING}"
)
_CANARY_RESULT = "canary-tool-result-4f8b1e"
_ALL_CANARIES = (
    _CANARY_EMAIL,
    _CANARY_TOKEN,
    _CANARY_BODY,
    _CANARY_REASONING,
    _CANARY_RESULT,
)
_MODEL_NAME = "qwen3.8-max"
_BASE_TIME = datetime(2026, 9, 23, 10, 0, 0, tzinfo=UTC)


def _assert_diagnostic_canaries_absent(*responses: str) -> None:
    """确认诊断响应没有扩散运行时原始内容。"""
    assert all(canary not in response for response in responses for canary in _ALL_CANARIES)


def _login_admin(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
) -> tuple[TestClient, str]:
    """种入并登录管理员，返回持 admin 会话的客户端与其管理员 ID。"""
    username = f"admin-{uuid4().hex[:8]}"
    admin_id = seed_admin(username, "adminpass1")
    admin_client = build_client()
    login_response = admin_client.post(
        "/admin/auth/login", json={"identifier": username, "password": "adminpass1"}
    )
    assert login_response.status_code == 200
    return admin_client, admin_id


def _seed_run_with_tracing_events(
    repository: SqlAlchemyRunRepository,
    entity_registry: TrackedEntityRegistry,
) -> str:
    """创建一个真实 Run，并回放两轮模型与两个同名工具的 canonical 事件。

    Returns:
        str: 播种的 Run ID。
    """
    run_id = f"run_{uuid4().hex}"
    created_run = repository.create_run(
        Run(
            id=run_id,
            owner_id="owner_trace_validation",
            subject_id="subject_trace_validation",
            subject_type="internal",
            subject_snapshot=RunSubjectSnapshot(
                subject_type="internal",
                subject_id="subject_trace_validation",
                subject_name="Trace Validation Subject",
                snapshot_checksum="c" * 64,
            ),
            subject_snapshot_checksum="c" * 64,
            status=RunStatus.QUEUED,
            last_event_seq=0,
            created_at=_BASE_TIME,
        ),
        idempotency_key_hash=uuid4().hex,
        request_checksum="r" * 64,
        input_text="validate admin run tracing",
    )
    entity_registry.run_ids.append(created_run.id)

    trace_id = derive_trace_id(run_id)
    root_span_id = derive_root_span_id(run_id)
    model_span_id = derive_span_id(run_id, "model", "call_turn_0")
    parented_tool_span_id = derive_span_id(run_id, "tool", "source_tool_a")
    fallback_tool_span_id = derive_span_id(run_id, "tool", "source_tool_b")

    def _candidate(
        event_type: str,
        payload: dict[str, object],
        *,
        span_id: str,
        offset_seconds: int,
    ) -> RunEventCandidate:
        """构造一条带 canonical trace/span 的候选事件。"""
        return RunEventCandidate(
            event_type,
            payload,
            occurred_at=_BASE_TIME + timedelta(seconds=offset_seconds),
            trace_id=trace_id,
            span_id=span_id,
        )

    repository.append_event(
        run_id,
        _candidate(
            "run.started",
            {"started_at": _BASE_TIME.isoformat()},
            span_id=root_span_id,
            offset_seconds=1,
        ),
    )
    repository.append_event(
        run_id,
        _candidate(
            "model.call.started",
            {"model_call_id": "call_turn_0", "model_name": _MODEL_NAME, "turn_index": 0},
            span_id=model_span_id,
            offset_seconds=2,
        ),
    )
    # 一个工具由本轮模型触发；另一个来源无法确认父级。
    repository.append_event(
        run_id,
        _candidate(
            "tool.call.started",
            {
                "tool_call_id": "tool_a",
                "tool_name": "read_attachment",
                "arguments": {"path": _CANARY_ARGUMENT},
                "parent_model_call_id": "call_turn_0",
            },
            span_id=parented_tool_span_id,
            offset_seconds=3,
        ),
    )
    repository.append_event(
        run_id,
        _candidate(
            "tool.call.completed",
            {"tool_call_id": "tool_a", "result": _CANARY_RESULT, "result_checksum": "e" * 64},
            span_id=parented_tool_span_id,
            offset_seconds=4,
        ),
    )
    repository.append_event(
        run_id,
        _candidate(
            "model.call.completed",
            {
                "model_call_id": "call_turn_0",
                "model_name": _MODEL_NAME,
                "turn_index": 0,
                "usage": {"prompt": 812, "completion": 120, "total": 932},
                "finish_reason": "tool_calls",
            },
            span_id=model_span_id,
            offset_seconds=5,
        ),
    )
    repository.append_event(
        run_id,
        _candidate(
            "tool.call.started",
            {
                "tool_call_id": "tool_b",
                "tool_name": "read_attachment",
                "arguments": {"path": _CANARY_ARGUMENT},
            },
            span_id=fallback_tool_span_id,
            offset_seconds=6,
        ),
    )
    repository.append_event(
        run_id,
        _candidate(
            "tool.call.completed",
            {"tool_call_id": "tool_b", "result": _CANARY_RESULT, "result_checksum": "f" * 64},
            span_id=fallback_tool_span_id,
            offset_seconds=7,
        ),
    )
    repository.append_event(
        run_id,
        _candidate(
            "run.completed", {"message_id": "message_1"}, span_id=root_span_id, offset_seconds=8
        ),
    )
    return run_id


def test_admin_trace_api_projects_seeded_run_without_leaking_content(
    build_client: Callable[[], TestClient],
    seed_admin: Callable[[str, str], str],
    entity_registry: TrackedEntityRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """管理员能读到真实 Run 的 root/模型/工具节点，且响应不含种子 canary。"""
    repository = SqlAlchemyRunRepository(SessionLocal)
    run_id = _seed_run_with_tracing_events(repository, entity_registry)

    admin_client, admin_id = _login_admin(build_client, seed_admin)
    public_client = build_client()

    _assert_admin_trace_contract(admin_client, public_client, run_id)

    export_response = admin_client.get(f"/admin/run-traces/{run_id}/export")
    assert export_response.status_code == 200
    # 四个响应头必须逐条断言：只断其中一部分会让剩下的契约完全无人守住。
    assert export_response.headers["cache-control"] == "no-store"
    assert export_response.headers["pragma"] == "no-cache"
    assert export_response.headers["x-content-type-options"] == "nosniff"
    assert export_response.headers["content-disposition"] == (
        f'attachment; filename="run-{run_id}.json"'
    )
    export_body = export_response.json()
    with SessionLocal() as fresh_session:
        run_row = (
            fresh_session.execute(
                text("SELECT last_event_seq FROM run WHERE id = :run_id"), {"run_id": run_id}
            )
            .mappings()
            .one()
        )
    assert export_body["event_count"] == run_row["last_event_seq"]
    assert [event["seq"] for event in export_body["events"]] == list(
        range(1, run_row["last_event_seq"] + 1)
    )
    assert all(canary in export_response.text for canary in _ALL_CANARIES)
    assert public_client.get(f"/admin/run-traces/{run_id}/export").status_code == 401
    assert admin_client.get("/admin/run-traces/run_missing/export").status_code == 404

    with SessionLocal() as audit_session:
        audit_row = (
            audit_session.execute(
                text(
                    "SELECT actor_id, event_count, byte_count FROM run_export_audit "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id},
            )
            .mappings()
            .one()
        )
    assert audit_row["actor_id"] == admin_id
    assert audit_row["event_count"] == export_body["event_count"]
    assert audit_row["byte_count"] == len(export_response.content)

    # 拒绝路径必须经 router 的 RunExportError→HTTPException 映射到达客户端；
    # 只在 use case 层断言会让这段映射永远没有测试执行到。
    with SessionLocal.begin() as database_session:
        database_session.execute(
            text("UPDATE run SET status = 'running' WHERE id = :run_id"),
            {"run_id": run_id},
        )
    non_terminal_response = admin_client.get(f"/admin/run-traces/{run_id}/export")
    assert non_terminal_response.status_code == 409
    assert non_terminal_response.json()["detail"] == "Run 尚未终结，请稍后下载"

    # 用把上限压到 1 的方式驱动 413 映射：断言的是状态码契约，不是 10000 这个默认值
    # （默认值边界由 test_run_trace_export.py 覆盖）。
    with SessionLocal.begin() as database_session:
        database_session.execute(
            text("UPDATE run SET status = 'succeeded' WHERE id = :run_id"),
            {"run_id": run_id},
        )
    monkeypatch.setattr(trace_use_cases, "MAX_RAW_EXPORT_EVENTS", 1)
    over_limit_response = admin_client.get(f"/admin/run-traces/{run_id}/export")
    assert over_limit_response.status_code == 413
    assert over_limit_response.json()["detail"] == "事件数量超过下载上限"

    with SessionLocal() as audit_session:
        audit_count = audit_session.execute(
            text("SELECT COUNT(*) FROM run_export_audit WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).scalar_one()
    # 两次被拒的请求都不得留下审计行，成功的导出仍然只有那一条。
    assert audit_count == 1


def _assert_admin_trace_contract(
    admin_client: TestClient,
    public_client: TestClient,
    run_id: str,
) -> None:
    """断言 admin 诊断契约与低敏边界。"""
    list_response = admin_client.get("/admin/run-traces", params={"run_id": run_id})
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert list_body["total"] == 1
    listed_run = list_body["items"][0]
    assert listed_run["run_id"] == run_id
    assert listed_run["visibility"] == "full"
    assert listed_run["model_call_count"] == 1
    assert listed_run["tool_call_count"] == 2

    detail_response = admin_client.get(f"/admin/run-traces/{run_id}")
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["content_policy"] == "metadata-only"
    assert detail_body["root_span_id"]

    spans = detail_body["spans"]
    root_spans = [span for span in spans if span["kind"] == "root"]
    model_spans = [span for span in spans if span["kind"] == "model"]
    tool_spans = [span for span in spans if span["kind"] == "tool"]
    assert len(root_spans) == 1
    assert len(model_spans) == 1
    assert all(span["parent_span_id"] == detail_body["root_span_id"] for span in model_spans)
    assert all("unknown_parent" not in span["diagnostics"] for span in model_spans)

    # 并行同名工具靠调用 ID 分开，不按工具名合并。
    assert len({span["tool_call_id"] for span in tool_spans}) == 2
    assert len({span["span_id"] for span in tool_spans}) == 2
    assert all(span["tool_name"] == "read_attachment" for span in tool_spans)
    parented_tool_spans = [
        span for span in tool_spans if span["parent_span_id"] != detail_body["root_span_id"]
    ]
    fallback_tool_spans = [
        span for span in tool_spans if span["parent_span_id"] == detail_body["root_span_id"]
    ]
    assert len(parented_tool_spans) == 1
    assert len(fallback_tool_spans) == 1
    assert "parent_source_unavailable" in fallback_tool_spans[0]["diagnostics"]
    assert parented_tool_spans[0]["parent_span_id"] == model_spans[0]["span_id"]

    tree = detail_body["tree"]
    assert [node["span"]["span_id"] for node in tree] == [detail_body["root_span_id"]]
    root_node = tree[0]
    # 根的直接子节点 = 一条模型 span + 一个父级来源不可确认、降级到根的工具 span。
    assert len(root_node["children"]) == 2
    assert {child["span"]["span_id"] for child in root_node["children"]} == {
        model_spans[0]["span_id"],
        fallback_tool_spans[0]["span_id"],
    }
    first_turn_node = next(
        child
        for child in root_node["children"]
        if child["span"]["span_id"] == parented_tool_spans[0]["parent_span_id"]
    )
    assert [child["span"]["span_id"] for child in first_turn_node["children"]] == [
        parented_tool_spans[0]["span_id"]
    ]

    # 低敏边界：诊断响应只给 checksum 与长度，canary 原文不得出现。
    _assert_diagnostic_canaries_absent(detail_response.text, list_response.text)
    # 测试边界负控：污染一份响应副本，证明 canary 扫描会变红。
    with pytest.raises(AssertionError):
        _assert_diagnostic_canaries_absent(
            json.dumps({**detail_body, "leaked_result": _CANARY_RESULT})
        )
    completed_tool_span = next(span for span in tool_spans if span["result_checksum"])
    assert completed_tool_span["result_length"] == len(_CANARY_RESULT)
    # 工具原始入参/结果不进入诊断节点字段。
    assert all("arguments" not in span for span in spans)
    assert all("result" not in span for span in tool_spans)

    # 同一 Run 再次读取（等价于浏览器刷新）仍得到同一棵树。
    refreshed_body = admin_client.get(f"/admin/run-traces/{run_id}").json()
    assert [span["span_id"] for span in refreshed_body["spans"]] == [
        span["span_id"] for span in spans
    ]
    assert [span["status"] for span in refreshed_body["spans"]] == [
        span["status"] for span in spans
    ]
    assert refreshed_body["summary"]["trace_id"] == detail_body["summary"]["trace_id"]

    # public 身份不能读取 admin 诊断 API。
    assert public_client.get("/admin/run-traces", params={"run_id": run_id}).status_code == 401
    assert public_client.get(f"/admin/run-traces/{run_id}").status_code == 401
    assert admin_client.get("/admin/run-traces/run_missing").status_code == 404
