"""Deterministic mutation killers for the audit-chain walker (Requirement 6, design E4.1).

Feature: purpose-achievement-audit, task 12.2 - the mutation gate on
``orchestrator/audit/chain_walk.py``.

Property 18 and the R6.15 scope test quantify over generated chains: the right instrument
for the tamper classes, and the wrong one for a mutation gate. A mutant they kill dies by
shrinking, mutmut reads a kill slower than twice its baseline as ``ok_suspicious``, and
``scripts/check_mutation_threshold.py`` counts that as SURVIVING. And several documented
behaviours - the exit-code mapping, the detail texts, both walk bounds and the clock
sampling, the log events - are pinned by no generated example; the bounds and the clock
are never even reached. Each test below pins one of them with a hand-built chain and an
exact expected value, and the mutation runner names this file first so ``-x`` ends a
killed mutant's run in seconds.

Not killable by any test, so not attempted: a mutation inside a function-local annotation
(never evaluated - PEP 526, and ``from __future__ import annotations``), and dropping the
``"Z"`` replacement in ``load_chain_bounds`` (CPython 3.11's ``datetime.fromisoformat``
already reads a trailing ``Z`` as UTC).

No Hypothesis, no database, no network, no sleep. Rows are the shared ``ChainRowDraft`` and
``CanonicalDecision`` from ``strategies_audit``, hashed by the untouched production
primitives (I-4); the wall-clock bound is driven by an injected, scripted clock (AD-7).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Final
from uuid import UUID

import pytest
import structlog
from pydantic import ValidationError
from structlog.testing import capture_logs

from orchestrator.audit.chain_walk import (
    BOUNDS_PATH,
    BreakKind,
    ChainBounds,
    ChainRow,
    WalkReport,
    load_chain_bounds,
    walk,
)
from orchestrator.audit.hash_chain import GENESIS_HASH, hash_payload_for_row
from packages.tests.strategies_audit import (
    BREAK_KIND_HEAD_UNREACHABLE,
    BREAK_KIND_LINKAGE,
    BREAK_KIND_NULL_AFTER_BOUNDARY,
    BREAK_KIND_PAYLOAD,
    CanonicalDecision,
    ChainRowDraft,
    Perturbation,
    apply_perturbation,
    head_hash,
    nullify_hashes,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

    from structlog.typing import EventDict

#: The boundary every walk here is handed. ``walk`` takes it as a parameter (AD-7), so one
#: pinned instant makes every rendered detail a literal a reader can check by eye. It is
#: the committed instant, but nothing here reads the committed file for it: a reviewed
#: correction of the boundary must not turn this file red.
BOUNDARY: Final[datetime] = datetime(2026, 5, 24, 11, 32, 51, tzinfo=UTC)
BOUNDARY_TEXT: Final[str] = "2026-05-24T11:32:51+00:00"

#: India Standard Time, the offset the boundary's provenance commit was authored in.
IST: Final[timezone] = timezone(timedelta(hours=5, minutes=30))

#: Report details quote a 12-character hash prefix (the existing CLI's convention).
HASH_PREFIX: Final[int] = 12

#: A bounds file whose boundary carries a ``Z`` suffix, as the committed file's does.
BOUNDS_WITH_A_Z_SUFFIX: Final[str] = """\
migration_boundary:
  value: "2026-05-24T11:32:51Z"
walk_bounds:
  max_rows: 7
  max_wall_clock_seconds: 30
anchor_freshness:
  max_age_hours: 48
