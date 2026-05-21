"""ETL lineage — OpenLineage-style events to the Postgres audit ledger.

ADR-026: SYNAPSE keeps the 16-topic Kafka freeze (I-6), so lineage cannot mint
a 17th topic. Instead each ETL run emits a `LineageEvent` row into the audit
ledger and stamps the active OpenTelemetry span with `synapse.lineage.run_id`.

Events follow the OpenLineage 1.0 schema (subset): `run`, `job`, `inputs`,
`outputs`, `eventType` ∈ {START, COMPLETE, FAIL}.

Persistence is best-effort and degrades open if Postgres is unreachable: a
WARN log is written but the ETL is not blocked. Lineage is observability,
not a synchronous gate (which is what `quality_gates.py` is for).
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Dataset:
    namespace: str
    name: str


@dataclass
class LineageEvent:
    """OpenLineage-1.0 event subset."""

    run_id: str
    job_name: str
    event_type: str  # START | COMPLETE | FAIL
    inputs: list[dict[str, str]] = field(default_factory=list)
    outputs: list[dict[str, str]] = field(default_factory=list)
    facets: dict[str, Any] = field(default_factory=dict)
    event_time: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat().replace("+00:00", "Z")
    )

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def new_run_id() -> str:
    return str(uuid.uuid4())


def emit(event: LineageEvent) -> None:
    """Persist a lineage event. Best-effort: Postgres outage degrades to WARN log."""
    _annotate_otel(event)
    _persist(event)


def _annotate_otel(event: LineageEvent) -> None:
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is not None and span.is_recording():
            span.set_attribute("synapse.lineage.run_id", event.run_id)
            span.set_attribute("synapse.lineage.job", event.job_name)
            span.set_attribute("synapse.lineage.event_type", event.event_type)
    except Exception as exc:  # noqa: BLE001 — observability never crashes the caller
        logger.debug("lineage_otel_skip", error=str(exc))


def _persist(event: LineageEvent) -> None:
    """Insert into a `lineage_events` table on the audit ledger.

    Schema lives in `infrastructure/postgres/migrations/002_lineage_events.sql`.
    """
    dsn = os.environ.get(
        "POSTGRES_DSN",
        "postgresql://synapse:synapse_audit_2026@postgres:5432/synapse_audit",
    )
    try:
        import psycopg2

        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO lineage_events
                        (run_id, job_name, event_type, event_time, inputs, outputs, facets)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
                    """,
                    (
                        event.run_id,
                        event.job_name,
                        event.event_type,
                        event.event_time,
                        json.dumps(event.inputs, sort_keys=True),
                        json.dumps(event.outputs, sort_keys=True),
                        json.dumps(event.facets, sort_keys=True),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning(
            "lineage_persist_failed",
            error=str(exc),
            run_id=event.run_id,
            job=event.job_name,
        )


__all__ = [
    "Dataset",
    "LineageEvent",
    "emit",
    "new_run_id",
]
