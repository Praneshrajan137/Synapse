"""Property-based test for anchor head commitment (design E4.3; R6.11, R6.12).

Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims

    *For any* correctly linked chain, the ``AnchorRecord`` built over it commits to
    exactly the ``current_hash`` of that chain's head row, and its published bytes are
    compact canonical JSON that round-trips byte-identically. *Any* perturbation of the
    chain at or before the anchored head - including a rewrite that recomputes the head
    forward, which leaves the presentation internally consistent - makes the commitment
    detectably wrong to a party holding nothing but the anchor. An honest append *after*
    the anchor is not a detection. And the freshness verdict is total: no anchor and a
    stale anchor are both reported UNVERIFIABLE, never verified.

Why the property is shaped this way. Requirement 6.12 does not ask whether an anchor
*exists* - the pre-task-7.6 anchorer already wrote a file every day. It asks whether the
anchor is a **commitment** strong enough that a third party holding only it can detect a
later rewrite. That framing decides every assertion below:

* **The commitment is the hash, not the row id.** ``AnchorRecord`` also carries
  ``head_row_id`` and ``head_created_at``, which are provenance. So each detection is
  run twice - once with the full record and once with a *minimal* record carrying only
  the head hash, an empty row id and no timestamp - and the two verdicts must agree. If
  detection ever leaned on the row id, that clause fails, and R6.12's "a party holding
  only that anchor" would be false however green the rest of the file looked.

* **Two rewrite mechanisms, not one.** A rewrite that does *not* recompute breaks the
  walk over the anchored window (``PAYLOAD`` / ``LINKAGE``). A rewrite that *does*
  recompute forward produces a chain that walks perfectly clean - and is caught only
  because the hash the anchor names is then carried by no row (``HEAD_UNREACHABLE``).
  ``test_a_rewrite_that_recomputes_the_head_forward_still_fails_the_commitment``
  asserts the second half explicitly, first proving the presentation *is* internally
  verified so the assertion cannot be satisfied by a chain that was broken anyway. An
  anchor that only caught the first mechanism would be worth very little, because
  recomputing forward is what an attacker with write access would actually do.

* **Non-detection is load-bearing in the other direction.** A detector that shouted
  "rewritten" at everything would satisfy every detection clause, so the null
  perturbation must come back ``intact`` on every example, and a chain with rows honestly
  appended *after* the anchor must also come back ``intact`` - the anchor never committed
  to those rows, and reporting them would make every later append look like tampering
  (``test_rows_appended_after_the_anchor_are_outside_its_window``).

* **A walk that proved nothing is not a clean bill of health (I-7).** Starving the walk
  of its row budget must yield ``unverifiable``, never ``intact``: absence of proof is
  never a pass. That is also the third arm that makes ``detect_rewrite``'s verdict total.

* **R6.11 has no positive outcome.** ``scripts/audit/anchor_truth.py`` deliberately has
  no ``verified`` state - its best finding is ``anchored``, meaning a walk *could* now be
  run against an independent head. The totality test therefore pins the whole verdict
  function (no usable anchor -> ``unavailable``; newest staler than the committed bound
  -> ``unavailable``; a defective published file beside a fresh one -> ``fail``;
  otherwise ``pass``) and asserts that an ``unverifiable`` chain is never a pass.

**No Postgres, no clock, no network.** Every decision under test is pure by design:
``select_head``, ``build_anchor_record``, ``scope_to_anchor`` and ``detect_rewrite`` take
values and return values, and ``evaluate_anchors`` takes the evaluation instant as an
argument. That purity is why Property 19 is testable at all under I-0 - the database-backed
anchor publication and the live freshness read belong to
``.github/workflows/publish-audit-anchor.yml``, never to this machine.

``make_canonical_row`` and ``hash_payload_for_row`` are imported and called, never
reimplemented and never modified (I-4: the canonical row is byte-pinned by
``packages/tests/test_audit_chain.py``). The chains come from the shared
``packages/tests/strategies_audit.py`` generators, so a chain this test calls "correctly
linked" is one the writer would actually have produced, and the head this test calls "the
head" is the same head ``orchestrator/audit/chain_walk.py`` walks to.

Bounds are read from ``infrastructure/quality/audit-chain-bounds.yaml`` (AD-13) - the
freshness bound, the migration boundary and the row-count bound are never literals here.
``max_examples`` is never set: the budget comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 6.11, 6.12**
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from orchestrator.audit.anchorer import (
    ANCHOR_SCHEMA_VERSION,
    AnchorFormatError,
    AnchorRecord,
    build_anchor_record,
    detect_rewrite,
    scope_to_anchor,
    select_head,
)
from orchestrator.audit.chain_walk import BreakKind, ChainRow, walk
from orchestrator.audit.hash_chain import hash_payload_for_row
from packages.tests.strategies_audit import (
    Perturbation,
    chain_bounds,
    chains,
    head_hash,
    nullify_hashes,
    perturbed_chains,
)
from scripts.audit.anchor_truth import AnchorFile, evaluate_anchors, load_anchor_settings

if TYPE_CHECKING:
    from collections.abc import Sequence

    from packages.tests.strategies_audit import ChainRowDraft, PerturbedChain

# The committed settings, read once (E-S13-07 utf-8 reads happen inside the loaders).
# Nothing below hardcodes a bound: the freshness bound, the anchor directory label, the
# migration boundary and the row-count bound all come from
# ``infrastructure/quality/audit-chain-bounds.yaml`` (AD-13).
_SETTINGS: Final = load_anchor_settings()
_BOUNDS: Final = chain_bounds()
_MAX_AGE_HOURS: Final[int] = _BOUNDS.anchor_max_age_hours
_MAX_AGE_SECONDS: Final[int] = _MAX_AGE_HOURS * 3600

#: The exit code each verdict owes a CI step (``2`` is non-passing, I-7).
_EXPECTED_EXIT: Final[dict[str, int]] = {"pass": 0, "fail": 1, "unavailable": 2}

#: The five rules ``scripts/audit/anchor_truth.py`` documents in its module table. Held
#: here so a new rule appearing without a documented meaning fails the totality clause.
_DECLARED_RULES: Final[frozenset[str]] = frozenset(
    {
        "no-anchor",
        "stale-anchor",
        "unreadable-anchor",
        "non-canonical-anchor",
        "anchor-dir-drift",
    }
)

#: Hypothesis requires naive bounds when ``timezones`` is supplied.
_MIN_ANCHORED: Final = datetime(2026, 6, 1)
_MAX_ANCHORED: Final = datetime(2027, 6, 1)

#: A fixed publication instant for the clauses that are about tampering, not time.
_ANCHORED_AT: Final = datetime(2026, 6, 2, 12, 0, tzinfo=UTC)

#: Deterministically invalid commitments: wrong length, uppercase, non-hex. An "anchor"
#: naming one of these commits to nothing, so parsing must refuse rather than publish a
#: false positive (I-7).
_NON_DIGESTS: Final[tuple[str, ...]] = ("", "A" * 64, "g" * 64, "0" * 63, "0" * 65)


# ---------------------------------------------------------------------------
# Bridges and strategies
# ---------------------------------------------------------------------------


def chain_rows(rows: Sequence[ChainRowDraft]) -> list[ChainRow]:
    """Bridge the shared drafts into the walker's frozen model.

    ``ChainRow(**draft.as_kwargs())`` is the seam ``strategies_audit`` documents: the
    strategy module owns a plain frozen draft, ``chain_walk`` owns the Pydantic model,
    and neither imports the other.
    """
    return [ChainRow(**draft.as_kwargs()) for draft in rows]


def hashed_positions(rows: Sequence[ChainRowDraft]) -> tuple[int, ...]:
    """Positions of the hashed rows - the only rows that carry a head to commit to."""
    return tuple(index for index, row in enumerate(rows) if not row.is_legacy)


def anchor_timestamps() -> st.SearchStrategy[datetime]:
    """UTC publication instants."""
    return st.datetimes(
        min_value=_MIN_ANCHORED, max_value=_MAX_ANCHORED, timezones=st.just(UTC)
    )


@st.composite
def anchored_chains(draw: st.DrawFn) -> tuple[tuple[ChainRowDraft, ...], AnchorRecord]:
    """A correctly linked chain and the anchor published over its head."""
    rows = draw(chains())
    head = select_head(chain_rows(rows))
    # ``chains`` guarantees at least two hashed rows, so a head always exists.
    assert head is not None
    return rows, build_anchor_record(head, anchored_at=draw(anchor_timestamps()))


@st.composite
def anchored_prefixes(
    draw: st.DrawFn,
) -> tuple[tuple[ChainRowDraft, ...], int, AnchorRecord]:
    """A chain, a split point, and the anchor published over the prefix up to it.

    The rows after the split are honest later appends: they are outside what the anchor
    committed to, and R6.12's window must exclude them.
    """
    rows = draw(chains(min_length=3, max_length=8))
    split = draw(st.sampled_from(hashed_positions(rows)[:-1]))
    head = select_head(chain_rows(rows[: split + 1]))
    assert head is not None
    return rows, split, build_anchor_record(head, anchored_at=draw(anchor_timestamps()))


@st.composite
def anchor_file_sets(draw: st.DrawFn) -> tuple[tuple[AnchorFile, ...], datetime]:
    """A published anchor directory: any mix of good, non-canonical and unreadable files.

    Ages span zero to three times the committed bound so both sides of the freshness
    boundary are exercised, and the ages are drawn in whole seconds so the expected
    verdict is exact integer arithmetic rather than a float comparison that could flake
    at the boundary.
    """
    now = draw(anchor_timestamps())
    kinds = draw(st.lists(st.sampled_from(("canonical", "non-canonical", "bad")), max_size=4))
    files: list[AnchorFile] = []
    for position, kind in enumerate(kinds):
        if kind == "bad":
            files.append(
                AnchorFile(
                    name=f"{position:02d}-unreadable.json",
                    record=None,
                    canonical=False,
                    error="published file names no head hash",
                )
            )
            continue
        head = select_head(chain_rows(draw(chains(min_length=2, max_length=4))))
        assert head is not None
        age_seconds = draw(st.integers(min_value=0, max_value=_MAX_AGE_SECONDS * 3))
        record = build_anchor_record(head, anchored_at=now - timedelta(seconds=age_seconds))
        files.append(
            AnchorFile(
                name=f"{position:02d}-{record.date}.json",
                record=record,
                canonical=kind == "canonical",
                error=None,
            )
        )
    return tuple(files), now


def minimal_anchor(record: AnchorRecord) -> AnchorRecord:
    """``record`` stripped to the commitment itself: the head hash and nothing else.

    What a third party who was handed only the anchored digest holds. Detection run
    against this must agree with detection run against the full record, or the
    commitment is secretly leaning on provenance fields (R6.12).
    """
    return AnchorRecord(
        schema_version=record.schema_version,
        date=record.date,
        anchored_at=record.anchored_at,
        head_hash=record.head_hash,
        head_row_id="",
        head_created_at=None,
        synapse_version="",
    )


# ---------------------------------------------------------------------------
# R6.12 - the commitment
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(case=anchored_chains())
def test_an_anchor_commits_to_exactly_the_head_of_the_rows_it_was_built_over(
    case: tuple[tuple[ChainRowDraft, ...], AnchorRecord],
) -> None:
    """R6.12: the anchored hash is the head's ``current_hash``, and the intact chain passes."""
    rows, record = case
    presented = chain_rows(rows)

    # The two definitions of "the head" - the anchorer's and the shared strategies' -
    # are the same definition. If these drift, the anchor and the walker would commit
    # to different rows and HEAD_UNREACHABLE would fire on an untampered chain.
    head = select_head(presented)
    assert head is not None
    assert head.head_hash == head_hash(rows)
    assert record.head_hash == head.head_hash
    assert record.head_row_id == head.row_id
    assert record.schema_version == ANCHOR_SCHEMA_VERSION
    # Legacy pre-boundary rows carry no hash, so they cannot move the head.
    assert record.head_hash == rows[-1].current_hash
    assert json.loads(record.to_json())["head_hash"] == head.head_hash

    scope = scope_to_anchor(record, presented)
    assert scope.reachable is True
    assert scope.head_position == len(presented) - 1
    assert scope.rows == tuple(presented)

    detection = detect_rewrite(
        record,
        presented,
        boundary=_BOUNDS.migration_boundary,
        max_rows=_BOUNDS.max_rows,
    )
    assert detection.status == "intact"
    assert detection.detected is False
    assert detection.head_reachable is True
    assert detection.anchored_head == record.head_hash
    assert detection.anchored_rows == len(presented)
    assert detection.report.status == "verified"
    assert detection.report.exit_code == 0
    assert detection.report.breaks == ()
    assert detection.report.verified == len(hashed_positions(rows))
    assert detection.report.head_hash == record.head_hash

    # The commitment carries the verdict on its own: strip the provenance fields and
    # the conclusion is unchanged (R6.12, "a party holding only that anchor").
    stripped = detect_rewrite(
        minimal_anchor(record),
        presented,
        boundary=_BOUNDS.migration_boundary,
        max_rows=_BOUNDS.max_rows,
    )
    assert stripped.status == detection.status
    assert stripped.head_reachable == detection.head_reachable
    assert stripped.anchored_rows == detection.anchored_rows

    # I-7: a walk stopped by its declared bound proved nothing. It is 'unverifiable' -
    # never 'intact', and never a detection either.
    starved = detect_rewrite(
        record, presented, boundary=_BOUNDS.migration_boundary, max_rows=0
    )
    assert starved.status == "unverifiable"
    assert starved.detected is False
    assert starved.report.status == "not_verified"
    assert starved.report.bound_exceeded is not None
    assert starved.report.exit_code == 2


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(case=anchored_prefixes())
def test_rows_appended_after_the_anchor_are_outside_its_window(
    case: tuple[tuple[ChainRowDraft, ...], int, AnchorRecord],
) -> None:
    """R6.12: the guarantee is scoped to rows at or before the anchored head.

    The non-false-positive half. An anchor published yesterday committed to yesterday's
    head; today's honest appends were never covered by it. A detector that walked the
    whole presentation against an older anchor would flag every subsequent append as
    tampering, and an operator who saw that once would stop believing the next one.
    """
    rows, split, record = case
    presented = chain_rows(rows)

    scope = scope_to_anchor(record, presented)
    assert scope.reachable is True
    assert scope.head_position == split
    assert len(scope.rows) == split + 1
    assert scope.rows == tuple(presented[: split + 1])

    detection = detect_rewrite(
        record,
        presented,
        boundary=_BOUNDS.migration_boundary,
        max_rows=_BOUNDS.max_rows,
    )
    assert detection.status == "intact"
    assert detection.detected is False
    assert detection.head_reachable is True
    assert detection.anchored_rows == split + 1
    assert detection.report.walked == split + 1
    assert detection.report.breaks == ()


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(perturbed=perturbed_chains())
def test_any_perturbation_at_or_before_the_anchored_head_is_detected(
    perturbed: PerturbedChain,
) -> None:
    """R6.12: every one of Property 18's tamper classes is visible from the anchor alone.

    The six operators are reused deliberately rather than re-derived: they are the same
    tamper classes Requirement 6 enumerates, and three of them (delete, re-link, swap)
    are exactly the ones the pre-AD-8 verifier could not see. Here they are judged from
    the *anchor's* side - a third party with one digest - rather than from a walk handed
    the recorded head by the same database it is auditing.
    """
    original = chain_rows(perturbed.original)
    head = select_head(original)
    assert head is not None
    assert head.head_hash == perturbed.recorded_head

    record = build_anchor_record(head, anchored_at=_ANCHORED_AT)
    presented = chain_rows(perturbed.rows)
    detection = detect_rewrite(
        record,
        presented,
        boundary=perturbed.boundary,
        max_rows=_BOUNDS.max_rows,
    )
    stripped = detect_rewrite(
        minimal_anchor(record),
        presented,
        boundary=perturbed.boundary,
        max_rows=_BOUNDS.max_rows,
    )
    # The head hash alone carries the verdict, for every operator.
    assert stripped.status == detection.status
    assert stripped.head_reachable == detection.head_reachable

    if perturbed.perturbation is Perturbation.NONE:
        # The null operator: no false detection, on every example.
        assert detection.status == "intact"
        assert detection.detected is False
        assert detection.head_reachable is True
        assert detection.report.breaks == ()
        return

    assert detection.status == "rewritten"
    assert detection.detected is True
    # The commitment is detectably wrong: either the anchored head is carried by no
    # presented row, or the walk over the anchored window broke. Never both silent.
    assert not (detection.head_reachable and detection.report.status == "verified")
    assert detection.report.status == "broken"
    assert detection.report.breaks
    first = detection.report.first_break
    assert first is not None

    if perturbed.perturbation is Perturbation.TRUNCATE_TAIL:
        # The rows are gone, so the digest the anchor names is nowhere in the
        # presentation. This is the one class detectable *only* because a head was
        # independently recorded - which is the whole reason an anchor is published.
        assert detection.head_reachable is False
        assert record.head_hash not in {row.current_hash for row in presented}
        assert first.kind is BreakKind.HEAD_UNREACHABLE
        assert first.position is None
        assert first.row_id is None
    else:
        # The head row survives an alteration, a deletion, a re-link and a swap, so
        # reachability is NOT what flagged these. The break has to come from the walk
        # over the anchored window, which is the linkage comparison AD-8 added.
        assert detection.head_reachable is True
        assert BreakKind.HEAD_UNREACHABLE not in {
            break_.kind for break_ in detection.report.breaks
        }
        assert first.kind in (BreakKind.PAYLOAD, BreakKind.LINKAGE)
        # The anchored window is a prefix, so positions inside it are the walk's own
        # positions: the named row is exactly the tampered one.
        assert first.position == perturbed.index
        assert first.row_id == perturbed.rows[perturbed.index].row_id


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(case=anchored_chains())
def test_a_rewrite_that_recomputes_the_head_forward_still_fails_the_commitment(
    case: tuple[tuple[ChainRowDraft, ...], AnchorRecord],
) -> None:
    """R6.12: the attack that defeats a walk is the one the anchor exists to catch.

    An attacker with write access does not leave a stale hash behind - they rewrite the
    row and recompute. The result walks perfectly clean (asserted here first, so the
    detection below cannot be credited to a chain that was broken anyway), and the only
    surviving evidence is that the digest the anchor committed to is now carried by no
    row at all.

    ``hash_payload_for_row`` is called, not reimplemented: I-4 pins those bytes.
    """
    rows, record = case
    target = rows[-1]
    altered = dict(target.canonical)
    altered["audit_trace"] = [*list(altered.get("audit_trace", [])), "rewritten"]
    rewritten = replace(
        target,
        canonical=altered,
        current_hash=hash_payload_for_row(target.prev_hash, altered),
    )
    presented = chain_rows((*rows[:-1], rewritten))

    # The presentation is internally consistent - a self-consistency verifier, and even
    # the linkage walk with no recorded head, reports it verified.
    unanchored = walk(
        presented,
        boundary=_BOUNDS.migration_boundary,
        recorded_head=None,
        max_rows=_BOUNDS.max_rows,
    )
    assert unanchored.status == "verified"
    assert unanchored.breaks == ()

    # The anchor is what breaks the tie.
    detection = detect_rewrite(
        record,
        presented,
        boundary=_BOUNDS.migration_boundary,
        max_rows=_BOUNDS.max_rows,
    )
    assert detection.status == "rewritten"
    assert detection.detected is True
    assert detection.head_reachable is False
    assert record.head_hash != rewritten.current_hash
    assert record.head_hash not in {row.current_hash for row in presented}
    first = detection.report.first_break
    assert first is not None
    assert first.kind is BreakKind.HEAD_UNREACHABLE


