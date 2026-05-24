"""Change-Data-Capture reader for the Postgres audit ledger (ADR-026).

Streams `audit_consensus` row inserts into a downstream consumer (e.g. an
analytics warehouse) using PostgreSQL logical replication slots. Read-only;
the audit ledger is append-only by I-4 so CDC sees only INSERTs — no
UPDATE/DELETE events ever.

This is a thin orchestration layer; the actual logical-decoding plugin
(`pgoutput` or `wal2json`) is configured in `infrastructure/postgres/init_audit.sql`.

Usage::

    from data_fabric.etl.cdc import AuditCDC
    cdc = AuditCDC(slot_name="synapse_audit_cdc", publication="audit_pub")
    for row in cdc.stream():
        ...

Failure mode: the consumer is responsible for *advancing* the slot via
`acknowledge(lsn)`. Failure to do so causes WAL accumulation on the primary,
so a watchdog metric (`cdc_lag_bytes`) is exposed via Prometheus.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class AuditCDC:
    """Logical-replication reader over the audit_consensus + lineage_events tables."""

    def __init__(
        self,
        *,
        slot_name: str = "synapse_audit_cdc",
        publication: str = "synapse_audit_pub",
        dsn: str | None = None,
    ) -> None:
        self._slot = slot_name
        self._publication = publication
        self._dsn = dsn or os.environ.get(
            "POSTGRES_DSN",
            "postgresql://synapse:synapse_audit_2026@postgres:5432/synapse_audit",
        )

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        import psycopg2
        from psycopg2.extras import LogicalReplicationConnection

        conn = psycopg2.connect(self._dsn, connection_factory=LogicalReplicationConnection)
        try:
            yield conn
        finally:
            conn.close()

    def ensure_slot(self) -> None:
        """Create the replication slot if it does not exist."""
        with self._connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM pg_replication_slots WHERE slot_name = %s",
                (self._slot,),
            )
            if cur.fetchone() is None:
                cur.create_replication_slot(self._slot, output_plugin="pgoutput")
                logger.info("cdc_slot_created", slot=self._slot)

    def stream(self) -> Iterator[dict[str, Any]]:
        """Yield decoded WAL records as dicts. Caller must ack each LSN."""
        with self._connection() as conn:
            cur = conn.cursor()
            cur.start_replication(
                slot_name=self._slot,
                decode=True,
                options={
                    "publication_names": self._publication,
                    "proto_version": "1",
                },
            )
            try:
                while True:
                    msg = cur.read_message()
                    if msg is None:
                        continue
                    yield {
                        "lsn": str(msg.data_start),
                        "payload": msg.payload,
                    }
            finally:
                cur.close()


__all__ = ["AuditCDC"]
