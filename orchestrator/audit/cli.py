"""Audit-chain verification CLI - the module both call sites already name (design E4.2).

Feature: purpose-achievement-audit, task 7.3. Requirements R6.9, R6.13, R6.14.

``Makefile::deploy-gcp-verify`` and ``.github/workflows/cd-gcp.yml::deploy-to-vm`` have
invoked ``python -m orchestrator.audit.cli verify`` for two sprints while this module did
not exist, and both call sites also discarded the exit status - so neither the absence
nor a non-zero could ever surface. This module is the missing half; task 7.3 also drops
the swallowing constructs at both sites, and ``scripts/audit/command_path_truth.py``
(task 7.4) is what keeps the pair from going quiet again.

**AD-7: this is a thin database adapter, nothing more.** The verification logic is the
pure :func:`orchestrator.audit.chain_walk.walk`, which is property-tested without
Postgres (task 7.2) and therefore testable at all under I-0. Everything here is I/O:
read an ordered snapshot, build :class:`ChainRow` values, hand them to ``walk``, print an
ASCII report, and return the report's exit code. No verification decision is made in this
file - if you find yourself adding one, it belongs in ``chain_walk``.

**I-4.** ``make_canonical_row`` is imported and called with exactly the field set
``scripts/synapse_cli/audit_verify.py`` passed it, never reimplemented and never
modified: the chain is byte-pinned by a literal-digest test
(``packages/tests/test_audit_chain.py``). This module reads; it never writes. The write
side's own guarantees are unchanged - ``synapse_app`` has UPDATE/DELETE revoked on
``audit_consensus`` (``infrastructure/postgres/02_sprint4_consensus.sql:47,56``) and the
only statement issued here is a ``SELECT``.

The snapshot (R6.10)
--------------------

The read is **ordered** (``ORDER BY created_at, id``) and happens **in one transaction**
opened at ``REPEATABLE READ``, so every statement in the block sees the one snapshot
taken when the transaction began. Rows appended while the walk runs are outside it by
construction, which is what makes R6.10's "walk the row set fixed by a snapshot taken at
the start of the run" a property of the read rather than a hope about timing. The order
is *never* re-sorted afterwards: ``walk`` honours the caller's order because R6.4
(adjacent reorder, stored bytes unchanged) is only detectable that way.

Two things the snapshot reports, and why there are two
-----------------------------------------------------

``audit_consensus.id`` is a ``UUID``, not a monotone integer, while
``ChainRow.row_id``/``WalkReport.snapshot_upper_bound`` are ``int``. So:

* ``row_id`` is the **1-based ordinal position** in the ordered snapshot, and
  ``WalkReport.snapshot_upper_bound`` is consequently the snapshot's row count. That is a
  real upper boundary of a position-ordered walk, and it is what makes a break's
  ``position`` and ``row_id`` agree.
* the snapshot's **storage** upper boundary - the last row's ``created_at`` and its
  database ``id`` - is carried separately on :class:`ChainSnapshot` and printed. It is
  the value an operator needs to re-run a walk over the same window, and the value that
  says concretely where "everything after this is out of scope" falls.

Every break line resolves its ordinal back to the database ``id``, so R6.2's "name the
successor of the deleted row" names a row an operator can actually go and look at.

The recorded head (R6.5)
------------------------

``--head`` supplies the independently recorded head hash. It is deliberately **not**
read from ``audit_consensus`` itself: a head taken from the table being verified is
circular and cannot detect truncation, which is the whole point of R6.5. Task 7.6 wires
the anchor (``orchestrator/audit/anchorer.py``) as the source and
``scripts/audit/anchor_truth.py`` as the freshness gate; until then, omitting ``--head``
disables the reachability check and the report says so rather than implying it passed.

``--since`` and CF-6
--------------------

CF-6's resolution is that the verifier takes ``--since <migration-boundary>`` from a
committed constant, so a blocking deploy-time walk is not failed by pre-chain rows. That
boundary is therefore the **default**: it comes from
``infrastructure/quality/audit-chain-bounds.yaml`` via ``load_chain_bounds`` and is never
inlined (AD-13). ``--since all`` widens the snapshot to the whole table, where
pre-boundary null-hash rows are counted as ``legacy`` and excluded from ``verified``
(R6.7) rather than being treated as breaks.

Exit codes (E4.2), straight from :attr:`WalkReport.exit_code`
-------------------------------------------------------------

* ``0`` - verified: at least one row verified and nothing broke (R6.6).
* ``1`` - broken: at least one break, named (R6.1-R6.5, R6.8).
* ``2`` - unavailable or not verified: the database could not be read, the walk exceeded
  its declared row-count or wall-clock bound (R6.13), or the snapshot verified nothing -
  zero rows, or nothing but legacy rows (R6.9). ``2`` is non-passing. An empty chain is
  *not* a verified chain, and reporting it as ``0`` is the exact dishonesty I-7 forbids.

Run::

    python -m orchestrator.audit.cli verify [--dsn ...] [--since ...|all]
                                            [--max-rows N] [--timeout S] [--head HASH]

Both blocking call sites run this **inside the orchestrator container**
(``cd-gcp.yml::deploy-to-vm`` and ``Makefile::deploy-gcp-verify``), which is why
``--dsn`` defaults through :func:`default_dsn` to the orchestrator's own configured
database rather than to a ``localhost`` literal, and why
``infrastructure/quality/audit-chain-bounds.yaml`` is copied into that image
(``orchestrator/Dockerfile``). A blocking gate that cannot reach its subject reports the
wrong thing.

``print`` is used in :func:`run` and nowhere else in this module; every other message is
``structlog``. All console output is ASCII (Windows console contract) and every file read
uses ``encoding='utf-8'`` (E-S13-07, applied inside ``load_chain_bounds``).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final

import structlog
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from synapse_common.metrics import AUDIT_CHAIN_TAMPER_DETECTED

# ``ChainRow`` is a runtime import: it is constructed here and it appears in a Pydantic
# field annotation on ``ChainSnapshot`` (ruff's runtime-evaluated-base-classes).
from orchestrator.audit.chain_walk import ChainRow, load_chain_bounds, walk
from orchestrator.audit.hash_chain import make_canonical_row
from orchestrator.audit.models import AuditConsensusRow
from orchestrator.config import OrchestratorConfig

if TYPE_CHECKING:
    from collections.abc import Sequence

    from orchestrator.audit.chain_walk import ChainBounds, WalkReport

logger = structlog.get_logger(__name__)

__all__ = [
    "DEFAULT_DSN",
    "SNAPSHOT_ISOLATION_LEVEL",
    "ChainSnapshot",
    "SnapshotUnavailableError",
    "build_parser",
    "canonical_row_for",
    "chain_rows_from",
    "default_dsn",
    "main",
    "read_snapshot",
    "redact_dsn",
    "render_breaks",
    "render_report",
    "run",
    "verify_and_report",
    "verify_once",
]

#: Last-resort local default, carried over verbatim from
#: ``scripts/synapse_cli/audit_verify.py`` so the delegating alias keeps its behaviour.
#: Reached only when neither ``$SYNAPSE_AUDIT_DSN`` nor the orchestrator's own
#: configuration answers (see :func:`default_dsn`). Always printed through
#: :func:`redact_dsn`.
DEFAULT_DSN: Final[str] = (
    "postgresql+asyncpg://synapse_app:synapse_app_2026@localhost:5432/synapse_audit"
)

#: The snapshot guarantee R6.10 asks for: every statement in the transaction sees the
#: state as of the transaction's start, so concurrent appends are out of scope by
#: construction rather than by timing luck.
SNAPSHOT_ISOLATION_LEVEL: Final[str] = "REPEATABLE READ"

#: ``--since all`` walks the whole table instead of starting at the committed boundary.
SINCE_ALL: Final[str] = "all"

#: Break lines printed before the rest are summarised as a count. A bound keeps the
#: report readable over an ssh session without a downstream ``| tail``, which would
#: discard the verifier's exit status (R6.13) - the exact construct task 7.3 removes.
MAX_PRINTED_BREAKS: Final[int] = 20

_EXIT_UNAVAILABLE: Final[int] = 2

#: ``scheme://user:password@rest`` - the password group is what gets replaced.
_DSN_PASSWORD_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?P<head>[^:]+://[^:/@]+:)(?P<password>[^@]*)(?P<tail>@.*)$"
)


class SnapshotUnavailableError(RuntimeError):
    """The ordered snapshot could not be read.

    Never a pass: the caller turns this into exit ``2`` with the reason printed. A
    verifier that cannot read the chain has not verified it (I-7).
    """


# ---------------------------------------------------------------------------
# Row conversion (I-4: make_canonical_row is called, never reimplemented)
# ---------------------------------------------------------------------------


def canonical_row_for(row: AuditConsensusRow) -> dict[str, Any]:
    """Build the canonical dict for one stored row.

    The field set and the coercions are exactly those
    ``scripts/synapse_cli/audit_verify.py::_to_canonical`` passed, because the stored
    ``current_hash`` was computed from them: any change here would invalidate every
    hash in the chain, which E-S9-02 makes a chain-rewrite migration and not an edit.
    """
    return make_canonical_row(
        decision_id=row.decision_id,
        tier=row.tier,
        selected_action=dict(row.selected_action) if row.selected_action else {},
        pareto_weights=dict(row.pareto_weights) if row.pareto_weights else {},
        confidence=float(row.confidence),
        proposals=list(row.proposals) if row.proposals else [],
        audit_trace=list(row.audit_trace) if row.audit_trace else [],
    )


def chain_rows_from(
    rows: Sequence[AuditConsensusRow],
) -> tuple[tuple[ChainRow, ...], tuple[str, ...]]:
    """Convert ordered ORM rows into ``ChainRow`` values plus their database ids.

    ``row_id`` is the 1-based ordinal in the given order (see the module docstring on
    why the ``UUID`` primary key cannot be it). The returned id tuple is positional:
    ``ids[row_id - 1]`` is the database ``id`` of the row the walker calls ``row_id``,
    which is how a break is reported against something an operator can query.

    The order of ``rows`` is preserved exactly - the snapshot's ``ORDER BY`` is the
    walk order, and re-sorting here would delete R6.4's detection.
    """
    chain_rows: list[ChainRow] = []
    ids: list[str] = []
    for position, row in enumerate(rows, start=1):
        chain_rows.append(
            ChainRow(
                row_id=position,
                created_at=row.created_at,
                prev_hash=row.prev_hash,
                current_hash=row.current_hash,
                canonical=canonical_row_for(row),
            )
        )
        ids.append(str(row.id))
    return tuple(chain_rows), tuple(ids)


# ---------------------------------------------------------------------------
# The snapshot
# ---------------------------------------------------------------------------


class ChainSnapshot(BaseModel):
    """One ordered, single-transaction read of ``audit_consensus``.

    Frozen for the same reason ``ChainRow`` is: the adapter must not be able to repair
    the evidence it is handing to the walker.
    """

    model_config = ConfigDict(frozen=True)

    rows: tuple[ChainRow, ...]
    row_ids: tuple[str, ...]
    isolation_level: str
    since: datetime | None
    upper_bound_created_at: datetime | None
    upper_bound_row_id: str | None

    def database_id(self, row_id: int | None) -> str | None:
        """The database ``id`` for a walked ordinal, or ``None`` when out of range."""
        if row_id is None or not 1 <= row_id <= len(self.row_ids):
            return None
        return self.row_ids[row_id - 1]


def redact_dsn(dsn: str) -> str:
    """Replace a DSN password with ``***`` so the report can name the DSN safely."""
    return _DSN_PASSWORD_RE.sub(r"\g<head>***\g<tail>", dsn)


def default_dsn() -> str:
    """The DSN to verify when ``--dsn`` is not given.

    Resolution order, and why it is not just the literal:

    1. ``$SYNAPSE_AUDIT_DSN`` - the explicit override the old CLI honoured.
    2. ``OrchestratorConfig().postgresql_url`` - the orchestrator's *own* configured
       database. Both blocking call sites run this verifier **inside the orchestrator
       container**, where that value comes from
       ``SYNAPSE_ORCHESTRATOR_POSTGRESQL_URL`` (``docker/docker-compose.gcp.yml``) and
       points at the ``postgres`` service. A ``localhost`` literal would make the
       now-blocking deploy step exit ``2`` on every deploy for a reason that has
       nothing to do with the chain - a red gate that reports the wrong thing is no
       better than a swallowed one.
    3. :data:`DEFAULT_DSN` - the local development literal, if the settings object
       cannot be built.
    """
    explicit = os.environ.get("SYNAPSE_AUDIT_DSN")
    if explicit:
        return explicit
    try:
        return str(OrchestratorConfig().postgresql_url)
    except ValidationError as exc:  # pragma: no cover - malformed orchestrator env
        logger.warning("audit_chain_dsn_config_unreadable", reason=str(exc))
        return DEFAULT_DSN


def _as_utc(value: datetime) -> datetime:
    """Normalise to UTC, treating a naive timestamp as UTC (as ``chain_walk`` does)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def read_snapshot(
    dsn: str,
    *,
    since: datetime | None,
    isolation_level: str = SNAPSHOT_ISOLATION_LEVEL,
) -> ChainSnapshot:
    """Read the ordered snapshot in one transaction (R6.10).

    Args:
        dsn: SQLAlchemy async DSN.
        since: Lower bound on ``created_at``, inclusive; ``None`` reads the whole table.
        isolation_level: Transaction isolation for the read. The default fixes the
            snapshot at transaction start, which is the guarantee R6.10 names.

    Raises:
        SnapshotUnavailableError: The engine could not be built or the read failed.
            Reported as exit ``2``, never as a verified chain.
    """
    try:
        engine = create_async_engine(dsn, isolation_level=isolation_level)
    except (SQLAlchemyError, ModuleNotFoundError, ValueError) as exc:
        raise SnapshotUnavailableError(
            f"cannot open {redact_dsn(dsn)} at {isolation_level}: {exc}"
        ) from exc

    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        # One transaction for the whole read. `session.begin()` is explicit rather
        # than implicit so the snapshot boundary is visible in the code that depends
        # on it, and so task 7.6's anchor read joins the same snapshot.
        async with factory() as session, session.begin():
            statement = select(AuditConsensusRow).order_by(
                AuditConsensusRow.created_at.asc(), AuditConsensusRow.id.asc()
            )
            if since is not None:
                statement = statement.where(AuditConsensusRow.created_at >= since)
            result = await session.execute(statement)
            orm_rows: list[AuditConsensusRow] = list(result.scalars())
    except (SQLAlchemyError, OSError) as exc:
        raise SnapshotUnavailableError(
            f"cannot read the audit chain from {redact_dsn(dsn)}: {exc}"
        ) from exc
    finally:
        await engine.dispose()

    rows, row_ids = chain_rows_from(orm_rows)
    last = orm_rows[-1] if orm_rows else None
    snapshot = ChainSnapshot(
        rows=rows,
        row_ids=row_ids,
        isolation_level=isolation_level,
        since=since,
        upper_bound_created_at=None if last is None else _as_utc(last.created_at),
        upper_bound_row_id=None if last is None else str(last.id),
    )
    logger.info(
        "audit_chain_snapshot_read",
        rows=len(snapshot.rows),
        isolation_level=isolation_level,
        since=None if since is None else since.isoformat(),
        upper_bound_row_id=snapshot.upper_bound_row_id,
    )
    return snapshot


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------


