"""One outcome per operator, four values, and an absence that says which absence it is.

Feature: decision-quality-proof, task 5.7. Requirements **R1.3, R1.4, R1.5**.

What this closes, and how it differs from Property 3
----------------------------------------------------

Property 3 (``test_declared_falsification_property.py``) already asserts that the
classifier is a total function of ``(GateRun, baseline)``. It does so per *probe*. What it
does not assert is the half of the contract R1.3-R1.5 add, which is about the **unit** and
about **attribution**:

* **R1.3** -- the report is per declared mutation *operator*, carrying the check id, the
  operator id, and exactly one of the four outcomes. Not per check. The committed
  declaration has 14 checks and 16 operators because C44 and C56 declare two each, so a
  per-check report physically cannot say which of C44's two mutations survived, and "which
  one" is the only actionable content in a survivor report.
* **R1.4** -- ``survived`` and ``not-applied`` exit non-zero **naming that check and that
  operator**. Both names, in the finding and in what a CI log actually shows. A red run
  that names a check but not an operator sends a reader to a gate with two mutations and no
  way to tell which one is broken.
* **R1.5** -- ``indeterminate`` says *which* condition made it indeterminate: a non-passing
  unmutated baseline **naming that baseline's exit status**, a timeout, or a subprocess that
  could not be started. Three conditions, three repairs. "The gate did not answer" names
  none of them.

The three R1.5 conditions are quantified over :func:`gate_fault_injection.unobservable_reason`,
which is the pure function that decides them, and then again through the classifier so the
reason reaches the reported detail rather than stopping at an internal call.

Ground truth is restated here
-----------------------------

:func:`expected_outcome` re-derives the precedence chain with plain comparisons instead of
importing the harness's decision table, so each assertion compares two implementations of
one rule rather than asking the harness to agree with itself.

Nothing here starts a process. ``sweep`` and ``run_gate`` are the harness's own
orchestrator and launcher, and substituting them is how the classifier is driven over its
whole input space at zero process cost (I-0); no gate's evaluator is ever replaced, which
is the distinction R9.5 draws.

``max_examples`` is never set -- the budget comes from the root ``conftest.py`` profiles
(``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

Locus: ``ci.yml::uplift-verify``'s fast step.

**Validates: Requirements 1.3, 1.4, 1.5**
"""

from __future__ import annotations

