"""Run 执行轨迹子系统装配。

把 Run repository、诊断用例与可选的 OTLP 导出出口组装成冻结组件集合。trace_sink
是可选旁路：配置了 Trace URL 且安装了 OpenTelemetry SDK 时才非空，任何情况下都
不影响本地诊断与 Run 终态。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.core.run_tracing import RunTraceUseCase
from backend.core.shared.interfaces.run_repository import RunRepository
from backend.core.shared.interfaces.run_trace_sink import RunTraceSink
from backend.infrastructure.config.settings import load_run_tracing_settings
from backend.infrastructure.observability import build_run_tracing_sink
from backend.infrastructure.persistence.repos.run_repo import SqlAlchemyRunRepository


@dataclass(frozen=True)
class RunTracingComponents:
    """Run 执行轨迹装配结果。

    Attributes:
        run_repository (RunRepository): Run/Event 事务仓库。
        run_trace_use_case (RunTraceUseCase): admin 诊断投影用例。
        trace_sink (RunTraceSink | None): 可选外部导出出口；未配置时为 ``None``。
    """

    run_repository: RunRepository
    run_trace_use_case: RunTraceUseCase
    trace_sink: RunTraceSink | None


def build_run_tracing_components(session_factory: Any) -> RunTracingComponents:
    """创建 Run 执行轨迹组件。

    Args:
        session_factory: SQLAlchemy 会话工厂；Run repository 每个操作使用独立短事务。

    Returns:
        RunTracingComponents: 装配好的仓库、用例与可选导出出口。
    """
    run_repository = SqlAlchemyRunRepository(session_factory)
    trace_sink = build_run_tracing_sink(load_run_tracing_settings())
    return RunTracingComponents(
        run_repository=run_repository,
        run_trace_use_case=RunTraceUseCase(run_repository),
        trace_sink=trace_sink,
    )


__all__ = ["RunTracingComponents", "build_run_tracing_components"]
