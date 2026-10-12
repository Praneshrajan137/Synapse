# Feature: decision-quality-proof, Property 87: A deferred leaf is terminal and reasoned, is never
# offered, and completion is reported only when nothing authorable, gated or pending remains
"""A deferred leaf is terminal and reasoned, and "complete" is a verdict rather than a sentence.

Feature: decision-quality-proof, task 29.1. Subject: ``scripts/audit/spec_ledger_census.py``.

**What this closes.** The census could only say "open", so a leaf the operator took out of
scope was indistinguishable from forgotten work, and ``--next 40`` offered it. A
``- deferred: <reason>`` sub-bullet now makes it a terminal state with its reason on the leaf,
and "the spec is finished" becomes ``complete``, which the census derives and prints.

**The oracle is the generator, not the census.** Every generated clause compares the census
with what the test BUILT -- which leaves it made authorable, gated, pending, deferred or
defective -- so no assertion passes by reading back the field it is about.

**Refusals are proven by construction.** A refusal that fires only on a malformed ledger may
never fire on the committed one, and a check that has never fired is not evidence. So each
failing path is built here and paired with its converse, which must pass, so that no clause
can hold by failing everything.

**Why task 9.12's wrapped prose line is generated.** Its body wraps a line that BEGINS with a
backticked ``deferred:``. Read with ``discharge:``'s key matching alone, that is a deferral of
a done leaf and the committed ledger goes non-passing on a sentence. The census therefore also
requires the entry to be a sub-bullet, and the decoy proves that holds for every mark and every
spelling of the key.

**Review defects 8 and 5.** A ``deferred:`` line with no reason defers nothing: its leaf stays
authorable or CI-gated exactly as if the line were absent, while ``deferred-without-reason``
names it. A checkbox the record grammar rejects (``- [ ] 31.1: X``, ``* [ ] 31.1 X``,
``- [ ] **31.1** X``) is a leaf in no count, so ``unparsed-checkbox`` names its line and
``complete`` is never derived over it -- nor by a census given no scan at all.

Budget inherited from the root ``conftest.py`` profile; no ``max_examples`` literal appears in
this file. Not slow-marked: pure parsing of in-memory text, no filesystem, no network, no
subprocess. Locus: ``ci.yml::uplift-verify-fast-3``, which collects ``tests/verify/test_[a-o]*``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.spec_ledger_census import (
    DEFAULT_BATCH,
    CensusOutcome,
    census,
    format_report,
    parse_records,
    unparsed_checkboxes,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from scripts.audit.spec_ledger_census import LedgerCensus

# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

_JOBS: Final = st.sampled_from(
    [
        "ci.yml::uplift-verify",
        "uplift.yml::twin-regret (checkpoint A)",
        "regenerate-truth-docs.yml::regenerate",
        "frontend.yml::quality step 8 (Vitest unit + property tests)",
    ]
)
#: Each names a GitHub Actions run id, so each harvests a ``[~]``. The oracle reads membership
#: here, never the census's own pattern.
_RUN_VALUES: Final[tuple[str, ...]] = (
    "run 34590696403",
    "run 34686422478 (sha 27a74a3)",
    "run `35125413492` (SYNAPSE CI, sha 5eef6ee) -- shard 3/4 `success`",
)
_RUNS: Final = st.sampled_from(_RUN_VALUES)
#: Each names NO run id -- session 11's line, a bare number, seven digits, an ordinal, a sha --
#: so each leaves a ``[~]`` exactly as unharvested as a missing line does.
_NO_RUNS: Final = st.sampled_from(
    [
        "none yet -- pushed at the session-11 wave-3 head; no run has read it yet",
        "34590696403",
        "run 1234567",
        "run 2",
        "sha 5eef6ee",
    ]
)
_REASONS: Final = st.sampled_from(
    [
        "structures 2/4/5 deferred by the R5.4 re-cut; none introduces a replenishment delay",
        "superseded by R5.45: checkpoint B-prime tests the information ceiling (task 14)",
        "operator decision 2026-09-16 -- unlocks other agents rather than this measurement",
    ]
)
#: What a reasonless line leaves after the key once the census strips the line.
_NO_REASON: Final = st.sampled_from(["", "   ", "\t"])
#: Every spelling of the key that the census's emphasis stripping reduces to one declaration.
_KEYS: Final = st.sampled_from(["deferred:", "**deferred:**", "`deferred:`", "Deferred:"])

#: Task 9.12's shape: a wrapped prose line that BEGINS with a backticked key.
_DECOY: Final[tuple[str, ...]] = (
    "    - Also pins that a missing key is refused rather than defaulted, and that every",
    "      `deferred:` entry is prose naming its owning task rather than a placeholder",
)
_PARENT: Final[str] = "- [ ] 9. The parent every generated leaf sits under"


@dataclass(frozen=True)
class _Leaf:
    """One generated leaf: its mark and the sub-bullets it carries."""

    mark: str
    discharge: str | None
    last_checked: str | None
    #: ``None`` = no ``deferred:`` line at all; otherwise the text written after the key.
    reason: str | None
    #: How the key is spelled when there is a line.
    key: str
    #: Carry task 9.12's wrapped prose line.
    decoy: bool


@dataclass(frozen=True)
class _Ledger:
    """Generated leaves in ledger order, all children of parent ``9``."""

    entries: tuple[tuple[str, _Leaf], ...]


@dataclass(frozen=True)
class _Truth:
    """What the generator built, derived from the contract's words and never from the census."""

    authorable: tuple[str, ...]
    gated: tuple[str, ...]
    deferred: frozenset[str]
    pending: tuple[str, ...]
    #: ``(rule, subject)`` for every refusal the built ledger must raise.
    findings: frozenset[tuple[str, str]]