import contextlib
import dataclasses
import io
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import gate_fault_injection as gfi
from scripts.audit.gate_fault_injection import EXIT_FAIL, GateRun, MutationOperator, OperatorKind
from tests.verify.sweep_strategies import (
    BLOCKING_OUTCOMES,
    PROBE_DIR,
    SWEEP_OUTCOMES,
    SweepDraft,
    gate_runs,
    patched_sweep,
    probe_result,
    sweep_drafts,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

REGISTERED_IDS: Final[tuple[str, ...]] = gfi.registered_ids()

#: Expected-name tokens chosen so none is a substring of another and none can occur in the
#: harness's own prose. Otherwise "the gate named the subject" would be satisfiable by the
#: report's boilerplate.
NAME_TOKENS: Final[tuple[str, ...]] = ("NAME_ALPHA", "NAME_BRAVO", "NAME_CHARLIE")

#: The finding rule each non-falsified outcome raises. ``indeterminate`` is the one that is
#: not blocking, because an absence of proof is not a defect of the gate.
OUTCOME_RULES: Final[dict[str, str]] = {
    "survived": "gate-survived-declared-mutation",
    "not-applied": "mutation-not-applied",
    "indeterminate": "falsification-indeterminate",
}


def expected_outcome(
    *,
    applied: bool,
    timed_out: bool,
    exit_code: int | None,
    missing_names: Sequence[str],
    baseline: GateRun | None,
) -> str:
    """The outcome the precedence chain mandates, restated. First match wins."""
    if not applied:
        return "not-applied"
    if timed_out or exit_code is None:
        return "indeterminate"
    # A negative return code is the POSIX "terminated by signal N" convention. The status
    # belongs to the signal, not to the gate, so it can never be read as a non-zero exit the
    # mutation caused -- which is what would otherwise let a killed subprocess report
    # ``falsified``. Restated here rather than delegated, because getting this wrong in the
    # ground truth is exactly the mistake this clause exists to catch in the subject.
    if exit_code < 0:
        return "indeterminate"
    if baseline is not None and not baseline.passed:
        return "indeterminate"
    if exit_code != 0 and not missing_names:
        return "falsified"
    return "survived"


# ---------------------------------------------------------------------------
# R1.5: the three indeterminate conditions, each named separately
# ---------------------------------------------------------------------------


@given(
    timeout=st.floats(min_value=1.0, max_value=900.0, allow_nan=False, allow_infinity=False),
    signal_number=st.integers(min_value=1, max_value=64),
)
def test_the_three_unobservable_conditions_are_named_separately(
    timeout: float, signal_number: int
) -> None:
    """R1.5: a timeout, an unstartable process and a signal are three different repairs.

    Collapsing them into one message names none of them. The signal case additionally must
    never be readable as a non-zero exit the mutation caused: a negative return code is the
    POSIX convention for "terminated by signal N", and its status belongs to the signal, so
    a classifier that treated it as an exit code would report ``falsified`` for a killed
    subprocess.
    """
    timed_out = gate_runs("C16", exit_code=None, timed_out=True)
    reason = gfi.unobservable_reason(timed_out, timeout=timeout)
    assert reason is not None
    assert f"{timeout:.0f}s" in reason
    assert "bound" in reason

    unstartable = gate_runs(
        "C16", exit_code=None, output="gate subprocess could not be started: no such file"
    )
    reason = gfi.unobservable_reason(unstartable, timeout=timeout)
    assert reason is not None
    assert "could not be started" in reason

    signalled = gate_runs("C16", exit_code=-signal_number)
    reason = gfi.unobservable_reason(signalled, timeout=timeout)
    assert reason is not None
    assert str(signal_number) in reason
    assert "signal" in reason
    assert "not the gate's" in reason

    # And the negative case: a run that did observe returns no reason at all, so
    # "unobservable" is a decision rather than a default.
    for observed in (0, 1, 2, 130):
        observed_run = gate_runs("C16", exit_code=observed)
        assert gfi.unobservable_reason(observed_run, timeout=timeout) is None

    # The three reasons are pairwise distinct, which is the whole content of R1.5.
    reasons = {
        gfi.unobservable_reason(run, timeout=timeout)
        for run in (timed_out, unstartable, signalled)
    }
    assert len(reasons) == 3


@given(baseline_exit=st.sampled_from((1, 2, 5, 130)))
def test_a_non_passing_baseline_makes_the_probe_indeterminate_naming_its_exit_status(
    baseline_exit: int,
) -> None:
    """R1.5: the baseline's *exit status* travels into the detail, not just its failure.

    "The gate was already red" is not actionable; "the gate was already red with exit 2"
    tells a reader whether the baseline was a FAIL or an unavailable measurement, which are
    different repairs on different owners. A gate that is already red proves nothing by
    staying red, so this can never be ``falsified``.
    """
    operator = MutationOperator(
        id="probe-operator",
        operator=OperatorKind.CREATE_FILE,
        target=f"{PROBE_DIR}/planted.py",
        expect_names=("NAME_ALPHA",),
        body='"""Planted by the sweep outcome property."""\n',
    )
    baseline = gate_runs("C44", exit_code=baseline_exit)

    with tempfile.TemporaryDirectory(prefix="sweep-outcome-") as tmp:
        tree = Path(tmp) / "synapse"
        (tree / PROBE_DIR).mkdir(parents=True)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                gfi,
                "run_gate",
                lambda check, _tree, **_kwargs: gate_runs(
                    check, exit_code=1, output="NAME_ALPHA named by the mutated run"
                ),
            )
            result = gfi.falsifies("C44", operator, tree=tree, baseline=baseline)

    assert result.outcome == "indeterminate"
    assert result.falsified is False
    assert result.baseline_probed is True
    assert result.baseline_exit_code == baseline_exit
    assert f"baseline exit {baseline_exit}" in result.detail
    assert "unmutated copy" in result.detail
    # The mutated run's own exit is reported too: a reader needs to know the mutation was
    # applied and the gate did answer, or the finding reads as a harness failure.
    assert str(result.exit_code) in result.detail