"""


# ---------------------------------------------------------------------------
# Fixtures and builders
# ---------------------------------------------------------------------------


@pytest.fixture
def captured_events() -> Iterator[list[EventDict]]:
    """Every structlog event emitted during the test, whatever the ambient configuration.

    ``capture_logs`` swaps the processor chain but keeps the configured wrapper class, and a
    level-filtering wrapper drops ``debug`` and ``warning`` before any processor runs.
    Several ``digital_twin`` test modules install exactly that wrapper at import, and
    ``ci.yml`` collects them in the same session as this file, so the wrapper is made
    unfiltered for the test and the caller's configuration is restored afterwards.
    """
    saved = structlog.get_config()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.NOTSET),
        cache_logger_on_first_use=False,
    )
    try:
        with capture_logs() as events:
            yield events
    finally:
        structlog.configure(**saved)


class _ScriptedClock:
    """A monotonic clock that returns the readings it was scripted with, and no more.

    ``walk`` documents its sampling: one reading when it starts, then one every
    ``_CLOCK_SAMPLE_ROWS`` (1,024) rows. Reading past the script is itself a breach of that
    contract, so it fails the test instead of inventing a time.
    """

    def __init__(self, *readings: float) -> None:
        self._readings = readings
        self.taken = 0

    def __call__(self) -> float:
        if self.taken == len(self._readings):
            raise AssertionError(
                f"the walk read its clock {self.taken + 1} times; "
                f"the sampling contract allows {len(self._readings)} here"
            )
        reading = self._readings[self.taken]
        self.taken += 1
        return reading


def _decision(seq: int) -> CanonicalDecision:
    """A fixed decision, so every hash in this file is the same on every run."""
    return CanonicalDecision(
        decision_id=UUID(int=seq),
        tier="tier_2",
        selected_action={"action": "restock", "sku_id": "SKU001", "quantity": seq},
        pareto_weights={"cost": 0.5, "time": 0.5},
        confidence=0.75,
        proposals=[{"agent_name": "inventory_sentinel", "confidence": 0.8}],
        audit_trace=[f"seq={seq}"],
    )


def _hashed(row_id: int, *, prev: str | None, created_at: datetime) -> ChainRowDraft:
    """A row as the writer stores it: its canonical content hashed onto ``prev`` (I-4)."""
    canonical = _decision(row_id).canonical()
    return ChainRowDraft(
        row_id=row_id,
        created_at=created_at,
        prev_hash=prev,
        current_hash=hash_payload_for_row(prev, canonical),
        canonical=canonical,
    )


def _unhashed(row_id: int, *, created_at: datetime) -> ChainRowDraft:
    """A row whose chain columns are NULL: legacy before the boundary, a break after it."""
    return ChainRowDraft(
        row_id=row_id,
        created_at=created_at,
        prev_hash=None,
        current_hash=None,
        canonical=_decision(row_id).canonical(),
    )


def _legacy_prefix(count: int) -> tuple[ChainRowDraft, ...]:
    """``count`` pre-boundary rows with NULL chain columns, oldest first (R6.7)."""
    return tuple(
        _unhashed(row_id, created_at=BOUNDARY - timedelta(seconds=count + 1 - row_id))
        for row_id in range(1, count + 1)
    )


def _chain(length: int, *, first_id: int = 1) -> tuple[ChainRowDraft, ...]:
    """``length`` correctly linked rows after the boundary, starting from genesis."""
    rows: list[ChainRowDraft] = []
    prev: str | None = None
    for row_id in range(first_id, first_id + length):
        row = _hashed(row_id, prev=prev, created_at=BOUNDARY + timedelta(minutes=row_id))
        rows.append(row)
        prev = row.current_hash
    return tuple(rows)


def _rows(drafts: Sequence[ChainRowDraft]) -> list[ChainRow]:
    """The documented bridge from the shared draft to the walker's frozen model."""
    return [ChainRow(**draft.as_kwargs()) for draft in drafts]


def _walk(
    drafts: Sequence[ChainRowDraft],
    *,
    recorded_head: str | None = None,
    boundary: datetime = BOUNDARY,
) -> WalkReport:
    """Walk through the production walker under the committed row bound (AD-13)."""
    return walk(
        _rows(drafts),
        boundary=boundary,
        recorded_head=recorded_head,
        max_rows=load_chain_bounds().max_rows,
    )


def _prefix(row: ChainRowDraft) -> str:
    """The quoted prefix of a hashed row's stored ``current_hash``."""
    assert row.current_hash is not None, f"row {row.row_id} carries no hash to quote"
    return row.current_hash[:HASH_PREFIX]


# ---------------------------------------------------------------------------
# The verdict, its counts, its exit code and its log event
# ---------------------------------------------------------------------------


def test_a_clean_chain_verifies_every_hashed_row_and_counts_legacy_rows_apart(
    captured_events: list[EventDict],
) -> None:
    """R6.6, R6.7, R6.10: verified; ``verified`` counts hashed rows, ``legacy`` the rest.

    The report also names the head the walk reached and the highest ``row_id`` it fixed,
    and the walk says so in exactly one debug event.
    """
    hashed = _chain(3, first_id=3)
    report = _walk((*_legacy_prefix(2), *hashed), recorded_head=head_hash(hashed))

    assert report.status == "verified"
    assert (report.walked, report.verified, report.legacy) == (5, 3, 2)
    assert report.breaks == ()
    assert report.first_break is None
    assert report.bound_exceeded is None
    assert report.snapshot_upper_bound == 5
    assert report.head_hash == hashed[-1].current_hash
    assert captured_events == [
        {
            "event": "audit_chain_walk_verified",
            "log_level": "debug",
            "verified": 3,
            "legacy": 2,
            "snapshot_upper_bound": 5,
        },
    ]


