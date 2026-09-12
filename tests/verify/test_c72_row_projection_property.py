"""The C72 row states the counts of the run that produced them, or admits it has none.

Feature: decision-quality-proof, task 5.10. Requirement **R1.12**.

What was wrong, precisely
------------------------

C72's detail used to end in a fixed sentence -- ``no falsification was probed`` -- and the
sentence was true in every context the check could run in, because the sweep copies the tree
and spawns one subprocess per declared check plus one per operator, which the registry's own
process cannot do. ``docs/state/CURRENT.md`` therefore recorded, permanently, a row that said
the declaration was valid and nothing had been checked. That is honest, and it is also the
end of the story: nothing in the repository ever reported a probe.

R1.12 closes it from the other side. The sweep job writes its canonical report; C72 reads it
back and states three counts from **that** run: probed operators, falsified checks, unproven
operators. The row becomes a projection of an execution instead of a fixed sentence about the
absence of one.

The three things that could go wrong, and are asserted here
----------------------------------------------------------

1. **Projecting the wrong run.** A row that reads a stale payload states counts for a sweep
   that is not this one. So the resolved path is named in the detail -- provenance is a claim,
   and a claim is stated rather than assumed -- and the environment variable the job sets
   takes precedence over the default path.
2. **Projecting a run that proved nothing.** A payload carrying ``probed: false`` is not a
   probe, and one carrying ``baseline_suppressed: true`` proved nothing by construction
   (R1.16): without a baseline an already-red gate stays red under mutation and reads as
   falsified. Either must leave the row on its unprobed detail, saying why.
3. **Reading an absence as a pass.** No payload, unreadable bytes, unparseable JSON and a
   document that is not a report are four different repairs and four distinct reasons -- and
   all four keep the row non-passing. A SKIP is not a PASS (I-7).

The status, not just the detail
------------------------------

R1.12 is written about the detail, but a row whose detail reported thirty falsified operators
while its status stayed SKIP would be self-contradictory. So the projected row's **status** is
derived from the read-back report's verdict through the same ``GATE_STATUS`` mapping every
other gate row uses, and that is asserted for all three verdicts -- including that
``unavailable`` maps to SKIP and never to PASS.

Nothing here starts a process. The payloads are produced by driving the aggregate over
generated declarations with the harness's own ``sweep`` substituted (I-0); no gate's
evaluator is replaced (R9.5).

``max_examples`` is never set -- the budget comes from the root ``conftest.py`` profiles.

Locus: ``ci.yml::uplift-verify``'s fast step.

**Validates: Requirement 1.12**
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import gate_fault_injection as gfi
from scripts.audit import verify_claims as vc
from scripts.audit.gate_fault_injection import (  # noqa: TC001 - runtime import: typeguard\r
    FaultInjectionReport,  # may resolve test annotations at call time, and a TYPE_CHECKING-only\r
)  # name would then be unresolvable.\r
from tests.verify.sweep_strategies import (
    SWEEP_OUTCOMES,
    SweepDraft,
    patched_sweep,
    probe_result,
    sweep_drafts,
)

REGISTERED_IDS: Final[tuple[str, ...]] = gfi.registered_ids()

#: The sentence the row falls back to when it has no report to project. Quoted from the
#: subject so a reword is a test failure rather than a silently unasserted clause.
UNPROBED_FRAGMENT: Final[str] = "no falsification was probed"


def _sweep_report(
    draft: SweepDraft,
    outcomes: tuple[gfi.Outcome, ...],
    *,
    probe: bool = True,
    with_baseline: bool = True,
    complete: bool = True,
) -> FaultInjectionReport:
    """The report a sweep of ``draft`` would produce, built through the real aggregate."""
    pairs = draft.declared_pairs if complete else draft.declared_pairs[:-1]
    results = tuple(
        probe_result(check, operator_id, outcome)
        for (check, operator_id), outcome in zip(pairs, outcomes, strict=False)
    )
    with tempfile.TemporaryDirectory(prefix="c72-projection-build-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results):
            return gfi.evaluate(
                declaration_path=declaration_path,
                schema_path=gfi.SCHEMA_FILE,
                probe=probe,
                with_baseline=with_baseline,
            )


def _written(report: FaultInjectionReport, directory: Path) -> Path:
    """``--report-json``'s exact output shape: canonical JSON, one trailing newline."""
    path = directory / "fault-injection.json"
    path.write_text(
        json.dumps(report.model_dump(mode="json"), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


@st.composite
def probed_reports(draw: st.DrawFn) -> FaultInjectionReport:
    """A report from a complete, baselined sweep -- the only kind that may be projected."""
    draft = draw(sweep_drafts(registered=REGISTERED_IDS))
    outcomes = tuple(
        draw(
            st.lists(
                st.sampled_from(SWEEP_OUTCOMES),
                min_size=draft.declared_operator_count,
                max_size=draft.declared_operator_count,
            )
        )
    )
    return _sweep_report(draft, outcomes)


# Feature: decision-quality-proof, Property 41: The C72 row projects the counts of the run that produced it  # noqa: E501
@given(report=probed_reports())
def test_the_row_states_the_three_counts_of_the_report_it_was_pointed_at(
    report: FaultInjectionReport,
) -> None:
    """R1.12: probed operators, falsified checks, unproven operators -- from that run.

    Each count is asserted against the payload rather than against a literal, so the test
    cannot pass by agreeing with a number somebody typed. The units are asserted too: the
    probed and declared terms are operator counts and say ``operator(s)``, while the
    falsified term is a check count -- and mixing the two is the defect R1.7 exists to
    prevent one layer down.
    """
    with tempfile.TemporaryDirectory(prefix="c72-projection-") as tmp:
        path = _written(report, Path(tmp))
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv(gfi.SWEEP_REPORT_ENV, str(path))
            result = vc.check_gate_fault_injection()

    assert result.cid == "C72"
    assert UNPROBED_FRAGMENT not in result.detail

    assert (
        f"{report.probed_operators} of {report.declared_operators} declared operator(s) probed"
        in result.detail
    )
    assert f"{len(report.falsified_ids)} check(s) falsified" in result.detail
    assert f"{len(report.unproven_operator_ids)} operator(s) unproven" in result.detail

    # The status is the read-back verdict, mapped through the same table every gate row uses.
    assert result.status == vc.GATE_STATUS[report.verdict]
    assert result.status in vc.STATUSES
    if report.verdict != "pass":
        assert result.status != "PASS"

    # Provenance: the row names the file it read and says the environment resolved it, so a
    # reader can tell a same-job report from a restored artifact without leaving the log.
    assert "environment" in result.detail
    assert path.name in result.detail


@given(report=probed_reports())
def test_the_environment_variable_outranks_the_default_path(
    report: FaultInjectionReport,
) -> None:
    """R1.12: "the run that produced it" is a provenance claim, so it needs a provenance.

    A file at the default path could have been written by anything -- a hand run, a previous
    job, a restored artifact. The environment variable is set by the job that ran the sweep,
    so it is the one piece of evidence tying the payload to the run. It therefore wins, and
    the resolution is reported so a reader can see which one was used.
    """
    with tempfile.TemporaryDirectory(prefix="c72-projection-env-") as tmp:
        declared = _written(report, Path(tmp))

        chosen, reason = gfi.read_sweep_report(path=Path(tmp) / "does-not-exist.json")
        assert chosen is None, "with no environment variable the argument path is used"
        assert "no sweep report" in reason

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv(gfi.SWEEP_REPORT_ENV, str(declared))
            chosen, reason = gfi.read_sweep_report(path=Path(tmp) / "does-not-exist.json")
        assert chosen is not None
        assert "environment" in reason
        assert chosen.probed_operators == report.probed_operators
        assert chosen.falsified_ids == report.falsified_ids
        assert chosen.unproven_operator_ids == report.unproven_operator_ids


@given(
    draft=sweep_drafts(registered=REGISTERED_IDS),
    suppressed=st.booleans(),
)
def test_a_payload_that_proved_nothing_is_read_but_never_projected(
    draft: SweepDraft, suppressed: bool
) -> None:
    """R1.12 with R1.16: a report of a non-probe is not a probe.

    Two payloads reach this branch. One has ``probed: false`` -- a declaration-only run, which
    is what every context outside the sweep job produces. The other has
    ``baseline_suppressed: true``, where probes did run and none of them counts, because
    without an unmutated baseline an already-red gate stays red under mutation and reads as
    falsified.

    Both are *readable*, which is why they are dangerous: the row would state real-looking
    counts from a run that established nothing. So the row falls back to its unprobed detail
    and says which of the two it found -- reporting the file it read rather than pretending it
    found none, because "there is a payload and it proves nothing" is a different state from
    "there is no payload".
    """
    outcomes = tuple("falsified" for _ in draft.declared_pairs)
    report = (
        _sweep_report(draft, outcomes, with_baseline=False)
        if suppressed
        else _sweep_report(draft, outcomes, probe=False)
    )
    assert (report.baseline_suppressed if suppressed else not report.probed)

    with tempfile.TemporaryDirectory(prefix="c72-projection-hollow-") as tmp:
        path = _written(report, Path(tmp))
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv(gfi.SWEEP_REPORT_ENV, str(path))
            result = vc.check_gate_fault_injection()

    assert result.cid == "C72"
    assert result.status != "PASS"
    assert "nothing is projected from it" in result.detail
    assert ("a suppressed baseline" if suppressed else "no probe") in result.detail
    # The falsified count of the hollow payload never reaches the row.
    assert f"{len(report.falsified_ids)} check(s) falsified" not in result.detail


@given(
    corruption=st.sampled_from(
        (
            "absent",
            "not-json",
            "json-but-not-an-object",
            "object-but-not-a-report",
        )
    )
)
def test_every_unreadable_payload_keeps_the_row_unprobed_and_non_passing(
    corruption: str,
) -> None:
    """R1.12 / I-7: four repairs, four reasons, one status -- and it is not PASS.

    The reasons are asserted to be pairwise distinct because that is the actionable content:
    "no report" points at the job, "not parseable JSON" at a truncated write, and "not a valid
    report" at a schema change that moved a field the consumer reads. A single "could not
    read" message would name none of them.

    In every case the row keeps the sentence it had before this feature existed. That is the
    honest state of a job in which no sweep ran, and it is deliberately the same sentence: a
    reader who sees it knows nothing was probed, which is exactly what they should conclude.
    """
    with tempfile.TemporaryDirectory(prefix="c72-projection-broken-") as tmp:
        path = Path(tmp) / "fault-injection.json"
        if corruption == "not-json":
            path.write_text('{"verdict": "pass"', encoding="utf-8")
        elif corruption == "json-but-not-an-object":
            path.write_text("[1, 2, 3]", encoding="utf-8")
        elif corruption == "object-but-not-a-report":
            path.write_text(
                json.dumps({"verdict": "pass", "probed": True}), encoding="utf-8"
            )

        chosen, reason = gfi.read_sweep_report(path=path)
        assert chosen is None
        expected = {
            "absent": "no sweep report",
            "not-json": "not parseable JSON",
            "json-but-not-an-object": "not a JSON object",
            "object-but-not-a-report": "not a valid report",
        }[corruption]
        assert expected in reason
        assert path.name in reason or str(path) in reason

        with pytest.MonkeyPatch.context() as mp:
            mp.setenv(gfi.SWEEP_REPORT_ENV, str(path))
            result = vc.check_gate_fault_injection()

    assert result.cid == "C72"
    assert result.status != "PASS"
    assert UNPROBED_FRAGMENT in result.detail
    assert expected in result.detail


def test_the_four_unreadable_reasons_are_pairwise_distinct() -> None:
    """The claim the case above makes per-corruption, asserted across all of them at once."""
    reasons: list[str] = []
    with tempfile.TemporaryDirectory(prefix="c72-projection-distinct-") as tmp:
        root = Path(tmp)
        absent = root / "absent.json"
        not_json = root / "not-json.json"
        not_json.write_text("{", encoding="utf-8")
        not_object = root / "not-object.json"
        not_object.write_text("42", encoding="utf-8")
        not_report = root / "not-report.json"
        not_report.write_text(json.dumps({"declaration": "x"}), encoding="utf-8")
        for candidate in (absent, not_json, not_object, not_report):
            chosen, reason = gfi.read_sweep_report(path=candidate)
            assert chosen is None
            reasons.append(reason.replace(candidate.name, "<file>"))
    assert len(set(reasons)) == 4


def test_the_unprobed_row_still_reports_both_units_and_never_passes() -> None:
    """The row a normal registry run produces, asserted against the committed declaration.

    This is the invocation every context outside the sweep job reaches, so it is the row that
    appears in ``docs/state/CURRENT.md``. Two obligations survive from before this feature:
    the row is non-passing, because validating a declaration proves nothing about any gate
    (I-7); and it reports the counts it *can* report, in both units, so a reader can see the
    size of what has not been proven rather than only that something has not been.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv(gfi.SWEEP_REPORT_ENV, str(Path("artifacts") / "absent-on-purpose.json"))
        result = vc.check_gate_fault_injection()

    declaration = gfi.evaluate(probe=False)
    assert result.cid == "C72"
    assert result.status == "SKIP"
    assert result.status != "PASS"
    assert UNPROBED_FRAGMENT in result.detail
    assert f"{len(declaration.declared_ids)} of {len(declaration.registered_ids)} registered" in (
        result.detail
    )
    assert f"{declaration.declared_operators} operator(s)" in result.detail
    assert f"{len(declaration.undeclared_ids)} undeclared" in result.detail
