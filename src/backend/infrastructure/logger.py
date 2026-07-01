"""应用日志配置。

支持纯文本与结构化 JSON 两种输出。JSON 模式面向容器运行时，由 Docker
日志驱动将标准输出转发到日志聚合器（如 Vector -> Loki）；本地开发默认使用
文本模式。
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Any

from pythonjsonlogger import json as jsonlogger

from backend.infrastructure.config.settings import config
from backend.shared.context import request_id_var, span_id_var, trace_id_var


class _ContextFilter(logging.Filter):
    """将 ``contextvars`` 中的上下文 ID 注入每条日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or ""  # type: ignore[attr-defined]
        record.trace_id = trace_id_var.get() or ""  # type: ignore[attr-defined]
        record.span_id = span_id_var.get() or ""  # type: ignore[attr-defined]
        return True


class _TextFormatter(logging.Formatter):
    """本地开发使用的人类可读文本格式化器。"""

    def __init__(self) -> None:
        super().__init__(
            fmt=("%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"),
            datefmt="%Y-%m-%d %H:%M:%S",
        )


class _JsonFormatter(jsonlogger.JsonFormatter):
    """面向日志聚合管道的 JSON 格式化器。

    字段列表故意保持平台无关，任何能消费 JSON 日志的后端（Vector/Loki、
    Fluentd/Elasticsearch、Datadog、Splunk）都能解析这些字段。
    """

    def __init__(self) -> None:
        observability = config.observability
        super().__init__(
            fmt="%(timestamp)s %(levelname)s %(name)s %(message)s",
            rename_fields={
                "levelname": "level",
                "name": "logger",
            },
            static_fields={
                "service_name": observability.service_name,
                "service_version": observability.service_version,
                "deployment_environment": observability.deployment_environment,
            },
        )

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        super().add_fields(log_record, record, message_dict)
        log_record["timestamp"] = self.formatTime(record)
        log_record["source_file"] = record.filename
        log_record["source_line"] = record.lineno
        log_record["request_id"] = getattr(record, "request_id", "")
        log_record["trace_id"] = getattr(record, "trace_id", "")
        log_record["span_id"] = getattr(record, "span_id", "")

        # 移除空的上下文字段，保持日志记录紧凑。
        for key in ("request_id", "trace_id", "span_id"):
            if not log_record.get(key):
                log_record.pop(key, None)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        return logging.Formatter.formatTime(self, record, datefmt)


class Logger:
    """单例日志管理器。"""

    _instance: "Logger | None" = None
    _logger: logging.Logger | None = None

    def __new__(cls) -> "Logger":
        """创建或返回单例日志管理器实例。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """首次使用时初始化单例日志记录器。"""
        if self._logger is None:
            self._setup_logger()

    def _create_formatter(self) -> logging.Formatter:
        if config.observability.log_format.lower() == "json":
            return _JsonFormatter()
        return _TextFormatter()

    def _setup_logger(self) -> None:
        self._logger = logging.getLogger(config.app_name)
        self._logger.setLevel(getattr(logging, config.log_level))

        if self._logger.handlers:
            return

        formatter = self._create_formatter()
        context_filter = _ContextFilter()

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, config.log_level))
        console_handler.setFormatter(formatter)
        console_handler.addFilter(context_filter)
        if hasattr(console_handler.stream, "reconfigure"):
            try:
                console_handler.stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        self._logger.addHandler(console_handler)

        try:
            file_handler = TimedRotatingFileHandler(
                filename=str(config.log_file),
                when="midnight",
                interval=1,
                backupCount=14,
                encoding="utf-8",
                utc=False,
            )
            file_handler.suffix = "%Y-%m-%d"
            file_handler.setLevel(getattr(logging, config.log_level))
            file_handler.setFormatter(formatter)
            file_handler.addFilter(context_filter)
            self._logger.addHandler(file_handler)
        except (OSError, PermissionError) as error:
            print(f"Warning: 无法创建日志文件处理器: {error}")

    def get_logger(self) -> logging.Logger:
        """返回底层的 ``logging.Logger`` 实例。

        Returns:
            logging.Logger: 已配置的日志记录器实例。
        """
        if self._logger is None:
            self._setup_logger()
        return self._logger

    def __getattr__(self, name: str) -> Any:
        """将属性访问委托给底层日志记录器。"""
        if self._logger is None:
            self._setup_logger()
        return getattr(self._logger, name)


logger = Logger()

__all__ = [
    "Logger",
    "logger",
]