def test_one_verified_row_verifies_a_walk_and_zero_verified_rows_never_do() -> None:
    """R6.9: zero rows, or nothing but legacy rows, is ``not_verified`` - never a clean pass."""
    single = _walk(_chain(1))
    assert (single.status, single.verified) == ("verified", 1)

    empty = _walk(())
    assert empty.status == "not_verified"
    assert (empty.walked, empty.verified, empty.legacy, empty.breaks) == (0, 0, 0, ())
    assert (empty.snapshot_upper_bound, empty.head_hash) == (0, None)

    legacy_only = _walk(_legacy_prefix(2))
    assert legacy_only.status == "not_verified"
    assert (legacy_only.walked, legacy_only.verified, legacy_only.legacy) == (2, 0, 2)
    assert legacy_only.breaks == ()


def test_a_walk_exits_0_verified_1_broken_and_2_for_every_unproved_outcome() -> None:
    """E4.2: ``2`` covers zero rows, an all-legacy snapshot and a bound-exceeded walk.

    None of those verified the chain and none found a break, so reporting any of them as
    ``0`` would be the dishonesty I-7 forbids.
    """
    chain = _chain(3)
    over_the_bound = walk(_rows(chain), boundary=BOUNDARY, recorded_head=None, max_rows=2)
    verdicts = {
        "verified": _walk(chain),
        "broken": _walk(apply_perturbation(chain, Perturbation.ALTER_PAYLOAD, 1)),
        "zero rows": _walk(()),
        "all legacy": _walk(_legacy_prefix(1)),
        "over the row bound": over_the_bound,
    }
    assert {name: (report.status, report.exit_code) for name, report in verdicts.items()} == {
        "verified": ("verified", 0),
        "broken": ("broken", 1),
        "zero rows": ("not_verified", 2),
        "all legacy": ("not_verified", 2),
        "over the row bound": ("not_verified", 2),
    }


def test_every_unproved_verdict_is_logged_as_a_warning_naming_its_first_break(
    captured_events: list[EventDict],
) -> None:
    """A broken walk names its first break's kind and row; a walk with none says ``None``."""
    _walk(apply_perturbation(_chain(3), Perturbation.ALTER_PAYLOAD, 1))
    _walk(())

    assert captured_events == [
        {
            "event": "audit_chain_walk_not_verified",
            "log_level": "warning",
            "status": "broken",
            "walked": 3,
            "verified": 2,
            "legacy": 0,
            "breaks": 1,
            "first_break_kind": "payload",
            "first_break_row": 2,
        },
        {
            "event": "audit_chain_walk_not_verified",
            "log_level": "warning",
            "status": "not_verified",
            "walked": 0,
            "verified": 0,
            "legacy": 0,
            "breaks": 0,
            "first_break_kind": None,
            "first_break_row": None,
        },
    ]


# ---------------------------------------------------------------------------
# Row-level breaks and the details an operator acts on
# ---------------------------------------------------------------------------


def test_an_altered_payload_is_one_payload_break_quoting_both_hash_prefixes() -> None:
    """R6.1: content edited, hashes untouched - one break, and it does not cascade.

    The walk advances from each row's stored ``current_hash``, so the row after the edit
    still verifies against what the edited row stores.
    """
    chain = _chain(3)
    tampered = apply_perturbation(chain, Perturbation.ALTER_PAYLOAD, 1)
    report = _walk(tampered)

    stored = _prefix(chain[1])
    recomputed = hash_payload_for_row(chain[0].current_hash, dict(tampered[1].canonical))
    expected = recomputed[:HASH_PREFIX]
    assert report.status == "broken"
    assert report.verified == 2
    assert len(report.breaks) == 1
    payload = report.breaks[0]
    assert (payload.kind, payload.position, payload.row_id) == (BreakKind.PAYLOAD, 1, 2)
    assert (payload.stored, payload.expected) == (stored, expected)
    assert len(stored) == len(expected) == HASH_PREFIX
    assert payload.detail == (
        f"row=2 position=1 stored current_hash={stored} but its content and link "
        f"recompute to {expected}"
    )