# ---------------------------------------------------------------------------
# R6.12 - the published bytes
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(case=anchored_chains())
def test_anchor_serialisation_is_canonical_and_byte_stable(
    case: tuple[tuple[ChainRowDraft, ...], AnchorRecord],
) -> None:
    """E-S9-03: compact canonical JSON, byte-stable, and it names the head it commits to.

    Byte stability is not cosmetic here. ``publish-audit-anchor.yml`` cosigns the anchor
    file, so a signature covers bytes; if two publications of the same head produced
    different bytes, a verifier could not tell a re-publication from a substitution.
    """
    rows, record = case
    text = record.to_json()

    assert text == json.dumps(record.payload(), sort_keys=True, separators=(",", ":"))
    assert "\n" not in text
    assert ", " not in text
    assert '": ' not in text
    decoded = json.loads(text)
    assert tuple(decoded) == tuple(sorted(decoded))
    assert decoded["head_hash"] == record.head_hash
    assert decoded["anchor_schema_version"] == ANCHOR_SCHEMA_VERSION

    # Re-publishing the same head at the same instant is byte-identical, which is what
    # makes a re-run of the scheduled anchorer idempotent.
    head = select_head(chain_rows(rows))
    assert head is not None
    assert build_anchor_record(head, anchored_at=record.anchored_at).to_json() == text

    # Round-trip: read the published bytes back and re-emit them unchanged.
    parsed = AnchorRecord.from_json(text)
    assert parsed.head_hash == record.head_hash
    assert parsed.head_row_id == record.head_row_id
    assert parsed.head_created_at == record.head_created_at
    assert parsed.anchored_at == record.anchored_at
    assert parsed.to_json() == text

    # A pre-task-7.6 anchor still reads: refusing to parse a published anchor would
    # destroy evidence. The commitment is the same digest under either key name.
    legacy_payload: dict[str, object] = {
        "anchored_at": record.anchored_at.isoformat(),
        "current_hash": record.head_hash,
        "date": record.date,
        "row_id": record.head_row_id,
    }
    if record.head_created_at is not None:
        legacy_payload["row_created_at"] = record.head_created_at.isoformat()
    legacy = AnchorRecord.from_payload(legacy_payload)
    assert legacy.head_hash == record.head_hash
    assert legacy.schema_version == 1
    assert legacy.head_created_at == record.head_created_at

    # An "anchor" that names no digest commits to nothing and is refused, not published
    # as a false positive (I-7).
    for bad in _NON_DIGESTS:
        with pytest.raises(AnchorFormatError):
            AnchorRecord.from_payload(
                {"head_hash": bad, "anchored_at": record.anchored_at.isoformat()}
            )
    with pytest.raises(AnchorFormatError):
        AnchorRecord.from_payload({"head_hash": record.head_hash})
    with pytest.raises(AnchorFormatError):
        AnchorRecord.from_json("{not json")
    with pytest.raises(AnchorFormatError):
        AnchorRecord.from_json(json.dumps([record.head_hash]))