# ---------------------------------------------------------------------------
# Rendering and the oracle
# ---------------------------------------------------------------------------


def _title(task_id: str) -> str:
    return f"Generated leaf {task_id}"


def _subject(task_id: str) -> str:
    """How every census finding names a record: ``LedgerRecord.name``'s shape."""
    return f'task {task_id} "{_title(task_id)}"'


def _numeric(task_id: str) -> tuple[int, ...]:
    """Task ids order by their integer parts: ``9.2`` precedes ``9.12``."""
    return tuple(int(part) for part in task_id.split("."))


def _render(ledger: _Ledger, *, deferrals: bool) -> str:
    """``tasks.md`` text for the ledger; ``deferrals=False`` omits every ``deferred:`` line."""
    lines = ["# Generated plan", "", _PARENT]
    for task_id, leaf in ledger.entries:
        lines.append(f"  - [{leaf.mark}] {task_id} {_title(task_id)}")
        if leaf.discharge is not None:
            lines.append(f"    - discharge: {leaf.discharge}")
        if leaf.last_checked is not None:
            lines.append(f"    - last-checked: {leaf.last_checked}")
        if deferrals and leaf.reason is not None:
            lines.append(f"    - {leaf.key} {leaf.reason}")
        if leaf.decoy:
            lines.extend(_DECOY)
        lines.append("    - Files: `some/module.py`")
    return "\n".join([*lines, ""])


def _truth(ledger: _Ledger) -> _Truth:
    """The buckets and refusals the contract assigns to what was built."""
    authorable: list[str] = []
    gated: list[str] = []
    deferred: set[str] = set()
    pending: list[str] = []
    findings: set[tuple[str, str]] = set()
    for task_id, leaf in ledger.entries:
        subject = _subject(task_id)
        # Only a reason defers. A reasonless line leaves its leaf where it would be without it.
        reasoned = leaf.reason is not None and bool(leaf.reason.strip())
        if leaf.mark == " ":
            if reasoned:
                deferred.add(task_id)
            elif leaf.discharge is not None:
                gated.append(task_id)
            else:
                authorable.append(task_id)
        elif leaf.mark == "~":
            pending.append(task_id)
            # Harvested only by a value BUILT as a run id: no line and a line naming none
            # are one refusal.
            if leaf.last_checked not in _RUN_VALUES:
                findings.add(("unharvested-pending", subject))
        if leaf.reason is not None:
            if leaf.mark != " ":
                findings.add(("deferred-marked-done", subject))
            if not reasoned:
                findings.add(("deferred-without-reason", subject))
            if leaf.discharge is not None:
                findings.add(("deferred-and-gated", subject))
    return _Truth(
        authorable=tuple(authorable),
        gated=tuple(gated),
        deferred=frozenset(deferred),
        pending=tuple(pending),
        findings=frozenset(findings),
    )


