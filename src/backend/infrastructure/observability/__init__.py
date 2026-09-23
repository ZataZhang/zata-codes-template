"""基础设施层可观测性实现。

当前提供 Run 执行轨迹的可选 OTLP 导出出口；OpenTelemetry SDK 属于可选依赖，
仅在装配时按需导入。
"""

from __future__ import annotations

from backend.infrastructure.observability.run_otlp_exporter import (
    RunOtlpExporter,
    RunTracingUnavailableError,
    build_run_tracing_sink,
)

__all__ = [
    "RunOtlpExporter",
    "RunTracingUnavailableError",
    "build_run_tracing_sink",
]
