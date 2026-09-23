"""Canonical Run 轨迹到 OTLP 的 best-effort 投影。

只消费已提交事件的 trace/span ID：导出的每个 span 都用 canonical envelope 上的
显式 SpanContext 构造，父子关系也来自事件里已裁决的父 span，因此云端 trace 与本地
诊断树逐节点一致，不会生成第二套 ID。

OpenTelemetry SDK 是**可选依赖**：本模块只在装配时按需导入，未安装时由
:func:`build_run_tracing_sink` 降级为不装配，本地诊断完全不受影响。地址为空时也
不装配；导出超时、被拒绝、队列满或关停 flush 失败都只记录受控日志，绝不回滚事件、
改变 Run 终态或向调用方抛出。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from backend.core.shared.models.run import (
    RunEvent,
    derive_root_span_id,
    derive_span_id,
)
from backend.infrastructure.config.settings import RunTracingSettings
from backend.infrastructure.logger import logger

_INSTRUMENTATION_NAME = "backend.run_tracing"

_SPAN_NAME_RUN = "run"
_SPAN_NAME_MODEL = "gen_ai.chat"
_SPAN_NAME_TOOL = "execute_tool"

_ATTR_RUN_ID = "run.id"
_ATTR_RUN_STATUS = "run.status"
_ATTR_SUBJECT_ID = "run.subject.id"
_ATTR_OPERATION_NAME = "gen_ai.operation.name"
_ATTR_REQUEST_MODEL = "gen_ai.request.model"
_ATTR_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
_ATTR_INPUT_TOKENS = "gen_ai.usage.input_tokens"
_ATTR_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
_ATTR_TURN_INDEX = "run.model.turn_index"
_ATTR_MODEL_CALL_ID = "run.model.call_id"
_ATTR_TOOL_NAME = "gen_ai.tool.name"
_ATTR_TOOL_CALL_ID = "gen_ai.tool.call.id"
_ATTR_TOOL_PARENT_SOURCE = "run.tool.parent_source"
_ATTR_ERROR_CODE = "run.error.code"

_TOOL_PARENT_SOURCE_MODEL_CALL = "model_call"
_TOOL_PARENT_SOURCE_RUN_FALLBACK = "run_fallback"

_TERMINAL_EVENT_TYPES = frozenset(
    {"run.completed", "run.failed", "run.cancelled", "run.interrupted"}
)


class RunTracingUnavailableError(RuntimeError):
    """OpenTelemetry SDK 未安装，无法装配 OTLP 导出。"""


@dataclass(frozen=True)
class _OtelBindings:
    """惰性加载后的 OpenTelemetry 符号集合。"""

    otlp_span_exporter_cls: Any
    resource_cls: Any
    tracer_provider_cls: Any
    batch_span_processor_cls: Any
    instrumentation_scope_cls: Any
    span_context_cls: Any
    span_kind: Any
    status_cls: Any
    status_code: Any
    trace_flags_cls: Any
    canonical_span_cls: Any


_otel_bindings: _OtelBindings | None = None


def _load_otel_bindings() -> _OtelBindings:
    """按需导入 OpenTelemetry SDK 并缓存符号。

    导入放在函数体内是刻意的：模板的依赖守卫只扫描模块级 import，这样
    ``opentelemetry`` 才能保持可选依赖，未安装的派生项目不会在导入期失败。

    Returns:
        _OtelBindings: 装配 OTLP exporter 所需的 SDK 符号。

    Raises:
        RunTracingUnavailableError: 未安装 OpenTelemetry SDK 时抛出。
    """
    global _otel_bindings
    if _otel_bindings is not None:
        return _otel_bindings
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import Span, TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.util.instrumentation import InstrumentationScope
        from opentelemetry.trace import (
            SpanContext,
            SpanKind,
            Status,
            StatusCode,
            TraceFlags,
        )
    except ImportError as import_error:
        raise RunTracingUnavailableError(
            "未安装 OpenTelemetry SDK，无法装配 OTLP 导出；"
            "请安装可选依赖：uv sync --extra tracing。"
        ) from import_error

    class _CanonicalSpan(Span):
        """允许用显式 canonical SpanContext 构造的 SDK span。

        ``Tracer`` 只会给 span 生成自己的新 ID，而本投影必须沿用已提交事件里的
        trace/span ID 才能与本地诊断树对齐，因此直接构造 SDK span 并传入固定 context。
        """

        def __new__(cls, *args: object, **kwargs: object) -> _CanonicalSpan:
            """绕过 SDK 对直接构造基类 ``Span`` 的保护。"""
            return object.__new__(cls)

    _otel_bindings = _OtelBindings(
        otlp_span_exporter_cls=OTLPSpanExporter,
        resource_cls=Resource,
        tracer_provider_cls=TracerProvider,
        batch_span_processor_cls=BatchSpanProcessor,
        instrumentation_scope_cls=InstrumentationScope,
        span_context_cls=SpanContext,
        span_kind=SpanKind,
        status_cls=Status,
        status_code=StatusCode,
        trace_flags_cls=TraceFlags,
        canonical_span_cls=_CanonicalSpan,
    )
    return _otel_bindings


class RunOtlpExporter:
    """把 canonical 事件按同一 trace/span ID 投影成 OTLP span。"""

    def __init__(
        self,
        *,
        endpoint: str,
        service_name: str,
        service_version: str,
        deployment_environment: str,
        timeout_seconds: float,
        batch_size: int,
        schedule_delay_ms: int,
        span_exporter: Any | None = None,
    ) -> None:
        """装配 OTLP/HTTP trace exporter。

        调用方传入的 ``endpoint`` 是已解析完成的最终 Trace URL，按原样使用，
        不再追加 signal 路径，也不解析或拼装任何鉴权信息。

        Args:
            endpoint (str): 已解析的最终 Trace URL。
            service_name (str): 服务标识，写入 resource attributes。
            service_version (str): 服务版本，写入 resource attributes。
            deployment_environment (str): 部署环境，写入 resource attributes。
            timeout_seconds (float): 单次导出的网络超时。
            batch_size (int): 批量导出的单批 span 上限。
            schedule_delay_ms (int): 批量导出的调度间隔。
            span_exporter (Any | None): 测试可注入的协议级 exporter。

        Raises:
            RunTracingUnavailableError: 未安装 OpenTelemetry SDK 时抛出。
        """
        bindings = _load_otel_bindings()
        self._bindings = bindings
        self._endpoint = endpoint
        # 同一 Run 的父子 span 与 context 需要跨事件保持；Run 终结后立即释放，避免
        # 长驻进程里按 Run 无限累积。
        self._open_spans: dict[str, dict[str, Any]] = {}
        self._span_contexts: dict[str, dict[str, Any]] = {}
        # 根 span ID 与子节点自己的 span ID 不同，必须单独记住，否则子节点会去
        # 查自己的 ID 当作根，导致导出的父子关系丢失。
        self._root_span_ids: dict[str, str] = {}
        # 模型调用 ID → 实际落库的模型 span ID。工具父级必须走这张表，不能用
        # derive_span_id 重新算一遍：那样在来源改过 span 派生规则时会与本地投影分叉。
        self._model_span_ids_by_call_id: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()
        self._resource = bindings.resource_cls.create(
            {
                "service.name": service_name,
                "service.version": service_version,
                "deployment.environment": deployment_environment,
            }
        )
        self._span_exporter = span_exporter or bindings.otlp_span_exporter_cls(
            endpoint=endpoint,
            timeout=timeout_seconds,
        )
        # 先建 processor 再交给 provider：span 构造需要直接持有它，provider 负责
        # 关停时的 flush 生命周期。
        self._span_processor = bindings.batch_span_processor_cls(
            self._span_exporter,
            max_export_batch_size=batch_size,
            schedule_delay_millis=schedule_delay_ms,
        )
        self._tracer_provider = bindings.tracer_provider_cls(resource=self._resource)
        self._tracer_provider.add_span_processor(self._span_processor)
        self._instrumentation_scope = bindings.instrumentation_scope_cls(_INSTRUMENTATION_NAME)

    @property
    def endpoint(self) -> str:
        """返回本次装配使用的完整 Trace URL。"""
        return self._endpoint

    def record_committed_event(self, event: RunEvent) -> None:
        """把一条已提交事件投影成 OTLP span 或 span 事件。

        永不向调用方抛出：Run 的持久化与终态不受外部导出可用性影响。

        Args:
            event (RunEvent): 已提交的事件 envelope。
        """
        try:
            self._project_event(event)
        except Exception as export_error:  # noqa: BLE001 - 导出故障必须与 Run 隔离
            logger.warning(
                "run trace export skipped run_id=%s event_type=%s error=%s",
                event.run_id,
                event.event_type,
                export_error,
            )

    def shutdown(self) -> None:
        """冲刷并关闭 exporter；失败只记录日志。"""
        try:
            with self._lock:
                for run_spans in self._open_spans.values():
                    for open_span in run_spans.values():
                        open_span.end()
                self._open_spans.clear()
                self._span_contexts.clear()
                self._root_span_ids.clear()
                self._model_span_ids_by_call_id.clear()
            self._tracer_provider.shutdown()
        except Exception as export_error:  # noqa: BLE001 - 关停失败不得阻断应用退出
            logger.warning("run trace export shutdown failed error=%s", export_error)

    def _project_event(self, event: RunEvent) -> None:
        """按事件类型投影 span 生命周期。"""
        with self._lock:
            if event.event_type in {"run.created", "run.started"}:
                self._start_root_span(event)
            elif event.event_type == "model.call.started":
                self._start_model_span(event)
            elif event.event_type in {"model.call.completed", "model.call.failed"}:
                self._end_span(event)
            elif event.event_type == "tool.call.started":
                self._start_tool_span(event)
            elif event.event_type in {"tool.call.completed", "tool.call.failed"}:
                self._end_span(event)
            elif event.event_type == "artifact.created":
                self._record_artifact_event(event)
            elif event.event_type in _TERMINAL_EVENT_TYPES:
                self._finish_run(event)

    def _start_root_span(self, event: RunEvent) -> None:
        """开启 Run 根 span，已存在时只补属性。"""
        canonical_span_id = event.span_id or derive_root_span_id(event.run_id)
        self._root_span_ids[event.run_id] = canonical_span_id
        if canonical_span_id in self._open_spans.get(event.run_id, {}):
            return
        self._build_span(
            event=event,
            span_name=_SPAN_NAME_RUN,
            canonical_span_id=canonical_span_id,
            parent_context=None,
            attributes={
                _ATTR_RUN_ID: event.run_id,
                _ATTR_SUBJECT_ID: event.subject_id,
                _ATTR_RUN_STATUS: "running",
            },
        )

    def _start_model_span(self, event: RunEvent) -> None:
        """开启模型 span，父级固定为 Run 根。"""
        model_call_id = str(event.payload.get("model_call_id") or "")
        if not model_call_id:
            # 与本地投影保持一致：没有调用 ID 就没有可关联的节点，两边都丢弃，
            # 避免云端出现本地树里没有的 span。
            self._warn_dropped_event(event, "missing model_call_id")
            return
        attributes: dict[str, object] = {
            _ATTR_RUN_ID: event.run_id,
            _ATTR_OPERATION_NAME: "chat",
            _ATTR_REQUEST_MODEL: str(event.payload.get("model_name") or "unknown"),
            _ATTR_MODEL_CALL_ID: model_call_id,
        }
        turn_index = event.payload.get("turn_index")
        if _is_plain_int(turn_index):
            attributes[_ATTR_TURN_INDEX] = turn_index
        self._build_span(
            event=event,
            span_name=_SPAN_NAME_MODEL,
            canonical_span_id=event.span_id or derive_span_id(event.run_id, "model", model_call_id),
            parent_context=self._root_context(event),
            attributes=attributes,
        )

    def _start_tool_span(self, event: RunEvent) -> None:
        """开启工具 span：父级只认来源声明的模型调用，否则挂 Run 根。"""
        if not str(event.payload.get("tool_call_id") or ""):
            # 同上：本地投影也会丢弃，导出侧不得单独造出一个节点。
            self._warn_dropped_event(event, "missing tool_call_id")
            return
        parent_model_call_id = str(event.payload.get("parent_model_call_id") or "")
        parent_context = None
        parent_source = _TOOL_PARENT_SOURCE_RUN_FALLBACK
        if parent_model_call_id:
            recorded_model_span_id = self._model_span_ids_by_call_id.get(event.run_id, {}).get(
                parent_model_call_id
            )
            model_span_context = (
                self._span_contexts.get(event.run_id, {}).get(recorded_model_span_id)
                if recorded_model_span_id is not None
                else None
            )
            if model_span_context is not None:
                parent_context = model_span_context
                parent_source = _TOOL_PARENT_SOURCE_MODEL_CALL
        if parent_context is None:
            parent_context = self._root_context(event)
        self._build_span(
            event=event,
            span_name=_SPAN_NAME_TOOL,
            canonical_span_id=event.span_id
            or derive_span_id(event.run_id, "tool", str(event.payload.get("tool_call_id") or "")),
            parent_context=parent_context,
            attributes={
                _ATTR_RUN_ID: event.run_id,
                _ATTR_OPERATION_NAME: "execute_tool",
                _ATTR_TOOL_NAME: str(event.payload.get("tool_name") or "unknown"),
                _ATTR_TOOL_CALL_ID: str(event.payload.get("tool_call_id") or ""),
                _ATTR_TOOL_PARENT_SOURCE: parent_source,
            },
        )

    def _build_span(
        self,
        *,
        event: RunEvent,
        span_name: str,
        canonical_span_id: str,
        parent_context: Any | None,
        attributes: dict[str, object],
    ) -> None:
        """用 canonical trace/span ID 构造一个 SDK span 并登记其 context。"""
        if canonical_span_id in self._open_spans.setdefault(event.run_id, {}):
            return
        bindings = self._bindings
        canonical_span = bindings.canonical_span_cls(
            name=span_name,
            context=bindings.span_context_cls(
                trace_id=int(event.trace_id or "", 16),
                span_id=int(canonical_span_id, 16),
                is_remote=False,
                trace_flags=bindings.trace_flags_cls(bindings.trace_flags_cls.SAMPLED),
            ),
            parent=parent_context,
            kind=bindings.span_kind.INTERNAL,
            resource=self._resource,
            attributes=attributes,
            span_processor=self._span_processor,
            instrumentation_scope=self._instrumentation_scope,
        )
        self._open_spans[event.run_id][canonical_span_id] = canonical_span
        self._span_contexts.setdefault(event.run_id, {})[canonical_span_id] = (
            canonical_span.get_span_context()
        )
        if span_name == _SPAN_NAME_MODEL:
            model_call_id = str(event.payload.get("model_call_id") or "")
            if model_call_id:
                self._model_span_ids_by_call_id.setdefault(event.run_id, {})[model_call_id] = (
                    canonical_span_id
                )
        # 用 canonical 事件的发生时间作为 span 端点，云端时长与本地诊断一致。
        canonical_span.start(start_time=_to_unix_nano(event.occurred_at))

    def _record_artifact_event(self, event: RunEvent) -> None:
        """把产物作为根 span 上的事件记录，不额外制造 span。"""
        root_span = self._open_spans.get(event.run_id, {}).get(self._root_span_id(event))
        if root_span is None or not root_span.is_recording():
            return
        root_span.add_event("artifact.created")

    def _finish_run(self, event: RunEvent) -> None:
        """写入 Run 终态、收尾所有未结束 span 并释放该 Run 的状态。"""
        run_spans = self._open_spans.get(event.run_id, {})
        root_span = run_spans.get(self._root_span_id(event))
        if root_span is not None:
            root_span.set_attribute(_ATTR_RUN_STATUS, event.event_type.removeprefix("run."))
        terminal_nano = _to_unix_nano(event.occurred_at)
        for open_span in run_spans.values():
            if open_span is root_span:
                continue
            # 终态时仍在执行的步骤按中断收尾，避免云端留下永不结束的 span。
            open_span.set_attribute(_ATTR_RUN_STATUS, "interrupted")
            open_span.end(end_time=terminal_nano)
        if root_span is not None:
            if event.event_type == "run.failed":
                root_span.set_status(
                    self._bindings.status_cls(self._bindings.status_code.ERROR, "run_failed")
                )
            root_span.end(end_time=terminal_nano)
        self._open_spans.pop(event.run_id, None)
        self._span_contexts.pop(event.run_id, None)
        self._root_span_ids.pop(event.run_id, None)
        self._model_span_ids_by_call_id.pop(event.run_id, None)

    def _end_span(self, event: RunEvent) -> None:
        """结束一个模型或工具 span，并写入低敏 attributes。"""
        run_spans = self._open_spans.get(event.run_id, {})
        open_span = run_spans.pop(event.span_id or "", None)
        if open_span is None:
            return
        if event.event_type == "model.call.completed":
            usage = event.payload.get("usage")
            if isinstance(usage, dict):
                prompt_count = usage.get("prompt")
                completion_count = usage.get("completion")
                if _is_plain_int(prompt_count):
                    open_span.set_attribute(_ATTR_INPUT_TOKENS, prompt_count)
                if _is_plain_int(completion_count):
                    open_span.set_attribute(_ATTR_OUTPUT_TOKENS, completion_count)
            finish_reason = event.payload.get("finish_reason")
            if finish_reason:
                open_span.set_attribute(_ATTR_RESPONSE_FINISH_REASONS, [str(finish_reason)])
        elif event.event_type in {"model.call.failed", "tool.call.failed"}:
            error_code = ""
            error_payload = event.payload.get("error")
            if isinstance(error_payload, dict):
                error_code = str(error_payload.get("code") or "")
            open_span.set_attribute(_ATTR_ERROR_CODE, error_code or "failed")
            open_span.set_status(
                self._bindings.status_cls(self._bindings.status_code.ERROR, error_code or "failed")
            )
        open_span.end(end_time=_to_unix_nano(event.occurred_at))

    @staticmethod
    def _warn_dropped_event(event: RunEvent, reason: str) -> None:
        """记录一次被丢弃的 tracing 事件，避免静默与本地树分叉。"""
        logger.warning(
            "run trace export skipped run_id=%s event_type=%s reason=%s",
            event.run_id,
            event.event_type,
            reason,
        )

    def _root_span_id(self, event: RunEvent) -> str:
        """返回该 Run 已登记的根 span ID。"""
        return self._root_span_ids.get(event.run_id) or derive_root_span_id(event.run_id)

    def _root_context(self, event: RunEvent) -> Any | None:
        """返回该 Run 根 span 的 context；根尚未开启时返回空。"""
        return self._span_contexts.get(event.run_id, {}).get(self._root_span_id(event))


def build_run_tracing_sink(settings: RunTracingSettings) -> RunOtlpExporter | None:
    """按配置装配 OTLP 导出出口；未启用或缺依赖时返回 ``None``。

    Args:
        settings (RunTracingSettings): 由 :func:`load_run_tracing_settings` 解析的配置。

    Returns:
        RunOtlpExporter | None: 已装配的导出出口；未配置 endpoint 或未安装
        OpenTelemetry SDK 时返回 ``None``，Run 与本地诊断不受影响。
    """
    if not settings.enabled:
        return None
    try:
        return RunOtlpExporter(
            endpoint=settings.endpoint,
            service_name=settings.service_name,
            service_version=settings.service_version,
            deployment_environment=settings.deployment_environment,
            timeout_seconds=settings.timeout_seconds,
            batch_size=settings.batch_size,
            schedule_delay_ms=settings.schedule_delay_ms,
        )
    except RunTracingUnavailableError as unavailable_error:
        logger.warning("run tracing exporter 未装配：%s", unavailable_error)
        return None


def _is_plain_int(value: object) -> bool:
    """判断是否为非布尔整数。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _to_unix_nano(moment: datetime) -> int:
    """把事件时间转换为 OpenTelemetry 使用的纳秒时间戳。"""
    return int(moment.timestamp() * 1_000_000_000)


__all__ = [
    "RunOtlpExporter",
    "RunTracingUnavailableError",
    "build_run_tracing_sink",
]
