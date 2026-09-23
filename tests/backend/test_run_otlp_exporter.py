"""Canonical Run OTLP 导出测试。

用本地协议级接收器接住真实 OTLP/HTTP 请求：断言请求命中部署方给出的完整 Trace
URL、span 树与 canonical 事件使用同一组 trace/span ID，并验证 endpoint 缺失与
endpoint 拒绝连接都不会向调用方抛出。

OpenTelemetry 是可选依赖（``uv sync --extra tracing``），因此模块级 import 包在
try/except 里：未安装时整文件 skip，同时满足依赖声明守卫对可选能力的口径。
"""

from __future__ import annotations

import gzip
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

try:
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.proto.trace.v1.trace_pb2 import Status
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
except ImportError:  # pragma: no cover - 缺少可选依赖时跳过整个文件
    pytest.skip(
        "需要 OpenTelemetry 可选依赖：uv sync --extra tracing",
        allow_module_level=True,
    )

from backend.core.shared.models.run import (
    RunEvent,
    derive_root_span_id,
    derive_span_id,
    derive_trace_id,
)
from backend.infrastructure.config.settings import ObservabilitySettings, config
from backend.infrastructure.observability.run_otlp_exporter import RunOtlpExporter

_RUN_ID = "run_otlp_fixture"
_BASE_TIME = datetime(2026, 9, 21, 10, 0, 0, tzinfo=UTC)
_TRACE_ID = derive_trace_id(_RUN_ID)
_ROOT_SPAN_ID = derive_root_span_id(_RUN_ID)
_MODEL_SPAN_ID = derive_span_id(_RUN_ID, "model", "call_1")
_TOOL_SPAN_ID = derive_span_id(_RUN_ID, "tool", "source_tool_1")


@dataclass
class _ReceivedRequest:
    """接收器记录的一次 OTLP 请求。"""

    path: str
    payload: ExportTraceServiceRequest


@dataclass
class _OtlpReceiver:
    """本地 OTLP/HTTP 接收器，记录请求路径与解码后的 payload。"""

    requests: list[_ReceivedRequest] = field(default_factory=list)
    server: ThreadingHTTPServer | None = None
    _thread: threading.Thread | None = None

    @property
    def endpoint(self) -> str:
        """返回接收器的完整 Trace URL。"""
        assert self.server is not None
        host, port = self.server.server_address[:2]
        return f"http://{host}:{port}"

    def collect_spans(self) -> list[Any]:
        """返回所有收到请求里的扁平 span 列表。"""
        return [
            span
            for received_request in self.requests
            for resource_spans in received_request.payload.resource_spans
            for scope_spans in resource_spans.scope_spans
            for span in scope_spans.spans
        ]


