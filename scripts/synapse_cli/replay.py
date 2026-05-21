"""``synapse replay <decision_id>`` — re-derive a past decision (WS-4 §3).

Usage::

    python -m scripts.synapse_cli.replay <decision_id> [--dsn DSN]

Exits non-zero on divergence so the command is gate-able from CI.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from orchestrator.replay.replay import replay_decision

DEFAULT_DSN = "postgresql+asyncpg://synapse_app:synapse_app_2026@localhost:5432/synapse_audit"


async def _run(decision_id: UUID, dsn: str) -> int:
    engine = create_async_engine(dsn)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as session:
            result = await replay_decision(session, decision_id)
    finally:
        await engine.dispose()

    if result.note:
        print(f"note: {result.note}", file=sys.stderr)

    print(f"decision_id      = {result.decision_id}")
    print(f"original_hash    = {result.original_hash[:12]}")
    print(f"replay_hash      = {result.replay_hash[:12]}")
    print(f"diverged         = {result.diverged}")
    if result.divergences:
        print("divergences:")
        for div in result.divergences:
            print(f"  - {div.field}: expected={div.expected!r} actual={div.actual!r}")
    return 1 if result.diverged else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="synapse replay")
    parser.add_argument("decision_id", help="UUID of the audited decision to replay")
    parser.add_argument(
        "--dsn",
        default=os.environ.get("SYNAPSE_AUDIT_DSN", DEFAULT_DSN),
        help="async SQLAlchemy DSN for the audit database",
    )
    args = parser.parse_args(argv)
    decision_id = UUID(args.decision_id)
    return asyncio.run(_run(decision_id, args.dsn))


if __name__ == "__main__":
    raise SystemExit(main())
