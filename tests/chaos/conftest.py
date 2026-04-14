from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog

logger = structlog.get_logger()


class ChaosTestClock:
    """Deterministic clock for chaos test timing assertions."""

    def __init__(self) -> None:
        self._start: float | None = None

    def start(self) -> None:
        self._start = time.monotonic()

    def elapsed_seconds(self) -> float:
        if self._start is None:
            return 0.0
        return time.monotonic() - self._start

    def assert_within_sla(self, max_seconds: float, failure_mode: str) -> None:
        elapsed = self.elapsed_seconds()
        assert elapsed <= max_seconds, (
            f"SLA VIOLATION: {failure_mode} recovery took {elapsed:.2f}s, "
            f"max allowed {max_seconds}s"
        )


@pytest.fixture()
def chaos_clock() -> ChaosTestClock:
    return ChaosTestClock()


@pytest.fixture()
def chaos_kafka_producer() -> AsyncMock:
    producer = AsyncMock()
    producer.produce = AsyncMock()
    producer.flush = MagicMock()
    return producer


@pytest.fixture()
def chaos_feast_client() -> AsyncMock:
    client = AsyncMock()
    client.get_online_features = AsyncMock()
    return client


@pytest.fixture()
def chaos_ollama_client() -> AsyncMock:
    client = AsyncMock()
    client.generate = AsyncMock()
    client.chat = AsyncMock()
    return client


@pytest.fixture()
def chaos_redis_client() -> AsyncMock:
    client = AsyncMock()
    client.xadd = AsyncMock()
    client.xread = AsyncMock(return_value=[])
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock()
    return client