def _start_receiver() -> Iterator[_OtlpReceiver]:
    """启动本地接收器并在测试结束后关闭。"""
    receiver = _OtlpReceiver()

    class _Handler(BaseHTTPRequestHandler):
        """把请求体解码成 OTLP payload 并返回成功响应。"""

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 契约
            """记录一次 OTLP 导出请求。"""
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            if self.headers.get("Content-Encoding") == "gzip":
                raw_body = gzip.decompress(raw_body)
            decoded_payload = ExportTraceServiceRequest()
            decoded_payload.ParseFromString(raw_body)
            receiver.requests.append(_ReceivedRequest(path=self.path, payload=decoded_payload))
            response_body = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response_body)))
            self.end_headers()
            self.wfile.write(response_body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            """静默 HTTP 日志，避免污染测试输出。"""

    receiver.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    receiver._thread = threading.Thread(target=receiver.server.serve_forever, daemon=True)
    receiver._thread.start()
    try:
        yield receiver
    finally:
        if receiver.server is not None:
            receiver.server.shutdown()
            receiver.server.server_close()


def _event(
    seq: int,
    event_type: str,
    payload: dict[str, object],
    *,
    span_id: str | None,
    offset_seconds: int = 0,
) -> RunEvent:
    """构造一条已提交事件 envelope。"""
    occurred_at = _BASE_TIME + timedelta(seconds=offset_seconds)
    return RunEvent(
        run_id=_RUN_ID,
        seq=seq,
        event_type=event_type,
        occurred_at=occurred_at,
        recorded_at=occurred_at,
        subject_id="subject_1",
        subject_snapshot_checksum="c" * 64,
        payload=payload,
        payload_checksum="d" * 64,
        trace_id=_TRACE_ID,
        span_id=span_id,
    )


def _run_created_payload() -> dict[str, object]:
    """``run.created`` 的通用主体载荷。"""
    return {"subject_id": "subject_1", "subject_snapshot_checksum": "c" * 64}


def _committed_events() -> list[RunEvent]:
    """构造一次含两轮模型与一次工具调用的完整 Run 事件流。"""
    return [
        _event(1, "run.created", _run_created_payload(), span_id=_ROOT_SPAN_ID),
        _event(2, "run.started", {"started_at": _BASE_TIME.isoformat()}, span_id=_ROOT_SPAN_ID),
        _event(
            3,
            "model.call.started",
            {"model_call_id": "call_1", "model_name": "qwen3.8-max", "turn_index": 0},
            span_id=_MODEL_SPAN_ID,
            offset_seconds=1,
        ),
        _event(
            4,
            "tool.call.started",
            {
                "tool_call_id": "tool_1",
                "tool_name": "read_attachment",
                "arguments": {},
                "parent_model_call_id": "call_1",
            },
            span_id=_TOOL_SPAN_ID,
            offset_seconds=2,
        ),
        _event(
            5,
            "tool.call.completed",
            {"tool_call_id": "tool_1", "result": "ok", "result_checksum": "e" * 64},
            span_id=_TOOL_SPAN_ID,
            offset_seconds=3,
        ),
        _event(
            6,
            "model.call.completed",
            {
                "model_call_id": "call_1",
                "model_name": "qwen3.8-max",
                "turn_index": 0,
                "usage": {"prompt": 812, "completion": 120, "total": 932},
                "finish_reason": "stop",
            },
            span_id=_MODEL_SPAN_ID,
            offset_seconds=4,
        ),
        _event(
            7,
            "run.completed",
            {"message_id": "message_1"},
            span_id=_ROOT_SPAN_ID,
            offset_seconds=5,
        ),
    ]


def _build_exporter(endpoint: str) -> RunOtlpExporter:
    """按生产参数装配 exporter。"""
    return RunOtlpExporter(
        endpoint=endpoint,
        service_name="template-backend-test",
        service_version="0.1.0",
        deployment_environment="test",
        timeout_seconds=2.0,
        batch_size=64,
        schedule_delay_ms=10,
    )


def test_complete_trace_url_is_used_verbatim_without_signal_path() -> None:
    """完整 Trace URL 原样使用：命中部署方给的路径，不追加 /v1/traces。"""
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    try:
        custom_path = "/arms/traces/tenant_42"
        exporter = _build_exporter(f"{receiver.endpoint}{custom_path}")
        for committed_event in _committed_events():
            exporter.record_committed_event(committed_event)
        exporter.shutdown()

        assert [request.path for request in receiver.requests] == [custom_path]
        assert all("/v1/traces" not in request.path for request in receiver.requests)
    finally:
        receiver_iterator.close()


def test_exported_spans_reuse_canonical_trace_span_ids_and_tree() -> None:
    """导出的 span 与 canonical 事件使用同一 trace/span ID 和父子关系。"""
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    try:
        exporter = _build_exporter(receiver.endpoint)
        for committed_event in _committed_events():
            exporter.record_committed_event(committed_event)
        exporter.shutdown()

        spans = receiver.collect_spans()
        span_ids = {span.span_id.hex(): span for span in spans}
        assert _ROOT_SPAN_ID in span_ids
        assert _MODEL_SPAN_ID in span_ids
        assert _TOOL_SPAN_ID in span_ids
        assert all(span.trace_id.hex() == _TRACE_ID for span in spans)

        assert span_ids[_ROOT_SPAN_ID].parent_span_id == b""
        assert span_ids[_MODEL_SPAN_ID].parent_span_id.hex() == _ROOT_SPAN_ID
        assert span_ids[_TOOL_SPAN_ID].parent_span_id.hex() == _MODEL_SPAN_ID

        span_names = {span.name for span in spans}
        assert span_names == {"run", "gen_ai.chat", "execute_tool"}

        model_attributes = {
            attribute.key: attribute.value for attribute in span_ids[_MODEL_SPAN_ID].attributes
        }
        assert model_attributes["gen_ai.usage.input_tokens"].int_value == 812
        assert model_attributes["gen_ai.usage.output_tokens"].int_value == 120

        tool_attributes = {
            attribute.key: attribute.value for attribute in span_ids[_TOOL_SPAN_ID].attributes
        }
        assert tool_attributes["gen_ai.tool.name"].string_value == "read_attachment"
        assert tool_attributes["run.tool.parent_source"].string_value == "model_call"
        assert "run.error.code" not in tool_attributes
        assert span_ids[_TOOL_SPAN_ID].status.code != Status.STATUS_CODE_ERROR

        # 外部 payload 不得携带 prompt、工具原始参数或结果。
        exported_keys = {attribute.key for span in spans for attribute in span.attributes}
        assert not any(
            forbidden in key
            for key in exported_keys
            for forbidden in ("prompt", "arguments", "result", "reasoning")
        )
    finally:
        receiver_iterator.close()


def test_failed_tool_call_exports_error_status_and_code() -> None:
    """工具调用失败时导出 ERROR 状态与错误码，Run 成功也不掩盖这次失败。"""
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    try:
        exporter = _build_exporter(receiver.endpoint)
        # 前四条事件里已包含 tool.call.started，随后用 failed 取代 completed：
        # 终态事件之前追加，因为终态之后 canonical 事件不再被接受。
        for committed_event in [
            *_committed_events()[:4],
            _event(
                5,
                "tool.call.failed",
                {"tool_call_id": "tool_1", "error": {"code": "upstream_timeout"}},
                span_id=_TOOL_SPAN_ID,
                offset_seconds=3,
            ),
            _event(
                6,
                "run.completed",
                {"message_id": "message_1"},
                span_id=_ROOT_SPAN_ID,
                offset_seconds=4,
            ),
        ]:
            exporter.record_committed_event(committed_event)
        exporter.shutdown()

        tool_span = next(
            span for span in receiver.collect_spans() if span.span_id.hex() == _TOOL_SPAN_ID
        )
        tool_attributes = {attribute.key: attribute.value for attribute in tool_span.attributes}
        assert tool_attributes["run.error.code"].string_value == "upstream_timeout"
        assert tool_span.status.code == Status.STATUS_CODE_ERROR
    finally:
        receiver_iterator.close()


def test_tool_without_reliable_parent_exports_run_fallback() -> None:
    """来源没有给出父级模型调用时，导出侧同样显式降级到 Run 根并标记来源。"""
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    try:
        exporter = _build_exporter(receiver.endpoint)
        fallback_span_id = derive_span_id(_RUN_ID, "tool", "source_tool_2")
        # 追加一个没有 parent_model_call_id 的工具调用，模拟来源能力不足；它必须
        # 排在终态事件之前，因为终态之后 canonical 事件不再被接受。
        for committed_event in [
            *_committed_events()[:-1],
            _event(
                8,
                "tool.call.started",
                {"tool_call_id": "tool_2", "tool_name": "lookup_rate", "arguments": {}},
                span_id=fallback_span_id,
                offset_seconds=5,
            ),
            _event(
                9,
                "tool.call.completed",
                {"tool_call_id": "tool_2", "result": "ok", "result_checksum": "f" * 64},
                span_id=fallback_span_id,
                offset_seconds=6,
            ),
            _event(
                10,
                "run.completed",
                {"message_id": "message_1"},
                span_id=_ROOT_SPAN_ID,
                offset_seconds=7,
            ),
        ]:
            exporter.record_committed_event(committed_event)
        exporter.shutdown()

        fallback_span = next(
            span for span in receiver.collect_spans() if span.span_id.hex() == fallback_span_id
        )
        assert fallback_span.parent_span_id.hex() == _ROOT_SPAN_ID
        fallback_attributes = {
            attribute.key: attribute.value for attribute in fallback_span.attributes
        }
        assert fallback_attributes["run.tool.parent_source"].string_value == "run_fallback"
    finally:
        receiver_iterator.close()


def test_endpoint_failure_is_isolated_from_the_caller() -> None:
    """endpoint 拒绝连接时导出静默失败，不向执行侧抛出。"""
    # 取一个已关闭端口：先绑定再关闭，保证端口当前无人监听。
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    closed_endpoint = receiver.endpoint
    receiver_iterator.close()

    exporter = _build_exporter(f"{closed_endpoint}/traces")
    for committed_event in _committed_events():
        exporter.record_committed_event(committed_event)

    # 关闭时会 flush 并失败；必须只记录日志，不抛异常。
    exporter.shutdown()


def test_unconfigured_endpoint_does_not_assemble_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    """变量为空或只有空白时不装配 exporter，也不产生任何请求。"""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    assert ObservabilitySettings(otlp_endpoint="").otlp_export_enabled is False
    assert ObservabilitySettings(otlp_endpoint="   ").otlp_export_enabled is False
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4318/x")
    configured_settings = ObservabilitySettings()
    assert configured_settings.otlp_export_enabled is True


def test_settings_read_traces_specific_env_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """traces 专用变量优先于宽作用域地址，且原样使用。"""
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://arms.example.com/otel/traces")
    assert ObservabilitySettings().otlp_traces_endpoint == "http://arms.example.com/otel/traces"


def test_general_endpoint_accepts_its_field_name_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    """通用地址必须同时接受字段名，否则 config.toml 的 ``[observability]`` 会被静默忽略。

    配置文件的 section source 与构造参数都按**字段名**传值，只声明 ``validation_alias`` 会让
    这两个通道直接失效——所以这里断言的是字段名通道本身，而不是环境变量通道。
    """
    # settings 模块在导入期就把 .env / .env.local 合并进 os.environ，因此必须先清掉环境变量，
    # 否则环境源会盖过构造参数，观察不到字段名通道的行为。
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", raising=False)
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)

    by_field_name = ObservabilitySettings(otlp_base_endpoint="http://base.example:4318")
    assert by_field_name.otlp_base_endpoint == "http://base.example:4318"
    # 走通用地址时同样要按解析规则补上 signal 路径。
    assert by_field_name.otlp_traces_endpoint == "http://base.example:4318/v1/traces"

    # 对照：traces 专用字段名本来就支持，两个字段的行为必须一致。
    by_traces_field_name = ObservabilitySettings(otlp_endpoint="http://traces.example/x")
    assert by_traces_field_name.otlp_base_endpoint == ""
    assert by_traces_field_name.otlp_traces_endpoint == "http://traces.example/x"