# ---------------------------------------------------------------------------
# R6.11 - freshness: unverifiable, never verified
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(now=anchor_timestamps())
def test_a_missing_anchor_yields_unverifiable_and_never_verified(now: datetime) -> None:
    """R6.11: no anchor means UNVERIFIABLE. Silence is not health.

    Both spellings of "no anchor" are asserted, because to a third party they are the
    same fact: an empty directory, and a directory holding files that are not readable
    commitments. The second is the one that could have been fudged - the files exist, so
    a gate counting files would have called it fresh.
    """
    # The two readers of the committed bound agree, so a reviewed bound change moves the
    # walker and the freshness gate together (AD-13).
    assert _SETTINGS.max_age_hours == _MAX_AGE_HOURS

    empty = evaluate_anchors(
        (), now=now, max_age_hours=_MAX_AGE_HOURS, anchor_dir=_SETTINGS.declared_dir
    )
    assert empty.chain_status == "unverifiable"
    assert empty.verdict == "unavailable"
    assert empty.exit_code == _EXPECTED_EXIT["unavailable"]
    assert empty.newest_head is None
    assert empty.newest_anchored_at is None
    assert empty.newest_age_hours is None
    assert {finding.rule for finding in empty.findings} == {"no-anchor"}

    unreadable = evaluate_anchors(
        (
            AnchorFile(
                name="2026-06-01.json",
                record=None,
                canonical=False,
                error="anchor names no head hash",
            ),
        ),
        now=now,
        max_age_hours=_MAX_AGE_HOURS,
        anchor_dir=_SETTINGS.declared_dir,
    )
    assert unreadable.chain_status == "unverifiable"
    assert unreadable.verdict == "unavailable"
    assert unreadable.newest_head is None
    rules = {finding.rule for finding in unreadable.findings}
    assert rules == {"no-anchor", "unreadable-anchor"}


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(
    case=anchored_chains(),
    age_seconds=st.integers(min_value=0, max_value=_MAX_AGE_SECONDS * 3),
)
def test_an_anchor_older_than_the_committed_bound_yields_unverifiable(
    case: tuple[tuple[ChainRowDraft, ...], AnchorRecord],
    age_seconds: int,
) -> None:
    """R6.11: past the committed freshness bound the chain is UNVERIFIABLE, not verified.

    The age is drawn in whole seconds so the expected verdict is exact integer
    arithmetic against the committed bound - including the boundary itself, where an
    anchor exactly at the bound is still fresh.
    """
    _, record = case
    now = record.anchored_at + timedelta(seconds=age_seconds)
    report = evaluate_anchors(
        (AnchorFile(name=f"{record.date}.json", record=record, canonical=True, error=None),),
        now=now,
        max_age_hours=_MAX_AGE_HOURS,
        anchor_dir=_SETTINGS.declared_dir,
    )

    assert report.newest_head == record.head_hash
    assert report.newest_anchored_at == record.anchored_at
    assert report.newest_age_hours == pytest.approx(age_seconds / 3600.0)
    # There is no 'verified' outcome to reach: the best this gate reports is 'anchored'.
    assert report.chain_status in {"anchored", "unverifiable"}

    if age_seconds > _MAX_AGE_SECONDS:
        assert report.chain_status == "unverifiable"
        assert report.verdict == "unavailable"
        assert report.exit_code == _EXPECTED_EXIT["unavailable"]
        assert {finding.rule for finding in report.findings} == {"stale-anchor"}
        assert report.findings[0].requirement == "R6.11"
    else:
        assert report.chain_status == "anchored"
        assert report.verdict == "pass"
        assert report.exit_code == _EXPECTED_EXIT["pass"]
        assert report.findings == ()


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(case=anchor_file_sets())
def test_the_anchor_freshness_verdict_is_total(
    case: tuple[tuple[AnchorFile, ...], datetime],
) -> None:
    """R6.11: every published directory gets exactly one verdict, and it is predictable.

    The whole verdict function is pinned, not merely its type: no usable anchor ->
    ``unavailable``; newest staler than the committed bound -> ``unavailable``; a
    defective published file beside a fresh one -> ``fail``; otherwise ``pass``. The
    ``fail`` / ``unavailable`` split is the operator-facing distinction between "the
    anchor we have is broken" and "nobody anchored", which are different repairs - and
    neither is a pass.
    """
    files, now = case
    report = evaluate_anchors(
        files, now=now, max_age_hours=_MAX_AGE_HOURS, anchor_dir=_SETTINGS.declared_dir
    )

    # Totality of the shape.
    assert report.verdict in _EXPECTED_EXIT
    assert report.exit_code == _EXPECTED_EXIT[report.verdict]
    assert report.chain_status in {"anchored", "unverifiable"}
    assert report.reason
    assert len(report.anchors) == len(files)
    for finding in report.findings:
        assert finding.rule in _DECLARED_RULES
        assert finding.subject
        assert finding.detail
        assert finding.requirement

    usable = [item.record for item in files if item.record is not None]
    defective = [item for item in files if item.record is None or not item.canonical]
    rules = {finding.rule for finding in report.findings}

    if not usable:
        expected = "unavailable"
        assert report.chain_status == "unverifiable"
        assert "no-anchor" in rules
        assert report.newest_head is None
    else:
        newest = max(usable, key=lambda record: record.anchored_at)
        if (now - newest.anchored_at).total_seconds() > _MAX_AGE_SECONDS:
            expected = "unavailable"
            assert report.chain_status == "unverifiable"
            assert "stale-anchor" in rules
        else:
            expected = "fail" if defective else "pass"
            assert report.chain_status == "anchored"
        assert report.newest_head == newest.head_hash
        assert report.newest_anchored_at == newest.anchored_at

    assert report.verdict == expected

    # I-7, stated twice from both sides: an unverifiable chain is never a pass, and a
    # pass never carries an unresolved finding.
    if report.chain_status == "unverifiable":
        assert report.verdict != "pass"
    if report.verdict == "pass":
        assert report.chain_status == "anchored"
        assert report.findings == ()


