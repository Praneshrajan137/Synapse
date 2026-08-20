"""Pure audit-chain walker: linkage verification, not self-consistency (R6, AD-7/AD-8).

Feature: purpose-achievement-audit, task 7.1.

The verifier that exists today (``scripts/synapse_cli/audit_verify.py:71``) checks each
row against **its own stored** ``prev_hash``::

    expected = hash_payload_for_row(row.prev_hash or prev_hash, _to_canonical(row))

The walked ``prev_hash`` is reassigned from every row's ``current_hash`` and no
comparison ever consumes it, so nothing asserts that a row's stored ``prev_hash``
equals the ``current_hash`` of the row that actually precedes it in the ordered walk.
That single fallback is why row deletion, segment re-linking, and adjacent reorder are
invisible: each surviving row remains self-consistent. The fallback is **removed** here
(AD-8). This module compares stored links against walked links, which is the whole
detection capability the requirement is about.

**Purity (AD-7).** :func:`walk` takes an already-materialised, ordered row sequence and
returns a :class:`WalkReport`. No database, no session, no I/O, no ambient clock: the
wall-clock bound is measured through an injected monotonic ``clock``, so a bound-exceeded
walk is deterministically reproducible in a test. Purity is what makes the six tamper
classes property-testable without Postgres, and therefore testable at all under I-0. The
database read, the metric increment, and the printed report are the CLI adapter's job
(task 7.3).

**I-4.** ``make_canonical_row`` and ``hash_payload_for_row`` are imported and called,
never reimplemented and never modified: the chain is byte-pinned by a literal-digest test
(``packages/tests/test_audit_chain.py``). This module is a read-path addition only.

Conventions this module fixes, each load-bearing for task 7.2
----------------------------------------------------------------

1. **Walk order is the caller's order.** The row sequence is *never* re-sorted. R6.4
   (adjacent reorder, stored bytes unchanged) is only detectable if the walk honours the
   order it was handed; a defensive ``sorted()`` here would silently delete that
   detection. Ordering (``ORDER BY created_at, id``) belongs to the snapshot adapter.

2. **At most one break per row, in a fixed precedence:**
   ``NULL_AFTER_BOUNDARY`` > ``LINKAGE`` > ``PAYLOAD``. The precedence reports the
   *structural* cause rather than its arithmetic shadow. Deleting a row makes the
   successor's stored ``prev_hash`` point at a hash no longer in the walk, which fails
   linkage *and*, consequentially, the payload recompute; reporting both would say
   "payload tampering" about a row whose bytes were never touched.

3. **``DELETE_AND_RELINK`` is reported as ``PAYLOAD``** - the convention
   ``packages/tests/strategies_audit.py::_EXPECTED_BREAK_KINDS`` left open, and task 7.2
   may now narrow that operator to this single kind. Rationale: the operator rewrites the
   successor's ``prev_hash`` to the surviving predecessor's ``current_hash`` but does not
   recompute the successor's ``current_hash`` (recomputing forward would re-hash the whole
   tail - a different attack). The attacker has therefore *made linkage consistent*, so
   linkage passes honestly and the surviving evidence is the un-recomputed
   ``current_hash``: a payload break. Under precedence (2) exactly one kind is reported,
   and the pair (payload break, linkage intact) is the fingerprint of a re-link rather
   than of a byte edit.

4. **The payload recompute chains from the walked predecessor's stored
   ``current_hash``**, per design E4.1, and the walked value is advanced from each row's
   *stored* ``current_hash`` whether or not that row broke. Advancing from the stored
   value is what keeps a single tamper a single break instead of cascading through every
   later row and burying the first divergence (R6.1). Note the two comparisons coincide
   whenever linkage holds, and precedence (2) means the payload comparison only runs when
   linkage holds - so "recompute from ``prev_walked``" and "recompute from the stored
   ``prev_hash``" are behaviourally identical here, and the fallback's blindness came
   purely from the missing linkage comparison, not from the recompute's input.

5. **``HEAD_UNREACHABLE`` is reachability, not final position.** The break fires when
   ``recorded_head`` is carried by *no* row in the walked snapshot. A reorder that moves
   the head row without removing it is a linkage fault and is reported as such; only a
   truncation (or a rewrite of the head row itself) makes the recorded head unreachable
   (R6.5).

6. **A null hash is never a silent skip.** Pre-boundary null rows are counted as
   ``legacy``, excluded from ``verified`` (R6.7), and do not advance the walked link -
   they carry no hash to chain from. After the committed migration boundary a null is a
   break (R6.8). A null ``prev_hash`` on the *first* hashed row is the legitimate genesis
   link and is normalised to ``GENESIS_HASH``, not charged as a break.

7. **Absence of proof is never a pass (I-7).** Zero rows, or a snapshot of nothing but
   legacy rows, is ``not_verified`` - never ``verified`` with ``breaks=0`` (R6.9). A walk
   that hits its row-count or wall-clock bound is ``not_verified`` and names the bound it
   hit (R6.13); it never reports a truncated walk as verified.

Bounds and the migration boundary are read from
``infrastructure/quality/audit-chain-bounds.yaml`` (AD-13) via :func:`load_chain_bounds`,
never inlined as literals.
"""

