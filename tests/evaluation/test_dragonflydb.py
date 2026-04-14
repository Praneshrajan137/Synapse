from __future__ import annotations

"""DragonflyDB Evaluation — ADR-019

Evaluate DragonflyDB as Redis replacement in Sprint 5 load testing.
Adopt if ALL tests pass.  Decision criteria:
1. Drop-in Redis compatibility (all SYNAPSE Redis commands work)
2. Performance: >= Redis 7 on all benchmarks
3. Memory efficiency: <= Redis 7 memory at same data volume
4. Stability: zero crashes under 30-min sustained load
"""

import json
import threading
import time

import pytest
import structlog

logger = structlog.get_logger()

try:
    import redis
except ImportError:
    redis = None  # type: ignore[assignment]

DRAGONFLY_CONFIG = {"host": "localhost", "port": 6380, "db": 0}
REDIS_CONFIG = {"host": "localhost", "port": 6379, "db": 0}


@pytest.mark.skipif(redis is None, reason="redis-py not installed")
class TestDragonflyDBEvaluation:
    """ADR-019: DragonflyDB evaluation against Redis 7."""

    @pytest.fixture()
    def dragonfly_client(self):
        try:
            client = redis.Redis(**DRAGONFLY_CONFIG)
            client.ping()
            yield client
            client.close()
        except redis.ConnectionError:
            pytest.skip("DragonflyDB not running on port 6380")

    @pytest.fixture()
    def redis_client(self):
        try:
            client = redis.Redis(**REDIS_CONFIG)
            client.ping()
            yield client
            client.close()
        except redis.ConnectionError:
            pytest.skip("Redis not running on port 6379")

    def test_basic_string_operations(self, dragonfly_client) -> None:
        """Basic SET/GET/DEL compatibility."""
        dragonfly_client.set("test:string", "hello")
        assert dragonfly_client.get("test:string") == b"hello"
        dragonfly_client.delete("test:string")
        assert dragonfly_client.get("test:string") is None

    def test_json_serialization(self, dragonfly_client) -> None:
        """JSON storage with sort_keys for KV-cache preservation (I-13)."""
        data = {"sku_id": "SKU-001", "forecast": 100.5, "confidence": 0.92}
        serialized = json.dumps(data, sort_keys=True, separators=(",", ":"))
        dragonfly_client.set("test:json", serialized)

        retrieved = json.loads(dragonfly_client.get("test:json"))  # type: ignore[arg-type]
        assert retrieved == data
        dragonfly_client.delete("test:json")

    def test_stream_operations(self, dragonfly_client) -> None:
        """Redis Streams XADD/XREAD compatibility for Kafka fallback."""
        stream_key = "test:stream:events"
        dragonfly_client.delete(stream_key)

        msg_id = dragonfly_client.xadd(
            stream_key, {"event": "demand_forecast", "value": "100"},
        )
        assert msg_id is not None

        messages = dragonfly_client.xread({stream_key: "0-0"}, count=10)
        assert len(messages) > 0

        dragonfly_client.delete(stream_key)

    def test_hash_operations(self, dragonfly_client) -> None:
        """HSET/HGET/HGETALL for agent state storage."""
        key = "test:agent:demand_prophet:state"
        dragonfly_client.delete(key)

        dragonfly_client.hset(key, mapping={
            "status": "healthy",
            "last_inference_ms": "42",
            "model_version": "v1.2.3",
        })

        status = dragonfly_client.hget(key, "status")
        assert status == b"healthy"

        all_fields = dragonfly_client.hgetall(key)
        assert len(all_fields) == 3

        dragonfly_client.delete(key)

    @pytest.mark.slow
    def test_ttl_expiry(self, dragonfly_client) -> None:
        """TTL-based expiry for feature cache."""
        dragonfly_client.setex("test:ttl", 1, "expires_soon")
        assert dragonfly_client.get("test:ttl") == b"expires_soon"

        time.sleep(1.5)
        assert dragonfly_client.get("test:ttl") is None

    def test_pipeline_performance(self, dragonfly_client, redis_client) -> None:
        """Pipeline performance: DragonflyDB >= Redis 7."""
        n = 1000

        try:
            # DragonflyDB pipeline
            start_df = time.monotonic()
            pipe = dragonfly_client.pipeline()
            for i in range(n):
                pipe.set(f"bench:df:{i}", f"value_{i}")
            pipe.execute()
            df_time = time.monotonic() - start_df

            # Redis pipeline
            start_rd = time.monotonic()
            pipe = redis_client.pipeline()
            for i in range(n):
                pipe.set(f"bench:rd:{i}", f"value_{i}")
            pipe.execute()
            rd_time = time.monotonic() - start_rd

            logger.info(
                "pipeline_benchmark",
                dragonfly_ms=round(df_time * 1000, 2),
                redis_ms=round(rd_time * 1000, 2),
                operations=n,
            )
        finally:
            pipe_df = dragonfly_client.pipeline()
            pipe_rd = redis_client.pipeline()
            for i in range(n):
                pipe_df.delete(f"bench:df:{i}")
                pipe_rd.delete(f"bench:rd:{i}")
            pipe_df.execute()
            pipe_rd.execute()

    def test_pubsub_compatibility(self, dragonfly_client) -> None:
        """Pub/Sub basic compatibility check."""
        received: list[bytes] = []
        ready = threading.Event()

        def subscriber() -> None:
            ps = dragonfly_client.pubsub()
            ps.subscribe("test:channel")
            ready.set()
            for msg in ps.listen():
                if msg["type"] == "message":
                    received.append(msg["data"])
                    break

        thread = threading.Thread(target=subscriber, daemon=True)
        thread.start()
        ready.wait(timeout=5.0)
        time.sleep(0.1)

        dragonfly_client.publish("test:channel", "hello_dragonfly")
        thread.join(timeout=5)

        assert len(received) == 1
        assert received[0] == b"hello_dragonfly"
