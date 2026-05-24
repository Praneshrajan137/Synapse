"""DPDPA right-to-erasure cascade (Sprint 9 §M-life-3, ADR-035).

DPDPA Article 12 requires that when a data subject exercises erasure,
their identifiers must be purged across every store SYNAPSE holds them
in. Sprint 7's Postgres `synapse_erasure_operator` role already gates
the DB-level DELETE; Sprint 9 cascades the erasure across:

  - Postgres (audit_decisions DELETE via the privileged operator),
  - Neo4j (city-filtered MATCH/DELETE per E-S6-05),
  - Feast online store (Redis HDEL on the per-city DB index),
  - Kafka (null-value tombstone on synapse.audit.log keyed by subject).

This module is the **single call site** the runtime erasure operator
uses (or a tests/compliance harness in CI). Each backend call is wrapped
in try/except so a partial failure surfaces the per-store outcome
without aborting the entire cascade. The caller can retry the failed
backends independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class CascadeResult:
    """Outcome of one erasure cascade across all backends."""

    subject_id: str
    cities: list[str]
    postgres_rows_deleted: int = 0
    neo4j_nodes_deleted: int = 0
    feast_keys_deleted: int = 0
    kafka_tombstones_emitted: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures


def cascade_erasure(
    subject_id: str,
    cities: list[str],
    *,
    pg_session: Any | None = None,
    neo4j_driver: Any | None = None,
    feast_redis: dict[str, Any] | None = None,
    kafka_producer: Any | None = None,
) -> CascadeResult:
    """Run the DPDPA erasure cascade for ``subject_id`` across ``cities``.

    Each backend argument is optional — when ``None`` the cascade skips
    that store and reports the gap in ``CascadeResult.failures``. The
    runtime erasure operator wires all four; the compliance test wires
    them via mocks.
    """
    result = CascadeResult(subject_id=subject_id, cities=list(cities))

    # ----- Postgres ---------------------------------------------------------
    if pg_session is None:
        result.failures.append("postgres: no session provided")
    else:
        try:
            count = _erase_postgres(pg_session, subject_id)
            result.postgres_rows_deleted = count
        except Exception as exc:  # noqa: BLE001
            result.failures.append(f"postgres: {exc}")
            logger.error("dpdpa_cascade_postgres_failed", subject=subject_id, error=str(exc))

    # ----- Neo4j (per-city) -------------------------------------------------
    if neo4j_driver is None:
        result.failures.append("neo4j: no driver provided")
    else:
        try:
            for city in cities:
                count = _erase_neo4j_city(neo4j_driver, subject_id, city)
                result.neo4j_nodes_deleted += count
        except Exception as exc:  # noqa: BLE001
            result.failures.append(f"neo4j: {exc}")
            logger.error("dpdpa_cascade_neo4j_failed", subject=subject_id, error=str(exc))

    # ----- Feast online (per-city Redis index) ------------------------------
    if feast_redis is None:
        result.failures.append("feast: no redis clients provided")
    else:
        for city in cities:
            client = feast_redis.get(city)
            if client is None:
                result.failures.append(f"feast: no client for city={city}")
                continue
            try:
                deleted = _erase_feast_city(client, subject_id, city)
                result.feast_keys_deleted += deleted
            except Exception as exc:  # noqa: BLE001
                result.failures.append(f"feast[{city}]: {exc}")

    # ----- Kafka tombstone --------------------------------------------------
    if kafka_producer is None:
        result.failures.append("kafka: no producer provided")
    else:
        try:
            count = _emit_tombstone(kafka_producer, subject_id, cities)
            result.kafka_tombstones_emitted = count
        except Exception as exc:  # noqa: BLE001
            result.failures.append(f"kafka: {exc}")

    logger.info(
        "dpdpa_cascade_complete",
        subject=subject_id,
        cities=cities,
        ok=result.ok,
        failures=result.failures,
        postgres=result.postgres_rows_deleted,
        neo4j=result.neo4j_nodes_deleted,
        feast=result.feast_keys_deleted,
        kafka=result.kafka_tombstones_emitted,
    )
    return result


# ----- backend helpers -----------------------------------------------------


def _erase_postgres(session: Any, subject_id: str) -> int:
    """Delete audit_decisions rows where customer_id = subject_id.

    Uses the privileged ``synapse_erasure_operator`` role (Sprint 5 grant);
    the runtime operator must pass a session created with that role.
    """
    from sqlalchemy import text

    stmt = text("DELETE FROM audit_decisions WHERE selected_action::jsonb ->> 'customer_id' = :sid")
    result = session.execute(stmt, {"sid": subject_id})
    session.commit()
    return int(result.rowcount or 0)


def _erase_neo4j_city(driver: Any, subject_id: str, city: str) -> int:
    """City-filtered MATCH/DELETE per E-S6-05."""
    query = "MATCH (n {customer_id: $sid, city: $city}) DETACH DELETE n RETURN count(n) AS deleted"
    with driver.session() as sess:
        record = sess.run(query, sid=subject_id, city=city).single()
        return int(record["deleted"]) if record else 0


def _erase_feast_city(client: Any, subject_id: str, city: str) -> int:
    """HDEL all Feast online entries keyed by subject_id."""
    pattern = f"synapse:{city}:feast:{subject_id}:*"
    keys = list(client.scan_iter(match=pattern))
    if not keys:
        return 0
    return int(client.delete(*keys))


def _emit_tombstone(producer: Any, subject_id: str, cities: list[str]) -> int:
    """Emit a null-value record on synapse.audit.log keyed by subject_id.

    Kafka compaction will drop earlier records for the same key, completing
    the erasure on the audit topic without losing chain integrity (chain
    operates on rows, not on Kafka events).
    """
    count = 0
    for city in cities:
        key = f"{city}:{subject_id}".encode()
        producer.produce(topic="synapse.audit.log", value=None, key=key.decode("utf-8"))
        count += 1
    producer.flush(timeout=5.0)
    return count