def _census(text: str) -> LedgerCensus:
    """The census as ``evaluate`` derives it: the records AND the checkbox scan of one text."""
    return census(
        parse_records(text),
        spec="synthetic",
        source="synthetic/tasks.md",
        unparsed=unparsed_checkboxes(text),
    )


def _refusals(report: LedgerCensus) -> tuple[tuple[str, str], ...]:
    """Every finding as ``(rule, subject)``, kept as a sorted multiset so a duplicate shows."""
    return tuple(sorted((finding.rule, finding.subject) for finding in report.findings))


def _barriers(ledger: _Ledger, truth: _Truth, size: int) -> tuple[str, ...]:
    """Gated leaves ahead of the last OFFERED id, from the positions the generator chose."""
    offered = truth.authorable[:size]
    if not offered:
        return ()
    position = {task_id: index for index, (task_id, _) in enumerate(ledger.entries)}
    return tuple(task_id for task_id in truth.gated if position[task_id] < position[offered[-1]])


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


def _leaf(
    mark: str,
    *,
    discharge: st.SearchStrategy[str | None],
    last_checked: st.SearchStrategy[str | None],
    reason: st.SearchStrategy[str | None],
) -> st.SearchStrategy[_Leaf]:
    return st.builds(
        _Leaf,
        mark=st.just(mark),
        discharge=discharge,
        last_checked=last_checked,
        reason=reason,
        key=_KEYS,
        decoy=st.booleans(),
    )


#: Any state the vocabulary allows, including every malformed deferral and every harvest line
#: that names no run.
_ANY_LEAF: Final = st.sampled_from([" ", "~", "x"]).flatmap(
    lambda mark: _leaf(
        mark,
        discharge=st.none() | _JOBS,
        last_checked=st.none() | _RUNS | _NO_RUNS,
        reason=st.none() | _REASONS | _NO_REASON,
    )
)
#: A well-formed deferral: open, reasoned, not gated.
_DEFERRED: Final = _leaf(" ", discharge=st.none(), last_checked=st.none(), reason=_REASONS)
#: A done leaf, keeping whatever discharge record it earned. It owes no harvest, so a line
#: naming no run is no finding on it.
_DONE: Final = _leaf(
    "x", discharge=st.none() | _JOBS, last_checked=st.none() | _RUNS | _NO_RUNS, reason=st.none()
)
#: Neither deferred nor refused.
_CLEAN: Final = st.one_of(
    _leaf(" ", discharge=st.none() | _JOBS, last_checked=st.none(), reason=st.none()),
    _leaf("~", discharge=_JOBS, last_checked=_RUNS, reason=st.none()),
    _DONE,
)
#: Each makes a finished ledger unfinished, for one of the reasons the contract names.
_UNFINISHING: Final = st.one_of(
    _leaf(" ", discharge=st.none(), last_checked=st.none(), reason=st.none()),  # authorable
    _leaf(" ", discharge=_JOBS, last_checked=st.none(), reason=st.none()),  # CI-gated
    _leaf("~", discharge=_JOBS, last_checked=_RUNS, reason=st.none()),  # pending, no finding
    _leaf("~", discharge=_JOBS, last_checked=st.none(), reason=st.none()),  # unharvested
    _leaf("~", discharge=_JOBS, last_checked=_NO_RUNS, reason=st.none()),  # names no run id
    _leaf(" ", discharge=st.none(), last_checked=st.none(), reason=_NO_REASON),  # no reason
    _leaf(" ", discharge=_JOBS, last_checked=st.none(), reason=_REASONS),  # deferred, gated
    _leaf("x", discharge=st.none(), last_checked=st.none(), reason=_REASONS),  # deferred, done
)
#: One isolated offender per refusal: each raises its own rule and nothing else.
_OFFENDERS: Final[dict[str, st.SearchStrategy[_Leaf]]] = {
    "deferred-marked-done": st.sampled_from(["x", "~"]).flatmap(
        lambda mark: _leaf(mark, discharge=st.none(), last_checked=_RUNS, reason=_REASONS)
    ),
    "deferred-without-reason": _leaf(
        " ", discharge=st.none(), last_checked=st.none(), reason=_NO_REASON
    ),
    "deferred-and-gated": _leaf(" ", discharge=_JOBS, last_checked=st.none(), reason=_REASONS),
}


