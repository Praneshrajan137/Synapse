"""Tests for structured logging configuration."""
from __future__ import annotations

import logging

import pytest
import structlog

from synapse_common.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _clean_root_logger() -> None:  # type: ignore[misc]
    """Remove handlers added by configure_logging to avoid cross-test pollution."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    yield  # type: ignore[misc]
    root.handlers = original_handlers
    root.setLevel(original_level)


class TestConfigureLogging:

    def test_console_renderer(self) -> None:
        configure_logging(level="DEBUG", json_output=False)
        root = logging.getLogger()
        assert root.level == logging.DEBUG
        assert len(root.handlers) >= 1

    def test_json_renderer(self) -> None:
        configure_logging(level="WARNING", json_output=True)
        root = logging.getLogger()
        assert root.level == logging.WARNING
        assert len(root.handlers) >= 1

    def test_structlog_configured(self) -> None:
        configure_logging()
        log = structlog.get_logger("test")
        assert log is not None