# ---------------------------------------------------------------------------
# The head an anchor can commit to at all
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 19: An anchor commits to the head it claims
@given(rows=chains())
def test_head_selection_is_total_and_never_invents_a_commitment(
    rows: tuple[ChainRowDraft, ...],
) -> None:
    """R6.11/R6.12: a chain with no hashed row yields no head, so no anchor is published.

    ``select_head`` returning ``None`` is what makes ``anchor_today`` exit
    ``EXIT_UNAVAILABLE`` instead of writing an anchor over a hash it does not have. The
    alternative - committing to a placeholder - would be fabrication, and the freshness
    gate would then read that fabrication as evidence.
    """
    presented = chain_rows(rows)
    head = select_head(presented)
    assert head is not None
    assert head.head_hash == head_hash(rows)
    assert head.row_id == str(rows[-1].row_id)
    assert head.created_at == rows[-1].created_at

    # Order is the caller's: the head is the last hashed row of the snapshot as handed
    # over, not the numerically largest hash or row id. ``select_head`` re-sorting here
    # would silently disagree with the walker, which also honours the caller's order.
    reversed_head = select_head(list(reversed(presented)))
    assert reversed_head is not None
    assert reversed_head.head_hash == rows[hashed_positions(rows)[0]].current_hash

    assert select_head(()) is None

    nulled = rows
    for position in hashed_positions(rows):
        nulled = nullify_hashes(nulled, position)
    assert head_hash(nulled) is None
    assert select_head(chain_rows(nulled)) is None