def _ids(count: int) -> st.SearchStrategy[tuple[str, ...]]:
    """Distinct children of ``9``, drawn so ledger order and numeric order disagree."""
    return st.lists(st.integers(1, 40), min_size=count, max_size=count, unique=True).map(
        lambda numbers: tuple(f"9.{number}" for number in numbers)
    )


def _ledger(ids: Sequence[str], leaves: Sequence[_Leaf]) -> _Ledger:
    return _Ledger(entries=tuple(zip(ids, leaves, strict=True)))


@st.composite
def _ledgers(draw: st.DrawFn) -> _Ledger:
    """At least one leaf, in any state the vocabulary allows."""
    leaves = draw(st.lists(_ANY_LEAF, min_size=1, max_size=9))
    return _ledger(draw(_ids(len(leaves))), leaves)


@st.composite
def _ledgers_with_a_deferral(draw: st.DrawFn) -> _Ledger:
    """Any leaves, plus at least one well-formed open deferral at a drawn position."""
    drawn = draw(st.lists(_ANY_LEAF, max_size=8))
    at = draw(st.integers(0, len(drawn)))
    leaves = [*drawn[:at], draw(_DEFERRED), *drawn[at:]]
    return _ledger(draw(_ids(len(leaves))), leaves)


@st.composite
def _finished_and_unfinished(draw: st.DrawFn) -> tuple[_Ledger, _Ledger]:
    """A finished ledger holding a deferral, and the same ledger with one leaf unfinished."""
    drawn = draw(st.lists(_DONE | _DEFERRED, max_size=7))
    forced_at = draw(st.integers(0, len(drawn)))
    finished = [*drawn[:forced_at], draw(_DEFERRED), *drawn[forced_at:]]
    at = draw(st.integers(0, len(finished) - 1))
    unfinished = [*finished[:at], draw(_UNFINISHING), *finished[at + 1 :]]
    ids = draw(_ids(len(finished)))
    return _ledger(ids, finished), _ledger(ids, unfinished)


# ---------------------------------------------------------------------------
# (a) Never offered, never a barrier, at any batch size
# ---------------------------------------------------------------------------


@given(ledger=_ledgers_with_a_deferral())
def test_a_deferred_leaf_is_never_offered_and_never_a_barrier_at_any_batch_size(
    ledger: _Ledger,
) -> None:
    """The offered sequence is the built authorable sequence, and deferral only subtracts."""
    truth = _truth(ledger)
    assert truth.deferred, "the generator must build a deferral, or every clause is vacuous"
    report = _census(_render(ledger, deferrals=True))

    for size in (*range(len(ledger.entries) + 2), DEFAULT_BATCH):
        offered = report.next_batch(size)
        barriers = report.barriers_crossed(size)
        assert offered == truth.authorable[:size]
        assert barriers == _barriers(ledger, truth, size)
        assert not truth.deferred & {*offered, *barriers}, (size, offered, barriers)

    assert report.deferred_ids == tuple(sorted(truth.deferred, key=_numeric))
    assert report.deferred == len(truth.deferred)
    assert not truth.deferred & {*report.authorable, *report.gated_jobs}
    # Terminal, yet still inside `open`: both partitions hold.
    assert report.done + report.pending + report.open_count == report.leaves
    assert len(report.authorable) + len(report.gated) + report.deferred == report.open_count

    # Surgical: dropping every deferred line changes WHICH ids are offered and nothing else.
    undeferred = _census(_render(ledger, deferrals=False))
    assert undeferred.deferred == 0
    assert report.authorable == tuple(
        task_id for task_id in undeferred.authorable if task_id not in truth.deferred
    )
    assert tuple(report.gated_jobs) == tuple(
        task_id for task_id in undeferred.gated_jobs if task_id not in truth.deferred
    )