def test_a_deleted_row_is_one_linkage_break_at_its_successor_quoting_both_links() -> None:
    """R6.2: the successor's stored link names a row the walk never reached.

    The walk re-anchors on the successor's stored hash, so the row after it verifies.
    """
    chain = _chain(4)
    report = _walk(apply_perturbation(chain, Perturbation.DELETE_ROW, 1))

    stored, walked = _prefix(chain[1]), _prefix(chain[0])
    assert report.status == "broken"
    assert report.verified == 2
    assert len(report.breaks) == 1
    linkage = report.breaks[0]
    assert (linkage.kind, linkage.position, linkage.row_id) == (BreakKind.LINKAGE, 1, 3)
    assert (linkage.stored, linkage.expected) == (stored, walked)
    assert linkage.detail == (
        f"row=3 position=1 stored prev_hash={stored} but the preceding row in the walk "
        f"hashes to {walked}"
    )


def test_a_nulled_row_is_a_break_and_the_next_row_is_held_to_the_last_real_link() -> None:
    """R6.8: a NULL hash after the boundary is a break, never folded into ``legacy``.

    A NULL row has no hash to chain from, so the walked link stays where it was and the
    next row is compared with the last real link - not excused as a fresh genesis row,
    and not skipped: the walk carries on past the NULL row.
    """
    chain = _chain(3)
    report = _walk(nullify_hashes(chain, 1))

    assert [(item.kind, item.position, item.row_id) for item in report.breaks] == [
        (BreakKind.NULL_AFTER_BOUNDARY, 1, 2),
        (BreakKind.LINKAGE, 2, 3),
    ]
    nulled, successor = report.breaks
    assert (nulled.stored, nulled.expected) == (None, None)
    assert nulled.detail == (
        "row=2 position=1 has a null current_hash but was created after the "
        f"chain-migration boundary {BOUNDARY_TEXT}"
    )
    assert (successor.stored, successor.expected) == (_prefix(chain[1]), _prefix(chain[0]))
    assert (report.legacy, report.verified) == (0, 1)


def test_a_null_prev_hash_mid_chain_is_one_break_and_the_walk_resumes_from_its_hash() -> None:
    """R6.8: after the boundary only the genesis row may carry a NULL ``prev_hash``.

    The walk advances from the offending row's stored ``current_hash`` (convention 4), so
    one NULL link is one break rather than a cascade through every later row.
    """
    chain = _chain(3)
    tampered = (chain[0], replace(chain[1], prev_hash=None), chain[2])
    report = _walk(tampered, recorded_head=head_hash(chain))

    assert len(report.breaks) == 1
    null_link = report.breaks[0]
    assert null_link.kind is BreakKind.NULL_AFTER_BOUNDARY
    assert (null_link.position, null_link.row_id) == (1, 2)
    assert (null_link.stored, null_link.expected) == (None, _prefix(chain[0]))
    assert null_link.detail == (
        "row=2 position=1 has a null prev_hash but is not the genesis row and was created "
        f"after the chain-migration boundary {BOUNDARY_TEXT}"
    )
    assert report.verified == 2
    assert report.head_hash == chain[2].current_hash


# ---------------------------------------------------------------------------
# Head reachability (R6.5, convention 5)
# ---------------------------------------------------------------------------


def test_a_truncated_tail_is_an_unreachable_head_naming_where_the_walk_ended() -> None:
    """R6.5: a truncation is visible only because a head was recorded independently."""
    chain = _chain(3)
    survivors = apply_perturbation(chain, Perturbation.TRUNCATE_TAIL, 2)
    report = _walk(survivors, recorded_head=head_hash(chain))

    recorded, walk_end = _prefix(chain[2]), _prefix(chain[1])
    assert report.status == "broken"
    assert (report.verified, report.head_hash) == (2, chain[1].current_hash)
    assert len(report.breaks) == 1
    unreachable = report.breaks[0]
    assert unreachable.kind is BreakKind.HEAD_UNREACHABLE
    assert (unreachable.position, unreachable.row_id) == (None, None)
    assert (unreachable.stored, unreachable.expected) == (walk_end, recorded)
    assert unreachable.detail == (
        f"recorded head {recorded} is carried by no row in the walked snapshot; "
        f"the walk ended at {walk_end}"
    )


def test_a_recorded_head_carried_by_any_walked_row_is_reachable_wherever_it_sits() -> None:
    """Convention 5: reachability, not final position; a ``None`` head disables the check.

    An anchor taken before later appends names a row in the middle of the snapshot.
    """
    chain = _chain(3)
    assert _walk(chain, recorded_head=chain[1].current_hash).status == "verified"
    assert _walk(chain, recorded_head=None).status == "verified"


