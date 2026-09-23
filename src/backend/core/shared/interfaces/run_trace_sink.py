"""Canonical Run 事件的只读导出端口。

导出是 Run 执行的可选旁路：实现必须 best-effort，任何失败都不得回滚事件、改变
Run 终态或向调用方抛出。
"""

from __future__ import annotations

from typing import Protocol

from backend.core.shared.models.run import RunEvent


class RunTraceSink(Protocol):
    """已提交 canonical 事件的外部投影出口。"""

    def record_committed_event(self, event: RunEvent) -> None:
        """把一条已提交事件投影到外部系统。

        Args:
            event (RunEvent): 已提交的事件 envelope（含 trace/span ID）。
        """
        ...