def test_a_deferral_behind_a_checkpoint_cannot_make_the_checkpoint_crossed() -> None:
    """Counted as an offered id, deferred 9.3 would report gated 9.2 as stepped over."""
    deferral = "    - deferred: operator decision 2026-09-16, reason recorded\n"
    text = (
        "- [ ] 9. Parent\n"
        "  - [ ] 9.1 Authorable, and the only offered id\n"
        "  - [ ] 9.2 A CI-gated checkpoint\n"
        "    - discharge: uplift.yml::twin-regret\n"
        "  - [ ] 9.3 Deferred, after the checkpoint\n" + deferral
    )
    report = _census(text)
    assert report.next_batch(DEFAULT_BATCH) == ("9.1",)
    assert report.deferred_ids == ("9.3",)
    assert all(report.barriers_crossed(size) == () for size in range(DEFAULT_BATCH + 1))

    # The converse, so the clause is not vacuous: undeferred, 9.3 is offered and 9.2 crossed.
    undeferred = _census(text.replace(deferral, ""))
    assert undeferred.next_batch(DEFAULT_BATCH) == ("9.1", "9.3")
    assert undeferred.barriers_crossed(DEFAULT_BATCH) == ("9.2",)


# ---------------------------------------------------------------------------
# (b) Each refusal fires by construction and names its leaf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule", sorted(_OFFENDERS))
@given(data=st.data())
def test_each_deferral_refusal_fires_by_construction_and_names_its_leaf(
    rule: str, data: st.DataObject
) -> None:
    """Built, not waited for; and paired with the converse, which must pass."""
    base = data.draw(st.lists(_CLEAN, max_size=6))
    at = data.draw(st.integers(0, len(base)))
    leaves = [*base[:at], data.draw(_OFFENDERS[rule]), *base[at:]]
    ids = data.draw(_ids(len(leaves)))
    named = f'task {ids[at]} "'
    report = _census(_render(_ledger(ids, leaves), deferrals=True))

    assert _refusals(report) == ((rule, _subject(ids[at])),)
    assert named in report.findings[0].detail, "the printed detail must name the leaf"
    assert any(
        line.startswith(f"  [??] {rule}: ") and named in line for line in format_report(report)
    )
    assert report.outcome is CensusOutcome.UNAVAILABLE
    assert report.exit_code == 2, "non-passing under --check, as unharvested-pending is"
    assert report.complete is False

    clean = _census(_render(_ledger([*ids[:at], *ids[at + 1 :]], base), deferrals=True))
    assert clean.findings == ()
    assert clean.outcome is CensusOutcome.PASS


_TASK_9_12: Final[str] = (
    "- [x] 9.12 Write property test for the comparator's recorded restock configuration\n"
    "  - Also pins that a missing key is **refused rather than defaulted**, and that every\n"
    "    `deferred:` entry is prose naming its owning task rather than a placeholder number\n"
)


def test_a_wrapped_prose_line_that_begins_with_the_key_is_not_a_deferral() -> None:
    """Task 9.12's own shape, from the committed ledger.

    Read with ``discharge:``'s key matching alone this is a deferral of a done leaf, and the
    committed census goes non-passing on a sentence. The converse proves a real sub-bullet in
    the same body is still read, and still refused.
    """
    assert parse_records(_TASK_9_12)[0].deferred is None
    prose = _census(_TASK_9_12)
    assert prose.findings == ()
    assert prose.outcome is CensusOutcome.PASS

    bullet = _census(_TASK_9_12 + "  - deferred: superseded by task 28.5\n")
    assert [finding.rule for finding in bullet.findings] == ["deferred-marked-done"]


# ---------------------------------------------------------------------------
# (c) complete is exactly "nothing authorable, gated, pending or refused"
# ---------------------------------------------------------------------------