# ---------------------------------------------------------------------------
# R1.3: one outcome per operator, and the operator is the unit
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RunShape:
    """One synthesised mutated run plus the baseline it is judged against."""

    expect_names: tuple[str, ...]
    visible: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    baseline_probed: bool
    baseline_exit: int | None
    baseline_timed_out: bool

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(name for name in self.expect_names if name not in self.visible)

    def mutated(self, check: str) -> GateRun:
        return GateRun(
            check=check,
            command=("synthetic", "launcher"),
            exit_code=self.exit_code,
            output=f"[XX] {check}: {' '.join(self.visible)}",
            timed_out=self.timed_out,
        )

    def baseline(self, check: str) -> GateRun | None:
        if not self.baseline_probed:
            return None
        return gate_runs(
            check, exit_code=self.baseline_exit, timed_out=self.baseline_timed_out
        )


@st.composite
def run_shapes(draw: st.DrawFn) -> RunShape:
    """Every ``(mutated run, baseline)`` pair the real launcher can produce."""
    expect = tuple(
        draw(st.lists(st.sampled_from(NAME_TOKENS), min_size=1, max_size=3, unique=True))
    )
    visible = tuple(draw(st.lists(st.sampled_from(expect), max_size=len(expect), unique=True)))
    timed_out = draw(st.booleans())
    exit_code = None if timed_out else draw(st.sampled_from((None, 0, 1, 2, -9)))
    baseline_probed = draw(st.booleans())
    baseline_timed_out = draw(st.booleans()) if baseline_probed else False
    baseline_exit = (
        None
        if (not baseline_probed or baseline_timed_out)
        else draw(st.sampled_from((None, 0, 1, 2)))
    )
    return RunShape(
        expect_names=expect,
        visible=visible,
        exit_code=exit_code,
        timed_out=timed_out,
        baseline_probed=baseline_probed,
        baseline_exit=baseline_exit,
        baseline_timed_out=baseline_timed_out,
    )


# Feature: decision-quality-proof, Property 38: Sweep outcome classification is total, four-valued and per-operator  # noqa: E501
@given(
    first=run_shapes(),
    second=run_shapes(),
    check=st.sampled_from(REGISTERED_IDS),
)
def test_two_operators_on_one_check_are_classified_and_reported_independently(
    first: RunShape, second: RunShape, check: str
) -> None:
    """R1.3: the reported unit is the operator, so one check can carry two verdicts.

    This is the shape a per-check report cannot express, and it is not hypothetical: C44
    declares ``add-an-orphan-module`` and ``unparse-a-seam-marker``, and C56 declares two
    drift operators. If one survives and the other falsifies, a per-check report has to
    choose a single word for two facts -- and whichever it chooses, a reader cannot act on
    it.

    Each probe is run against its own synthesised launcher result, and the two results are
    asserted to differ in every field that identifies them and to agree with the precedence
    chain independently.
    """
    operators = tuple(
        MutationOperator(
            id=f"operator-{index}",
            operator=OperatorKind.CREATE_FILE,
            target=f"{PROBE_DIR}/planted-{index}.py",
            expect_names=shape.expect_names,
            body=f'"""Planted operator {index}."""\n',
        )
        for index, shape in enumerate((first, second))
    )

    results = []
    with tempfile.TemporaryDirectory(prefix="sweep-outcome-pair-") as tmp:
        tree = Path(tmp) / "synapse"
        (tree / PROBE_DIR).mkdir(parents=True)
        for shape, operator in zip((first, second), operators, strict=True):
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(
                    gfi,
                    "run_gate",
                    lambda gate, _tree, _shape=shape, **_kwargs: _shape.mutated(gate),
                )
                results.append(
                    gfi.falsifies(
                        check, operator, tree=tree, baseline=shape.baseline(check)
                    )
                )

    for shape, operator, result in zip((first, second), operators, results, strict=True):
        # Total and four-valued.
        assert result.outcome in SWEEP_OUTCOMES
        assert result.falsified is (result.outcome == "falsified")
        assert result.outcome == expected_outcome(
            applied=result.applied,
            timed_out=result.timed_out,
            exit_code=result.exit_code,
            missing_names=result.missing_names,
            baseline=shape.baseline(check),
        )
        # Per-operator: both identifiers travel with the verdict.
        assert result.check == check
        assert result.operator_id == operator.id
        assert result.target == operator.target
        assert result.expect_names == operator.expect_names

    # The two verdicts are attributable to different operators of the same check, which is
    # exactly what a per-check unit destroys.
    assert results[0].check == results[1].check
    assert results[0].operator_id != results[1].operator_id
    assert results[0].target != results[1].target


