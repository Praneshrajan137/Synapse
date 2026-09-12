"""An unharvested `[~]` is non-passing, and the refusal is proven by construction.

Feature: decision-quality-proof, Property 63: A `[~]` that records no run its discharge job
was read at is non-passing, and only `[~]` carries that obligation.

Session 8, guardrail **G4** of `.kiro/steering/throughput-with-integrity.md`. Subject:
``scripts/audit/spec_ledger_census.py``.

**Why the obligation is an artifact rather than a network call.** G4 is "no session closes with
an unharvested ``[~]``". The obvious implementation asks GitHub whether each discharge job has
reported -- which would move this census out of the LOCAL allow-list in
``.kiro/steering/execution-routing.md``, where it sits as a ~1s pure file reader, and couple a
cheap local hygiene check to an API's availability. So the harvest leaves a ``last-checked:``
sub-bullet, exactly as the mark already leaves a ``discharge:`` one, and the census asserts the
artifact exists. **Derivable from the file alone, and auditable by a reader.**

**Why it is proven by construction and not by observation.** The tree currently has ``pending: 0``
-- there is no ``[~]`` anywhere -- so nothing in the repository exercises this clause today. A
gate that has never executed is not evidence (this spec's own lesson), so the failing path is
built here from synthetic ledgers rather than waited for. **The clause that matters is the one
asserting it FAILS**, because a check that only ever passes is indistinguishable from one that
does nothing.

**What this prevents, measured.** Task 26.1 sat dischargeable for **two sessions**: both of its
discharge subjects had reported and no sweep noticed, because sweeps were scoped to what a wave
*changed*. From the ledger alone, a mark whose proof has silently arrived looks exactly like one
still waiting.

Budget inherited from the root ``conftest.py`` profile. **No ``max_examples`` literal appears in
this file** (CF-13).

Locus: ``ci.yml::uplift-verify`` fast step. **Not** slow-marked: pure parsing of in-memory text,
no filesystem, no network, no subprocess.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from scripts.audit.spec_ledger_census import (
    CensusOutcome,
    census,
    parse_records,
)

_JOBS = st.sampled_from(
    [
        "ci.yml::uplift-verify",
        "uplift.yml::twin-regret (checkpoint A)",
        "regenerate-truth-docs.yml::regenerate",
        "truth-gates.yml::truth-gates",
    ]
)
_RUNS = st.sampled_from(["34590696403", "run 34574731853 (sha 2d86899)", "34505290388"])


def _ledger(mark: str, *, discharge: str, last_checked: str | None) -> str:
    """One leaf record, with the harvest bullet present or absent."""
    body = [f"  - discharge: {discharge}"]
    if last_checked is not None:
        body.append(f"  - last-checked: {last_checked}")
    body.append("  - Files: `some/module.py`")
    return "\n".join([f"- [{mark}] 99. A synthetic leaf", *body, ""])


def _verdict(text: str) -> object:
    records = parse_records(text)
    return census(records, spec="synthetic", source="synthetic/tasks.md")


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
    detail = next(f.detail for f in report.findings if f.rule == "unharvested-pending")
    assert job in detail


@given(job=_JOBS, run=_RUNS)
def test_a_pending_leaf_that_records_its_run_passes(job: str, run: str) -> None:
    """The converse, so the check cannot pass by failing everything."""
    report = _verdict(_ledger("~", discharge=job, last_checked=run))

    assert report.pending == 1
    assert report.unharvested == ()
    assert report.outcome is CensusOutcome.PASS
    assert report.exit_code == 0


# ---------------------------------------------------------------------------
# 2. Only `[~]` carries the obligation
# ---------------------------------------------------------------------------


@given(job=_JOBS)
def test_an_open_gated_leaf_owes_no_harvest(job: str) -> None:
    """An open leaf has not been authored, so no proof is owed and none can have arrived."""
    report = _verdict(_ledger(" ", discharge=job, last_checked=None))

    assert report.open_count == 1
    assert report.unharvested == ()
    assert report.outcome is CensusOutcome.PASS


@given(job=_JOBS)
def test_a_done_leaf_owes_no_harvest(job: str) -> None:
    """A `[x]` has already had its proof; re-demanding one would be noise."""
    report = _verdict(_ledger("x", discharge=job, last_checked=None))

    assert report.done == 1
    assert report.unharvested == ()
    assert report.outcome is CensusOutcome.PASS


# ---------------------------------------------------------------------------
# 3. The committed ledger is clean, and that is asserted rather than assumed
# ---------------------------------------------------------------------------


def test_the_check_is_not_vacuous_on_the_shape_it_will_actually_see() -> None:
    """A `[~]` with the bullet and one without must reach DIFFERENT verdicts.

    Without this, both clauses above could pass while the parser ignored the bullet
    entirely -- the `None == None` shape C75 exists to close, one level up.
    """
    job = "ci.yml::uplift-verify"
    without = _verdict(_ledger("~", discharge=job, last_checked=None))
    with_run = _verdict(_ledger("~", discharge=job, last_checked="34590696403"))

    assert without.outcome is not with_run.outcome
    assert without.exit_code != with_run.exit_code
    # And the recorded run must survive parsing, or the artifact is write-only.
    records = parse_records(_ledger("~", discharge=job, last_checked="34590696403"))
    assert records[0].last_checked == "34590696403"
    assert records[0].is_unharvested is False