@given(ledger=_ledgers())
def test_complete_is_exactly_nothing_authorable_gated_or_pending_and_nothing_refused(
    ledger: _Ledger,
) -> None:
    """The contract's biconditional, judged against what was built."""
    truth = _truth(ledger)
    report = _census(_render(ledger, deferrals=True))

    assert _refusals(report) == tuple(sorted(truth.findings))
    finished = not (truth.authorable or truth.gated or truth.pending or truth.findings)
    assert report.complete == finished
    assert report.complete == (
        not report.authorable and not report.gated and report.pending == 0 and not report.findings
    )


@given(pair=_finished_and_unfinished())
def test_both_verdicts_are_reached_and_only_done_or_deferred_leaves_admit_completion(
    pair: tuple[_Ledger, _Ledger],
) -> None:
    """Each example reaches BOTH truth values, so neither branch can be empty."""
    finished, unfinished = pair
    finished_report = _census(_render(finished, deferrals=True))
    assert finished_report.leaves == len(finished.entries)
    assert finished_report.deferred >= 1, "a deferral must be shown compatible with completion"
    assert finished_report.done + finished_report.deferred == finished_report.leaves
    assert finished_report.outcome is CensusOutcome.PASS
    assert finished_report.complete is True
    assert "  complete      : yes" in format_report(finished_report)

    truth = _truth(unfinished)
    assert truth.authorable or truth.gated or truth.pending or truth.findings
    unfinished_report = _census(_render(unfinished, deferrals=True))
    assert unfinished_report.complete is False
    assert "  complete      : no" in format_report(unfinished_report)


def test_a_ledger_with_no_leaves_is_never_complete() -> None:
    """The non-vacuity clause: "nothing remains" over nothing is not a finished spec."""
    empty = _census("# Plan\n\nEvery checkbox was reformatted away.\n")
    assert (empty.leaves, empty.findings, empty.outcome) == (0, (), CensusOutcome.PASS)
    assert empty.complete is False

    unreadable = census(
        (), spec="synthetic", source="synthetic/tasks.md", read_error="could not be read"
    )
    assert unreadable.complete is False
    assert unreadable.exit_code == 2


def test_the_json_carries_the_deferral_count_the_sorted_ids_and_the_verdict() -> None:
    """``deferred_ids`` sorts by number -- ``9.2`` before ``9.12`` -- against ledger order."""
    text = (
        "- [ ] 9. Parent\n"
        "  - [ ] 9.12 Deferred, first in ledger order\n"
        "    - deferred: operator decision 2026-09-16, reason recorded\n"
        "  - [x] 9.3 Done\n"
        "  - [ ] 9.2 Deferred, second in ledger order\n"
        "    - **deferred:** superseded by task 28.5's measurement\n"
    )
    report = _census(text)
    payload = json.loads(report.canonical_json())
    assert payload["deferred"] == 2
    assert payload["deferred_ids"] == ["9.2", "9.12"]
    assert payload["complete"] is True

    lines = format_report(report)
    assert "  deferred      : 2   (out of scope, reason recorded - never offered)" in lines
    assert "  complete      : yes" in lines
    assert all(line.isascii() for line in lines)
    assert report.next_batch(DEFAULT_BATCH) == ()


# ---------------------------------------------------------------------------
# (d) A ledger with no deferred line classifies exactly as before
# ---------------------------------------------------------------------------

_NO_DEFERRALS: Final[str] = """# Plan

- [x] 1. Parent whose children are all done
  - [x] 1.1 First child
  - [x] 1.2 Second child

- [ ] 2. Checkpoint with no children
  - discharge: uplift.yml::twin-regret

- [ ] 3. Parent with mixed children
  - [~] 3.1 Authored, discharge owed
    - discharge: ci.yml::uplift-verify
    - last-checked: run 34590696403
  - [ ] 3.2 Open and authorable, carrying task 9.12's wrapped prose line
    - Also pins that a missing key is refused rather than defaulted, and that every
      `deferred:` entry is prose naming its owning task
  - [ ] 3.3 Open but CI-gated
    - **discharge:** `uplift.yml::uplift-proof`
  - [ ] 3.4 Open and authorable, after a barrier

- [ ] 4. Deeply nested leaf
    - [ ] 4.1 Indented four spaces, not two
"""