def test_default_test_run_does_not_assemble_an_exporter() -> None:
    """默认测试运行不得向外部 OTLP 接收端发送轨迹：本进程内的配置单例必须处于关闭态。

    这是 ``tests/conftest.py`` 的 ``_disable_otlp_trace_export`` 的守卫。删掉那个 autouse
    fixture 后，``.env.local`` 里的 ``OTEL_EXPORTER_OTLP_ENDPOINT`` 会让本用例变红；否则
    「测试不外发」只是一个无法失败的说法（导出失败被设计成静默，其他用例不会因此变红）。
    """
    observability = config.observability
    assert observability.otlp_endpoint == ""
    assert observability.otlp_base_endpoint == ""
    assert observability.otlp_export_enabled is False


@pytest.mark.parametrize(
    ("configured_endpoint", "expected_path"),
    [
        ("/adapt_tenant/api/otlp/traces", "/adapt_tenant/api/otlp/traces"),
        ("/v1/traces", "/v1/traces"),
        ("", "/v1/traces"),
        ("/collector", "/collector/v1/traces"),
    ],
)
def test_general_endpoint_resolves_and_exports_traces(
    monkeypatch: pytest.MonkeyPatch,
    configured_endpoint: str,
    expected_path: str,
) -> None:
    """通用变量同时支持完整 Trace 地址与 OTLP 基础地址。"""
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    try:
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "")
        monkeypatch.setenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT", f"{receiver.endpoint}{configured_endpoint}"
        )
        configured_settings = ObservabilitySettings()
        assert configured_settings.otlp_export_enabled is True
        exporter = _build_exporter(configured_settings.otlp_traces_endpoint)
        for committed_event in _committed_events():
            exporter.record_committed_event(committed_event)
        exporter.shutdown()
        assert [request.path for request in receiver.requests] == [expected_path]
    finally:
        receiver_iterator.close()


