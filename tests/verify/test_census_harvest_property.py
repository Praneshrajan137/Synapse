"""An unharvested `[~]` is non-passing, and the refusal is proven by construction.

Feature: decision-quality-proof, Property 63: A `[~]` whose `last-checked:` names no run id its
discharge job was read at is non-passing, and only `[~]` carries that obligation.

Session 8, guardrail **G4** of `.kiro/steering/throughput-with-integrity.md`. Subject:
``scripts/audit/spec_ledger_census.py``.

**Why the obligation is an artifact rather than a network call.** G4 is "no session closes with
an unharvested ``[~]``". The obvious implementation asks GitHub whether each discharge job has
reported -- which would move this census out of the LOCAL allow-list in
``.kiro/steering/execution-routing.md``, where it sits as a ~1s pure file reader, and couple a
cheap local hygiene check to an API's availability. So the harvest leaves a ``last-checked:``
sub-bullet, exactly as the mark already leaves a ``discharge:`` one, and the census asserts the
artifact exists. **Derivable from the file alone, and auditable by a reader.**

**Why the artifact must name a run id, not merely exist.** Session 11 wrote ``last-checked: none
yet -- pushed at the session-11 wave-3 head; no run has read it yet`` on five leaves, and a rule
accepting any non-empty value passed all five: G4's artifact existed and named nothing a later
reader could open. A harvest now names a GitHub Actions run id -- the word ``run``, then an
integer of at least 8 digits, backticks optional -- and any other value is refused under the
same rule as a missing line, by a detail that tells the two apart.

**Why it is proven by construction and not by observation.** The committed ledger often holds no
``[~]`` at all -- it held none when this file was written, and holds none again whenever every
discharge has been harvested -- so the repository cannot be relied on to exercise this clause. A
gate that has never executed is not evidence (this spec's own lesson), so the failing path is
built here from synthetic ledgers rather than waited for. **The clause that matters is the one
asserting it FAILS**, because a check that only ever passes is indistinguishable from one that
does nothing. The oracle is the generator: a value harvests because the test BUILT it from a run
id, never because the census's own pattern says so.

**What this prevents, measured.** Task 26.1 sat dischargeable for **two sessions**: both of its
discharge subjects had reported and no sweep noticed, because sweeps were scoped to what a wave
*changed*. From the ledger alone, a mark whose proof has silently arrived looks exactly like one
still waiting.

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal appears in
this file** (CF-13).

Locus: ``ci.yml::uplift-verify-fast-3``, which collects ``tests/verify/test_[a-o]*``. **Not**
slow-marked: pure parsing of in-memory text, no filesystem, no network, no subprocess.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.spec_ledger_census import (
    CensusOutcome,
    census,
    parse_records,
)

if TYPE_CHECKING:
    from scripts.audit.spec_ledger_census import LedgerCensus

_JOBS = st.sampled_from(
    [
        "ci.yml::uplift-verify",
        "uplift.yml::twin-regret (checkpoint A)",
        "regenerate-truth-docs.yml::regenerate",
        "truth-gates.yml::truth-gates",
    ]
)
#: Each value the test BUILT from a run id, mapped to that id: the oracle every harvest reads.
_RUN_IDS: Final[dict[str, str]] = {
    "run 34590696403": "34590696403",
    "run 34574731853 (sha 2d86899)": "34574731853",
    "Run `34505290388` (SYNAPSE CI, sha 5eef6ee) -- shard 3/4 `success`": "34505290388",
    "Uplift Proof run 36860454801 (sha ec0eb91), cell off_off": "36860454801",
}
_RUNS = st.sampled_from(sorted(_RUN_IDS))
#: Session 11's line, verbatim. It even contains the word ``run``.
_NONE_YET: Final[str] = "none yet -- pushed at the session-11 wave-3 head; no run has read it yet"
#: Values naming NO run id: each must leave a ``[~]`` exactly as unharvested as a missing line.
_NOT_RUNS = st.sampled_from(
    [
        _NONE_YET,
        "none yet",
        "34590696403",  # no word `run`: a bare number may be a date, a count, a digest
        "run 1234567",  # seven digits
        "run 2 (an ordinal, as this ledger's prose numbers its measurements)",
        "sha 5eef6ee -- pushed, not yet read",
    ]
)
#: How every finding names the one leaf ``_ledger`` builds.
_LEAF: Final[str] = 'task 99 "A synthetic leaf"'


def _ledger(mark: str, *, discharge: str, last_checked: str | None) -> str:
    """One leaf record, with the harvest bullet present or absent."""
    body = [f"  - discharge: {discharge}"]
    if last_checked is not None:
        body.append(f"  - last-checked: {last_checked}")
    body.append("  - Files: `some/module.py`")
    return "\n".join([f"- [{mark}] 99. A synthetic leaf", *body, ""])


def _verdict(text: str) -> LedgerCensus:
    records = parse_records(text)
    return census(records, spec="synthetic", source="synthetic/tasks.md")


def _refusal(report: LedgerCensus) -> str:
    """The one ``unharvested-pending`` detail a single-leaf ledger can raise."""
    return next(
        finding.detail for finding in report.findings if finding.rule == "unharvested-pending"
    )


# ---------------------------------------------------------------------------
# 1. The refusal fires -- this is the clause that makes the check real
# ---------------------------------------------------------------------------


@given(job=_JOBS)
def test_a_pending_leaf_without_a_last_checked_run_is_non_passing(job: str) -> None:
    """The failing path, built rather than waited for."""
    report = _verdict(_ledger("~", discharge=job, last_checked=None))

    assert report.pending == 1
    assert report.unharvested, "an unharvested `[~]` must be named, not merely counted"
    assert report.outcome is CensusOutcome.UNAVAILABLE
    assert report.exit_code == 2, "unavailable is non-passing (I-7)"
    rules = {finding.rule for finding in report.findings}
    assert "unharvested-pending" in rules
    # The finding must name the job, or a reader cannot act on it.
    detail = _refusal(report)
    assert job in detail
    assert "no `last-checked:` line" in detail, "a missing line is told apart from a bad one"


@given(job=_JOBS, value=_NOT_RUNS, run=_RUNS)
def test_a_last_checked_value_that_names_no_run_id_is_non_passing(
    job: str, value: str, run: str
) -> None:
    """The line exists and survives parsing, and still harvests nothing: session 11's shape.

    The premise comes first -- the parser kept the value -- so the refusal is the run-id rule's
    and not a parser that lost the line. The converse writes a run id in the same place.
    """
    text = _ledger("~", discharge=job, last_checked=value)
    record = parse_records(text)[0]
    assert record.last_checked == value, "the value must reach the rule, or this is vacuous"
    assert record.run_id is None
    report = _verdict(text)

    assert report.unharvested == (f"99 -> {job}",)
    assert [finding.rule for finding in report.findings] == ["unharvested-pending"]
    assert report.outcome is CensusOutcome.UNAVAILABLE
    assert report.exit_code == 2, "a line naming no run is as non-passing as no line (I-7)"
    assert job in _refusal(report)

    harvested = _verdict(_ledger("~", discharge=job, last_checked=run))
    assert (harvested.unharvested, harvested.findings) == ((), ())
    assert harvested.outcome is CensusOutcome.PASS


@given(job=_JOBS, run=_RUNS)
def test_a_pending_leaf_that_records_its_run_passes(job: str, run: str) -> None:
    """The converse, so the check cannot pass by failing everything."""
    text = _ledger("~", discharge=job, last_checked=run)
    report = _verdict(text)

    assert report.pending == 1
    assert report.unharvested == ()
    assert report.outcome is CensusOutcome.PASS
    assert report.exit_code == 0
    # The id read is the one the test built -- not a sha's digits, not a date's.
    assert parse_records(text)[0].run_id == _RUN_IDS[run]


# ---------------------------------------------------------------------------
# 2. Only `[~]` carries the obligation
# ---------------------------------------------------------------------------


@given(job=_JOBS, value=st.none() | _NOT_RUNS)
def test_an_open_gated_leaf_owes_no_harvest(job: str, value: str | None) -> None:
    """An open leaf has not been authored, so no proof is owed -- whatever its line says."""
    report = _verdict(_ledger(" ", discharge=job, last_checked=value))

    assert report.open_count == 1
    assert report.unharvested == ()
    assert report.outcome is CensusOutcome.PASS


@given(job=_JOBS, value=st.none() | _NOT_RUNS)
def test_a_done_leaf_owes_no_harvest(job: str, value: str | None) -> None:
    """A `[x]` has already had its proof; re-demanding one would be noise, whatever it says."""
    report = _verdict(_ledger("x", discharge=job, last_checked=value))

    assert report.done == 1
    assert report.unharvested == ()
    assert report.outcome is CensusOutcome.PASS


# ---------------------------------------------------------------------------
# 3. What names a run, case by case
# ---------------------------------------------------------------------------


def test_none_yet_is_unharvested() -> None:
    """Session 11's line, verbatim: it satisfied G4 on five leaves while naming no run.

    It contains the word ``run`` -- "no run has read it yet" -- so a rule that looks for the
    word alone, without the id after it, would still accept it.
    """
    job = "uplift.yml::twin-regret (checkpoint A)"
    report = _verdict(_ledger("~", discharge=job, last_checked=_NONE_YET))

    assert report.unharvested == (f"99 -> {job}",)
    assert report.exit_code == 2


def test_a_run_id_under_eight_digits_is_unharvested() -> None:
    """Seven digits is refused and eight harvests: the floor is pinned from both sides.

    Below it sit an ordinal -- this ledger's prose calls two measurements ``run 1`` and
    ``run 2`` -- and a workflow run number, neither of which names one run a reader can open.
    """
    job = "ci.yml::uplift-verify"
    seven = _ledger("~", discharge=job, last_checked="run 1234567")
    eight = _ledger("~", discharge=job, last_checked="run 12345678")

    assert parse_records(seven)[0].run_id is None
    assert _verdict(seven).unharvested == (f"99 -> {job}",)
    assert _verdict(seven).exit_code == 2
    assert parse_records(eight)[0].run_id == "12345678"
    assert (_verdict(eight).unharvested, _verdict(eight).exit_code) == ((), 0)


def test_a_backticked_run_id_is_harvested() -> None:
    """The ledger's own spelling, ``run `<id>```, mid-line and where it ends the line.

    At the end of a line the census's emphasis stripping removes the closing backtick, so an id
    whose wrapping lost its second half must still be read -- this pins that it is.
    """
    job = "frontend.yml::quality step 8 (Vitest unit + property tests)"
    for value in ("run `34686422504`", "run `34686422504` (SYNAPSE Frontend CI, sha 27a74a3)"):
        text = _ledger("~", discharge=job, last_checked=value)
        assert parse_records(text)[0].run_id == "34686422504", value
        report = _verdict(text)
        assert (report.unharvested, report.findings, report.exit_code) == ((), (), 0), value


def test_the_refusal_names_the_leaf_and_says_no_run_id_was_found() -> None:
    """A session acts on the detail, so it must say WHICH leaf and WHAT the line held.

    A missing line and a line naming no run are told apart, and the value is quoted -- cut, so
    a paragraph-long line cannot flood the report, but from its first character, so the line
    can be found in the ledger.
    """
    job = "ci.yml::uplift-verify"
    long_value = _NONE_YET + " -- " + "and the paragraph goes on " * 8 + "END-OF-VALUE"
    missing = _refusal(_verdict(_ledger("~", discharge=job, last_checked=None)))
    unnamed = _refusal(_verdict(_ledger("~", discharge=job, last_checked=long_value)))

    for detail in (missing, unnamed):
        assert _LEAF in detail, "the detail must name the leaf"
        assert job in detail, "and the job that owes its proof"
    assert "no `last-checked:` line" in missing
    assert "no `last-checked:` line" not in unnamed
    assert "names no run id" in unnamed
    assert _NONE_YET[:30] in unnamed, "quoted from its first character"
    assert "END-OF-VALUE" not in unnamed, "and cut, not reproduced whole"


def test_only_the_first_last_checked_line_is_read_and_previously_lines_never_are() -> None:
    """Keyed as ``discharge:`` is: the first ``last-checked:`` is the record, the rest history.

    So a later line cannot rescue a first one that names no run, and a ``previously:`` line --
    the ledger's shape once a run is superseded -- harvests nothing however real its run is.
    """
    job = "ci.yml::uplift-verify"
    head = f"- [~] 99. A synthetic leaf\n  - discharge: {job}\n"
    none_first = head + "  - last-checked: none yet\n  - last-checked: run 36976629141\n"
    run_first = head + "  - last-checked: run 36976629141\n  - last-checked: none yet\n"
    history = head + "  - previously: run 36860316695 (sha ec0eb91) -- cancelled at its bound\n"

    assert _verdict(none_first).unharvested == (f"99 -> {job}",)
    assert _verdict(run_first).unharvested == ()
    assert parse_records(history)[0].last_checked is None
    assert "no `last-checked:` line" in _refusal(_verdict(history))


# ---------------------------------------------------------------------------
# 4. The check is not vacuous on the shape it will actually see
# ---------------------------------------------------------------------------


def test_the_check_is_not_vacuous_on_the_shape_it_will_actually_see() -> None:
    """A `[~]` with the bullet and one without must reach DIFFERENT verdicts.

    Without this, both clauses above could pass while the parser ignored the bullet
    entirely -- the `None == None` shape C75 exists to close, one level up.
    """
    job = "ci.yml::uplift-verify"
    without = _verdict(_ledger("~", discharge=job, last_checked=None))
    with_run = _verdict(_ledger("~", discharge=job, last_checked="run 34590696403"))

    assert without.outcome is not with_run.outcome
    assert without.exit_code != with_run.exit_code
    # And the recorded run must survive parsing, or the artifact is write-only.
    records = parse_records(_ledger("~", discharge=job, last_checked="run 34590696403"))
    assert records[0].last_checked == "run 34590696403"
    assert records[0].run_id == "34590696403"
    assert records[0].is_unharvested is False