from __future__ import annotations

import time
from collections.abc import Mapping  # runtime import: a Pydantic field annotation
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal

import structlog
import yaml
from pydantic import BaseModel, ConfigDict

from orchestrator.audit.hash_chain import GENESIS_HASH, hash_payload_for_row

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

logger = structlog.get_logger(__name__)

__all__ = [
    "BOUNDS_PATH",
    "BreakKind",
    "ChainBounds",
    "ChainBreak",
    "ChainRow",
    "WalkReport",
    "load_chain_bounds",
    "walk",
]

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
BOUNDS_PATH: Final[Path] = REPO_ROOT / "infrastructure" / "quality" / "audit-chain-bounds.yaml"

#: Rows between wall-clock samples. A bound check per row would cost 5M ``monotonic()``
#: calls at ``max_rows``; sampling keeps the check cheap while still bounding the walk to
#: the declared budget plus at most one batch.
_CLOCK_SAMPLE_ROWS: Final[int] = 1024

#: Hash prefix length in report details, matching the existing CLI's convention.
_PREFIX: Final[int] = 12


# ---------------------------------------------------------------------------
# Committed bounds (AD-13 - read, never inlined)
# ---------------------------------------------------------------------------


class ChainBounds(BaseModel):
    """The committed migration boundary and walk bounds.

    Mirrors ``packages/tests/strategies_audit.py::ChainBounds`` deliberately: that one is
    the test-side reader, this is the production-side reader, and both parse the same
    committed file so a reviewed boundary correction moves both at once.
    """

    model_config = ConfigDict(frozen=True)

    migration_boundary: datetime
    max_rows: int
    max_wall_clock_seconds: int
    anchor_max_age_hours: int