async def verify_once(
    *,
    dsn: str,
    since: datetime | None,
    boundary: datetime,
    recorded_head: str | None,
    max_rows: int,
    timeout: float,
) -> tuple[ChainSnapshot, WalkReport]:
    """Read one snapshot and walk it, sharing ``timeout`` between the two halves.

    The declared wall-clock bound (R6.13) covers the whole run, not just the walk: a
    read that hangs is exactly as unverified as a walk that overruns. The read is
    bounded by :func:`asyncio.wait_for` and whatever budget survives it is handed to
    ``walk``; an exhausted budget is reported unavailable naming the bound rather than
    letting a zero-budget walk look like a completed one.

    Raises:
        SnapshotUnavailableError: The snapshot could not be read within the bound.
    """
    started = time.monotonic()
    try:
        snapshot = await asyncio.wait_for(
            read_snapshot(dsn, since=since), timeout=timeout
        )
    except TimeoutError as exc:
        raise SnapshotUnavailableError(
            f"reading the ordered snapshot exceeded the declared bound timeout={timeout}s"
        ) from exc

    remaining = timeout - (time.monotonic() - started)
    if remaining <= 0.0:
        raise SnapshotUnavailableError(
            f"the declared bound timeout={timeout}s was exhausted by the snapshot read; "
            "no budget remained for the walk"
        )

    report = walk(
        snapshot.rows,
        boundary=boundary,
        recorded_head=recorded_head,
        max_rows=max_rows,
        max_wall_clock_seconds=remaining,
    )
    return snapshot, report