def test_tool_parent_uses_recorded_model_span_id_not_a_recomputed_one() -> None:
    """工具父级走已落库的模型 span ID，而不是重新派生：两者分叉时不得挂错。"""
    receiver_iterator = _start_receiver()
    receiver = next(receiver_iterator)
    try:
        exporter = _build_exporter(receiver.endpoint)
        explicit_model_span_id = "a1b2c3d4e5f60718"
        assert explicit_model_span_id != _MODEL_SPAN_ID
        explicit_tool_span_id = "0f1e2d3c4b5a6978"
        for committed_event in [
            _event(1, "run.created", _run_created_payload(), span_id=_ROOT_SPAN_ID),
            _event(2, "run.started", {"started_at": _BASE_TIME.isoformat()}, span_id=_ROOT_SPAN_ID),
            _event(
                3,
                "model.call.started",
                {"model_call_id": "call_1", "model_name": "qwen3.8-max", "turn_index": 0},
                span_id=explicit_model_span_id,
            ),
            _event(
                4,
                "tool.call.started",
                {
                    "tool_call_id": "tool_1",
                    "tool_name": "read_attachment",
                    "arguments": {},
                    "parent_model_call_id": "call_1",
                },
                span_id=explicit_tool_span_id,
            ),
            _event(
                5,
                "tool.call.completed",
                {"tool_call_id": "tool_1", "result": "ok", "result_checksum": "e" * 64},
                span_id=explicit_tool_span_id,
            ),
            _event(
                6,
                "model.call.completed",
                {
                    "model_call_id": "call_1",
                    "model_name": "qwen3.8-max",
                    "turn_index": 0,
                    "usage": {"total": 10},
                    "finish_reason": "stop",
                },
                span_id=explicit_model_span_id,
            ),
            _event(
                7,
                "run.completed",
                {"message_id": "message_1"},
                span_id=_ROOT_SPAN_ID,
            ),
        ]:
            exporter.record_committed_event(committed_event)
        exporter.shutdown()

        spans_by_id = {span.span_id.hex(): span for span in receiver.collect_spans()}
        assert explicit_model_span_id in spans_by_id
        assert explicit_tool_span_id in spans_by_id
        tool_span = spans_by_id[explicit_tool_span_id]
        assert tool_span.parent_span_id.hex() == explicit_model_span_id
        tool_attributes = {attribute.key: attribute.value for attribute in tool_span.attributes}
        assert tool_attributes["run.tool.parent_source"].string_value == "model_call"
    finally:
        receiver_iterator.close()


