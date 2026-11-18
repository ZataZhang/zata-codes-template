"""模型流式增量与 Canonical Event 合批的行为测试。

这些用例守护「成员能看到增量结果」的最小契约：执行器把 SSE 文本片段按顺序
交给回调，并把最终内容与非流式响应归一化为同一结构；Run 用例只通过
``message.delta`` 这一条事件链持久化片段。网络请求打到测试内的真实本地
HTTP 服务，不使用 httpx 传输层替身。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from backend.core.agent.runs import _StreamedDeltas
from backend.core.shared.interfaces.agent_executor import (
    A2AResponse,
    AgentExecutionCallbacks,
    AgentExternalCallEvent,
)
from backend.core.shared.interfaces.agent_types import A2APeer
from backend.core.shared.models.run import RunEventCandidate
from backend.engines.agent_adapters.model_agent_executor import OpenAICompatibleAgentExecutor
from backend.infrastructure.config.settings import (
    PRIMARY_MODEL_API_KEY_ENV,
    PRIMARY_MODEL_BASE_URL_ENV,
    PRIMARY_MODEL_NAME_ENV,
)

STREAM_FRAGMENTS = ("Hello", " from", " the", " streamed", " reply")


class _StreamingModelServer:
    """按 OpenAI Chat Completions 协议返回 SSE 或普通 JSON 的本地端点。"""

    def __init__(self, *, streaming: bool, truncated: bool = False) -> None:
        self.streaming = streaming
        self.received_requests: list[dict[str, Any]] = []
        server_owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args: object) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                request_document = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                server_owner.received_requests.append(request_document)
                if server_owner.streaming:
                    self._write_stream()
                else:
                    self._write_document()

            def _write_stream(self) -> None:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for fragment in STREAM_FRAGMENTS:
                    chunk = {
                        "choices": [{"index": 0, "delta": {"content": fragment}}],
                    }
                    self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                    self.wfile.flush()
                if truncated:
                    return
                final_chunk = {
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                self.wfile.write(f"data: {json.dumps(final_chunk)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

            def _write_document(self) -> None:
                document = {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "".join(STREAM_FRAGMENTS),
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }
                encoded = json.dumps(document).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self._server.server_address[1])
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def close(self) -> None:
        self._server.shutdown()


class _UnusedA2AClient:
    """本测试不触发 A2A 调用，保留端口形状即可。"""

    async def send_message(
        self, *, organization_id: str, peer_id: str, message: str, idempotency_key: str
    ) -> A2AResponse:
        raise AssertionError("unexpected A2A call in streaming test")


class _RecordingRunRepository:
    """只记录 ``append_event`` 的仓库替身，用于核对增量合批。"""

    def __init__(self) -> None:
        self.candidates: list[RunEventCandidate] = []

    def append_event(self, run_id: str, candidate: RunEventCandidate) -> None:
        """记录 Run 用例提交的事件候选。"""
        self.candidates.append(candidate)


def _build_executor(server: _StreamingModelServer, monkeypatch: pytest.MonkeyPatch) -> Any:
    """把主模型三件套指向测试内端点并构造真实执行器。"""
    monkeypatch.setenv(PRIMARY_MODEL_BASE_URL_ENV, server.base_url)
    monkeypatch.setenv(PRIMARY_MODEL_API_KEY_ENV, "test-model-key")
    monkeypatch.setenv(PRIMARY_MODEL_NAME_ENV, "test-model")
    return OpenAICompatibleAgentExecutor(_UnusedA2AClient())


def test_executor_streams_text_fragments_to_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    """执行器按顺序交付流式片段，并归一化出与非流式一致的最终内容。"""
    server = _StreamingModelServer(streaming=True)
    try:
        executor = _build_executor(server, monkeypatch)
        received_fragments: list[str] = []

        async def collect(delta_text: str) -> None:
            received_fragments.append(delta_text)

        execution_result = asyncio.run(
            executor.execute(
                snapshot={"organization_id": "org-1", "instructions": "be brief"},
                message="stream please",
                peers=(),
                callbacks=AgentExecutionCallbacks(on_delta=collect),
            )
        )
    finally:
        server.close()

    assert received_fragments == list(STREAM_FRAGMENTS)
    assert execution_result.content == "".join(STREAM_FRAGMENTS)
    assert execution_result.content_streamed is True
    assert server.received_requests[0]["stream"] is True


def test_executor_reports_non_streamed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """端点忽略 ``stream`` 时仍返回完整回复，并声明未交付片段。"""
    server = _StreamingModelServer(streaming=False)
    try:
        executor = _build_executor(server, monkeypatch)
        received_fragments: list[str] = []

        async def collect(delta_text: str) -> None:
            received_fragments.append(delta_text)

        execution_result = asyncio.run(
            executor.execute(
                snapshot={"organization_id": "org-1"},
                message="no stream",
                peers=(),
                callbacks=AgentExecutionCallbacks(on_delta=collect),
            )
        )
    finally:
        server.close()

    assert received_fragments == []
    assert execution_result.content == "".join(STREAM_FRAGMENTS)
    assert execution_result.content_streamed is False


def test_streamed_deltas_are_batched_into_one_event_chain() -> None:
    """流式片段按阈值合批，并且只写入 ``message.delta`` 事件。"""
    run_repository = _RecordingRunRepository()
    streamed_deltas = _StreamedDeltas(
        run_id="run-1",
        run_repository=run_repository,
        trace_id="trace-1",
        span_id="span-1",
        flush_threshold=10,
    )

    async def push_fragments() -> None:
        for fragment in ("abcdefgh", "ij", "klmnop", "q"):
            await streamed_deltas.append(fragment)
        streamed_deltas.flush()

    asyncio.run(push_fragments())

    deltas = [candidate.payload["delta"] for candidate in run_repository.candidates]
    assert all(candidate.event_type == "message.delta" for candidate in run_repository.candidates)
    assert "".join(str(delta) for delta in deltas) == "abcdefghijklmnopq"
    assert len(deltas) == 2


def test_executor_rejects_truncated_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常关闭但缺少结束原因的流不能把部分回复当成成功。"""
    server = _StreamingModelServer(streaming=True, truncated=True)
    try:
        executor = _build_executor(server, monkeypatch)
        received_fragments: list[str] = []

        async def collect(delta_text: str) -> None:
            received_fragments.append(delta_text)

        with pytest.raises(RuntimeError, match="model_stream_incomplete"):
            asyncio.run(
                executor.execute(
                    snapshot={"organization_id": "org-1"},
                    message="truncated stream",
                    peers=(),
                    callbacks=AgentExecutionCallbacks(on_delta=collect),
                )
            )
        assert received_fragments == list(STREAM_FRAGMENTS)
    finally:
        server.close()


