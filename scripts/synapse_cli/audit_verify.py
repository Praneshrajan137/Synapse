"""``synapse audit verify`` - thin delegating alias for the chain verifier (ADR-033).

Feature: purpose-achievement-audit, task 7.3. Requirements R6.9, R6.13, R6.14.

This module used to *be* the verifier. It is now an alias: every line of verification
logic lives in :mod:`orchestrator.audit.cli` (the thin database adapter, design E4.2)
over the pure :func:`orchestrator.audit.chain_walk.walk` (design E4.1, AD-7). The alias
exists so the entry point ADR-033 names keeps working; it is deliberately incapable of
producing a different verdict from ``python -m orchestrator.audit.cli verify``, because
two implementations of one guarantee is how the original divergence happened.

Why the old body had to go, not just be wired up
------------------------------------------------

The removed per-row check was::

    expected = hash_payload_for_row(row.prev_hash or prev_hash, _to_canonical(row))

It validated each row against that row's **own stored** ``prev_hash``. The walked
``prev_hash`` was reassigned from every row's ``current_hash`` and no comparison ever
consumed it, so nothing asserted that a row's stored link equalled the ``current_hash``
of the row that actually precedes it in the ordered walk. Every surviving row therefore
stayed self-consistent, and row deletion, segment re-linking, and adjacent reorder were
all invisible - the exact tamper classes an append-only ledger exists to detect. Wiring
this body to a call site unchanged would have added no detection capability over the
per-row recompute the console already performs (``api/routers/decisions.py:321``).
``chain_walk`` compares stored links against walked links instead (AD-8), and this file
delegates to it.

Argv contract (preserved)
-------------------------

``--dsn`` and ``--since`` keep their names and their meanings, and ``main(argv)`` still
returns the process exit code::

    python -m scripts.synapse_cli.audit_verify [--dsn ...] [--since ISO] [--head HASH]

As before, omitting ``--since`` walks the **whole table**: pre-boundary rows carrying
null chain values are counted as ``legacy`` and excluded from the verified count (R6.7)
rather than being treated as breaks, so the wide default stays safe. The module CLI
defaults ``--since`` to the committed migration boundary instead, which is CF-6's
deploy-time default; both are reachable from either entry point.

``--head`` is new and optional: it supplies the independently recorded head hash for the
reachability check (R6.5). Omitted, reachability is not checked and the report says so.

``--dsn``'s default gained one step: ``$SYNAPSE_AUDIT_DSN``, then the orchestrator's own
configured ``postgresql_url``, then the same local literal as before
(:func:`orchestrator.audit.cli.default_dsn`). The old localhost-only default was
unusable inside the orchestrator container, which is where both deploy call sites run
the verifier.

Exit codes - and the one behaviour change
-----------------------------------------

``0`` verified / ``1`` broken / ``2`` unavailable-or-not-verified. The change from the
old behaviour is deliberate and is the requirement, not a regression: this file used to
print ``checked=0 ... breaks=0`` and return ``0`` for an empty or fully-truncated table,
and to return ``0`` for a table containing nothing but null-hash rows. Both now exit
``2`` (R6.9) - a walk that verified nothing has not verified the chain, and reporting
absence of proof as a pass is exactly what I-7 forbids.

The walk bounds and the migration boundary come from
``infrastructure/quality/audit-chain-bounds.yaml`` via ``load_chain_bounds`` (AD-13),
never from literals here. ``make_canonical_row`` is untouched (I-4, byte-pinned).
All console output is ASCII and ``print`` appears only on the entry path.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from orchestrator.audit.chain_walk import load_chain_bounds
from orchestrator.audit.cli import DEFAULT_DSN, default_dsn, verify_and_report

if TYPE_CHECKING:
    from orchestrator.audit.chain_walk import ChainBounds

logger = structlog.get_logger(__name__)

__all__ = ["DEFAULT_DSN", "main", "verify_chain"]

_EXIT_UNAVAILABLE = 2


async def verify_chain(
    dsn: str,
    since: datetime | None = None,
    *,
    recorded_head: str | None = None,
    bounds: ChainBounds | None = None,
) -> int:
    """Walk the chain and print the report; returns the exit code.

    Signature-compatible with the implementation this alias replaces, so any existing
    caller awaiting ``verify_chain(dsn, since)`` keeps working and now gets linkage
    detection for free.

    Args:
        dsn: SQLAlchemy async DSN.
        since: Inclusive lower bound on ``created_at``; ``None`` walks the whole table.
        recorded_head: Independently recorded head hash, or ``None`` to skip the
            reachability check (R6.5).
        bounds: Committed bounds, read from the committed file when omitted.
    """
    resolved = bounds if bounds is not None else load_chain_bounds()
    return await verify_and_report(
        dsn=dsn,
        since=since,
        max_rows=resolved.max_rows,
        timeout=float(resolved.max_wall_clock_seconds),
        recorded_head=recorded_head,
        bounds=resolved,
    )


def main(argv: list[str] | None = None) -> int:
    """The preserved entry point: parse the same argv, delegate, return the exit code."""
    parser = argparse.ArgumentParser(
        prog="synapse audit verify",
        description=(
            "Walk the append-only audit chain and report its integrity. Delegates to "
            "python -m orchestrator.audit.cli verify."
        ),
    )
    parser.add_argument(
        "--dsn",
        default=default_dsn(),
        help=(
            "SQLAlchemy async DSN (default: $SYNAPSE_AUDIT_DSN, else the orchestrator's "
            "configured postgresql_url, else the local dev DSN)."
        ),
    )
    parser.add_argument(
        "--since",
        type=str,
        default=None,
        help="ISO-8601 date or datetime; verify rows created at or after this point.",
    )
    parser.add_argument(
        "--head",
        default=os.environ.get("SYNAPSE_AUDIT_CHAIN_HEAD") or None,
        help=(
            "Independently recorded chain head hash. Omitted: head reachability is not "
            "checked (R6.5)."
        ),
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    since_dt: datetime | None = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(str(args.since))
        except ValueError as exc:
            print(f"invalid --since: {exc}", file=sys.stderr)
            return _EXIT_UNAVAILABLE
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=UTC)

    try:
        bounds = load_chain_bounds()
    except (OSError, KeyError, ValueError) as exc:
        # Without the committed boundary there is nothing to judge a null hash against,
        # and inventing one is not permitted (AD-13). Unavailable, never a pass (I-7).
        logger.error("audit_chain_bounds_unreadable", reason=str(exc))
        print(f"cannot read the committed chain bounds: {exc}", file=sys.stderr)
        return _EXIT_UNAVAILABLE

    return asyncio.run(
        verify_chain(
            str(args.dsn),
            since_dt,
            recorded_head=None if args.head is None else str(args.head),
            bounds=bounds,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