# ---------------------------------------------------------------------------
# ASCII report
# ---------------------------------------------------------------------------


def render_report(
    *,
    dsn: str,
    bounds: ChainBounds,
    snapshot: ChainSnapshot,
    report: WalkReport,
    recorded_head: str | None,
    max_rows: int,
    timeout: float,
) -> tuple[str, ...]:
    """The summary lines, ASCII-only, in a fixed order.

    ``verified`` and ``legacy`` are printed as separate lines against the same
    ``walked`` denominator, which is R6.7's "report their count separately from the
    count of verified rows" made literal.
    """
    boundary = _as_utc(bounds.migration_boundary)
    since = snapshot.since
    if since is None:
        since_text = "all rows (--since all)"
    elif since == boundary:
        since_text = f"{since.isoformat()} (committed migration boundary)"
    else:
        since_text = since.isoformat()

    head_text = (
        "not supplied; head reachability NOT checked (R6.5 pending task 7.6's anchor)"
        if recorded_head is None
        else recorded_head[:12]
    )

    if snapshot.upper_bound_row_id is None:
        upper_bound = "empty snapshot"
    else:
        last_created = (
            "unknown"
            if snapshot.upper_bound_created_at is None
            else snapshot.upper_bound_created_at.isoformat()
        )
        upper_bound = (
            f"rows={report.snapshot_upper_bound} "
            f"last_created_at={last_created} "
            f"last_id={snapshot.upper_bound_row_id}"
        )
    return (
        "Audit-chain verification (E4.2 - R6)",
        f"  dsn             : {redact_dsn(dsn)}",
        f"  isolation       : {snapshot.isolation_level} (one transaction, ordered snapshot)",
        f"  since           : {since_text}",
        f"  boundary        : {boundary.isoformat()}",
        f"  bounds          : max_rows={max_rows} timeout={timeout}s",
        f"  recorded head   : {head_text}",
        f"  snapshot bound  : {upper_bound}",
        f"  walked          : {report.walked}",
        f"  verified        : {report.verified}",
        f"  legacy (null)   : {report.legacy}  [excluded from verified, R6.7]",
        f"  breaks          : {len(report.breaks)}",
        f"  walked head     : {'none' if report.head_hash is None else report.head_hash[:12]}",
        f"  bound exceeded  : {report.bound_exceeded or 'no'}",
        f"  status          : {report.status}  (exit {report.exit_code})",
    )