def test_a_ledger_without_deferred_lines_classifies_exactly_as_before() -> None:
    """Every bucket, batch and barrier, pinned by hand from the pre-change census.

    Leaf 3.2 carries task 9.12's wrapped prose line, so the committed ledger's awkward shape
    sits inside the pin rather than beside it.
    """
    report = _census(_NO_DEFERRALS)
    assert (report.leaves, report.parents, report.done, report.pending) == (8, 3, 2, 1)
    assert report.open_count == 5
    assert report.authorable == ("3.2", "3.4", "4.1")
    assert report.gated == ("2 -> uplift.yml::twin-regret", "3.3 -> uplift.yml::uplift-proof")
    assert report.open_order == ("2", "3.2", "3.3", "3.4", "4.1")
    assert report.gated_jobs == {"2": "uplift.yml::twin-regret", "3.3": "uplift.yml::uplift-proof"}
    assert report.pending_discharges == ("3.1 -> ci.yml::uplift-verify",)
    assert report.unharvested == ()
    assert report.findings == ()
    assert report.outcome is CensusOutcome.PASS
    assert [report.next_batch(size) for size in (0, 1, 2, 3, DEFAULT_BATCH)] == [
        (),
        ("3.2",),
        ("3.2", "3.4"),
        ("3.2", "3.4", "4.1"),
        ("3.2", "3.4", "4.1"),
    ]
    assert [report.barriers_crossed(size) for size in (0, 1, 2, 3)] == [
        (),
        ("2",),
        ("2", "3.3"),
        ("2", "3.3"),
    ]
    # The only new facts, each at its honest value: nothing deferred, and work remains.
    assert (report.deferred, report.deferred_ids, report.complete) == (0, (), False)


# ---------------------------------------------------------------------------
# (e) A reasonless deferral defers nothing, and is still refused by name
# ---------------------------------------------------------------------------


@given(data=st.data())
def test_a_reasonless_deferral_leaves_its_leaf_offered_exactly_as_if_the_line_were_absent(
    data: st.DataObject,
) -> None:
    """Fail-safe: the refusal names the line and the census does not obey it.

    "As if absent" is judged against the SAME ledger rendered without the line, never
    restated. The converse gives the line a reason and the leaf leaves the offer, so neither
    clause can hold by the census ignoring ``deferred:`` altogether.
    """
    base = data.draw(st.lists(_CLEAN, max_size=6))
    at = data.draw(st.integers(0, len(base)))
    offender = data.draw(
        _leaf(" ", discharge=st.none() | _JOBS, last_checked=st.none(), reason=_NO_REASON)
    )
    ids = data.draw(_ids(len(base) + 1))
    task_id, subject = ids[at], _subject(ids[at])
    ledger = _ledger(ids, [*base[:at], offender, *base[at:]])
    report = _census(_render(ledger, deferrals=True))
    absent = _census(_render(ledger, deferrals=False))

    if offender.discharge is None:
        assert task_id in report.next_batch(DEFAULT_BATCH), "the reasonless line hid the leaf"
    else:
        assert report.gated_jobs[task_id] == offender.discharge
    assert (report.deferred, report.deferred_ids) == (0, ())
    assert (report.authorable, report.gated, report.open_order, report.gated_jobs) == (
        absent.authorable,
        absent.gated,
        absent.open_order,
        absent.gated_jobs,
    )
    for size in (*range(len(ids) + 2), DEFAULT_BATCH):
        assert report.next_batch(size) == absent.next_batch(size)
        assert report.barriers_crossed(size) == absent.barriers_crossed(size)

    refused = {("deferred-without-reason", subject)}
    if offender.discharge is not None:
        refused.add(("deferred-and-gated", subject))
    assert _refusals(report) == tuple(sorted(refused))
    assert absent.findings == ()
    assert report.exit_code == 2, "offered AND refused: the census is still non-passing"

    with_reason = replace(offender, reason=data.draw(_REASONS), discharge=None)
    converse = _ledger(ids, [*base[:at], with_reason, *base[at:]])
    reasoned = _census(_render(converse, deferrals=True))
    assert reasoned.deferred_ids == (task_id,)
    assert task_id not in {*reasoned.authorable, *reasoned.gated_jobs}
    assert reasoned.findings == ()