def load_chain_bounds(path: Path | None = None) -> ChainBounds:
    """Load the committed chain bounds (``encoding='utf-8'`` per E-S13-07)."""
    source = path if path is not None else BOUNDS_PATH
    payload: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
    boundary_raw = str(payload["migration_boundary"]["value"])
    walk_bounds: Mapping[str, Any] = payload["walk_bounds"]
    return ChainBounds(
        migration_boundary=datetime.fromisoformat(boundary_raw.replace("Z", "+00:00")),
        max_rows=int(walk_bounds["max_rows"]),
        max_wall_clock_seconds=int(walk_bounds["max_wall_clock_seconds"]),
        anchor_max_age_hours=int(payload["anchor_freshness"]["max_age_hours"]),
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ChainRow(BaseModel):
    """One ``audit_consensus`` row as the walker sees it.

    Frozen: the walker must not be able to repair the evidence it is judging.
    Constructible from the shared test draft as ``ChainRow(**draft.as_kwargs())``
    (``packages/tests/strategies_audit.py::ChainRowDraft``), which is how the E4
    properties build chains without either module importing the other.

    ``canonical`` is the output of the untouched ``make_canonical_row`` (I-4), passed
    through unmodified - the walker never rebuilds it and never edits a key.
    """

    model_config = ConfigDict(frozen=True)

    row_id: int
    created_at: datetime
    prev_hash: str | None
    current_hash: str | None
    canonical: Mapping[str, Any]


class BreakKind(StrEnum):
    """The four ways a walk can find the chain broken."""

    PAYLOAD = "payload"
    """Recompute from the walked link does not equal the stored ``current_hash``."""

    LINKAGE = "linkage"
    """Stored ``prev_hash`` does not equal the walked predecessor's ``current_hash``."""

    NULL_AFTER_BOUNDARY = "null_after_boundary"
    """A row created after the committed migration boundary carries a null hash."""

    HEAD_UNREACHABLE = "head_unreachable"
    """The independently recorded head hash is carried by no row in the snapshot."""


class ChainBreak(BaseModel):
    """One divergence, named precisely enough to act on.

    Frozen for the same reason as :class:`ChainRow`: a break record is evidence.
    ``position`` is the 0-based index in the walked sequence and ``row_id`` the stored
    identifier; both are ``None`` for :attr:`BreakKind.HEAD_UNREACHABLE`, which is a
    property of the snapshot as a whole rather than of any row in it.
    """

    model_config = ConfigDict(frozen=True)

    kind: BreakKind
    position: int | None
    row_id: int | None
    stored: str | None
    expected: str | None
    detail: str


class WalkReport(BaseModel):
    """The verdict of one walk over one snapshot.

    ``verified`` counts rows that passed both the linkage and the payload comparison;
    ``legacy`` counts pre-boundary null-hash rows and is deliberately *not* added into it
    (R6.7). ``walked`` is the size of the snapshot, so ``verified``, ``legacy``, and the
    row-level breaks are all readable against the same denominator.
    """

    walked: int
    verified: int
    legacy: int
    breaks: tuple[ChainBreak, ...]
    snapshot_upper_bound: int
    head_hash: str | None
    status: Literal["verified", "broken", "not_verified"]
    bound_exceeded: str | None = None

    @property
    def first_break(self) -> ChainBreak | None:
        """The first divergence in walk order - the row R6.1/R6.2/R6.4 must name."""
        return self.breaks[0] if self.breaks else None

    @property
    def exit_code(self) -> int:
        """``0`` verified / ``1`` broken / ``2`` not verified, for the CLI (E4.2).

        ``2`` covers zero rows, an all-legacy snapshot, and a bound-exceeded walk: none
        of those verified the chain, and none of them found a break either. Reporting
        them as ``0`` is the exact dishonesty I-7 forbids.
        """
        if self.status == "verified":
            return 0
        return 1 if self.status == "broken" else 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _as_utc(value: datetime) -> datetime:
    """Normalise to UTC, treating a naive timestamp as UTC.

    Postgres ``TIMESTAMP WITHOUT TIME ZONE`` reads back naive while the committed
    boundary is tz-aware; comparing the two raises ``TypeError``. Coercing here keeps the
    boundary comparison from being an accidental crash on a real snapshot.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _link_value(value: str | None) -> str:
    """Normalise a chain link, where a null genesis link means ``GENESIS_HASH``.

    ``hash_payload_for_row`` already applies ``prev_hash or GENESIS_HASH``, so a stored
    ``None`` and a stored all-zero digest are the same link. The comparison must agree
    with the hash function or the genesis row reports a phantom linkage break.
    """
    return value or GENESIS_HASH


def _short(value: str | None) -> str:
    """ASCII-safe hash prefix for a report detail."""
    return "none" if value is None else value[:_PREFIX]


def _upper_bound(rows: Sequence[ChainRow]) -> int:
    """Highest ``row_id`` in the snapshot; ``0`` when the snapshot is empty (R6.10)."""
    return max((row.row_id for row in rows), default=0)


def _bound_report(
    rows: Sequence[ChainRow],
    *,
    bound: str,
    walked: int,
    verified: int,
    legacy: int,
    breaks: Sequence[ChainBreak],
    head: str | None,
) -> WalkReport:
    """A bound-exceeded verdict: ``not_verified``, naming the bound (R6.13).

    Breaks found before the bound was hit are preserved - they are real evidence - but
    the status is never ``broken``, because "broken" claims a completed walk and never
    ``verified``, because the walk stopped short.
    """
    return WalkReport(
        walked=walked,
        verified=verified,
        legacy=legacy,
        breaks=tuple(breaks),
        snapshot_upper_bound=_upper_bound(rows),
        head_hash=head,
        status="not_verified",
        bound_exceeded=bound,
    )


# ---------------------------------------------------------------------------
# The walk
# ---------------------------------------------------------------------------


def walk(
    rows: Sequence[ChainRow],
    *,
    boundary: datetime,
    recorded_head: str | None,
    max_rows: int,
    max_wall_clock_seconds: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> WalkReport:
    """Walk an ordered snapshot and report its integrity.

    Args:
        rows: The snapshot, **already ordered** as the chain was written
            (``ORDER BY created_at, id``). Never re-sorted here: R6.4 depends on the walk
            honouring the caller's order.
        boundary: The committed chain-migration boundary. Null hashes before it are
            legacy (R6.7); after it they are breaks (R6.8).
        recorded_head: The independently recorded head hash (an anchor, or a chain-head
            record). ``None`` disables the reachability check; a value not carried by any
            row in the snapshot is ``HEAD_UNREACHABLE`` (R6.5).
        max_rows: Declared row-count bound. A larger snapshot is ``not_verified`` naming
            the bound - never a silently truncated walk (R6.13).
        max_wall_clock_seconds: Declared wall-clock bound, sampled every
            ``_CLOCK_SAMPLE_ROWS`` rows. ``None`` disables it.
        clock: Monotonic time source, injected so the bound is deterministically
            testable without sleeping.

    Returns:
        A :class:`WalkReport`. ``status`` is ``verified`` only when at least one row
        verified and nothing broke.
    """
    started = clock()
    total = len(rows)

    if total > max_rows:
        logger.warning("audit_chain_walk_row_bound_exceeded", rows=total, max_rows=max_rows)
        return _bound_report(
            rows,
            bound=f"max_rows={max_rows} (snapshot={total})",
            walked=0,
            verified=0,
            legacy=0,
            breaks=(),
            head=None,
        )

    verified = 0
    legacy = 0
    breaks: list[ChainBreak] = []
    # ``None`` means "no hashed predecessor walked yet", i.e. the next hashed row is the
    # genesis row and its null ``prev_hash`` is legitimate.
    prev_walked: str | None = None
    seen_hashes: set[str] = set()
    boundary_utc = _as_utc(boundary)

    for position, row in enumerate(rows):
        if (
            max_wall_clock_seconds is not None
            and position % _CLOCK_SAMPLE_ROWS == 0
            and clock() - started > max_wall_clock_seconds
        ):
            logger.warning(
                "audit_chain_walk_wall_clock_bound_exceeded",
                position=position,
                max_wall_clock_seconds=max_wall_clock_seconds,
            )
            return _bound_report(
                rows,
                bound=(
                    f"max_wall_clock_seconds={max_wall_clock_seconds} "
                    f"(stopped at row {position})"
                ),
                walked=position,
                verified=verified,
                legacy=legacy,
                breaks=breaks,
                head=prev_walked,
            )

        post_boundary = _as_utc(row.created_at) >= boundary_utc

        # --- an unhashed row: legacy before the boundary, a break after it ----------
        if row.current_hash is None:
            if not post_boundary:
                legacy += 1
                continue
            breaks.append(
                ChainBreak(
                    kind=BreakKind.NULL_AFTER_BOUNDARY,
                    position=position,
                    row_id=row.row_id,
                    stored=None,
                    expected=None,
                    detail=(
                        f"row={row.row_id} position={position} has a null current_hash but was "
                        f"created after the chain-migration boundary "
                        f"{boundary_utc.isoformat()}"
                    ),
                )
            )
            # No hash to chain from: the walked link is deliberately left where it was
            # rather than advanced to None, so the next hashed row is still checked
            # against the last real link instead of being excused as a genesis row.
            continue

        # --- a null prev_hash on a non-genesis post-boundary row (R6.8) -------------
        if row.prev_hash is None and prev_walked is not None and post_boundary:
            breaks.append(
                ChainBreak(
                    kind=BreakKind.NULL_AFTER_BOUNDARY,
                    position=position,
                    row_id=row.row_id,
                    stored=None,
                    expected=_short(prev_walked),
                    detail=(
                        f"row={row.row_id} position={position} has a null prev_hash but is not "
                        f"the genesis row and was created after the chain-migration boundary "
                        f"{boundary_utc.isoformat()}"
                    ),
                )
            )
            seen_hashes.add(row.current_hash)
            prev_walked = row.current_hash
            continue

        # --- linkage: stored link vs the walked predecessor (AD-8) ------------------
        expected_link = _link_value(prev_walked)
        stored_link = _link_value(row.prev_hash)
        if stored_link != expected_link:
            breaks.append(
                ChainBreak(
                    kind=BreakKind.LINKAGE,
                    position=position,
                    row_id=row.row_id,
                    stored=_short(row.prev_hash),
                    expected=_short(expected_link),
                    detail=(
                        f"row={row.row_id} position={position} stored prev_hash="
                        f"{_short(row.prev_hash)} but the preceding row in the walk hashes to "
                        f"{_short(expected_link)}"
                    ),
                )
            )
            seen_hashes.add(row.current_hash)
            prev_walked = row.current_hash
            continue

        # --- payload: recompute from the walked link (R6.1) -------------------------
        recomputed = hash_payload_for_row(prev_walked, dict(row.canonical))
        if recomputed != row.current_hash:
            breaks.append(
                ChainBreak(
                    kind=BreakKind.PAYLOAD,
                    position=position,
                    row_id=row.row_id,
                    stored=_short(row.current_hash),
                    expected=_short(recomputed),
                    detail=(
                        f"row={row.row_id} position={position} stored current_hash="
                        f"{_short(row.current_hash)} but its content and link recompute to "
                        f"{_short(recomputed)}"
                    ),
                )
            )
        else:
            verified += 1

        seen_hashes.add(row.current_hash)
        prev_walked = row.current_hash

    # --- head reachability (R6.5) --------------------------------------------------
    if recorded_head is not None and recorded_head not in seen_hashes:
        breaks.append(
            ChainBreak(
                kind=BreakKind.HEAD_UNREACHABLE,
                position=None,
                row_id=None,
                stored=_short(prev_walked),
                expected=_short(recorded_head),
                detail=(
                    f"recorded head {_short(recorded_head)} is carried by no row in the walked "
                    f"snapshot; the walk ended at {_short(prev_walked)}"
                ),
            )
        )

    if breaks:
        status: Literal["verified", "broken", "not_verified"] = "broken"
    elif verified == 0:
        # Zero rows, or nothing but legacy rows: no break found and nothing proved (R6.9).
        status = "not_verified"
    else:
        status = "verified"

    report = WalkReport(
        walked=total,
        verified=verified,
        legacy=legacy,
        breaks=tuple(breaks),
        snapshot_upper_bound=_upper_bound(rows),
        head_hash=prev_walked,
        status=status,
    )

    if status == "verified":
        logger.debug(
            "audit_chain_walk_verified",
            verified=verified,
            legacy=legacy,
            snapshot_upper_bound=report.snapshot_upper_bound,
        )
    else:
        first = report.first_break
        logger.warning(
            "audit_chain_walk_not_verified",
            status=status,
            walked=total,
            verified=verified,
            legacy=legacy,
            breaks=len(breaks),
            first_break_kind=None if first is None else str(first.kind),
            first_break_row=None if first is None else first.row_id,
        )
    return report
