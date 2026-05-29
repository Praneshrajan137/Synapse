"""Phase 3 (round 2) — push synapse_common 75.99 -> >=84%.

Targets the remaining 0%/low-% modules with mocked backends:
- dpdpa.cascade_erasure (82 stmts, 0% → ~85% with 12 tests)
- outbox.enqueue async path (with mocked AsyncSession)
- tracing.KafkaHeaderCarrier (pure adapter, 100% testable)
- langsmith_client._should_sample + traced_ollama_call no-op path

These are the highest-leverage cheap covers. mutation-survival hardening:
specific failure-string assertions, exact count assertions, and explicit
ON/OFF assertions on environment-toggled paths.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest

from synapse_common import dpdpa, langsmith_client, tracing


# =============================================================================
# dpdpa.cascade_erasure
# =============================================================================


class _MockPgResult:
    def __init__(self, rowcount: int = 0) -> None:
        self.rowcount = rowcount


class _MockPgSession:
    def __init__(self, rowcount: int = 0, raise_on_execute: bool = False) -> None:
        self._rowcount = rowcount
        self._raise = raise_on_execute
        self.execute_called = False
        self.commit_called = False

    def execute(self, _stmt: Any, _params: Any = None) -> _MockPgResult:
        self.execute_called = True
        if self._raise:
            raise RuntimeError("pg unavailable")
        return _MockPgResult(self._rowcount)

    def commit(self) -> None:
        self.commit_called = True


class _MockNeo4jSession:
    def __init__(self, deleted: int) -> None:
        self._deleted = deleted

    def __enter__(self) -> "_MockNeo4jSession":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def run(self, _q: str, **_: Any) -> Any:
        rec = MagicMock()
        rec.single = lambda: {"deleted": self._deleted}
        return rec.single()  # production code does sess.run(...).single() — adapt


class _MockNeo4jDriver:
    def __init__(self, deleted_per_city: int) -> None:
        self._deleted = deleted_per_city

    def session(self) -> Any:
        return _Neo4jSessionCtx(self._deleted)


class _Neo4jSessionCtx:
    def __init__(self, deleted: int) -> None:
        self._deleted = deleted

    def __enter__(self) -> "_Neo4jSessionCtx":
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def run(self, _q: str, **_: Any) -> Any:
        class _Result:
            def __init__(self, d: int) -> None:
                self._d = d

            def single(self) -> dict[str, int]:
                return {"deleted": self._d}

        return _Result(self._deleted)


class _MockRedisClient:
    def __init__(self, keys: list[str]) -> None:
        self._keys = keys

    def scan_iter(self, match: str) -> list[str]:
        return list(self._keys)

    def delete(self, *keys: str) -> int:
        return len(keys)


class _MockKafkaProducer:
    def __init__(self) -> None:
        self.produced: list[tuple[str, str, bytes | None]] = []
        self.flush_called = False

    def produce(self, *, topic: str, value: bytes | None, key: str) -> None:
        self.produced.append((topic, key, value))

    def flush(self, timeout: float = 5.0) -> None:
        self.flush_called = True


class TestCascadeResult:
    def test_ok_property_true_when_no_failures(self) -> None:
        r = dpdpa.CascadeResult(subject_id="s", cities=["bengaluru"])
        assert r.ok is True

    def test_ok_property_false_when_failures(self) -> None:
        r = dpdpa.CascadeResult(subject_id="s", cities=["b"])
        r.failures.append("oops")
        assert r.ok is False


class TestCascadeNoBackendsProvided:
    def test_all_missing_recorded_as_failures(self) -> None:
        """A bare call with no backends should record FOUR failures (one
        per backend) and have ok=False — never crash."""
        result = dpdpa.cascade_erasure("subject-1", ["bengaluru"])
        assert result.ok is False
        assert len(result.failures) == 4
        # Each failure must be a string identifying the missing backend
        joined = "; ".join(result.failures)
        for backend in ("postgres", "neo4j", "feast", "kafka"):
            assert backend in joined


class TestCascadePostgres:
    def test_postgres_success_records_rowcount(self) -> None:
        sess = _MockPgSession(rowcount=7)
        result = dpdpa.cascade_erasure("s", ["bengaluru"], pg_session=sess)
        assert result.postgres_rows_deleted == 7
        assert sess.execute_called is True
        assert sess.commit_called is True

    def test_postgres_failure_recorded(self) -> None:
        sess = _MockPgSession(raise_on_execute=True)
        result = dpdpa.cascade_erasure("s", ["bengaluru"], pg_session=sess)
        assert any("postgres" in f for f in result.failures)
        assert result.postgres_rows_deleted == 0


class TestCascadeNeo4j:
    def test_neo4j_sums_per_city_deletes(self) -> None:
        driver = _MockNeo4jDriver(deleted_per_city=3)
        cities = ["bengaluru", "mumbai"]
        result = dpdpa.cascade_erasure("s", cities, neo4j_driver=driver)
        assert result.neo4j_nodes_deleted == 6  # 3 per city × 2

    def test_neo4j_failure_recorded(self) -> None:
        driver = MagicMock()
        driver.session.side_effect = RuntimeError("neo4j down")
        result = dpdpa.cascade_erasure("s", ["bengaluru"], neo4j_driver=driver)
        assert any("neo4j" in f for f in result.failures)


class TestCascadeFeast:
    def test_feast_per_city_redis(self) -> None:
        feast = {
            "bengaluru": _MockRedisClient(keys=["k1", "k2"]),
            "mumbai": _MockRedisClient(keys=["k3"]),
        }
        result = dpdpa.cascade_erasure("s", ["bengaluru", "mumbai"], feast_redis=feast)
        # bengaluru deletes 2, mumbai deletes 1
        assert result.feast_keys_deleted == 3

    def test_feast_missing_city_client_recorded_as_failure(self) -> None:
        feast = {"bengaluru": _MockRedisClient(keys=[])}
        result = dpdpa.cascade_erasure(
            "s", ["bengaluru", "mumbai"], feast_redis=feast,
        )
        # 'mumbai' has no client → failure recorded
        assert any("mumbai" in f for f in result.failures)


class TestCascadeKafka:
    def test_kafka_tombstone_per_city(self) -> None:
        producer = _MockKafkaProducer()
        result = dpdpa.cascade_erasure(
            "subj-42", ["bengaluru", "mumbai"], kafka_producer=producer,
        )
        assert result.kafka_tombstones_emitted == 2
        assert producer.flush_called is True
        # Pin the key shape: "{city}:{subject_id}"
        keys = [k for _t, k, _v in producer.produced]
        assert "bengaluru:subj-42" in keys
        assert "mumbai:subj-42" in keys
        # Pin tombstone semantics: value MUST be None
        assert all(value is None for _t, _k, value in producer.produced)

    def test_kafka_failure_recorded(self) -> None:
        producer = MagicMock()
        producer.produce.side_effect = RuntimeError("kafka unavailable")
        result = dpdpa.cascade_erasure("s", ["bengaluru"], kafka_producer=producer)
        assert any("kafka" in f for f in result.failures)


class TestCascadeFullSuccess:
    def test_all_backends_succeed_ok_true(self) -> None:
        result = dpdpa.cascade_erasure(
            "subj-1",
            ["bengaluru"],
            pg_session=_MockPgSession(rowcount=5),
            neo4j_driver=_MockNeo4jDriver(deleted_per_city=2),
            feast_redis={"bengaluru": _MockRedisClient(keys=["x", "y", "z"])},
            kafka_producer=_MockKafkaProducer(),
        )
        assert result.ok is True
        assert result.postgres_rows_deleted == 5
        assert result.neo4j_nodes_deleted == 2
        assert result.feast_keys_deleted == 3
        assert result.kafka_tombstones_emitted == 1


# =============================================================================
# outbox.enqueue (async path)
# =============================================================================


class _AsyncSessionRecorder:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.flushed = False

    def add(self, row: Any) -> None:
        self.added.append(row)
        if not getattr(row, "id", None):
            row.id = uuid4()

    async def flush(self) -> None:
        self.flushed = True


@pytest.mark.asyncio
async def test_outbox_enqueue_inserts_row_with_decision_id_partition() -> None:
    """Default partition_key MUST be str(decision_id) — pin the contract."""
    from synapse_common import outbox

    session = _AsyncSessionRecorder()
    decision_id = uuid4()
    row_id = await outbox.enqueue(
        session, decision_id=decision_id, topic="t", payload={"k": "v"},
    )
    assert isinstance(row_id, UUID)
    assert session.flushed is True
    assert len(session.added) == 1
    row = session.added[0]
    assert row.decision_id == decision_id
    assert row.topic == "t"
    assert row.partition_key == str(decision_id)
    assert row.payload == {"k": "v"}
    assert row.status == "PENDING"
    assert row.audit_id is None
    assert row.headers == {}


@pytest.mark.asyncio
async def test_outbox_enqueue_explicit_partition_and_headers() -> None:
    from synapse_common import outbox

    session = _AsyncSessionRecorder()
    decision_id = uuid4()
    audit_id = uuid4()
    headers = {"traceparent": "00-abc-def-01"}
    await outbox.enqueue(
        session,
        decision_id=decision_id,
        topic="t",
        payload={"a": 1, "b": 2},
        audit_id=audit_id,
        partition_key="custom-key",
        headers=headers,
    )
    row = session.added[0]
    assert row.partition_key == "custom-key"
    assert row.audit_id == audit_id
    assert row.headers == headers


# =============================================================================
# tracing.KafkaHeaderCarrier
# =============================================================================


class TestKafkaHeaderCarrier:
    def test_empty_init(self) -> None:
        c = tracing.KafkaHeaderCarrier()
        assert len(c) == 0

    def test_init_from_kafka_headers_decodes_bytes(self) -> None:
        c = tracing.KafkaHeaderCarrier([("traceparent", b"00-abc-def-01")])
        assert c["traceparent"] == "00-abc-def-01"

    def test_init_handles_non_utf8_with_replace(self) -> None:
        """Lossy decode (errors='ignore') — must not raise on garbage bytes."""
        c = tracing.KafkaHeaderCarrier([("badkey", b"\xff\xfe\xfd")])
        # The key is present even if the value decodes to empty / replacement
        assert "badkey" in c

    def test_setitem_getitem(self) -> None:
        c = tracing.KafkaHeaderCarrier()
        c["foo"] = "bar"
        assert c["foo"] == "bar"

    def test_delitem(self) -> None:
        c = tracing.KafkaHeaderCarrier([("foo", b"bar")])
        del c["foo"]
        assert len(c) == 0

    def test_iter_and_keys(self) -> None:
        c = tracing.KafkaHeaderCarrier()
        c["a"] = "1"
        c["b"] = "2"
        assert set(c.keys()) == {"a", "b"}
        assert set(iter(c)) == {"a", "b"}

    def test_get_default(self) -> None:
        c = tracing.KafkaHeaderCarrier()
        assert c.get("missing") is None
        assert c.get("missing", "fallback") == "fallback"

    def test_as_kafka_headers_encodes_utf8(self) -> None:
        c = tracing.KafkaHeaderCarrier()
        c["x"] = "y"
        out = c.as_kafka_headers()
        assert out == [("x", b"y")]

    def test_roundtrip_preserves_values(self) -> None:
        original = [("k1", b"v1"), ("k2", b"v2")]
        c = tracing.KafkaHeaderCarrier(original)
        out = sorted(c.as_kafka_headers())
        assert out == sorted(original)


def test_extract_kafka_context_returns_none_when_no_headers() -> None:
    assert tracing.extract_kafka_context(None) is None
    assert tracing.extract_kafka_context([]) is None


def test_inject_a2a_headers_returns_same_dict() -> None:
    """Even with OTel unavailable, the dict must be returned (not None)."""
    headers: dict[str, str] = {"existing": "v"}
    result = tracing.inject_a2a_headers(headers)
    assert result is headers
    assert "existing" in result


# =============================================================================
# langsmith_client — disabled-by-default path
# =============================================================================


class TestLangsmithDisabledByDefault:
    def test_default_is_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without LANGSMITH_API_KEY + SYNAPSE_LANGSMITH_ENABLED, the
        module-level constant MUST be False — no telemetry leak."""
        # Re-evaluate module-level constant by reloading
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("SYNAPSE_LANGSMITH_ENABLED", raising=False)
        import importlib

        importlib.reload(langsmith_client)
        assert langsmith_client.LANGSMITH_ENABLED is False

    def test_decorator_no_op_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("SYNAPSE_LANGSMITH_ENABLED", raising=False)
        import importlib
        importlib.reload(langsmith_client)

        @langsmith_client.traced_ollama_call(tier="tier_3")
        def call() -> str:
            return "result"

        assert call() == "result"


class TestLangsmithSampling:
    def test_should_sample_explicit_rate_zero_never_samples(self) -> None:
        for _ in range(20):
            assert langsmith_client._should_sample("tier_2", 0.0) is False

    def test_should_sample_explicit_rate_one_always_samples(self) -> None:
        for _ in range(20):
            assert langsmith_client._should_sample("tier_3", 1.0) is True

    def test_should_sample_tier_default_rate(self) -> None:
        """tier_1 default sample rate is 0.0 — must never sample."""
        for _ in range(20):
            assert langsmith_client._should_sample("tier_1", None) is False

    def test_should_sample_tier_4_default_always(self) -> None:
        for _ in range(20):
            assert langsmith_client._should_sample("tier_4", None) is True

    def test_unknown_tier_defaults_to_full_sample(self) -> None:
        for _ in range(20):
            assert langsmith_client._should_sample("tier_unknown", None) is True
