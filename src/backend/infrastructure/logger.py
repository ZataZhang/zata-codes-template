"""Application logging configuration.

Supports both plain text and structured JSON output. JSON mode is intended
for container runtimes where Docker's logging driver forwards stdout to a
log aggregator (e.g. Vector -> Loki). Text mode remains the default for local
development.
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
    """Inject contextual IDs from ``contextvars`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get() or ""  # type: ignore[attr-defined]
        record.trace_id = trace_id_var.get() or ""  # type: ignore[attr-defined]
        record.span_id = span_id_var.get() or ""  # type: ignore[attr-defined]
        return True


class _TextFormatter(logging.Formatter):
    """Human-readable text formatter used for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt=(
                "%(asctime)s - %(name)s - %(levelname)s - "
                "%(filename)s:%(lineno)d - %(message)s"
            ),
            datefmt="%Y-%m-%d %H:%M:%S",
        )


class _JsonFormatter(jsonlogger.JsonFormatter):
    """JSON formatter intended for log aggregation pipelines.

    The field list is intentionally platform-agnostic: any backend that can
    consume JSON logs (Vector/Loki, Fluentd/Elasticsearch, Datadog, Splunk)
    will be able to parse these fields.
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

        # Remove empty contextual fields to keep log records compact.
        for key in ("request_id", "trace_id", "span_id"):
            if not log_record.get(key):
                log_record.pop(key, None)

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:  # noqa: N802
        return logging.Formatter.formatTime(self, record, datefmt)


class Logger:
    """Singleton logger manager."""

    _instance: "Logger | None" = None
    _logger: logging.Logger | None = None

    def __new__(cls) -> "Logger":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
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
        """Return the underlying ``logging.Logger`` instance.

        Returns:
            logging.Logger: The configured logger instance.
        """
        if self._logger is None:
            self._setup_logger()
        return self._logger

    def __getattr__(self, name: str) -> Any:
        if self._logger is None:
            self._setup_logger()
        return getattr(self._logger, name)


logger = Logger()

__all__ = [
    "Logger",
    "logger",
]