def render_breaks(
    snapshot: ChainSnapshot, report: WalkReport, *, limit: int = MAX_PRINTED_BREAKS
) -> tuple[str, ...]:
    """One line per break, first divergence first, each naming the database row."""
    lines: list[str] = []
    for chain_break in report.breaks[:limit]:
        database_id = snapshot.database_id(chain_break.row_id)
        located = "" if database_id is None else f" db_id={database_id}"
        lines.append(f"  TAMPER [{chain_break.kind}]{located} {chain_break.detail}")
    hidden = len(report.breaks) - len(lines)
    if hidden > 0:
        lines.append(f"  ... {hidden} further break(s) not shown (limit={limit})")
    return tuple(lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_since(raw: str, *, boundary: datetime) -> datetime | None:
    """Resolve ``--since``: the committed boundary by default, ``all``, or an ISO value.

    Raises:
        ValueError: The value is neither ``all`` nor an ISO-8601 timestamp.
    """
    if raw == SINCE_ALL:
        return None
    if not raw:
        return _as_utc(boundary)
    return _as_utc(datetime.fromisoformat(raw))


def build_parser(bounds: ChainBounds) -> argparse.ArgumentParser:
    """The argv contract. Defaults come from the committed bounds, never from literals."""
    parser = argparse.ArgumentParser(
        prog="python -m orchestrator.audit.cli",
        description="Walk the append-only audit chain and report its integrity (R6).",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser(
        "verify", help="Walk an ordered snapshot of audit_consensus and report breaks."
    )
    verify_parser.add_argument(
        "--dsn",
        default=default_dsn(),
        help=(
            "SQLAlchemy async DSN (default: $SYNAPSE_AUDIT_DSN, else the orchestrator's "
            "configured postgresql_url, else the local dev DSN)."
        ),
    )
    verify_parser.add_argument(
        "--since",
        default="",
        help=(
            "ISO-8601 date or datetime to start the snapshot at, or 'all' for the whole "
            "table. Default: the committed chain-migration boundary (CF-6)."
        ),
    )
    verify_parser.add_argument(
        "--max-rows",
        type=int,
        default=bounds.max_rows,
        help="Declared row-count bound; a larger snapshot is not verified (R6.13).",
    )
    verify_parser.add_argument(
        "--timeout",
        type=float,
        default=float(bounds.max_wall_clock_seconds),
        help="Declared wall-clock bound in seconds for the read plus the walk (R6.13).",
    )
    verify_parser.add_argument(
        "--head",
        default=os.environ.get("SYNAPSE_AUDIT_CHAIN_HEAD") or None,
        help=(
            "Independently recorded chain head hash. Omitted: reachability is not "
            "checked and the report says so (R6.5; task 7.6 wires the anchor)."
        ),
    )
    return parser


async def verify_and_report(
    *,
    dsn: str,
    since: datetime | None,
    max_rows: int,
    timeout: float,
    recorded_head: str | None,
    bounds: ChainBounds,
) -> int:
    """The async core: read, walk, print, and answer with the exit code.

    Separated from :func:`run` so ``scripts/synapse_cli/audit_verify.py`` can delegate
    here from inside its own ``asyncio.run`` and remain a genuinely thin alias - one
    report renderer, one set of exit codes, one place where a verdict is printed. The
    alias keeping its own copy of this body is how the two verifiers would drift apart
    again.
    """
    try:
        snapshot, report = await verify_once(
            dsn=dsn,
            since=since,
            boundary=bounds.migration_boundary,
            recorded_head=recorded_head,
            max_rows=max_rows,
            timeout=timeout,
        )
    except SnapshotUnavailableError as exc:
        logger.error("audit_chain_verify_unavailable", reason=str(exc))
        print("Audit-chain verification (E4.2 - R6)")
        print(f"  status          : unavailable  (exit {_EXIT_UNAVAILABLE})")
        print(f"  reason          : {exc}", file=sys.stderr)
        return _EXIT_UNAVAILABLE

    for line in render_report(
        dsn=dsn,
        bounds=bounds,
        snapshot=snapshot,
        report=report,
        recorded_head=recorded_head,
        max_rows=max_rows,
        timeout=timeout,
    ):
        print(line)

    if report.breaks:
        # One tamper event per break, preserving the existing metric's label value so
        # the series is continuous with the CLI this module replaces.
        for _ in report.breaks:
            AUDIT_CHAIN_TAMPER_DETECTED.labels(source="verify_cli").inc()
        for line in render_breaks(snapshot, report):
            print(line, file=sys.stderr)

    return report.exit_code


def run(
    *,
    dsn: str,
    since_raw: str,
    max_rows: int,
    timeout: float,
    recorded_head: str | None,
    bounds: ChainBounds,
) -> int:
    """Resolve ``--since``, verify, and return the process exit code.

    ``print`` belongs here and in :func:`verify_and_report` - this is the entry point,
    matching ``scripts/audit/verify_claims.py``. Break lines go to stderr so a deploy log
    shows them even when stdout is captured; the exit code is the machine-readable
    answer, and it is the answer both call sites now propagate.
    """
    try:
        since = _parse_since(since_raw, boundary=bounds.migration_boundary)
    except ValueError as exc:
        print(f"invalid --since: {exc}", file=sys.stderr)
        return _EXIT_UNAVAILABLE

    return asyncio.run(
        verify_and_report(
            dsn=dsn,
            since=since,
            max_rows=max_rows,
            timeout=timeout,
            recorded_head=recorded_head,
            bounds=bounds,
        )
    )


def main(argv: list[str] | None = None) -> int:
    """``python -m orchestrator.audit.cli verify ...``."""
    try:
        bounds = load_chain_bounds()
    except (OSError, KeyError, ValueError) as exc:
        # The committed bounds are the boundary and the two walk bounds. Without them
        # there is no declared boundary to judge null hashes against, so the run is
        # unavailable - it is not permitted to invent one (AD-13).
        logger.error("audit_chain_bounds_unreadable", reason=str(exc))
        print(f"cannot read the committed chain bounds: {exc}", file=sys.stderr)
        return _EXIT_UNAVAILABLE

    args = build_parser(bounds).parse_args(argv if argv is not None else sys.argv[1:])
    return run(
        dsn=str(args.dsn),
        since_raw=str(args.since),
        max_rows=int(args.max_rows),
        timeout=float(args.timeout),
        recorded_head=None if args.head is None else str(args.head),
        bounds=bounds,
    )


if __name__ == "__main__":
    raise SystemExit(main())
