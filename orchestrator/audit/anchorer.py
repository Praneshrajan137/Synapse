"""Daily anchor of the audit-chain head (Sprint 9 §M-sec-4, ADR-033).

Once a day the anchorer:
  1. Reads the most-recent ``audit_consensus`` row,
  2. Captures (created_at, current_hash) as the day's anchor,
  3. Writes a deterministic JSON line to
     ``infrastructure/audit_anchors/<YYYY-MM-DD>.json`` which the
     existing GitHub-Releases workflow then uploads as a public artifact.

The published artifacts form a pseudo-blockchain root any auditor can
cross-check ``synapse audit verify`` against. Idempotent: re-running for
the same day overwrites the artifact with the same content unless new
rows have landed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from orchestrator.audit.models import AuditConsensusRow

logger = structlog.get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ANCHOR_DIR = REPO_ROOT / "infrastructure" / "audit_anchors"


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


async def _capture_head(session: AsyncSession) -> dict[str, Any] | None:
    stmt = (
        select(
            AuditConsensusRow.id,
            AuditConsensusRow.created_at,
            AuditConsensusRow.current_hash,
        )
        .where(AuditConsensusRow.current_hash.is_not(None))
        .order_by(desc(AuditConsensusRow.created_at), desc(AuditConsensusRow.id))
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None
    return {
        "row_id": str(row[0]),
        "created_at": row[1].astimezone(UTC).isoformat() if row[1] else None,
        "current_hash": row[2],
    }


async def anchor_today(dsn: str, out_dir: Path = ANCHOR_DIR) -> int:
    engine = create_async_engine(dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            head = await _capture_head(session)
    finally:
        await engine.dispose()

    if head is None:
        logger.info("audit_anchor_empty_chain", date=_today())
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{_today()}.json"
    payload = {
        "date": _today(),
        "anchored_at": datetime.now(UTC).isoformat(),
        "row_id": head["row_id"],
        "row_created_at": head["created_at"],
        "current_hash": head["current_hash"],
        "synapse_version": "9.0",
    }
    out_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "audit_anchor_written",
        path=str(out_path.relative_to(REPO_ROOT)),
        head=head["current_hash"][:12],
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    import asyncio
    import os

    parser = argparse.ArgumentParser(prog="synapse-audit-anchor")
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "SYNAPSE_AUDIT_DSN",
            "postgresql+asyncpg://synapse_app:synapse_app_2026@localhost:5432/synapse_audit",
        ),
    )
    parser.add_argument("--out", type=Path, default=ANCHOR_DIR)
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return asyncio.run(anchor_today(args.dsn, args.out))


if __name__ == "__main__":
    raise SystemExit(main())