class _CapturingSpanExporter(SpanExporter):
    """捕获导出 span 的内存 exporter。"""

    def __init__(self) -> None:
        """初始化捕获列表。"""
        self.exported_spans: list[Any] = []

    def export(self, spans: Any) -> SpanExportResult:
        """记录一批 span。"""
        self.exported_spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """无需释放资源。"""


def test_events_without_a_call_id_are_not_exported() -> None:
    """没有调用 ID 的模型/工具事件两边都丢弃，云端不得出现本地树没有的节点。"""
    capturing_exporter = _CapturingSpanExporter()
    exporter = RunOtlpExporter(
        endpoint="http://collector.invalid/traces",
        service_name="template-backend-test",
        service_version="0.1.0",
        deployment_environment="test",
        timeout_seconds=2.0,
        batch_size=64,
        schedule_delay_ms=10,
        span_exporter=capturing_exporter,
    )
    for committed_event in [
        _event(1, "run.created", _run_created_payload(), span_id=_ROOT_SPAN_ID),
        _event(2, "run.started", {"started_at": _BASE_TIME.isoformat()}, span_id=_ROOT_SPAN_ID),
        _event(
            3,
            "model.call.started",
            {"model_call_id": "", "model_name": "m", "turn_index": 0},
            span_id=None,
        ),
        _event(
            4,
            "tool.call.started",
            {"tool_call_id": "", "tool_name": "lookup_rate", "arguments": {}},
            span_id=None,
        ),
        _event(5, "run.completed", {"message_id": "message_1"}, span_id=_ROOT_SPAN_ID),
    ]:
        exporter.record_committed_event(committed_event)
    exporter.shutdown()

    assert [span.name for span in capturing_exporter.exported_spans] == ["run"]
