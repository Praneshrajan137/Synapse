"""Daily anchor of the audit-chain head (design E4.3; R6.11, R6.12, ADR-033).

Feature: purpose-achievement-audit, task 7.6.

An anchor is a **commitment to the chain head hash**. Once published, a party who
holds nothing but the anchor can take any later presentation of the chain and decide
whether any row at or before the anchored head was rewritten: rewrite a row without
recomputing and the row's own hash stops matching its content (a ``PAYLOAD`` break);
rewrite it and recompute forward and the head hash changes, so the hash the anchor
names is carried by no row in the presentation (``HEAD_UNREACHABLE``). Either way the
walk that :func:`detect_rewrite` runs does not come back ``verified``. That is the
whole of R6.12, and it is why the commitment is the *hash* and not the row id: the
row id is provenance, the hash is the evidence.

What "the head" means, and why both halves must agree
----------------------------------------------------

``orchestrator/audit/chain_walk.py`` convention 5 is explicit that
``BreakKind.HEAD_UNREACHABLE`` is **reachability, not final position**: it fires when
``recorded_head`` is carried by *no* row in the walked snapshot. This module is the
thing that records that head, so the two must agree on what the head is, and the
agreement is stated once, here:

    **The head is the ``current_hash`` of the last row carrying a non-null
    ``current_hash`` in canonical walk order (``ORDER BY created_at ASC, id ASC``).**

Three consequences, all deliberate:

1. :func:`select_head` walks a materialised snapshot backwards to the newest hashed
   row, which is exactly ``packages/tests/strategies_audit.py::head_hash`` - so the
   shared strategies and this module cannot drift apart.
2. :func:`_capture_head` asks the database for ``ORDER BY created_at DESC, id DESC
   LIMIT 1`` over rows with a non-null ``current_hash``. Over a total order that is
   the same row :func:`select_head` returns, so the SQL path and the pure path anchor
   the same head without the SQL path having to materialise the chain.
3. A trailing run of legacy null-hash rows (E-S9-01) does not move the head, and
   cannot: those rows carry no hash for an anchor to commit to. ``chain_walk`` counts
   them as ``legacy`` rather than advancing the walked link, which is the same rule
   read from the other side.

The pure seam (task 7.7 drives this, no database and no network)
---------------------------------------------------------------

Property 19 ("an anchor commits to the head it claims") needs to quantify over
chains and rewrites without Postgres, so every decision in this module is pure and
the I/O is a shell around it:

* :func:`select_head` - snapshot -> :class:`ChainHead`
* :func:`build_anchor_record` - head + timestamp -> :class:`AnchorRecord`
* :meth:`AnchorRecord.to_json` / :meth:`AnchorRecord.from_json` - the published bytes
* :func:`scope_to_anchor` - the prefix of a presentation at or before the anchored
  head, which is precisely the window R6.12 scopes the guarantee to
* :func:`detect_rewrite` - anchor + presented rows -> :class:`AnchorDetection`,
  delegating the verification itself to the already-property-tested
  :func:`orchestrator.audit.chain_walk.walk`

``anchor_today`` and ``_capture_head`` are the only functions here that touch a
database, and neither makes a verification decision.

Conventions
-----------

* **E-S9-03**: the published bytes are compact canonical JSON -
  ``json.dumps(payload, sort_keys=True, separators=(',',':'))``. ``indent=2`` fails
  the JSON-determinism contract test that scans ``orchestrator/``.
* **I-4**: read-only. Nothing here writes to ``audit_consensus`` and
  ``make_canonical_row`` is untouched.
* **I-7**: a run that anchored nothing is never reported as a success. An empty
  chain, or a chain of nothing but legacy rows, exits :data:`EXIT_UNAVAILABLE` - the
  freshness gate ``scripts/audit/anchor_truth.py`` then reports the chain
  unverifiable rather than letting silence read as health.
* ``structlog`` everywhere except :func:`main`'s error path; ASCII-only output;
  ``encoding='utf-8'`` on every read and write (E-S13-07).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

import structlog
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Runtime imports: ``ChainRow`` and ``WalkReport`` appear in Pydantic field
# annotations (ruff runtime-evaluated-base-classes).
from orchestrator.audit.chain_walk import ChainRow, WalkReport, walk
from orchestrator.audit.models import AuditConsensusRow

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

__all__ = [
    "ANCHOR_DIR",
    "ANCHOR_SCHEMA_VERSION",
    "EXIT_OK",
    "EXIT_UNAVAILABLE",
    "AnchorDetection",
    "AnchorFormatError",
    "AnchorRecord",
    "AnchorScope",
    "ChainHead",
    "HeadUnavailableError",
    "anchor_path",
    "anchor_today",
    "build_anchor_record",
    "detect_rewrite",
    "main",
    "scope_to_anchor",
    "select_head",
    "write_anchor",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

#: Mirrors ``infrastructure/quality/audit-chain-bounds.yaml::anchor_freshness.anchor_dir``
#: and ADR-033. ``scripts/audit/anchor_truth.py`` reads the committed value and
#: compares it against this constant, so a move cannot happen on one side only.
ANCHOR_DIR: Final[Path] = REPO_ROOT / "infrastructure" / "audit_anchors"

#: ``2`` is the head-committing shape this task introduces. Version ``1`` is the
#: pre-task-7.6 payload (``current_hash`` / ``row_id`` / ``row_created_at``); it is
#: still readable, because refusing to read a published anchor would destroy evidence.
ANCHOR_SCHEMA_VERSION: Final[int] = 2

#: Carried in the payload for provenance, matching the pre-existing field.
SYNAPSE_VERSION: Final[str] = "9.0"

EXIT_OK: Final[int] = 0
EXIT_UNAVAILABLE: Final[int] = 2

#: A SHA-256 digest as the chain stores it. An "anchor" whose commitment is not one
#: commits to nothing, so parsing rejects it rather than publishing a false positive.
_HEX64_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")

_PREFIX: Final[int] = 12


class AnchorFormatError(ValueError):
    """A published anchor could not be read as a commitment to a head hash."""


class HeadUnavailableError(RuntimeError):
    """The chain head could not be read from the database.

    Never a pass: the caller turns this into :data:`EXIT_UNAVAILABLE`. A run that
    could not read the head has anchored nothing (I-7).
    """


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChainHead(BaseModel):
    """The head an anchor commits to.

    Frozen: the head is evidence, and the anchorer must not be able to adjust the
    thing it is about to publish a commitment to.

    ``row_id`` is **provenance only** - the database ``id`` on the SQL path, the
    walked ordinal on the pure path. No detection reads it; :func:`detect_rewrite`
    uses :attr:`head_hash` alone, because that is all a third party holds.
    """

    model_config = ConfigDict(frozen=True)

    head_hash: str
    row_id: str
    created_at: datetime | None


class AnchorRecord(BaseModel):
    """One published anchor: a commitment to the chain head hash (R6.12).

    Frozen, per the design's records table. Serialised by :meth:`to_json` as compact
    canonical JSON (E-S9-03) so two anchors of the same head are byte-identical and
    the cosign signature in ``publish-audit-anchor.yml`` covers a deterministic blob.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int
    date: str
    anchored_at: datetime
    head_hash: str
    head_row_id: str
    head_created_at: datetime | None
    synapse_version: str

    def payload(self) -> dict[str, Any]:
        """The JSON-ready mapping, keys named for what they commit to."""
        return {
            "anchor_schema_version": self.schema_version,
            "anchored_at": self.anchored_at.astimezone(UTC).isoformat(),
            "date": self.date,
            "head_created_at": (
                None
                if self.head_created_at is None
                else self.head_created_at.astimezone(UTC).isoformat()
            ),
            "head_hash": self.head_hash,
            "head_row_id": self.head_row_id,
            "synapse_version": self.synapse_version,
        }

    def to_json(self) -> str:
        """Compact canonical JSON, no trailing newline (E-S9-03)."""
        return json.dumps(self.payload(), sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_payload(cls, payload: Any) -> AnchorRecord:
        """Read an anchor payload, accepting the pre-task-7.6 key names.

        Raises:
            AnchorFormatError: The payload is not a mapping, names no head hash, or
                names one that is not a SHA-256 digest. A file that fails here is
                reported by the freshness gate as a defect, never ignored.
        """
        if not isinstance(payload, dict):
            raise AnchorFormatError(f"anchor payload is {type(payload).__name__}, not an object")
        mapping: dict[str, Any] = payload

        head_hash = mapping.get("head_hash") or mapping.get("current_hash")
        if not isinstance(head_hash, str) or not _HEX64_RE.match(head_hash):
            raise AnchorFormatError(
                "anchor names no head hash: expected 'head_hash' (or legacy "
                f"'current_hash') to be a 64-character lowercase hex digest, got {head_hash!r}"
            )

        anchored_raw = mapping.get("anchored_at")
        if not isinstance(anchored_raw, str):
            raise AnchorFormatError("anchor has no string 'anchored_at' timestamp")
        try:
            anchored_at = _as_utc(datetime.fromisoformat(anchored_raw))
        except ValueError as exc:
            raise AnchorFormatError(f"anchor 'anchored_at' is not ISO-8601: {exc}") from exc

        created_raw = mapping.get("head_created_at", mapping.get("row_created_at"))
        head_created_at: datetime | None = None
        if isinstance(created_raw, str):
            try:
                head_created_at = _as_utc(datetime.fromisoformat(created_raw))
            except ValueError as exc:
                raise AnchorFormatError(f"anchor 'head_created_at' is not ISO-8601: {exc}") from exc

        row_id = mapping.get("head_row_id", mapping.get("row_id"))
        date = mapping.get("date")
        return cls(
            schema_version=int(mapping.get("anchor_schema_version", 1)),
            date=str(date) if isinstance(date, str) else anchored_at.strftime("%Y-%m-%d"),
            anchored_at=anchored_at,
            head_hash=head_hash,
            head_row_id="" if row_id is None else str(row_id),
            head_created_at=head_created_at,
            synapse_version=str(mapping.get("synapse_version", "")),
        )

    @classmethod
    def from_json(cls, text: str) -> AnchorRecord:
        """Parse published anchor bytes.

        Raises:
            AnchorFormatError: The text is not JSON, or is not a readable anchor.
        """
        try:
            payload: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AnchorFormatError(f"anchor is not valid JSON: {exc}") from exc
        return cls.from_payload(payload)

    def age_hours(self, now: datetime) -> float:
        """Hours between publication and ``now``; never negative."""
        delta = _as_utc(now) - self.anchored_at
        return max(delta.total_seconds() / 3600.0, 0.0)

    def is_stale(self, now: datetime, *, max_age_hours: float) -> bool:
        """Whether this anchor is older than the committed freshness bound (R6.11)."""
        return self.age_hours(now) > max_age_hours


class AnchorScope(BaseModel):
    """The window an anchor's guarantee covers: rows at or before the anchored head.

    ``reachable`` is ``False`` when no presented row carries the anchored head hash,
    in which case ``rows`` is the whole presentation - the evidence a walk needs to
    report ``HEAD_UNREACHABLE`` rather than a silently narrowed window.
    """

    model_config = ConfigDict(frozen=True)

    rows: tuple[ChainRow, ...]
    reachable: bool
    head_position: int | None


class AnchorDetection(BaseModel):
    """What a party holding only the anchor concludes about a presented chain.

    Three outcomes, and ``intact`` is the only one that claims anything positive:

    * ``rewritten`` - the walk over the anchored window broke, or the anchored head
      is carried by no presented row. Either is a detected rewrite at or before the
      anchored head (R6.12).
    * ``intact`` - the anchored window walked clean and the anchored head was
      reached.
    * ``unverifiable`` - the walk proved nothing (no hashed rows in the window, or a
      declared bound was exceeded). Not a detection and not a clean bill of health;
      absence of proof is never a pass (I-7).
    """

    model_config = ConfigDict(frozen=True)

    anchored_head: str
    head_reachable: bool
    anchored_rows: int
    status: Literal["intact", "rewritten", "unverifiable"]
    report: WalkReport

    @property
    def detected(self) -> bool:
        """Whether a rewrite at or before the anchored head was detected."""
        return self.status == "rewritten"


# ---------------------------------------------------------------------------
# Pure core (the seam task 7.7 drives)
# ---------------------------------------------------------------------------


def _as_utc(value: datetime) -> datetime:
    """Normalise to UTC, treating a naive timestamp as UTC (as ``chain_walk`` does)."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _short(value: str | None) -> str:
    """ASCII-safe hash prefix for a log field or a report line."""
    return "none" if value is None else value[:_PREFIX]


def select_head(rows: Sequence[ChainRow]) -> ChainHead | None:
    """The head of an ordered snapshot: the last row carrying a ``current_hash``.

    The single definition of "the head" this module and ``chain_walk`` agree on (see
    the module docstring). ``None`` when the snapshot has no hashed row at all - an
    empty chain, or nothing but legacy null-hash rows - because there is then nothing
    to commit to and inventing a commitment would be fabrication (I-7).

    The sequence is **not** re-sorted: the caller's order is the chain's order, the
    same contract :func:`orchestrator.audit.chain_walk.walk` holds.
    """
    for row in reversed(tuple(rows)):
        if row.current_hash is not None:
            return ChainHead(
                head_hash=row.current_hash,
                row_id=str(row.row_id),
                created_at=row.created_at,
            )
    return None


def build_anchor_record(
    head: ChainHead,
    *,
    anchored_at: datetime,
    synapse_version: str = SYNAPSE_VERSION,
) -> AnchorRecord:
    """Build the record to publish for ``head``.

    Pure and total: same head plus same timestamp gives byte-identical
    :meth:`AnchorRecord.to_json`, which is what makes re-running the anchorer for a
    day idempotent unless new rows have landed.
    """
    stamped = _as_utc(anchored_at)
    return AnchorRecord(
        schema_version=ANCHOR_SCHEMA_VERSION,
        date=stamped.strftime("%Y-%m-%d"),
        anchored_at=stamped,
        head_hash=head.head_hash,
        head_row_id=head.row_id,
        head_created_at=None if head.created_at is None else _as_utc(head.created_at),
        synapse_version=synapse_version,
    )


def scope_to_anchor(anchor: AnchorRecord, rows: Sequence[ChainRow]) -> AnchorScope:
    """The prefix of ``rows`` at or before the anchored head (R6.12's window).

    Rows appended *after* the anchor was published are outside what the anchor
    committed to, so they are excluded: including them would let a later, honest
    append be reported against an anchor that never covered it. When no row carries
    the anchored head the whole presentation is returned with ``reachable=False`` -
    truncation is itself the finding.
    """
    ordered = tuple(rows)
    for index, row in enumerate(ordered):
        if row.current_hash == anchor.head_hash:
            return AnchorScope(rows=ordered[: index + 1], reachable=True, head_position=index)
    return AnchorScope(rows=ordered, reachable=False, head_position=None)


def detect_rewrite(
    anchor: AnchorRecord,
    rows: Sequence[ChainRow],
    *,
    boundary: datetime,
    max_rows: int,
    max_wall_clock_seconds: float | None = None,
) -> AnchorDetection:
    """Decide, from the anchor alone, whether the anchored window was rewritten.

    The verification is not reimplemented here: the anchored window is handed to
    :func:`orchestrator.audit.chain_walk.walk` with ``recorded_head=anchor.head_hash``,
    so both detection mechanisms - a broken payload/linkage and an unreachable head -
    come from the walker that task 7.2 already property-tests.

    Args:
        anchor: The published commitment. Only :attr:`AnchorRecord.head_hash` is read.
        rows: The presented chain, ordered as written and starting at or before the
            anchored head. A caller that hands over a window opening *after* the head
            will get ``rewritten`` on reachability grounds, which is correct for a
            third party and is why the CLI's ``--since`` default is the committed
            migration boundary rather than an arbitrary date.
        boundary: The committed chain-migration boundary.
        max_rows: Declared row-count bound.
        max_wall_clock_seconds: Declared wall-clock bound, or ``None``.

    Returns:
        An :class:`AnchorDetection` carrying the walk report as its evidence.
    """
    scope = scope_to_anchor(anchor, rows)
    report = walk(
        scope.rows,
        boundary=boundary,
        recorded_head=anchor.head_hash,
        max_rows=max_rows,
        max_wall_clock_seconds=max_wall_clock_seconds,
    )
    if report.status == "broken":
        status: Literal["intact", "rewritten", "unverifiable"] = "rewritten"
    elif report.status == "verified":
        status = "intact"
    else:
        status = "unverifiable"

    detection = AnchorDetection(
        anchored_head=anchor.head_hash,
        head_reachable=scope.reachable,
        anchored_rows=len(scope.rows),
        status=status,
        report=report,
    )
    logger.debug(
        "audit_anchor_detection",
        anchored_head=_short(anchor.head_hash),
        head_reachable=scope.reachable,
        anchored_rows=detection.anchored_rows,
        status=status,
    )
    return detection


def anchor_path(out_dir: Path, date: str) -> Path:
    """``<out_dir>/<YYYY-MM-DD>.json`` - the published artifact path (ADR-033)."""
    return out_dir / f"{date}.json"


def write_anchor(record: AnchorRecord, out_dir: Path = ANCHOR_DIR) -> Path:
    """Write ``record`` as compact canonical JSON (E-S9-03) and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = anchor_path(out_dir, record.date)
    path.write_text(record.to_json() + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Database adapter (the only I/O; makes no verification decision)
# ---------------------------------------------------------------------------


async def _capture_head(session: AsyncSession) -> ChainHead | None:
    """The newest hashed row, i.e. the head as defined in the module docstring.

    ``ORDER BY created_at DESC, id DESC LIMIT 1`` over rows with a non-null
    ``current_hash`` is the maximum of the same total order :func:`select_head` walks,
    so the SQL path and the pure path commit to the same head.
    """
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
    created_at: datetime | None = row[1]
    return ChainHead(
        head_hash=str(row[2]),
        row_id=str(row[0]),
        created_at=None if created_at is None else _as_utc(created_at),
    )


async def read_head(dsn: str) -> ChainHead | None:
    """Read the chain head from ``dsn``.

    Raises:
        HeadUnavailableError: The engine could not be built or the read failed.
    """
    try:
        engine = create_async_engine(dsn)
    except (SQLAlchemyError, ModuleNotFoundError, ValueError) as exc:
        raise HeadUnavailableError(f"cannot open the audit database: {exc}") from exc
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await _capture_head(session)
    except (SQLAlchemyError, OSError) as exc:
        raise HeadUnavailableError(f"cannot read the audit-chain head: {exc}") from exc
    finally:
        await engine.dispose()


async def anchor_today(
    dsn: str,
    out_dir: Path = ANCHOR_DIR,
    *,
    now: datetime | None = None,
) -> int:
    """Publish today's anchor. Returns the process exit code.

    ``0`` an anchor committing to the chain head was written; :data:`EXIT_UNAVAILABLE`
    (``2``) nothing was anchored - the head could not be read, or the chain carries no
    hashed row. ``2`` is deliberately not ``0``: a scheduled run that anchored nothing
    produced no tamper evidence, and reporting that as success is the silence
    ``scripts/audit/anchor_truth.py`` exists to break (I-7).
    """
    stamped = _as_utc(now) if now is not None else datetime.now(UTC)
    try:
        head = await read_head(dsn)
    except HeadUnavailableError as exc:
        logger.error("audit_anchor_unavailable", reason=str(exc))
        return EXIT_UNAVAILABLE

    if head is None:
        logger.warning(
            "audit_anchor_no_hashed_row",
            date=stamped.strftime("%Y-%m-%d"),
            reason="audit_consensus holds no row with a current_hash; nothing to commit to",
        )
        return EXIT_UNAVAILABLE

    record = build_anchor_record(head, anchored_at=stamped)
    path = write_anchor(record, out_dir)
    logger.info(
        "audit_anchor_written",
        path=path.name,
        date=record.date,
        head=_short(record.head_hash),
        head_row_id=record.head_row_id,
        schema_version=record.schema_version,
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """``python -m orchestrator.audit.anchorer [--dsn ...] [--out ...]``."""
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
    code = asyncio.run(anchor_today(str(args.dsn), Path(args.out)))
    if code != EXIT_OK:
        # The entry point may print; the library path above logs. ASCII only.
        print(
            "no anchor was published: the audit-chain head could not be read or the "
            "chain holds no hashed row",
            file=sys.stderr,
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