def test_an_anchor_no_hashed_row_can_reach_is_a_break_whose_walk_ended_at_none() -> None:
    """Legacy rows carry no hash, so an anchored head is unreachable from them.

    The walk never advanced past a hash, and the detail says so as ``none``.
    """
    report = _walk(_legacy_prefix(2), recorded_head="cd" * 32)

    assert report.status == "broken"
    assert (report.legacy, report.verified, report.head_hash) == (2, 0, None)
    assert len(report.breaks) == 1
    unreachable = report.breaks[0]
    assert unreachable.kind is BreakKind.HEAD_UNREACHABLE
    assert (unreachable.stored, unreachable.expected) == ("none", "cdcdcdcdcdcd")
    assert unreachable.detail == (
        "recorded head cdcdcdcdcdcd is carried by no row in the walked snapshot; "
        "the walk ended at none"
    )


# ---------------------------------------------------------------------------
# The migration boundary and time zones (R6.7, R6.8)
# ---------------------------------------------------------------------------


def test_a_null_row_stamped_exactly_at_the_boundary_is_already_a_break() -> None:
    """The boundary is the earliest instant the chain columns existed, so it is inclusive."""
    report = _walk((_unhashed(1, created_at=BOUNDARY),))

    assert report.legacy == 0
    assert [item.kind for item in report.breaks] == [BreakKind.NULL_AFTER_BOUNDARY]


def test_timestamps_are_compared_as_instants_whatever_offset_or_naivety_they_carry() -> None:
    """``_as_utc``: an offset timestamp is the instant it denotes, and a naive one is UTC.

    Postgres ``TIMESTAMP WITHOUT TIME ZONE`` reads back naive while the boundary is aware;
    comparing the two raw would raise ``TypeError`` instead of classifying the row.
    """
    # 16:30 IST is 11:00 UTC, half an hour BEFORE the boundary: legacy, not a break.
    before_in_ist = _unhashed(1, created_at=datetime(2026, 5, 24, 16, 30, tzinfo=IST))
    before_naive = _unhashed(2, created_at=datetime(2026, 5, 24, 11, 0))
    after_naive = _unhashed(3, created_at=datetime(2026, 5, 24, 12, 0))
    report = _walk((before_in_ist, before_naive, after_naive))

    assert report.legacy == 2
    assert [(item.kind, item.row_id) for item in report.breaks] == [
        (BreakKind.NULL_AFTER_BOUNDARY, 3),
    ]
    # The boundary is rendered in UTC whether it arrives with an offset (the provenance
    # commit's authored time, 17:02:51 IST) or naive.
    for boundary in (datetime(2026, 5, 24, 17, 2, 51, tzinfo=IST), BOUNDARY.replace(tzinfo=None)):
        detail = _walk((after_naive,), boundary=boundary).breaks[0].detail
        assert detail == (
            "row=3 position=0 has a null current_hash but was created after the "
            f"chain-migration boundary {BOUNDARY_TEXT}"
        )


# ---------------------------------------------------------------------------
# The walk bounds (R6.13)
# ---------------------------------------------------------------------------


def test_a_snapshot_over_the_row_bound_is_refused_unread_and_names_the_bound(
    captured_events: list[EventDict],
) -> None:
    """R6.13: over ``max_rows`` the walk reads no row and names the bound that refused it.

    Exactly ``max_rows`` rows is within the bound and is walked in full.
    """
    chain = _chain(3)
    refused = walk(_rows(chain), boundary=BOUNDARY, recorded_head=head_hash(chain), max_rows=2)

    assert refused.status == "not_verified"
    assert refused.bound_exceeded == "max_rows=2 (snapshot=3)"
    assert (refused.walked, refused.verified, refused.legacy, refused.breaks) == (0, 0, 0, ())
    assert (refused.head_hash, refused.snapshot_upper_bound) == (None, 3)
    assert captured_events == [
        {
            "event": "audit_chain_walk_row_bound_exceeded",
            "log_level": "warning",
            "rows": 3,
            "max_rows": 2,
        },
    ]

    at_bound = walk(_rows(chain), boundary=BOUNDARY, recorded_head=head_hash(chain), max_rows=3)
    assert (at_bound.status, at_bound.verified) == ("verified", 3)
    assert at_bound.bound_exceeded is None