# ---------------------------------------------------------------------------
# R1.4: a survivor exits non-zero naming BOTH the check and the operator
# ---------------------------------------------------------------------------


@given(draft=sweep_drafts(registered=REGISTERED_IDS), seed=st.integers(0, 2**16))
def test_a_survivor_or_unapplied_operator_exits_non_zero_naming_check_and_operator(
    draft: SweepDraft, seed: int
) -> None:
    """R1.4: both identifiers reach the exit status *and* the log a reader sees.

    A survivor report that names only the check is unactionable on any gate declaring two
    operators, and two of the fourteen do. So the assertion is made in three places: the
    structured finding, the aggregate's one-line reason, and the rendered human report --
    because the rendered report is what a CI log carries, and a field nobody prints is a
    field nobody reads.
    """
    pairs = draft.declared_pairs
    # Every declared operator is probed, so the outcome is the only thing under test here
    # and no unproven finding can be confused with a survivor finding.
    blocking_outcome = BLOCKING_OUTCOMES[seed % len(BLOCKING_OUTCOMES)]
    chosen = pairs[seed % len(pairs)]
    results = tuple(
        probe_result(
            check,
            operator_id,
            blocking_outcome if (check, operator_id) == chosen else "falsified",
        )
        for check, operator_id in pairs
    )

    with tempfile.TemporaryDirectory(prefix="sweep-outcome-naming-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results):
            report = gfi.evaluate(
                declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=True
            )

    assert report.verdict == "fail"
    assert report.exit_code == EXIT_FAIL
    assert report.passing is False

    findings = tuple(
        finding
        for finding in report.findings
        if finding.rule == OUTCOME_RULES[blocking_outcome]
    )
    assert len(findings) == 1
    assert findings[0].check == chosen[0]
    assert findings[0].operator_id == chosen[1]

    # The aggregate's reason names the pair, not just the check. `[:5]` truncates the list,
    # and there is exactly one blocking finding here, so it is always inside the window.
    assert f"{chosen[0]}/{chosen[1]}" in report.reason

    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        gfi._print_report(report)
    rendered = stdout.getvalue()
    assert f"{chosen[0]}/{chosen[1]}" in rendered
    assert OUTCOME_RULES[blocking_outcome] in rendered
    # The survivor's own probe line is printed too, so the log shows the outcome beside the
    # finding rather than only the aggregate's verdict.
    assert blocking_outcome in rendered


@given(draft=sweep_drafts(registered=REGISTERED_IDS))
def test_an_indeterminate_probe_is_unavailable_and_never_blocks_as_a_defect(
    draft: SweepDraft,
) -> None:
    """R1.5 / I-7: an absence of proof is non-passing, and it is not a gate defect.

    The two are separated deliberately. ``survived`` says the gate does not enforce, which
    is a defect somebody owns. ``indeterminate`` says the probe could not observe, which is
    a defect of the conditions -- a red baseline, a bound, a launcher. Reporting the second
    as the first would attribute a broken environment to a working gate; reporting either as
    a pass would be the failure I-7 forbids.
    """
    pairs = draft.declared_pairs
    results = tuple(
        probe_result(check, operator_id, "indeterminate") for check, operator_id in pairs
    )

    with tempfile.TemporaryDirectory(prefix="sweep-outcome-indeterminate-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results):
            report = gfi.evaluate(
                declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=True
            )

    assert report.verdict == "unavailable"
    assert report.passing is False
    assert report.falsified_ids == ()
    assert report.pass_eligible_ids == ()
    assert "proved nothing" in report.reason

    rules = {finding.rule for finding in report.findings}
    assert rules == {OUTCOME_RULES["indeterminate"]}
    for finding in report.findings:
        assert (finding.check, finding.operator_id) in pairs