def test_external_call_is_reported_before_followup_model_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """成功的远端 Task 在第二轮模型失败前已交给 Run 事件回调。"""
    server = _StreamingModelServer(streaming=False)

    class SuccessfulA2AClient:
        async def send_message(
            self, *, organization_id: str, peer_id: str, message: str, idempotency_key: str
        ) -> A2AResponse:
            assert (organization_id, peer_id, message) == ("org-1", "peer-1", "remote prompt")
            assert idempotency_key.endswith(":a2a:0")
            return A2AResponse(task_id="remote-task-1", content="remote answer")

    try:
        executor = _build_executor(server, monkeypatch)
        executor._a2a_client = SuccessfulA2AClient()
        completion_count = 0

        async def scripted_completion(**_kwargs: object) -> tuple[dict[str, object], bool]:
            nonlocal completion_count
            completion_count += 1
            if completion_count == 1:
                return (
                    {
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "tool_calls": [
                                        {
                                            "id": "model-tool-call-1",
                                            "function": {
                                                "name": "call_a2a_peer",
                                                "arguments": json.dumps(
                                                    {
                                                        "peer_id": "peer-1",
                                                        "message": "remote prompt",
                                                    }
                                                ),
                                            },
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                    False,
                )
            raise RuntimeError("model_request_failed")

        monkeypatch.setattr(executor, "_create_completion", scripted_completion)
        now = datetime.now(UTC)
        peer = A2APeer(
            id="peer-1",
            organization_id="org-1",
            created_by="admin-1",
            name="Remote Agent",
            card_url="https://peer.example/card",
            endpoint_url="https://peer.example/a2a",
            is_approved=True,
            is_enabled=True,
            approved_by="platform-admin-1",
            created_at=now,
            updated_at=now,
        )
        external_call_events: list[AgentExternalCallEvent] = []

        with pytest.raises(RuntimeError, match="model_request_failed"):
            asyncio.run(
                executor.execute(
                    snapshot={"organization_id": "org-1", "run_id": "run-1"},
                    message="delegate this",
                    peers=(peer,),
                    callbacks=AgentExecutionCallbacks(on_external_call=external_call_events.append),
                )
            )
    finally:
        server.close()

    assert completion_count == 2
    assert [call_event.phase for call_event in external_call_events] == ["started", "completed"]
    completed_call = external_call_events[1]
    assert completed_call.remote_task_id == "remote-task-1"
    assert completed_call.result_checksum == hashlib.sha256(b"remote answer").hexdigest()
    assert completed_call.result_length == len("remote answer")