def test_a_walk_over_its_clock_budget_stops_at_the_next_sample_and_names_that_row(
    captured_events: list[EventDict],
) -> None:
    """R6.13 with an injected clock (AD-7): one reading at the start, one per 1,024 rows.

    1,000 legacy rows then 25 hashed rows, a 1-second budget, and a clock that advances one
    second per reading: the row-0 sample sees exactly 1 s, which is within the budget, and
    the row-1024 sample sees 2 s, which is over it. So the walk stops at row 1024 - not at
    row 1, not at row 1025, and not never - having read its clock three times for 1,025
    rows, and it keeps the counts and the head of what it did walk.
    """
    hashed = _chain(25, first_id=1001)
    clock = _ScriptedClock(100.0, 101.0, 102.0)
    report = walk(
        _rows((*_legacy_prefix(1000), *hashed)),
        boundary=BOUNDARY,
        recorded_head=None,
        max_rows=load_chain_bounds().max_rows,
        max_wall_clock_seconds=1,
        clock=clock,
    )

    assert report.status == "not_verified"
    assert report.bound_exceeded == "max_wall_clock_seconds=1 (stopped at row 1024)"
    assert (report.walked, report.legacy, report.verified, report.breaks) == (1024, 1000, 24, ())
    assert report.head_hash == hashed[23].current_hash
    assert report.snapshot_upper_bound == 1025
    assert clock.taken == 3
    assert captured_events == [
        {
            "event": "audit_chain_walk_wall_clock_bound_exceeded",
            "log_level": "warning",
            "position": 1024,
            "max_wall_clock_seconds": 1,
        },
    ]


# ---------------------------------------------------------------------------
# The vocabulary and the models
# ---------------------------------------------------------------------------


def test_each_break_kind_reports_the_name_the_cli_the_log_and_the_strategies_share() -> None:
    """Four kinds, spelled as the CLI report and the log's ``first_break_kind`` print them.

    ``strategies_audit`` restates them as plain strings so that it never imports the
    walker; the two spellings must agree byte for byte.
    """
    assert {kind.name: str(kind) for kind in BreakKind} == {
        "PAYLOAD": "payload",
        "LINKAGE": "linkage",
        "NULL_AFTER_BOUNDARY": "null_after_boundary",
        "HEAD_UNREACHABLE": "head_unreachable",
    }
    assert {str(kind) for kind in BreakKind} == {
        BREAK_KIND_PAYLOAD,
        BREAK_KIND_LINKAGE,
        BREAK_KIND_NULL_AFTER_BOUNDARY,
        BREAK_KIND_HEAD_UNREACHABLE,
    }


def test_rows_breaks_and_bounds_refuse_reassignment_because_each_one_is_evidence() -> None:
    """``ChainRow``, ``ChainBreak`` and ``ChainBounds`` are frozen.

    A walker that could edit a row could repair the evidence it is judging; a break or a
    bound that could be edited after the fact could be argued out of its verdict.
    """
    bounds = load_chain_bounds()
    row = _rows(_chain(1))[0]
    first = _walk(apply_perturbation(_chain(2), Perturbation.ALTER_PAYLOAD, 0)).first_break
    assert first is not None

    for model, field, forged in (
        (bounds, "max_rows", bounds.max_rows + 1),
        (row, "current_hash", GENESIS_HASH),
        (first, "kind", BreakKind.LINKAGE),
    ):
        before = getattr(model, field)
        with pytest.raises(ValidationError, match="frozen"):
            setattr(model, field, forged)
        assert getattr(model, field) == before


def test_a_trailing_z_on_the_committed_boundary_is_read_as_utc(tmp_path: Path) -> None:
    """AD-13: the boundary is read from the bounds file, and a ``Z`` suffix means UTC.

    Read from a copy this test writes, so the assertion is about the parsing and a reviewed
    correction of the committed instant cannot turn it red. The default source is the
    committed file, and its boundary is timezone-aware too.
    """
    source = tmp_path / "audit-chain-bounds.yaml"
    source.write_text(BOUNDS_WITH_A_Z_SUFFIX, encoding="utf-8")

    bounds = load_chain_bounds(source)
    assert bounds == ChainBounds(
        migration_boundary=BOUNDARY,
        max_rows=7,
        max_wall_clock_seconds=30,
        anchor_max_age_hours=48,
    )
    assert bounds.migration_boundary.utcoffset() == timedelta(0)

    committed = load_chain_bounds()
    assert committed == load_chain_bounds(BOUNDS_PATH)
    assert committed.migration_boundary.utcoffset() == timedelta(0)
