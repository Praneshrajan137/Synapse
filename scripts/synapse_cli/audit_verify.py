"""``synapse audit verify`` — walk the audit chain and detect tampering (ADR-033).

Exit codes:
  0 — chain integrity confirmed (legacy NULL rows are reported but not fatal)
  1 — a row's stored ``current_hash`` does not match the recomputation
  2 — usage / connection error
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from synapse_common.metrics import AUDIT_CHAIN_TAMPER_DETECTED

from orchestrator.audit.hash_chain import (
    GENESIS_HASH,
    hash_payload_for_row,
    make_canonical_row,
)
from orchestrator.audit.models import AuditConsensusRow

logger = structlog.get_logger(__name__)


DEFAULT_DSN = "postgresql+asyncpg://synapse_app:synapse_app_2026@localhost:5432/synapse_audit"


def _to_canonical(row: AuditConsensusRow) -> dict[str, Any]:
    return make_canonical_row(
        decision_id=row.decision_id,
        tier=row.tier,
        selected_action=dict(row.selected_action) if row.selected_action else {},
        pareto_weights=dict(row.pareto_weights) if row.pareto_weights else {},
        confidence=float(row.confidence),
        proposals=list(row.proposals) if row.proposals else [],
        audit_trace=list(row.audit_trace) if row.audit_trace else [],
    )


async def verify_chain(dsn: str, since: datetime | None = None) -> int:
    engine = create_async_engine(dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    breaks: list[str] = []
    legacy: list[str] = []
    checked = 0
    prev_hash: str = GENESIS_HASH
    try:
        async with factory() as session:
            stmt = select(AuditConsensusRow).order_by(
                AuditConsensusRow.created_at.asc(), AuditConsensusRow.id.asc()
            )
            if since is not None:
                stmt = stmt.where(AuditConsensusRow.created_at >= since)
            result = await session.execute(stmt)
            rows = list(result.scalars())
    finally:
        await engine.dispose()

    for row in rows:
        if row.current_hash is None:
            legacy.append(str(row.id))
            continue
        expected = hash_payload_for_row(row.prev_hash or prev_hash, _to_canonical(row))
        if expected != row.current_hash:
            breaks.append(
                f"row={row.id} stored={row.current_hash[:12]} "
                f"expected={expected[:12]} prev={(row.prev_hash or '')[:12]}"
            )
            AUDIT_CHAIN_TAMPER_DETECTED.labels(source="verify_cli").inc()
        prev_hash = row.current_hash
        checked += 1

    print(f"checked={checked} legacy_rows={len(legacy)} breaks={len(breaks)}")
    for entry in breaks:
        print(f"  TAMPER: {entry}", file=sys.stderr)
    if legacy:
        print(
            f"  note: {len(legacy)} legacy rows have NULL chain values (pre-migration audit data)"
        )
    return 1 if breaks else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse audit verify")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("SYNAPSE_AUDIT_DSN", DEFAULT_DSN),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO-8601 date or datetime; verify rows created at or after this point.",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    since_dt: datetime | None = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(args.since)
            if since_dt.tzinfo is None:
                since_dt = since_dt.replace(tzinfo=UTC)
        except ValueError as exc:
            print(f"invalid --since: {exc}", file=sys.stderr)
            return 2
    return asyncio.run(verify_chain(args.dsn, since_dt))


if __name__ == "__main__":
    raise SystemExit(main())
