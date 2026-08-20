"""Property-based test for audit-chain perturbation detection (design E4.1 / AD-8).

Feature: purpose-achievement-audit, Property 18: Chain verification detects every
single-row perturbation

    *For any* chain of length n >= 2, *any* index i, and *any* perturbation operator
    drawn from {none, alter payload, delete row, delete-and-re-link successor, swap
    adjacent rows, truncate trailing rows}, the walk exits zero with
    ``verified == n`` for the null operator and exits non-zero for every other
    operator, naming a break at or before i whose kind is ``PAYLOAD`` for an
    alteration, ``LINKAGE`` for a deletion or a swap, ``PAYLOAD`` for a re-link, and
    ``HEAD_UNREACHABLE`` for a truncation; rows before the migration boundary
    carrying null hashes are counted as legacy and excluded from the verified count,
    a null hash after the boundary is a break, and the report names the snapshot
    upper bound it walked.

Why the property is shaped this way. Requirement 6's finding is not "there is no
verifier" - ``scripts/synapse_cli/audit_verify.py:71`` exists. The finding is that it
validates each row against that row's **own stored** ``prev_hash``
(``row.prev_hash or prev_hash``), so every surviving row stays self-consistent and
deletion, re-linking, and adjacent reorder are structurally invisible. A test that
only altered payload bytes would pass against that broken verifier. So this property
quantifies over the *tamper classes*, not over byte edits: three of the six operators
(delete, re-link, swap) are exactly the ones the old walk cannot see, and each is
asserted to produce a named break.

The null operator is load-bearing in the opposite direction. Without it, a verifier
that rejects every chain unconditionally would satisfy every other clause. R6.6 is
asserted on **every** example, not only on the ``NONE`` draws: each example also walks
its own unperturbed chain and requires ``verified`` (exit ``0``) with the full hashed
row count. Detection and non-rejection are the two halves that make the property a
specification rather than a smoke test.

The declared break kind for ``DELETE_AND_RELINK`` is ``PAYLOAD``, narrowed from the
two admissible kinds ``strategies_audit`` originally allowed. Task 7.1 settled the
convention with a per-row precedence ``NULL_AFTER_BOUNDARY`` > ``LINKAGE`` >
``PAYLOAD`` and at most one break per row: the operator makes linkage *consistent* (it
rewrites the successor's ``prev_hash`` to the surviving predecessor's ``current_hash``)
but leaves the successor's ``current_hash`` un-recomputed, so linkage passes honestly
and the un-recomputed hash is the surviving evidence. This test asserts both halves -
the payload break *and* the absence of a linkage break - because the pair is the
fingerprint that distinguishes a re-link from a byte edit.

**No Postgres.** ``walk`` is pure by design (AD-7): it takes an ordered, already
materialised row sequence and returns a report. That purity is exactly why the six
tamper classes are testable at all under I-0 - a database-backed equivalent would be a
container this machine must not start. The Postgres-backed deletion case is an
integration test in ``integration.yml`` (task 7.10), not here.

``make_canonical_row`` and ``hash_payload_for_row`` are called, never reimplemented
and never modified (I-4, byte-pinned by ``packages/tests/test_audit_chain.py``): the
generated chains are hashed by the production primitives, so a chain this test calls
"correctly linked" is one the writer would actually have produced.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.10**
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from hypothesis import given

from orchestrator.audit.chain_walk import BreakKind, ChainRow, WalkReport, walk
from packages.tests.strategies_audit import (
    BREAK_KIND_HEAD_UNREACHABLE,
    BREAK_KIND_LINKAGE,
    BREAK_KIND_NULL_AFTER_BOUNDARY,
    BREAK_KIND_PAYLOAD,
    Perturbation,
    PerturbedChain,
    chain_bounds,
    expected_break_kinds,
    head_hash,
    nullify_hashes,
    perturbed_chains,
)

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from packages.tests.strategies_audit import ChainRowDraft

#: Exit codes the CLI adapter (task 7.3) will propagate: 0 verified / 1 broken.
EXIT_VERIFIED = 0
EXIT_BROKEN = 1

#: The operators whose break is a property of a row, as opposed to of the snapshot as
#: a whole. ``TRUNCATE_TAIL`` is the exception: nothing in the walked rows is wrong,
#: the recorded head is simply absent from them (R6.5).
_ROW_LEVEL: tuple[Perturbation, ...] = (
    Perturbation.ALTER_PAYLOAD,
    Perturbation.DELETE_ROW,
    Perturbation.DELETE_AND_RELINK,
    Perturbation.SWAP_ADJACENT,
)


def walk_drafts(
    rows: Sequence[ChainRowDraft],
    *,
    boundary: datetime,
    recorded_head: str | None,
) -> WalkReport:
    """Walk a generated snapshot through the production walker.

    The bridge ``ChainRow(**draft.as_kwargs())`` is deliberate: the strategy module
    owns a plain frozen draft and the walker owns the Pydantic model, and neither
    imports the other. The row-count bound comes from the committed
    ``audit-chain-bounds.yaml`` (AD-13), never a literal; the wall-clock bound is left
    disabled because these snapshots are at most eight rows and a clock bound here
    would only add flake.
    """
    return walk(
        [ChainRow(**draft.as_kwargs()) for draft in rows],
        boundary=boundary,
        recorded_head=recorded_head,
        max_rows=chain_bounds().max_rows,
    )


def kinds(report: WalkReport) -> tuple[str, ...]:
    """The reported break kinds, as plain strings, in walk order."""
    return tuple(str(break_.kind) for break_ in report.breaks)


# Feature: purpose-achievement-audit, Property 18: Chain verification detects every
# single-row perturbation
@given(case=perturbed_chains())
def test_chain_verification_detects_every_single_row_perturbation(
    case: PerturbedChain,
) -> None:
    """R6.1-R6.6, R6.10: one operator, one named break, and no false rejection."""
    # --- the null operator half, asserted on EVERY example (R6.6) ------------------
    # Without this, a walker that rejects every chain would satisfy every clause
    # below. The unperturbed chain must verify, with the legacy rows accounted for
    # separately (R6.7) and the recorded head reachable.
    clean = walk_drafts(
        case.original,
        boundary=case.boundary,
        recorded_head=head_hash(case.original),
    )
    assert clean.status == "verified"
    assert clean.exit_code == EXIT_VERIFIED
    assert clean.breaks == ()
    assert clean.verified == case.expected_verified_count
    assert clean.legacy == case.expected_legacy_count
    assert clean.verified + clean.legacy == clean.walked == len(case.original)
    assert clean.bound_exceeded is None

    report = walk_drafts(
        case.rows,
        boundary=case.boundary,
        recorded_head=case.recorded_head,
    )

    # R6.10: the walk reports the upper boundary of the snapshot it fixed, for every
    # operator - including the ones that shortened the snapshot.
    assert report.walked == len(case.rows)
    assert report.snapshot_upper_bound == case.snapshot_upper_bound
    assert report.bound_exceeded is None

    # The verdict, and the exit code a CI step will observe.
    assert report.status == case.expected_status
    if case.perturbation is Perturbation.NONE:
        assert report.exit_code == EXIT_VERIFIED
        assert report.breaks == ()
        assert report.verified == case.expected_verified_count
        assert report.legacy == case.expected_legacy_count
        assert report.head_hash == case.recorded_head
        return

    # --- every other operator is detected -----------------------------------------
    assert report.status == "broken"
    assert report.exit_code == EXIT_BROKEN
    assert report.breaks
    # A tamper always costs at least one row its verified status, so the count can
    # never be mistaken for a clean walk's.
    assert report.verified < case.expected_verified_count

    declared = expected_break_kinds(case.perturbation)
    assert len(declared) == 1, "task 7.1 settled one kind per operator"
    first = report.first_break
    assert first is not None
    assert str(first.kind) == declared[0]

    if case.perturbation is Perturbation.TRUNCATE_TAIL:
        # R6.5: the recorded head is carried by no walked row. The break belongs to
        # the snapshot, not to a row, so it names neither position nor row id.
        assert str(first.kind) == BREAK_KIND_HEAD_UNREACHABLE
        assert first.position is None
        assert first.row_id is None
        assert case.recorded_head is not None
        assert case.recorded_head not in {row.current_hash for row in case.rows}
        assert report.head_hash != case.recorded_head
        assert first.expected is not None
        assert case.recorded_head.startswith(first.expected)
        # Nothing in the surviving prefix is broken: truncation is detected *only*
        # because a head was independently recorded.
        assert kinds(report) == (BREAK_KIND_HEAD_UNREACHABLE,)
        return

    # --- a row-level operator names the earliest diverging row (R6.1, R6.4) --------
    assert case.perturbation in _ROW_LEVEL
    assert first.position == case.index
    target = case.rows[case.index]
    assert first.row_id == target.row_id
    assert f"row={target.row_id} position={case.index}" in first.detail
    # The head row survives every row-level operator, so head reachability must not
    # be what flagged the tamper - otherwise a walk could pass this property while
    # being blind to the linkage fault (the exact hole R6.2/R6.3/R6.4 name).
    assert BreakKind.HEAD_UNREACHABLE not in {break_.kind for break_ in report.breaks}

    if case.perturbation is Perturbation.ALTER_PAYLOAD:
        # R6.1: bytes changed, both hashes untouched, so the row no longer hashes to
        # what it stores. Exactly one break: a payload edit does not cascade, because
        # the walk advances from the stored ``current_hash``.
        assert kinds(report) == (BREAK_KIND_PAYLOAD,)
        assert target.current_hash is not None
        assert first.stored is not None
        assert target.current_hash.startswith(first.stored)
        assert first.stored != first.expected

    elif case.perturbation is Perturbation.DELETE_ROW:
        # R6.2: the successor of the deleted row is named, and the finding is the
        # linkage comparison the old verifier never made.
        assert kinds(report) == (BREAK_KIND_LINKAGE,)
        deleted = case.original[case.index]
        successor = case.original[case.index + 1]
        assert first.row_id == successor.row_id
        assert deleted.row_id not in {row.row_id for row in case.rows}
        # The successor is still self-consistent against its own stored prev_hash -
        # which is precisely why a self-consistency verifier reports zero breaks.
        assert successor.prev_hash == deleted.current_hash

    elif case.perturbation is Perturbation.DELETE_AND_RELINK:
        # R6.3: the attacker made linkage consistent, so the linkage comparison
        # passes honestly and the un-recomputed ``current_hash`` is the evidence.
        assert kinds(report) == (BREAK_KIND_PAYLOAD,)
        assert BreakKind.LINKAGE not in {break_.kind for break_ in report.breaks}
        predecessor = case.rows[case.index - 1] if case.index > 0 else None
        assert target.prev_hash == (None if predecessor is None else predecessor.current_hash)

    else:
        # R6.4: two adjacent rows exchanged, stored bytes of both unchanged. The
        # earlier of the two positions is named, and the kind is linkage because no
        # row's content was touched.
        assert case.perturbation is Perturbation.SWAP_ADJACENT
        assert str(first.kind) == BREAK_KIND_LINKAGE
        assert first.row_id == case.original[case.index + 1].row_id
        assert case.rows[case.index + 1].row_id == case.original[case.index].row_id
        # Every stored hash survives the swap: only the order changed.
        assert {row.current_hash for row in case.rows} == {
            row.current_hash for row in case.original
        }


# Feature: purpose-achievement-audit, Property 18: Chain verification detects every
# single-row perturbation
@given(case=perturbed_chains())
def test_null_hashes_are_legacy_before_the_boundary_and_a_break_after_it(
    case: PerturbedChain,
) -> None:
    """R6.7, R6.8: the boundary clause of the same property.

    The two clauses are one decision made twice against the committed migration
    boundary. Before it, a null hash is a pre-chain row the ALTER left NULL: counted,
    excluded from ``verified``, never a break. After it, a null hash is a row that
    should have been chained and was not: a break, and specifically not absorbed into
    the legacy count, which is where an unhonest verifier would hide it (I-7).

    ``recorded_head`` is ``None`` here on purpose: nulling the head row would
    otherwise also raise ``HEAD_UNREACHABLE``, and this clause is about the null, not
    about reachability.
    """
    clean = walk_drafts(case.original, boundary=case.boundary, recorded_head=None)

    # R6.7: legacy rows are reported separately and are not in ``verified``.
    assert clean.status == "verified"
    assert clean.legacy == case.expected_legacy_count
    assert clean.verified == case.expected_verified_count
    assert clean.legacy + clean.verified == clean.walked
    assert sum(1 for row in case.original if row.is_legacy) == clean.legacy

    # R6.8: ``case.index`` always addresses a hashed, post-boundary row.
    nulled = nullify_hashes(case.original, case.index)
    report = walk_drafts(nulled, boundary=case.boundary, recorded_head=None)

    assert report.status == "broken"
    assert report.exit_code == EXIT_BROKEN
    first = report.first_break
    assert first is not None
    assert str(first.kind) == BREAK_KIND_NULL_AFTER_BOUNDARY
    assert first.position == case.index
    assert first.row_id == case.original[case.index].row_id
    assert str(case.original[case.index].row_id) in first.detail

    # The nulled row is charged as a break, not quietly added to the legacy tally,
    # and it is not counted as verified either.
    assert report.legacy == case.expected_legacy_count
    assert report.verified < case.expected_verified_count
    assert report.walked == len(nulled) == len(case.original)
    assert report.snapshot_upper_bound == max(row.row_id for row in case.original)
