from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
import structlog
import structlog.testing

logger = structlog.get_logger()

pytestmark = pytest.mark.chaos


class KafkaHealthChecker:
    """Detects Kafka partition failures and triggers Redis fallback."""

    HEARTBEAT_TIMEOUT_SECONDS = 10.0
    MAX_CONSUMER_LAG_MS = 5000

    def __init__(self) -> None:
        self.kafka_healthy: bool = True
        self.redis_fallback_active: bool = False
        self.last_heartbeat: float = time.monotonic()
        self.consumer_lag_ms: float = 0.0

    def receive_heartbeat(self) -> None:
        self.last_heartbeat = time.monotonic()
        self.kafka_healthy = True

    def check_health(self) -> dict:
        elapsed = time.monotonic() - self.last_heartbeat

        if elapsed > self.HEARTBEAT_TIMEOUT_SECONDS:
            self.kafka_healthy = False
            self.redis_fallback_active = True
            logger.warning(
                "kafka_heartbeat_timeout",
                elapsed_seconds=elapsed,
                action="activate_redis_fallback",
            )
            return {
                "kafka_healthy": False,
                "fallback": "redis_streams",
                "reason": "heartbeat_timeout",
            }

        if self.consumer_lag_ms > self.MAX_CONSUMER_LAG_MS:
            logger.warning(
                "kafka_consumer_lag_high",
                lag_ms=self.consumer_lag_ms,
                threshold_ms=self.MAX_CONSUMER_LAG_MS,
            )
            return {
                "kafka_healthy": True,
                "fallback": None,
                "warning": "high_consumer_lag",
            }

        return {"kafka_healthy": True, "fallback": None}

    def update_consumer_lag(self, lag_ms: float) -> None:
        self.consumer_lag_ms = lag_ms


class RedisFallbackProducer:
    """Produces messages to Redis Streams when Kafka is unavailable."""

    def __init__(self, redis_client: AsyncMock) -> None:
        self.redis = redis_client
        self.messages_produced: int = 0

    async def produce(self, stream: str, message: dict) -> str:
        msg_id = await self.redis.xadd(
            stream,
            {"data": json.dumps(message, sort_keys=True, separators=(",", ":"))},
        )
        self.messages_produced += 1
        return msg_id


class TestKafkaFailure:
    """Chaos logic validation: Kafka broker killed mid-stream. Auto rebalance
    with Redis Streams fallback. Recovery SLA: <30 seconds."""

    def test_heartbeat_timeout_triggers_fallback(self, chaos_clock) -> None:
        """Missing heartbeat beyond threshold activates Redis fallback."""
        checker = KafkaHealthChecker()
        checker.receive_heartbeat()
        checker.last_heartbeat = time.monotonic() - 15.0

        chaos_clock.start()
        with structlog.testing.capture_logs() as captured:
            result = checker.check_health()

        assert result["kafka_healthy"] is False
        assert result["fallback"] == "redis_streams"
        assert checker.redis_fallback_active is True
        chaos_clock.assert_within_sla(30.0, "Kafka failure detection")
        assert any(e.get("event") == "kafka_heartbeat_timeout" for e in captured)

    def test_high_consumer_lag_warning(self) -> None:
        """High consumer lag generates warning but not full fallback."""
        checker = KafkaHealthChecker()
        checker.receive_heartbeat()
        checker.update_consumer_lag(6000.0)

        result = checker.check_health()

        assert result["kafka_healthy"] is True
        assert result.get("warning") == "high_consumer_lag"

    @pytest.mark.asyncio
    async def test_redis_fallback_produces_messages(self, chaos_redis_client) -> None:
        """Redis fallback produces messages when Kafka is down."""
        chaos_redis_client.xadd = AsyncMock(return_value="1234-0")
        fallback = RedisFallbackProducer(chaos_redis_client)

        msg_id = await fallback.produce(
            "synapse.demand.forecast",
            {"sku_id": "SKU-001", "forecast": 100.0},
        )

        assert msg_id == "1234-0"
        assert fallback.messages_produced == 1
        chaos_redis_client.xadd.assert_called_once()

    def test_healthy_kafka_no_fallback(self) -> None:
        """Healthy Kafka with recent heartbeat triggers no fallback."""
        checker = KafkaHealthChecker()
        checker.receive_heartbeat()

        result = checker.check_health()

        assert result["kafka_healthy"] is True
        assert result["fallback"] is None

    def test_fallback_after_recovery_still_flagged(self) -> None:
        """Once redis_fallback_active is set it stays until explicit reset."""
        checker = KafkaHealthChecker()
        checker.last_heartbeat = time.monotonic() - 15.0
        checker.check_health()

        assert checker.redis_fallback_active is True

        checker.receive_heartbeat()
        checker.check_health()

        assert checker.redis_fallback_active is True
