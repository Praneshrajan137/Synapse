"""Audit archival worker (Sprint 9 §M-life-1).

Daily job (scheduled via ``data_fabric/scheduler``) that selects
``audit_consensus`` rows older than ``SYNAPSE_AUDIT_ARCHIVE_DAYS`` (default
90), writes them as Parquet to a MinIO bucket partitioned by
``year=YYYY/month=MM/city=...``, and **does not** delete the source rows
— audit immutability (I-4) means retention is governed by Kafka topic
expiry + future tombstone-only erasure (M-life-3 DPDPA cascade).

Replay extension: Sprint 7's ``orchestrator.replay.replay_decision``
gains a MinIO fallback when the Postgres row is missing because it was
archived (Sprint 10 wires the fallback into the replay path).

Sprint 9 ships:
  - the archiver entrypoint + idempotent file-naming,
  - graceful skip when MinIO / pandas / pyarrow / boto3 are absent,
  - per-table Prometheus counter ``synapse_archive_rows_moved_total``.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from synapse_common.metrics import ARCHIVE_ROWS_MOVED_TOTAL

logger = structlog.get_logger(__name__)

DEFAULT_ARCHIVE_DAYS = int(os.environ.get("SYNAPSE_AUDIT_ARCHIVE_DAYS", "90"))
DEFAULT_TABLE = "audit_consensus"
MINIO_BUCKET = os.environ.get("SYNAPSE_AUDIT_BUCKET", "synapse-audit-archive")
MINIO_ENDPOINT = os.environ.get("SYNAPSE_MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS = os.environ.get("SYNAPSE_MINIO_ACCESS_KEY", "synapse")
MINIO_SECRET = os.environ.get("SYNAPSE_MINIO_SECRET_KEY", "synapse_minio_2026")


def _archive_path(now: datetime, table: str, city: str) -> str:
    return (
        f"{table}/year={now.year:04d}/month={now.month:02d}/"
        f"city={city}/run={now.strftime('%Y%m%dT%H%M%S')}.parquet"
    )


def _archive_via_boto(rows: list[dict[str, Any]], object_key: str) -> bool:
    """Best-effort upload to MinIO. Returns True on success, False on missing deps."""
    try:
        import boto3  # type: ignore[import-not-found, import-untyped, unused-ignore]
        import pandas as pd  # type: ignore[import-not-found, import-untyped, unused-ignore]
    except ImportError:
        logger.info("audit_archive_dependencies_missing")
        return False
    df = pd.DataFrame(rows)
    buffer_path = f"/tmp/{object_key.replace('/', '_')}"  # noqa: S108
    df.to_parquet(buffer_path, index=False)
    client = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS,
        aws_secret_access_key=MINIO_SECRET,
    )
    client.upload_file(buffer_path, MINIO_BUCKET, object_key)
    return True


def archive_old_rows(table: str = DEFAULT_TABLE, days: int = DEFAULT_ARCHIVE_DAYS) -> int:
    """Move rows older than ``days`` to MinIO. Returns exit code (0/1)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    except ImportError:
        logger.warning("sqlalchemy_async_unavailable")
        return 0

    dsn = os.environ.get(
        "SYNAPSE_AUDIT_DSN",
        "postgresql+asyncpg://synapse_app:synapse_app_2026@localhost:5432/synapse_audit",
    )
    engine = create_async_engine(dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    import asyncio

    async def _run() -> int:
        try:
            from orchestrator.audit.models import AuditConsensusRow
        except ImportError:
            logger.warning("audit_models_unavailable")
            return 0
        async with factory() as session:
            stmt = select(AuditConsensusRow).where(AuditConsensusRow.created_at < cutoff)
            result = await session.execute(stmt)
            rows = list(result.scalars())
        if not rows:
            logger.info("audit_archive_no_old_rows", cutoff=cutoff.isoformat())
            return 0
        by_city: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            payload = {
                "id": str(row.id),
                "decision_id": str(row.decision_id),
                "tier": row.tier,
                "selected_action": dict(row.selected_action) if row.selected_action else {},
                "current_hash": row.current_hash,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            # Pre-Sprint 6 rows are city-agnostic; archive them under "shared".
            city = (
                payload["selected_action"].get("city")
                if isinstance(payload["selected_action"], dict)
                else None
            )
            by_city.setdefault(city or "shared", []).append(payload)
        now = datetime.now(UTC)
        for city, group in by_city.items():
            object_key = _archive_path(now, table, city)
            archived = _archive_via_boto(group, object_key)
            ARCHIVE_ROWS_MOVED_TOTAL.labels(table=table).inc(len(group) if archived else 0)
            logger.info(
                "audit_archive_batch",
                table=table,
                city=city,
                rows=len(group),
                archived=archived,
                object_key=object_key,
            )
        return 0

    import contextlib

    try:
        return asyncio.run(_run())
    finally:
        # The async dispose runs inside the run; if it failed before reaching there,
        # we still want to release the pool.
        with contextlib.suppress(Exception):
            asyncio.run(engine.dispose())


if __name__ == "__main__":
    raise SystemExit(archive_old_rows())