# ---------------------------------------------------------------------------
# (f) A checkbox the record grammar rejects is a leaf in no count: never complete
# ---------------------------------------------------------------------------

#: The three spellings the record grammar rejects; each names a leaf no count could see.
_MALFORMED: Final[tuple[str, ...]] = ("- [ ] 31.1: X", "* [ ] 31.1 X", "- [ ] **31.1** X")
#: What all three mean, spelled as the grammar reads it.
_REPAIRED: Final[str] = "- [ ] 31.1 X"
#: Every leaf done, so only a leaf the grammar cannot see can stand between this ledger and
#: ``complete: yes``.
_FINISHED: Final[tuple[str, ...]] = (
    "# Plan",
    "",
    "- [x] 30. Parent",
    "  - [x] 30.1 Done",
    "    - Files: `some/module.py`",
    "  - [x] 30.2 Done",
)


def _text(lines: Sequence[str]) -> str:
    return "\n".join([*lines, ""])


@pytest.mark.parametrize("shape", _MALFORMED)
@given(at=st.integers(0, len(_FINISHED)), indent=st.sampled_from(["", "  ", "    ", "\t"]))
def test_a_checkbox_the_grammar_rejects_is_refused_by_line_and_blocks_completion(
    shape: str, at: int, indent: str
) -> None:
    """At every position and depth, a leaf no record carries can never read as finished.

    The premise is asserted first -- the grammar really cannot see the leaf -- so the refusal
    is the only thing between this ledger and ``complete: yes``. Its converses: without the
    line the same ledger IS finished, and spelled as the grammar reads it the leaf is
    counted, open and offered.
    """
    text = _text([*_FINISHED[:at], f"{indent}{shape}", *_FINISHED[at:]])
    report = _census(text)

    assert "31.1" not in {record.task_id for record in parse_records(text)}
    assert (report.leaves, report.done) == (2, 2), "every leaf the grammar can see is done"
    assert [(item.line, item.text) for item in unparsed_checkboxes(text)] == [(at + 1, shape)]
    assert _refusals(report) == (("unparsed-checkbox", f"line {at + 1}"),)
    assert f"line {at + 1} " in report.findings[0].detail
    assert shape in report.findings[0].detail
    assert report.complete is False
    assert report.outcome is CensusOutcome.UNAVAILABLE
    assert report.exit_code == 2, "non-passing under --check"
    rendered = format_report(report)
    assert "  complete      : no" in rendered
    assert any(line.startswith(f"  [??] unparsed-checkbox: line {at + 1} ") for line in rendered)

    finished = _census(_text(_FINISHED))
    assert (finished.findings, finished.complete) == ((), True)

    repaired = text.replace(shape, _REPAIRED)
    visible = _census(repaired)
    assert unparsed_checkboxes(repaired) == ()
    assert (visible.findings, visible.leaves) == ((), 3)
    assert visible.next_batch(DEFAULT_BATCH) == ("31.1",)
    assert visible.complete is False


def test_a_census_given_no_checkbox_scan_never_reports_complete() -> None:
    """No scan, no ``complete``: absent proof that every checkbox parsed is not a pass (I-7).

    The converse is the same ledger WITH the scan, which is finished -- so the refusal is the
    omission's, and the census invents no finding to make it.
    """
    text = _text(_FINISHED)
    unscanned = census(parse_records(text), spec="synthetic", source="synthetic/tasks.md")
    assert (unscanned.complete, unscanned.findings, unscanned.outcome) == (
        False,
        (),
        CensusOutcome.PASS,
    )
    assert "no checkbox scan was supplied" in unscanned.detail
    assert "  complete      : no" in format_report(unscanned)
    assert _census(text).complete is True
