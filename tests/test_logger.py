"""Tests for logger configuration."""

from __future__ import annotations

import json
import logging
from logging.handlers import TimedRotatingFileHandler

import pytest
from pythonjsonlogger.json import JsonFormatter

from backend.infrastructure.config.settings import config
from backend.infrastructure.logger import Logger


def _reset_logger_singleton() -> None:
    """Reset the logger singleton so each test sees a fresh instance."""
    Logger._instance = None  # type: ignore[assignment]
    Logger._logger = None  # type: ignore[assignment]
    # Also clear the underlying stdlib logger handlers because Python caches
    # loggers by name across Logger singleton resets.
    underlying_logger = logging.getLogger(config.app_name)
    underlying_logger.handlers.clear()
    # alembic's env.py calls fileConfig(disable_existing_loggers=True), which
    # leaves previously-created loggers in a disabled state. Re-enable so the
    # JSON log capture test can still emit through the singleton.
    underlying_logger.disabled = False


@pytest.fixture(autouse=True)
def reset_logger_singleton() -> None:
    _reset_logger_singleton()
    yield
    _reset_logger_singleton()


def test_logger_uses_timed_rotating_file_handler() -> None:
    logger_instance = Logger().get_logger()
    handler_types = {type(handler) for handler in logger_instance.handlers}
    assert TimedRotatingFileHandler in handler_types


def test_timed_rotating_file_handler_suffix_set() -> None:
    logger_instance = Logger().get_logger()
    rotating_handlers = [
        handler
        for handler in logger_instance.handlers
        if isinstance(handler, TimedRotatingFileHandler)
    ]
    assert rotating_handlers, "TimedRotatingFileHandler is not configured."
    assert rotating_handlers[0].suffix == "%Y-%m-%d"


def test_default_formatter_is_text() -> None:
    logger_instance = Logger().get_logger()
    console_handlers = [
        handler
        for handler in logger_instance.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert console_handlers
    assert not isinstance(console_handlers[0].formatter, JsonFormatter)


def test_json_formatter_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.observability, "log_format", "json")
    _reset_logger_singleton()
    logger_instance = Logger().get_logger()
    console_handlers = [
        handler
        for handler in logger_instance.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert console_handlers
    assert isinstance(console_handlers[0].formatter, JsonFormatter)


def test_json_log_contains_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that JSON mode emits the expected structured fields."""
    import io

    monkeypatch.setattr(config.observability, "log_format", "json")
    _reset_logger_singleton()

    output = io.StringIO()
    logger_instance = Logger().get_logger()
    console_handlers = [
        handler
        for handler in logger_instance.handlers
        if isinstance(handler, logging.StreamHandler)
    ]
    assert console_handlers
    console_handlers[0].setStream(output)
    logger_instance.propagate = False

    test_message = "observability test log"
    logger_instance.info(test_message)

    log_line = output.getvalue().strip()
    assert log_line
    log_record = json.loads(log_line)

    assert log_record["message"] == test_message
    assert log_record["level"] == "INFO"
    assert log_record["service_name"] == config.observability.service_name
    assert log_record["service_version"] == config.observability.service_version
    assert log_record["deployment_environment"] == config.observability.deployment_environment
    assert "timestamp" in log_record
    assert "source_file" in log_record
    assert "source_line" in log_record
