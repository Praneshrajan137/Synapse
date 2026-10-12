"""Property-based test for declared gate falsification (design AD-4 / E2.1).

Feature: purpose-achievement-audit, Property 3: Every gate is falsified by its declared
mutation

    *For any* registered check and *any* mutation operator declared for it, applying
    that operator inside a temporary copy of the real repository tree and running the
    gate as a subprocess yields a non-zero exit naming the mutated subject; applying no
    operator yields the gate's unmutated verdict. No test in this property may replace,
    stub, or monkeypatch the gate's evaluator.

Why the property is shaped this way. The audit finding behind Requirement 1.2 is that a
repository with 53 mechanical checks has almost no evidence that any of them *bites*,
and the tell it names is a test that replaces the thing it is testing
(``packages/tests/test_agency_truth_gate.py:313-322`` monkeypatches
``agency_truth.evaluate`` and then asserts C57 reports FAIL). So the obligation here is
not "the harness computes something" but "a mutation of the real tree, evaluated by the
real gate in another process, produces a non-zero exit that *names the subject*". A
non-zero exit that names nothing is not a falsification: nobody can act on it.

What is asserted where, and why the split is not a convenience.

* The **cheap** cases below quantify over the parts of that obligation that are pure -
  operator application and its confinement to a temporary tree, document-path
  resolution, the totality of the outcome classification over every reachable
  ``GateRun`` shape, the naming obligation on both the falsified and the survived
  branch, and the ``reporting_tool`` / undeclared exclusion from PASS-eligibility. None
  of them starts a process.
* The **slow** case is the one that actually spawns a gate. It copies the real tree,
  runs the gate unmutated, applies a committed operator, runs the gate again, and
  checks that the harness's verdict is exactly what the declared decision table says
  about the two real runs - and that the working tree is byte-identical afterwards. It
  carries ``@pytest.mark.slow`` so ``-m "not slow"`` genuinely excludes it, and it runs
  in ``.github/workflows/ci.yml::uplift-verify`` (``pytest tests/uplift tests/verify -m
  "slow"`` at ``HYPOTHESIS_PROFILE=heavy``). Under I-0 it is never run on the dev box:
  a full tree copy plus two gate subprocesses is a CI workload by construction.

What is substituted, and why it is not the forbidden pattern. Two module-level seams are
replaced, both belonging to *this harness* and neither belonging to any gate:
``run_gate`` (the harness's own process launcher) and ``sweep`` (its orchestrator).
Substituting them is how the classifier and the verdict are driven over their whole
input space at zero process cost; the same precedent is set by
``test_registry_gate_verdict_property.py``, which replaces ``registry_gate.evaluate``
when the subject under test is the reporting path downstream of it. No check function,
no ``verify_claims`` evaluator, and no gate's ``evaluate`` is ever replaced - and every
claim of the form "the gate exited non-zero" is asserted only against a real
subprocess, in the slow case. The distinction is the whole of R9.5: the harness may be
driven, the thing being judged may not be replaced.

Ground truth is recomputed here. ``declared_outcome`` and ``declared_verdict`` restate
E2.1's precedence with plain comparisons rather than importing the module's decision
table, so each test compares two implementations of the same rule instead of asking the
harness to agree with itself.

**R1.5a (decision-quality-proof, amended 2026-10-02).** The precedence gained one branch.
A baseline that exited ``2`` printing the runner's own ``[SKIP] <cid>`` line abstained
rather than judged, so against it the runner's FAIL or PARTIAL - exit ``1`` WITH its own
status line - naming every declared subject is ``falsified``, a PASS is ``survived``, and
anything else, an exit-``1`` crash with no status line included, is ``indeterminate``; every
other non-passing baseline is still red (R1.5). ``runner_abstained`` and ``runner_reported``
restate the runner's lines with ``str.split`` and ``startswith`` rather than the harness's
regex, and the baseline
strategy draws the runner's abstention as often as each near miss that must not pass for
one.

The committed declaration is checked statically, per operator, against the real tree:
each operator is applied inside a throwaway directory seeded with *only* the single file
it targets, which proves the declaration still applies to today's tree without copying
the tree and without writing a byte inside it. Every such case hashes the real file
before and after and asserts it did not move.

Expect no assertion here that today's gates all falsify. ``gate-mutations.yaml`` records
in its own notes which declarations do not yet bite -- C28's zero-a-floor survived until
its measured-bound clause landed on 2026-10-01, and C44's probes read indeterminate while
its baseline was red. Asserting universal falsification would make this file red for
reasons the declaration already discloses; turning the shortfall into a gate is task
12.1's job, via ``gate_fault_injection --sweep`` in CI. What this file asserts is that the
harness *classifies* those cases honestly and never converts one of them into a pass (I-7).

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 1.2, 9.5, 12.3, 12.7**
"""

from __future__ import annotations

import ast
import contextlib
import dataclasses
import hashlib
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import gate_fault_injection as gfi
from scripts.audit import verify_claims as vc
from scripts.audit.gate_fault_injection import (
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_UNAVAILABLE,
    FaultInjectionResult,
    GateRun,
    MutationOperator,
    OperatorKind,
)
from tests.verify.strategies import check_ids

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence

# ---------------------------------------------------------------------------
# The subject's own vocabulary, restated so a drift in either is visible
# ---------------------------------------------------------------------------

#: Every outcome one probe may reach. A fifth would fall through the classifier's
#: precedence chain into ``survived``, so the closed set is pinned here.
OUTCOMES: Final[tuple[gfi.Outcome, ...]] = (
    "falsified",
    "survived",
    "indeterminate",
    "not-applied",
)

#: Outcomes that are a defect of the gate or of the declaration, so they FAIL.
BLOCKING_OUTCOMES: Final[tuple[str, ...]] = ("survived", "not-applied")

#: The verdict -> exit-status contract. ``2`` is non-passing: absence of proof is not a
#: pass (I-7).
EXPECTED_EXIT_CODES: Final[Mapping[str, int]] = {
    "pass": EXIT_PASS,
    "fail": EXIT_FAIL,
    "unavailable": EXIT_UNAVAILABLE,
}

#: Finding rules the classifier raises, and the one of them that is *not* blocking.
INDETERMINATE_RULE: Final[str] = "falsification-indeterminate"
OUTCOME_RULES: Final[Mapping[str, str]] = {
    "survived": "gate-survived-declared-mutation",
    "not-applied": "mutation-not-applied",
    "indeterminate": INDETERMINATE_RULE,
}

#: Expected-name tokens for the synthetic probes. Chosen so no token is a substring of
#: another and none can appear in the surrounding report text by accident - otherwise a
#: "the gate named the subject" assertion would be satisfied by the harness's own prose.
NAME_TOKENS: Final[tuple[str, ...]] = ("NAME_ALPHA", "NAME_BRAVO", "NAME_CHARLIE", "NAME_DELTA")

#: A directory that must not exist in the real tree. Every synthetic operator targets a
#: path beneath it, so ``restore``'s "re-sync the target from ``source``" step can never
#: resolve to a committed file, and a bug that pointed a write at the working tree would
#: show up as a missing directory rather than as a silent overwrite.
PROBE_DIR: Final[str] = "generated_fault_injection_probe"
PROBE_TARGET: Final[str] = f"{PROBE_DIR}/config.json"
PROBE_CREATED: Final[str] = f"{PROBE_DIR}/planted.py"

#: The document the synthetic ``set_json_path`` operator rewrites, in the exact byte
#: shape ``_inject_set_json_path`` re-emits, so "the mutation changed something" is a
#: statement about the *value* and not about formatting.
PROBE_BODY: Final[str] = (
    json.dumps({"thresholds": {"break": 50}}, indent=2, sort_keys=True) + "\n"
)

#: A line every synthetic run prints before its status line, because the runner's status
#: line is never the only thing a gate subprocess prints - so "the status line is a line"
#: is tested off the first line, not on it.
LOG_LINE: Final[str] = "2026-10-02 12:00:00 [info     ] synthetic_log_line"

#: Every unmutated baseline the classifier can be handed, keyed by what it is: the runner's
#: statuses, its unregistered line, the three unobservable runs, and each near miss R1.5a's
#: admission must refuse. ``(exit code, timed out, status line)``, ``{check}`` filled in per
#: probe. Drawn by shape, so the runner's abstention is as likely as any one near miss.
BASELINE_SHAPES: Final[Mapping[str, tuple[int | None, bool, str]]] = {
    "passed": (EXIT_PASS, False, "[PASS] {check} synthetic title: synthetic pass"),
    "failed": (EXIT_FAIL, False, "[FAIL] {check} synthetic title: synthetic defect"),
    "partial": (EXIT_FAIL, False, "[PARTIAL] {check} synthetic title: synthetic partial"),
    "abstained": (EXIT_UNAVAILABLE, False, "[SKIP] {check} synthetic title: an abstention"),
    "unregistered": (
        EXIT_UNAVAILABLE,
        False,
        "[??] {check} is not registered in this tree's Check_Registry",
    ),
    "skip-line-at-the-pre-r1-5a-exit": (
        EXIT_FAIL,
        False,
        "[SKIP] {check} synthetic title: the runner exited 1 for this until 2026-10-02",
    ),
    "skip-line-for-another-check": (
        EXIT_UNAVAILABLE,
        False,
        "[SKIP] {check}0 synthetic title: an id that merely starts with this one",
    ),
    "skip-line-quoted-mid-line": (
        EXIT_UNAVAILABLE,
        False,
        "log: the runner said [SKIP] {check} synthetic title: quoted, not printed",
    ),
    "exit-2-with-no-status-line": (
        EXIT_UNAVAILABLE,
        False,
        "usage: gate_fault_injection: error: unrecognized arguments",
    ),
    "signalled": (-9, False, ""),
    "timed-out": (None, True, ""),
    "unstartable": (None, False, "gate subprocess could not be started: synthetic"),
}

#: The status line a synthetic mutated run prints ahead of the names it mentions. Drawn
#: independently of the exit code, because against an abstaining baseline the line decides
#: as much as the code does (R1.5a): exit 1 is a verdict only with the runner's FAIL or
#: PARTIAL line, and SKIP on both copies only with its SKIP line. ``traceback`` is the
#: crash shape - exit 1 is also an uncaught exception's status, and it prints no status line.
MUTATED_LINES: Final[Mapping[str, str]] = {
    "verdict": "[FAIL] {check} synthetic title:",
    "partial": "[PARTIAL] {check} synthetic title:",
    "abstention": "[SKIP] {check} synthetic title:",
    "unregistered": "[??] {check} is not registered:",
    "unlabelled": "[XX] {check} synthetic gate output:",
    "traceback": "Traceback (most recent call last):",
}

# ---------------------------------------------------------------------------
# The committed declaration and the live registry, read once
# ---------------------------------------------------------------------------

#: Every identifier ``@register`` declared, read through the harness so "registered"
#: means exactly what the harness means by it.
REGISTERED_IDS: Final[tuple[str, ...]] = gfi.registered_ids()

COMMITTED_DOCUMENT: Final[dict[str, object]] = gfi.load_declaration()
COMMITTED_SCHEMA: Final[dict[str, object]] = gfi.load_schema()
COMMITTED: Final[gfi.MutationDeclaration] = gfi.parse_declaration(COMMITTED_DOCUMENT)

#: ``(check, operator)`` for every operator the committed file declares, in file order.
COMMITTED_OPERATORS: Final[tuple[tuple[str, MutationOperator], ...]] = tuple(
    (gate.check, operator) for gate in COMMITTED.gates for operator in gate.operators
)
COMMITTED_OPERATOR_IDS: Final[tuple[str, ...]] = tuple(
    f"{check}-{operator.id}" for check, operator in COMMITTED_OPERATORS
)


# ---------------------------------------------------------------------------
# Ground truth: E2.1's precedence, restated
# ---------------------------------------------------------------------------


def runner_abstained(baseline: GateRun | None, check: str) -> bool:
    """R1.5a's admission, restated: the baseline exited 2 AND printed ``[SKIP] <check>``.

    Written with ``str.split`` and ``startswith`` rather than the harness's regex, so the
    classifier is compared against a second implementation. The trailing space is what keeps
    ``C16`` from matching ``C160``; the line start is what keeps a quoted mention out.
    """
    if baseline is None or baseline.timed_out or baseline.exit_code != EXIT_UNAVAILABLE:
        return False
    return any(line.startswith(f"[SKIP] {check} ") for line in baseline.output.split("\n"))


def runner_reported(output: str, check: str, statuses: Sequence[str]) -> bool:
    """Whether ``output`` carries the runner's ``[STATUS] <check>`` line for any of ``statuses``.

    The same ``str.split``/``startswith`` restatement as :func:`runner_abstained`, applied to
    the mutated run: R1.5a credits exit 1 only beside the runner's FAIL or PARTIAL line.
    """
    return any(
        line.startswith(f"[{status}] {check} ")
        for status in statuses
        for line in output.split("\n")
    )


def declared_outcome(
    *,
    check: str,
    applied: bool,
    timed_out: bool,
    exit_code: int | None,
    mutated_output: str,
    missing_names: Sequence[str],
    baseline: GateRun | None,
) -> str:
    """The outcome E2.1 mandates for one probe, first match wins.

    1. the mutation did not land                                 -> ``not-applied``
    2. the gate did not answer inside its bound                  -> ``indeterminate``
    3. the gate could not be executed at all, or was signalled   -> ``indeterminate``
    4. the baseline abstained: exit 2 printing ``[SKIP] <check>`` (R1.5a, 2026-10-02)
       a. mutated exit 1 printing ``[FAIL]``/``[PARTIAL] <check>``,
          naming every declared subject                          -> ``falsified``
       b. the same naming less, or mutated exit 0                -> ``survived``
       c. any other mutated run - exit 1 with neither line (an
          uncaught exception), or 2 (SKIP on both) - included    -> ``indeterminate``
    5. the gate does not pass on the unmutated copy              -> ``indeterminate``
    6. non-zero exit naming every declared subject               -> ``falsified``
    7. zero exit                                                 -> ``survived``
    8. non-zero exit naming nothing                              -> ``survived``

    Rules 2, 3, 4c and 5 are the I-7 cases: each is an absence of proof, and none may read
    as a pass. Rule 5 is R1.5 (a check already red proves nothing by staying red), and rule
    4 is the one relaxation R1.5a makes of it: an abstention is not a verdict, so a change
    from SKIP to the runner's FAIL or PARTIAL is the mutation's doing, and nothing else that
    departs from SKIP is. Rule 8 is the naming obligation with teeth - a gate that fails
    without saying what failed has not satisfied its declaration.
    """
    if not applied:
        return "not-applied"
    if timed_out:
        return "indeterminate"
    if exit_code is None or exit_code < 0:
        return "indeterminate"
    if runner_abstained(baseline, check):
        if exit_code == EXIT_FAIL and runner_reported(mutated_output, check, ("FAIL", "PARTIAL")):
            return "survived" if missing_names else "falsified"
        if exit_code == EXIT_PASS:
            return "survived"
        return "indeterminate"
    if baseline is not None and not baseline.passed:
        return "indeterminate"
    if exit_code != 0 and not missing_names:
        return "falsified"
    return "survived"


def declared_verdict(
    *, blocking: int, probed: bool, indeterminate: int, unproven: int = 0
) -> str:
    """The aggregate verdict E2.1 mandates, first match wins.

    A declaration defect or a surviving mutation FAILs; an unprobed run is
    ``unavailable`` because nothing was proven; an indeterminate probe is
    ``unavailable`` for the same reason; only a fully probed, fully falsified run
    passes.

    ``unproven`` joins the blocking class rather than forming a category of its own
    (decision-quality-proof task 5.4, R1.7). A **complete** sweep that returned no
    outcome for a declared operator has proven nothing about that operator, and a
    denominator that quietly shrinks to the operators that happened to run is the exact
    shape of a gate reporting a pass over an absence. It is deliberately *not* folded into
    ``indeterminate``: an indeterminate probe ran and could not conclude, an unproven one
    never ran, and the two have different repairs.
    """
    if blocking or unproven:
        return "fail"
    if not probed:
        return "unavailable"
    if indeterminate:
        return "unavailable"
    return "pass"


def digest_of(path: Path) -> str:
    """SHA-256 of a file, for "the working tree did not move" assertions."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Synthetic operators and the throwaway trees they are applied to
# ---------------------------------------------------------------------------


def probe_operator(
    expect_names: tuple[str, ...] = ("NAME_ALPHA",),
    *,
    target: str = PROBE_TARGET,
) -> MutationOperator:
    """A ``set_json_path`` operator that flips one value in the synthetic document."""
    return MutationOperator(
        id="probe-operator",
        operator=OperatorKind.SET_JSON_PATH,
        target=target,
        expect_names=expect_names,
        path="$.thresholds.break",
        value=10,
        value_declared=True,
    )


def planting_operator() -> MutationOperator:
    """A ``create_file`` operator, so ``restore``'s remove-branch is reachable."""
    return MutationOperator(
        id="planting-operator",
        operator=OperatorKind.CREATE_FILE,
        target=PROBE_CREATED,
        expect_names=("NAME_ALPHA",),
        body='"""Planted by the declared-falsification property test."""\n',
    )


@contextlib.contextmanager
def probe_tree(*, seed_target: bool = True) -> Iterator[Path]:
    """A throwaway stand-in for the temporary tree copy, holding one synthetic file.

    Deliberately *not* ``gfi.tree_copy()``: copying the real repository is the CI
    workload the slow case owns, and none of the cheap cases needs a real tree to
    exercise operator application or the classifier.
    """
    with tempfile.TemporaryDirectory(prefix="declared-falsification-") as tmp:
        tree = Path(tmp) / "synapse"
        (tree / PROBE_DIR).mkdir(parents=True)
        if seed_target:
            (tree / PROBE_TARGET).write_text(PROBE_BODY, encoding="utf-8")
        yield tree


# ---------------------------------------------------------------------------
# Generated classification cases (no process is started for any of them)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ClassificationCase:
    """One synthesised gate run, plus the baseline it is judged against.

    ``visible`` is the subset of ``expect_names`` the synthetic gate output mentions:
    the classifier's job is to rediscover which declared subjects went unnamed.
    ``baseline_shape`` keys :data:`BASELINE_SHAPES`; ``None`` is a probe with no baseline
    at all, the diagnostic mode.
    """

    expect_names: tuple[str, ...]
    visible: tuple[str, ...]
    exit_code: int | None
    timed_out: bool
    mutated_line: str
    baseline_shape: str | None

    @property
    def present(self) -> tuple[str, ...]:
        return tuple(name for name in self.expect_names if name in self.visible)

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(name for name in self.expect_names if name not in self.visible)

    @property
    def baseline_probed(self) -> bool:
        return self.baseline_shape is not None

    def output(self, check: str) -> str:
        status = MUTATED_LINES[self.mutated_line].format(check=check)
        return f"{LOG_LINE}\n{status} {' '.join(self.visible)}"

    def gate_run(self, check: str) -> GateRun:
        return GateRun(
            check=check,
            command=("synthetic", "launcher"),
            exit_code=self.exit_code,
            output=self.output(check),
            timed_out=self.timed_out,
        )

    def baseline(self, check: str) -> GateRun | None:
        if self.baseline_shape is None:
            return None
        exit_code, timed_out, line = BASELINE_SHAPES[self.baseline_shape]
        return GateRun(
            check=check,
            command=("synthetic", "baseline"),
            exit_code=exit_code,
            output="\n".join(part for part in (LOG_LINE, line.format(check=check)) if part),
            timed_out=timed_out,
        )


@st.composite
def classification_cases(draw: st.DrawFn) -> ClassificationCase:
    """Every reachable ``(GateRun, baseline)`` shape the real launcher can produce.

    ``timed_out`` implies ``exit_code is None`` because that is what ``run_gate``
    actually returns on a ``TimeoutExpired``; an unstartable process is the other
    ``None`` case and is drawn separately, so both indeterminate branches are reachable
    without generating a shape the launcher could never emit. ``-9`` is a run a signal
    terminated, and ``130`` an exit status the runner itself never emits.

    The baseline is drawn by *shape* from :data:`BASELINE_SHAPES` rather than by exit
    code, so R1.5a's admitted case - the runner's own abstention - is drawn as often as
    each near miss it must be told apart from: an unregistered exit 2, a SKIP line at the
    pre-R1.5a exit 1, another check's SKIP line, a quoted one, and exit 2 with no line.
    """
    expect = tuple(
        draw(st.lists(st.sampled_from(NAME_TOKENS), min_size=1, max_size=4, unique=True))
    )
    visible = tuple(draw(st.lists(st.sampled_from(expect), max_size=len(expect), unique=True)))

    timed_out = draw(st.booleans())
    exit_code = None if timed_out else draw(st.sampled_from((None, 0, 1, 2, 130, -9)))
    return ClassificationCase(
        expect_names=expect,
        visible=visible,
        exit_code=exit_code,
        timed_out=timed_out,
        mutated_line=draw(st.sampled_from(tuple(MUTATED_LINES))),
        baseline_shape=draw(st.one_of(st.none(), st.sampled_from(tuple(BASELINE_SHAPES)))),
    )


# Feature: purpose-achievement-audit, Property 3: Every gate is falsified by its declared mutation
@given(case=classification_cases())
def test_the_probe_outcome_is_a_total_function_of_the_run_and_its_baseline(
    case: ClassificationCase,
) -> None:
    """R1.2, R9.5: one outcome per (run, baseline), and naming is half the contract.

    ``run_gate`` - the harness's own process launcher, not any gate - is replaced by a
    recorder so the classifier can be driven over its whole input space without starting
    a process (I-0). The mutation itself is applied for real, inside a throwaway tree.
    """
    check = "C16"
    operator = probe_operator(case.expect_names)
    calls: list[tuple[str, Path, float, object]] = []

    def launcher(
        gate: str,
        tree: Path,
        *,
        timeout: float = gfi.DEFAULT_TIMEOUT_S,
        command: Sequence[str] | None = None,
    ) -> GateRun:
        calls.append((gate, tree, timeout, command))
        return case.gate_run(gate)

    baseline = case.baseline(check)
    with probe_tree() as tree, pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "run_gate", launcher)
        result = gfi.falsifies(check, operator, tree=tree, baseline=baseline)
        # The mutation landed and was undone: one temporary copy serves a whole sweep,
        # so a probe that left its mutation behind would contaminate the next one. The
        # synthetic target has no counterpart in the real tree, so ``restore`` removes
        # it rather than re-syncing it - either way nothing survives the probe.
        assert not (tree / PROBE_TARGET).exists()

    # Total: exactly one of four outcomes, and ``falsified`` is exactly one of them.
    assert result.outcome in OUTCOMES
    assert result.falsified is (result.outcome == "falsified")
    assert result.outcome == declared_outcome(
        check=check,
        applied=result.applied,
        timed_out=result.timed_out,
        exit_code=result.exit_code,
        mutated_output=case.output(check),
        missing_names=result.missing_names,
        baseline=baseline,
    )

    # The gate ran exactly once, in the temporary tree, and was told the check id.
    assert len(calls) == 1
    assert calls[0][0] == check
    assert calls[0][1] == tree
    assert calls[0][3] is None, "the harness must not pass a bespoke command by default"

    # The result names its own subject whatever it concluded: an exclusion has to be
    # readable as an exclusion (I-7), which it cannot be if it names nothing.
    assert result.check == check
    assert result.operator_id == operator.id
    assert result.operator is operator.operator
    assert result.target == operator.target
    assert result.expect_names == operator.expect_names

    # The observed run is reported faithfully, not summarised.
    assert result.applied is True
    assert result.exit_code == case.exit_code
    assert result.timed_out == case.timed_out
    assert result.non_zero_exit is (case.exit_code not in (0, None))
    assert result.baseline_probed is case.baseline_probed
    assert result.baseline_exit_code == (baseline.exit_code if baseline else None)

    # Present and missing partition the declared names, in declaration order.
    assert result.names_present == case.present
    assert result.missing_names == case.missing
    assert set(result.names_present) | set(result.missing_names) == set(operator.expect_names)
    assert not set(result.names_present) & set(result.missing_names)

    # Falsified requires BOTH halves: a non-zero exit and every declared subject named.
    abstained = runner_abstained(baseline, check)
    observed = not result.timed_out and result.exit_code is not None and result.exit_code >= 0
    if result.falsified:
        assert result.non_zero_exit
        assert result.missing_names == ()
        assert not result.timed_out
        # Credit needs a baseline that passed or abstained (R1.5, R1.5a), and against an
        # abstention only the runner's FAIL/PARTIAL exit is a verdict the mutation caused.
        assert baseline is None or baseline.passed or abstained
        if abstained:
            assert result.exit_code == EXIT_FAIL
        for name in operator.expect_names:
            assert name in result.detail

    # A non-zero exit that named nothing is a survival, and the detail says which
    # subjects went unnamed - the difference between an actionable red and a mystery.
    if result.outcome == "survived" and result.missing_names:
        assert result.non_zero_exit or result.exit_code == 0
        if result.exit_code != 0:
            for name in result.missing_names:
                assert name in result.detail

    # I-7: an absence of proof is never a falsification.
    if not observed:
        assert result.outcome == "indeterminate"
        assert not result.falsified
    # R1.5 stands for every baseline that is red rather than abstaining - FAIL, PARTIAL,
    # unregistered, unobservable, or carrying a SKIP line it did not earn - and an
    # observed baseline's exit status travels into the detail.
    if baseline is not None and not baseline.passed and not abstained:
        assert result.outcome == "indeterminate"
        assert not result.falsified
        if (
            observed
            and not baseline.timed_out
            and baseline.exit_code is not None
            and baseline.exit_code >= 0
        ):
            assert f"baseline exit {baseline.exit_code}" in result.detail
    # R1.5a: against an abstention every detail names both exit statuses, and a SKIP on
    # both copies is indeterminate and says that is what it was.
    if abstained and observed:
        assert f"baseline exit {EXIT_UNAVAILABLE}" in result.detail
        assert f"mutated exit {result.exit_code}" in result.detail
        if result.exit_code == EXIT_UNAVAILABLE:
            assert result.outcome == "indeterminate"
            if case.mutated_line == "abstention":
                assert "abstained on both the unmutated and the mutated copy" in result.detail


@given(case=classification_cases())
def test_a_mutation_that_cannot_land_never_reaches_a_gate_and_never_survives(
    case: ClassificationCase,
) -> None:
    """R1.2: the harness must not turn its own defect into a verdict about the gate.

    An operator whose target is absent from the copy proves nothing about the gate. Two
    obligations follow: the outcome is ``not-applied`` (never ``survived``, which would
    read as "the gate does not gate"), and no process is started at all - a gate run
    whose mutation never landed would attribute its exit code to nothing.
    """
    check = "C28"
    operator = probe_operator(case.expect_names)
    calls: list[str] = []

    def launcher(gate: str, tree: Path, **_: object) -> GateRun:
        calls.append(gate)
        return case.gate_run(gate)

    with probe_tree(seed_target=False) as tree, pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "run_gate", launcher)
        result = gfi.falsifies(check, operator, tree=tree, baseline=case.baseline(check))

    assert calls == [], "a mutation that did not land must not spawn a gate subprocess"
    assert result.outcome == "not-applied"
    assert result.applied is False
    assert result.falsified is False
    assert result.exit_code is None
    assert result.non_zero_exit is False
    assert result.names_present == ()
    assert result.missing_names == ()
    # Naming the subject applies to the harness's own failures too.
    assert PROBE_TARGET in result.detail
    assert operator.id in result.detail


# ---------------------------------------------------------------------------
# R1.5a (decision-quality-proof, 2026-10-02): an abstaining baseline, one case per branch
# ---------------------------------------------------------------------------


def skip_line(check: str) -> str:
    """The runner's own SKIP line, rendered by the function the runner prints with."""
    return gfi._status_line("SKIP", check, "Synthetic title", "an abstention")


def fail_line(check: str, named: str = "NAME_ALPHA NAME_BRAVO") -> str:
    """The runner's own FAIL line, naming ``named``."""
    return gfi._status_line("FAIL", check, "Synthetic title", f"a breach of {named}")


def runner_run(check: str, *, exit_code: int | None, status_line: str) -> GateRun:
    """A gate run shaped like the runner's: a log line, then its one status line."""
    return GateRun(
        check=check,
        command=gfi._gate_command(check),
        exit_code=exit_code,
        output=f"{LOG_LINE}\n{status_line}",
        timed_out=False,
    )


def classify(check: str, *, baseline: GateRun | None, mutated: GateRun) -> FaultInjectionResult:
    """Drive the real classifier over two synthesised runs, starting no process.

    ``run_gate`` - the harness's own launcher, never a gate - returns ``mutated``; the
    mutation itself is applied for real inside a throwaway tree, as in the property above.
    Every case declares the same two subjects, ``NAME_ALPHA`` and ``NAME_BRAVO``.
    """

    def launcher(_gate: str, _tree: Path, **_: object) -> GateRun:
        return mutated

    operator = probe_operator(("NAME_ALPHA", "NAME_BRAVO"))
    with probe_tree() as tree, pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "run_gate", launcher)
        return gfi.falsifies(check, operator, tree=tree, baseline=baseline)


def test_a_skip_baseline_that_fails_under_its_mutation_naming_every_subject_is_falsified() -> None:
    """R1.5a: an abstention is not a verdict, so a SKIP -> FAIL change is the mutation's.

    R1.5 refuses a red baseline because a check already red proves nothing by staying red.
    A SKIP judged nothing, and with SKIP and FAIL on distinct exit codes the mutation is the
    only difference between the two copies. What this does NOT show is that the gate would
    PASS a sound subject - only that it can FAIL when its subject breaks.
    """
    check = "C60"
    result = classify(
        check,
        baseline=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=skip_line(check)),
        mutated=runner_run(check, exit_code=EXIT_FAIL, status_line=fail_line(check)),
    )

    assert result.outcome == "falsified"
    assert result.falsified is True
    assert result.baseline_probed is True
    assert result.baseline_exit_code == EXIT_UNAVAILABLE
    assert result.exit_code == EXIT_FAIL
    assert result.missing_names == ()
    for name in ("NAME_ALPHA", "NAME_BRAVO"):
        assert name in result.detail
    assert "SKIP -> FAIL" in result.detail
    assert f"`[FAIL] {check}`" in result.detail
    assert "R1.5a" in result.detail


def test_a_skip_baseline_that_reports_partial_under_its_mutation_is_falsified_too() -> None:
    """R1.5a: PARTIAL is the runner's other exit-1 verdict, credited as FAIL is."""
    check = "C70"
    partial = gfi._status_line("PARTIAL", check, "Synthetic title", "NAME_ALPHA NAME_BRAVO short")
    result = classify(
        check,
        baseline=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=skip_line(check)),
        mutated=runner_run(check, exit_code=EXIT_FAIL, status_line=partial),
    )

    assert result.outcome == "falsified"
    assert result.missing_names == ()
    assert "SKIP -> PARTIAL" in result.detail


def test_a_skip_baseline_still_abstaining_under_its_mutation_proves_nothing_and_says_so() -> None:
    """R1.5a / I-7: SKIP on both copies moved no verdict, whatever the output mentions.

    The mutated run names every declared subject on purpose. Before R1.5a a non-zero exit
    naming them would have been enough against a passing baseline; against an abstention it
    is not, because a gate that abstains on both copies judged neither. The detail says it
    abstained twice - a different repair (make the gate observable) from a survivor's.
    """
    check = "C71"
    abstaining = gfi._status_line("SKIP", check, "Synthetic title", "NAME_ALPHA NAME_BRAVO")
    result = classify(
        check,
        baseline=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=skip_line(check)),
        mutated=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=abstaining),
    )

    assert result.outcome == "indeterminate"
    assert result.falsified is False
    assert result.missing_names == ()
    assert "abstained on both the unmutated and the mutated copy" in result.detail
    assert f"mutated exit {EXIT_UNAVAILABLE}" in result.detail


def test_a_skip_baseline_that_passes_under_its_mutation_is_a_survivor() -> None:
    """R1.5a: a mutation that turns an abstaining gate into a PASS is a gate that does not gate.

    The subject was broken on purpose and the gate called it sound. That is the defect a
    survivor names, so it FAILs the sweep rather than reading as an absence.
    """
    check = "C70"
    passing = gfi._status_line("PASS", check, "Synthetic title", "NAME_ALPHA NAME_BRAVO hold")
    result = classify(
        check,
        baseline=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=skip_line(check)),
        mutated=runner_run(check, exit_code=EXIT_PASS, status_line=passing),
    )

    assert result.outcome == "survived"
    assert result.falsified is False
    assert "PASS a broken subject" in result.detail
    assert f"mutated exit {EXIT_PASS}" in result.detail


def test_a_skip_baseline_that_fails_without_naming_every_subject_survives_naming_the_gap() -> None:
    """R1.5a keeps the naming obligation: a FAIL that names less is not a falsification."""
    check = "C72"
    result = classify(
        check,
        baseline=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=skip_line(check)),
        mutated=runner_run(check, exit_code=EXIT_FAIL, status_line=fail_line(check, "NAME_ALPHA")),
    )

    assert result.outcome == "survived"
    assert result.names_present == ("NAME_ALPHA",)
    assert result.missing_names == ("NAME_BRAVO",)
    assert "NAME_BRAVO" in result.detail


@pytest.mark.parametrize(
    ("exit_code", "status_line"),
    [
        pytest.param(
            EXIT_FAIL,
            "Traceback (most recent call last):",
            id="an-uncaught-exception-exits-1-with-no-status-line",
        ),
        pytest.param(
            EXIT_FAIL,
            "[SKIP] C60 Synthetic title: a SKIP line printed at exit 1",
            id="exit-1-beside-a-skip-line-not-a-fail-line",
        ),
        pytest.param(
            130,
            "Traceback (most recent call last):",
            id="an-exit-the-runner-never-emits",
        ),
        pytest.param(
            EXIT_UNAVAILABLE,
            "[??] C60 is not registered in this tree's Check_Registry",
            id="exit-2-unregistered-in-the-mutated-copy",
        ),
    ],
)
def test_a_skip_baseline_whose_mutated_run_reaches_no_runner_verdict_is_indeterminate(
    exit_code: int, status_line: str
) -> None:
    """R1.5a credits only the runner's FAIL or PARTIAL; any other departure from SKIP is no verdict.

    Both runs name every declared subject, so the names cannot be what decides it, and the
    detail names the mutated exit status rather than claiming a double abstention. Exit 1
    alone is not the runner's FAIL: an uncaught exception in the mutated copy - an
    import-time traceback - exits 1 too, and prints no status line.
    """
    check = "C60"
    result = classify(
        check,
        baseline=runner_run(check, exit_code=EXIT_UNAVAILABLE, status_line=skip_line(check)),
        mutated=runner_run(
            check, exit_code=exit_code, status_line=f"{status_line} NAME_ALPHA NAME_BRAVO"
        ),
    )

    assert result.outcome == "indeterminate"
    assert result.missing_names == ()
    assert f"mutated exit {exit_code}" in result.detail
    assert "abstained on both" not in result.detail


def test_an_unregistered_id_exits_2_but_is_never_admitted_as_an_abstention() -> None:
    """R1.5 stands for exit 2 without the runner's SKIP line, using the runner's own output.

    The unregistered branch of ``run_single_check`` executes no check, so it is driven for
    real: its exit status and its ``[??]`` line are exactly what a baseline of an id the copy
    does not register looks like. SKIP shares exit 2 on purpose, so the line is the only
    thing telling the two apart, and a probe judged against this one stays
    ``indeterminate`` however well the mutated run names its subjects.
    """
    check = "C999"
    assert check not in REGISTERED_IDS
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = gfi.run_single_check(check)
    printed = stdout.getvalue()
    assert code == EXIT_UNAVAILABLE
    assert printed.startswith(f"[??] {check} ")

    baseline = GateRun(
        check=check,
        command=gfi._gate_command(check),
        exit_code=code,
        output=printed,
        timed_out=False,
    )
    result = classify(
        check,
        baseline=baseline,
        mutated=runner_run(check, exit_code=EXIT_FAIL, status_line=fail_line(check)),
    )

    assert result.outcome == "indeterminate"
    assert result.falsified is False
    assert f"baseline exit {EXIT_UNAVAILABLE}" in result.detail
    assert f"`[SKIP] {check}`" in result.detail


@pytest.mark.parametrize(
    ("exit_code", "status_line"),
    [
        pytest.param(EXIT_FAIL, skip_line("C60"), id="a-skip-line-at-the-pre-r1-5a-exit"),
        pytest.param(EXIT_UNAVAILABLE, skip_line("C600"), id="another-checks-skip-line"),
        pytest.param(EXIT_UNAVAILABLE, f"note: {skip_line('C60')}", id="a-skip-line-quoted"),
        pytest.param(EXIT_UNAVAILABLE, "usage: error: bad arguments", id="exit-2-with-no-line"),
        pytest.param(EXIT_FAIL, fail_line("C60", "nothing"), id="a-baseline-already-red"),
        pytest.param(
            EXIT_FAIL,
            gfi._status_line("PARTIAL", "C60", "Synthetic title", "partly red"),
            id="a-partial-baseline",
        ),
    ],
)
def test_a_baseline_is_admitted_as_an_abstention_only_at_exit_2_with_its_own_skip_line(
    exit_code: int, status_line: str
) -> None:
    """R1.5 stands for every non-passing baseline R1.5a does not admit.

    The admission has two halves - exit 2, and the runner's ``[SKIP] <check>`` line for
    THIS check at the start of a line - and each near miss lacks one of them. FAIL and
    PARTIAL are the red baselines R1.5 was written for. Each stays ``indeterminate``,
    naming the baseline's exit status, however well the mutated run names its subjects.
    """
    check = "C60"
    result = classify(
        check,
        baseline=runner_run(check, exit_code=exit_code, status_line=status_line),
        mutated=runner_run(check, exit_code=EXIT_FAIL, status_line=fail_line(check)),
    )

    assert result.outcome == "indeterminate"
    assert result.falsified is False
    assert f"baseline exit {exit_code}" in result.detail
    assert "does not pass on the unmutated copy" in result.detail


def test_escaping_a_capture_keeps_its_lines_so_the_status_line_stays_a_line() -> None:
    """R1.5a reads the runner's status line as a LINE, so escaping must not flatten it.

    ``unicode_escape`` escapes newlines too: one non-ASCII byte anywhere in a capture would
    otherwise collapse it into a single line, and the runner's real SKIP would read as no
    status line at all - an honest null, but for a reason no gate owns.
    """
    capture = "log: \u2192 a non-ASCII arrow before the status line\n" + skip_line("C60")
    kept = gfi._ascii_lines(capture)

    assert "\n" not in gfi._ascii(capture), "the flattening _ascii_lines exists to avoid"
    assert kept.isascii()
    assert kept.split("\n")[1] == skip_line("C60")
    baseline = GateRun(
        check="C60",
        command=gfi._gate_command("C60"),
        exit_code=EXIT_UNAVAILABLE,
        output=kept,
        timed_out=False,
    )
    mutated = runner_run("C60", exit_code=EXIT_FAIL, status_line=fail_line("C60"))
    assert classify("C60", baseline=baseline, mutated=mutated).outcome == "falsified"


def test_the_runner_gives_skip_its_own_exit_status_and_only_pass_exits_zero() -> None:
    """R1.5a's precondition, pinned against the registry's own status vocabulary.

    While SKIP shared exit 1 with FAIL, an abstaining baseline was indistinguishable from a
    red one, and R1.5 read C60, C70, C71 and C72 as red. The mapping covers exactly the
    statuses ``verify_claims._run_check`` coerces every result into, so no status reaches
    the runner unmapped, and PASS is the only one that exits 0 (I-7).
    """
    assert set(gfi.RUNNER_EXIT_CODES) == set(vc.STATUSES)
    assert gfi.RUNNER_EXIT_CODES["SKIP"] == EXIT_UNAVAILABLE
    assert gfi.RUNNER_EXIT_CODES["SKIP"] != gfi.RUNNER_EXIT_CODES["FAIL"]
    assert gfi.RUNNER_EXIT_CODES["FAIL"] == gfi.RUNNER_EXIT_CODES["PARTIAL"] == EXIT_FAIL
    passing = [status for status, code in gfi.RUNNER_EXIT_CODES.items() if code == EXIT_PASS]
    assert passing == ["PASS"]


def test_an_operator_that_changes_no_byte_is_refused_rather_than_reported_as_survived() -> None:
    """R1.2 / I-7: a no-op mutation cannot falsify, so it must not be able to acquit.

    This is the shape ``gate-mutations.yaml`` records for C60's retired
    ``incomplete: true`` operator: the committed value already *was* the mutation, so
    the gate would have exited zero for reasons that have nothing to do with the
    declaration. Re-applying the same value is the same condition, and it raises.
    """
    operator = probe_operator()
    with probe_tree() as tree:
        gfi.inject(operator, tree)
        mutated = (tree / PROBE_TARGET).read_text(encoding="utf-8")
        assert mutated != PROBE_BODY
        assert json.loads(mutated)["thresholds"]["break"] == 10

        with pytest.raises(gfi.InjectionError) as caught:
            gfi.inject(operator, tree)

    message = str(caught.value)
    assert "changed nothing" in message
    assert PROBE_TARGET in message
    assert operator.id in message


def test_restore_returns_a_probed_target_to_its_source_bytes() -> None:
    """One copy serves a whole sweep, so each probe must leave no trace behind.

    Both branches matter: a file the operator rewrote is re-synced byte-for-byte from
    the pristine source, and a file the operator *created* is removed rather than
    restored from a source that never had it.
    """
    with tempfile.TemporaryDirectory(prefix="declared-falsification-restore-") as tmp:
        root = Path(tmp)
        pristine, tree = root / "pristine", root / "tree"
        for base in (pristine, tree):
            (base / PROBE_DIR).mkdir(parents=True)
            (base / PROBE_TARGET).write_text(PROBE_BODY, encoding="utf-8")

        rewrite = probe_operator()
        gfi.inject(rewrite, tree)
        assert (tree / PROBE_TARGET).read_text(encoding="utf-8") != PROBE_BODY
        gfi.restore(rewrite, tree, source=pristine)
        assert (tree / PROBE_TARGET).read_text(encoding="utf-8") == PROBE_BODY

        plant = planting_operator()
        gfi.inject(plant, tree)
        assert (tree / PROBE_CREATED).is_file()
        gfi.restore(plant, tree, source=pristine)
        assert not (tree / PROBE_CREATED).exists()


# ---------------------------------------------------------------------------
# The working tree is never the subject
# ---------------------------------------------------------------------------


def test_injecting_into_the_working_tree_is_refused_before_anything_is_written() -> None:
    """An audit that edits the tree it audits is not an audit (design AD-4).

    The target chosen here is a real committed file, so a missing guard would be
    observable as a changed digest rather than as an exception nobody raised.
    """
    subject = gfi.ROOT / "CLAUDE.md"
    before = digest_of(subject)

    operator = probe_operator(target="CLAUDE.md")
    with pytest.raises(gfi.InjectionError) as caught:
        gfi.inject(operator, gfi.ROOT)

    assert "working tree" in str(caught.value)
    assert digest_of(subject) == before


@given(
    escape=st.sampled_from(
        (
            "../escaped.json",
            "../../escaped.json",
            f"../{PROBE_TARGET}",
            f"{PROBE_DIR}/../../escaped.json",
        )
    )
)
def test_a_target_that_escapes_the_temporary_tree_is_refused(escape: str) -> None:
    """A declared target may not reach outside the copy it was handed."""
    operator = probe_operator(target=escape)
    with probe_tree() as tree:
        with pytest.raises(gfi.InjectionError) as caught:
            gfi.inject(operator, tree)
        assert "escapes the temporary tree" in str(caught.value)
        assert not list(tree.parent.glob("escaped.json"))


def test_the_synthetic_probe_paths_do_not_exist_in_the_real_tree() -> None:
    """The precondition every cheap case above rests on.

    ``restore`` re-syncs a probed target from the real tree. If ``PROBE_DIR`` existed
    there, the cheap cases would be reading committed bytes while claiming to be
    hermetic, and a write-direction bug would be masked.
    """
    assert not (gfi.ROOT / PROBE_DIR).exists()


def test_the_temporary_copy_carries_no_git_metadata() -> None:
    """A fault-injected tree must not be mistakable for a branch.

    Asserted against the exclusion set rather than by copying the tree: ``tree_copy``
    itself is the CI workload the slow case owns (I-0).
    """
    assert ".git" in gfi.COPY_EXCLUDED_NAMES
    assert {"node_modules", ".venv", "__pycache__"} <= gfi.COPY_EXCLUDED_NAMES
    assert ".pyc" in gfi.COPY_EXCLUDED_SUFFIXES


# ---------------------------------------------------------------------------
# Document paths: the operator writes where the declaration says, or raises
# ---------------------------------------------------------------------------

#: Keys covering the three shapes the declaration actually uses: a bare name, a path-like
#: key that must be bracket-quoted, and a key containing a space.
_PATH_SEGMENTS: Final[tuple[str, ...]] = (
    "thresholds",
    "break",
    "packages/synapse_common",
    "with space",
)


@given(
    segments=st.lists(st.sampled_from(_PATH_SEGMENTS), min_size=1, max_size=4),
    value=st.one_of(st.integers(min_value=-5, max_value=5), st.booleans(), st.none()),
)
def test_a_bracket_quoted_path_resolves_to_the_member_it_names(
    segments: list[str], value: gfi.JsonScalar
) -> None:
    """``set_at`` writes at the declared path and nowhere else.

    Written as a round trip - render the path, write through it, walk the document by
    hand - because a path expression that quietly resolves to an *approximate* node
    would mutate the wrong value and then misreport the gate that read it.
    """
    rendered = "$" + "".join(f"['{segment}']" for segment in segments)
    assert gfi.parse_document_path(rendered) == tuple(segments)

    document: dict[str, object] = {}
    node = document
    for segment in segments[:-1]:
        child: dict[str, object] = {}
        node[segment] = child
        node = child

    sentinel = "untouched"
    document["decoy"] = sentinel
    returned = gfi.set_at(document, rendered, value)
    assert returned is document

    walked: object = document
    for segment in segments:
        assert isinstance(walked, dict)
        walked = walked[segment]
    assert walked == value
    assert document["decoy"] == sentinel


def test_the_supported_path_subset_is_exactly_what_the_declaration_uses() -> None:
    """Both spellings the committed file uses parse; anything else raises.

    ``set_yaml_path`` writes dotted-with-quoted-keys and ``set_json_path`` writes
    JSONPath, and one parser serves both. An unsupported subscript must raise rather
    than resolve to something plausible.
    """
    assert gfi.parse_document_path("$.thresholds.break") == ("thresholds", "break")
    assert gfi.parse_document_path("packages['packages/synapse_common'].line") == (
        "packages",
        "packages/synapse_common",
        "line",
    )
    assert gfi.parse_document_path('floors["kv cache"][2]') == ("floors", "kv cache", 2)

    for unsupported in ("", "$", "floors[kv_cache]", "floors[2", "floors[1.5]"):
        with pytest.raises(gfi.PathSyntaxError):
            gfi.parse_document_path(unsupported)


def test_a_path_whose_parents_are_absent_is_a_wrong_path_not_a_new_shape() -> None:
    """Only the leaf key may be created.

    Creating intermediate containers would hand the gate a document shape it never had,
    so the mutation would be testing the harness's invention rather than the gate.
    Creating the *leaf* is legitimate: "add a key the gate must reject" is a real
    mutation.
    """
    with pytest.raises(gfi.InjectionError):
        gfi.set_at({"floors": {}}, "floors.missing.line", 1.0)
    with pytest.raises(gfi.InjectionError):
        gfi.set_at({"floors": []}, "floors[3]", 1.0)
    with pytest.raises(gfi.InjectionError):
        gfi.set_at({"floors": 7}, "floors.line", 1.0)

    document: dict[str, object] = {"floors": {}}
    gfi.set_at(document, "floors.replicates_per_arm", 5)
    assert document == {"floors": {"replicates_per_arm": 5}}


# ---------------------------------------------------------------------------
# The subprocess is never told the answer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("check", "operator"), COMMITTED_OPERATORS, ids=COMMITTED_OPERATOR_IDS)
def test_the_gate_subprocess_is_told_the_check_id_and_nothing_about_the_mutation(
    check: str, operator: MutationOperator
) -> None:
    """R1.2: ``expect_names`` has to be earned by observation, not by echo.

    The whole naming obligation collapses if the harness hands the subprocess the
    strings it will later search for. The argv is therefore a function of the check id
    alone, and this asserts that no operator id and no target reaches it. The
    interpreter path (``argv[0]``) is excluded from the substring search because the
    harness did not choose it - on some hosts it legitimately contains digits that a
    numeric expectation would collide with.
    """
    argv = gfi._gate_command(check)
    assert argv[0] == sys.executable
    assert argv[1:] == ("-m", "scripts.audit.gate_fault_injection", "--run-check", check)

    joined = " ".join(argv[1:])
    assert check in joined
    assert operator.id not in joined
    assert operator.file_target not in joined
    if operator.symbol_target is not None:
        assert operator.symbol_target not in joined

    # Two operators of the same gate produce the same command, so the subprocess cannot
    # tell which mutation it is being asked about.
    assert gfi._gate_command(check) == argv


# ---------------------------------------------------------------------------
# Reporting tools, undeclared checks, and PASS-eligibility
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DeclarationDraft:
    """A generated ``gate-mutations.yaml``: which checks declare, which are excluded."""

    declared: tuple[str, ...]
    tools: tuple[str, ...]
    unregistered: tuple[str, ...] = ()
    declared_gates_override: int | None = None
    empty_expect_names: bool = False

    @property
    def gate_ids(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((*self.declared, *self.unregistered)))

    @property
    def declared_pairs(self) -> tuple[tuple[str, str], ...]:
        """``(check, operator_id)`` for every operator this draft declares, in file order.

        The unit a sweep is measured in (R1.7). ``document()`` names each operator
        ``op-{index}`` over :attr:`gate_ids`, and a synthetic sweep must return results
        keyed by these pairs: a result carrying an operator id the declaration does not
        contain models a sweep that cannot exist, and would leave every real declared
        operator unproven for a reason the harness is not responsible for.
        """
        return tuple((check, f"op-{index}") for index, check in enumerate(self.gate_ids))

    @property
    def known(self) -> frozenset[str]:
        return frozenset(self.gate_ids) | frozenset(self.tools)

    @property
    def undeclared(self) -> tuple[str, ...]:
        return tuple(cid for cid in REGISTERED_IDS if cid not in self.known)

    def document(self) -> dict[str, object]:
        """The YAML document, in the shape the committed schema requires."""
        gates: dict[str, object] = {}
        for index, check in enumerate(self.gate_ids):
            gates[check] = {
                "title": f"generated declaration for {check}",
                "operators": [
                    {
                        "id": f"op-{index}",
                        "operator": "delete_file",
                        "target": f"{PROBE_DIR}/{check.lower()}.txt",
                        "expect_names": [] if self.empty_expect_names else ["NAME_ALPHA"],
                    }
                ],
            }
        return {
            "version": 1,
            "gates": gates,
            "reporting_tools": [
                {"check": check, "reason": "generated: no falsifying mutation exists"}
                for check in self.tools
            ],
            # A committed declaration carries the sweep's per-subprocess bound, and a
            # probing run reads it rather than defaulting to ``DEFAULT_TIMEOUT_S``
            # (AD-22). Included here so these cases exercise the aggregate they are about
            # instead of the missing-budget refusal, which has its own coverage in
            # ``test_sweep_budget_admission.py``. Schema-complete: ``invariant`` and
            # ``derivation`` are required whenever the block is present.
            "sweep_budget": {
                "per_subprocess_timeout_s": 90,
                "install_budget_s": 420,
                "job_timeout_minutes": 60,
                "invariant": (
                    "(baselines + operators) * per_subprocess_timeout_s + "
                    "install_budget_s <= job_timeout_minutes * 60"
                ),
                "derivation": {
                    "baselines_from": "completeness.declared_gates",
                    "operators_from": "gates.*.operators",
                },
            },
            "completeness": {
                "declared_gates": (
                    len(gates)
                    if self.declared_gates_override is None
                    else self.declared_gates_override
                ),
                "registry_size_at_authoring": len(REGISTERED_IDS),
                "enforced_by": "generated: task 12.1",
            },
        }

    def write(self, directory: Path) -> Path:
        path = directory / "gate-mutations.yaml"
        path.write_text(
            yaml.safe_dump(self.document(), sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        return path


def synthetic_result(
    check: str, operator_id: str, outcome: gfi.Outcome
) -> FaultInjectionResult:
    """A probe result whose fields are consistent with the outcome it reports.

    Consistency matters even though the classifier is not under test here: an
    inconsistent result would let an aggregation bug hide behind a field nobody could
    have produced.
    """
    applied = outcome != "not-applied"
    timed_out = outcome == "indeterminate"
    exit_code = None if outcome in ("not-applied", "indeterminate") else (1 if applied else None)
    if outcome == "survived":
        exit_code = 0
    return FaultInjectionResult(
        check=check,
        operator_id=operator_id,
        operator=OperatorKind.DELETE_FILE,
        target=f"{PROBE_DIR}/{check.lower()}.txt",
        expect_names=("NAME_ALPHA",),
        applied=applied,
        exit_code=exit_code,
        non_zero_exit=exit_code not in (0, None),
        names_present=("NAME_ALPHA",) if outcome == "falsified" else (),
        missing_names=() if outcome == "falsified" else ("NAME_ALPHA",),
        baseline_exit_code=0 if applied else None,
        baseline_probed=applied,
        timed_out=timed_out,
        outcome=outcome,
        detail=f"generated {outcome} for {check}/{operator_id}",
    )


@st.composite
def sweep_cases(draw: st.DrawFn) -> tuple[DeclarationDraft, tuple[FaultInjectionResult, ...]]:
    """A generated declaration plus the probe results a sweep of it would return.

    ``tools`` is drawn independently of ``declared`` so the overlap case is reachable: a
    check that both declares an operator *and* is listed as a reporting tool is the case
    where the PASS-eligibility filter has to earn its keep, and that is the case a
    reporting tool could smuggle a PASS through.

    Results are keyed by the draft's own ``(check, operator_id)`` pairs, in declaration
    order, and the drawn subset includes the complete set. Two things follow, and both
    are deliberate (task 5.4). A **strict** subset is a sweep that left declared operators
    unproven, which R1.7 makes a FAIL -- so that branch is reachable. The **full** subset
    is a complete sweep, so the ``pass`` branch stays reachable too; keying results by
    invented operator ids would have made every draw unproven and quietly retired the pass
    branch from this property. A tool-only check -- one listed under ``reporting_tools``
    with no ``gates:`` entry -- has no declared operator, so no sweep can return a result
    for it; the PASS-eligibility filter is exercised through the overlap case instead,
    which is the reachable one.
    """
    declared = tuple(
        draw(st.lists(st.sampled_from(REGISTERED_IDS), min_size=1, max_size=4, unique=True))
    )
    tools = tuple(draw(st.lists(st.sampled_from(REGISTERED_IDS), max_size=3, unique=True)))
    draft = DeclarationDraft(declared=declared, tools=tools)

    pairs = draft.declared_pairs
    indices = sorted(
        draw(
            st.lists(
                st.integers(min_value=0, max_value=len(pairs) - 1),
                unique=True,
                max_size=len(pairs),
            )
        )
    )
    results = tuple(
        synthetic_result(pairs[index][0], pairs[index][1], draw(st.sampled_from(OUTCOMES)))
        for index in indices
    )
    return draft, results


@contextlib.contextmanager
def patched_sweep(
    results: tuple[FaultInjectionResult, ...],
) -> Iterator[list[gfi.MutationDeclaration]]:
    """Replace the harness's *own* sweep orchestrator, never a gate's evaluator.

    ``sweep`` copies the tree and runs one subprocess per gate plus one per operator.
    Driving the aggregate over generated result sets is the only way to quantify over it
    at zero process cost (I-0), and it substitutes nothing that any gate owns.
    """
    seen: list[gfi.MutationDeclaration] = []

    def fake_sweep(
        declaration: gfi.MutationDeclaration,
        *,
        only: str | None = None,
        operator_id: str | None = None,
        timeout: float = gfi.DEFAULT_TIMEOUT_S,
        with_baseline: bool = True,
    ) -> tuple[FaultInjectionResult, ...]:
        del only, operator_id, timeout, with_baseline
        seen.append(declaration)
        return results

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gfi, "sweep", fake_sweep)
        yield seen


@given(case=sweep_cases())
def test_a_reporting_tool_or_undeclared_check_is_never_pass_eligible(
    case: tuple[DeclarationDraft, tuple[FaultInjectionResult, ...]],
) -> None:
    """R1.2 / I-7: absence of a falsification is an exclusion, never an exemption.

    Three obligations, each recomputed here from the draft rather than read back from
    the report: the registered ids partition into declared / reporting-tool /
    undeclared with nothing lost; the excluded set is exactly the tools plus the
    undeclared; and PASS-eligibility contains only checks whose *every* declared probe
    falsified, minus every reporting tool. The last one is asserted even when the
    generated sweep hands back a falsified result for a tool-only check, because that is
    the direction in which an exclusion could silently become a pass.
    """
    draft, results = case
    with tempfile.TemporaryDirectory(prefix="declared-falsification-decl-") as tmp:
        declaration_path = draft.write(Path(tmp))
        with patched_sweep(results) as seen:
            report = gfi.evaluate(
                declaration_path=declaration_path,
                schema_path=gfi.SCHEMA_FILE,
                probe=True,
            )

    assert len(seen) == 1
    assert seen[0].declared_ids == draft.gate_ids

    # The declaration is schema-valid and every id is registered, so nothing about the
    # partition below is a consequence of a declaration defect.
    assert [f for f in report.findings if f.rule == "declaration-schema-invalid"] == []
    assert report.unregistered_declared_ids == ()
    assert report.registered_ids == REGISTERED_IDS
    assert report.declared_ids == draft.gate_ids
    assert report.reporting_tool_ids == draft.tools

    # Partition totality over the registry: no registered check falls through.
    assert report.undeclared_ids == draft.undeclared
    assert not set(report.undeclared_ids) & draft.known
    classified = (
        set(report.declared_ids) | set(report.reporting_tool_ids) | set(report.undeclared_ids)
    )
    assert classified >= set(REGISTERED_IDS)

    # Exclusion is the tools plus the undeclared, deduplicated, tools first.
    assert report.excluded_ids == tuple(dict.fromkeys((*draft.tools, *draft.undeclared)))
    assert set(draft.tools) <= set(report.excluded_ids)

    # A check is falsified only when EVERY operator DECLARED for it falsified (R1.6, as
    # AD-22 states it). Two clauses, and the second was added by task 5.4: every probed
    # result for the check falsified, AND no operator declared for it went unprobed. A check
    # whose second mutation was never applied is not falsified by its first.
    probed_pairs_seen = {(result.check, result.operator_id) for result in results}
    partially_probed = {
        check
        for check, operator_id in draft.declared_pairs
        if (check, operator_id) not in probed_pairs_seen
    }
    probed_order = tuple(dict.fromkeys(result.check for result in results))
    expected_falsified = tuple(
        check
        for check in probed_order
        if check not in partially_probed
        and all(result.falsified for result in results if result.check == check)
    )
    assert report.falsified_ids == expected_falsified

    # The core I-7 assertion: a reporting tool never contributes a PASS, even when its
    # own probe falsified it, and an undeclared check never appears at all.
    assert report.pass_eligible_ids == tuple(
        check for check in expected_falsified if check not in set(draft.tools)
    )
    assert not set(report.pass_eligible_ids) & set(report.reporting_tool_ids)
    assert not set(report.pass_eligible_ids) & set(report.undeclared_ids)
    assert set(report.pass_eligible_ids) <= set(report.falsified_ids)

    # The verdict follows E2.1's precedence, recomputed independently. Note that
    # ``probed`` is the *flag*, not the result count: E2.1's rule 3 keys off the request
    # to probe, so a sweep that returned no result at all reaches ``pass`` with an empty
    # PASS-eligible set. That is the documented behaviour and it is asserted as such
    # here rather than quietly assumed away; it is reported as an observation.
    blocking = sum(1 for result in results if result.outcome in BLOCKING_OUTCOMES)
    indeterminate = sum(1 for result in results if result.outcome == "indeterminate")

    # R1.7 (task 5.4): the probed and the declared count in the SAME UNIT, and the
    # remainder reported UNPROVEN. Recomputed from the draft rather than read back, so
    # this compares two implementations of the rule instead of asking the report to agree
    # with itself.
    probed_pairs = {(result.check, result.operator_id) for result in results}
    expected_unproven = tuple(
        f"{check}/{operator_id}"
        for check, operator_id in draft.declared_pairs
        if (check, operator_id) not in probed_pairs
    )
    assert report.declared_operators == len(draft.declared_pairs)
    assert report.probed_operators == len(results)
    assert report.complete_sweep is True
    assert report.unproven_operator_ids == expected_unproven
    assert report.probed_operators + len(report.unproven_operator_ids) == (
        report.declared_operators
    )
    unproven_findings = tuple(
        finding for finding in report.findings if finding.rule == "declared-operator-unproven"
    )
    assert len(unproven_findings) == len(expected_unproven)
    for finding in unproven_findings:
        assert f"{finding.check}/{finding.operator_id}" in expected_unproven
        assert finding.requirement == "R1.7"
        assert "UNPROVEN" in finding.detail

    assert report.verdict == declared_verdict(
        blocking=blocking,
        probed=True,
        indeterminate=indeterminate,
        unproven=len(expected_unproven),
    )
    assert report.exit_code == EXPECTED_EXIT_CODES[report.verdict]
    assert report.passing is (report.verdict == "pass")
    assert (report.exit_code == EXIT_PASS) is report.passing

    # Every non-falsified probe is surfaced as a finding naming its subject; a
    # falsified one raises none.
    unproven = tuple(result for result in results if result.outcome != "falsified")
    outcome_findings = tuple(
        finding for finding in report.findings if finding.rule in OUTCOME_RULES.values()
    )
    assert len(outcome_findings) == len(unproven)
    for finding, result in zip(outcome_findings, unproven, strict=True):
        assert finding.rule == OUTCOME_RULES[result.outcome]
        assert finding.check == result.check
        assert finding.operator_id == result.operator_id
        assert finding.detail == result.detail
        assert finding.requirement == "R1.2"

    # The excluded count is stated, so a reader can see how much was not proven.
    notes = "\n".join(report.notes)
    assert f"{len(report.reporting_tool_ids)} reporting tool(s)" in notes
    assert f"{len(report.undeclared_ids)} undeclared check(s)" in notes


@given(case=sweep_cases())
def test_an_unprobed_run_is_unavailable_however_clean_the_declaration_is(
    case: tuple[DeclarationDraft, tuple[FaultInjectionResult, ...]],
) -> None:
    """R1.2 / I-7: a valid declaration is not evidence that any gate bites.

    This is the honest default the module ships with, and it is the reason the local
    invocation cannot pass: validating the file proves the declaration is well formed,
    which is a precondition of the sweep and never a substitute for it.
    """
    draft, _results = case
    with tempfile.TemporaryDirectory(prefix="declared-falsification-unprobed-") as tmp:
        declaration_path = draft.write(Path(tmp))
        report = gfi.evaluate(
            declaration_path=declaration_path, schema_path=gfi.SCHEMA_FILE, probe=False
        )

    assert report.probed is False
    assert report.results == ()
    assert report.falsified_ids == ()
    assert report.pass_eligible_ids == ()
    assert report.verdict == "unavailable"
    assert report.exit_code == EXIT_UNAVAILABLE
    assert report.passing is False
    assert "not a pass" in report.reason
    assert any("--sweep" in note for note in report.notes)


# ---------------------------------------------------------------------------
# A defective declaration FAILs; it is never reported as merely unavailable
# ---------------------------------------------------------------------------


def _fail_report(draft: DeclarationDraft) -> gfi.FaultInjectionReport:
    with tempfile.TemporaryDirectory(prefix="declared-falsification-defect-") as tmp:
        return gfi.evaluate(
            declaration_path=draft.write(Path(tmp)),
            schema_path=gfi.SCHEMA_FILE,
            probe=False,
        )


def test_a_schema_invalid_declaration_fails_naming_the_check_and_the_operator() -> None:
    """A committed file that does not validate is a repository defect, not a gap.

    ``expect_names: []`` is the sharpest case: an operator that expects no name has no
    naming obligation at all, so it could never distinguish an actionable red from a
    mystery. The finding has to recover the check and the operator from the schema
    error's path, because "``/gates/C16/operators/0/expect_names`` is wrong" is not
    something a reader can act on.
    """
    draft = DeclarationDraft(declared=(REGISTERED_IDS[0],), tools=(), empty_expect_names=True)
    report = _fail_report(draft)

    findings = tuple(f for f in report.findings if f.rule == "declaration-schema-invalid")
    assert findings
    assert any(f.check == REGISTERED_IDS[0] and f.operator_id == "op-0" for f in findings)
    assert any("expect_names" in f.detail for f in findings)
    assert report.verdict == "fail"
    assert report.exit_code == EXIT_FAIL
    assert report.passing is False


@given(ids=check_ids(min_size=1, max_size=2))
def test_a_declaration_naming_an_unregistered_check_fails_naming_it(
    ids: tuple[str, ...],
) -> None:
    """A mutation for a check nobody registered can never be evaluated.

    The identifiers come from the shared registry-shaped generator and are mapped into
    the ``C9xx`` band, which is beyond every id the registry declares, so a generated id
    is unregistered because it is absent rather than because it is malformed - the
    schema still accepts its shape.
    """
    unregistered = tuple(
        dict.fromkeys(f"C9{cid[1:] if cid[1:].isdigit() else '0'}" for cid in ids)
    )
    assert not set(unregistered) & set(REGISTERED_IDS)

    draft = DeclarationDraft(
        declared=(REGISTERED_IDS[0],), tools=(), unregistered=unregistered
    )
    report = _fail_report(draft)

    assert set(report.unregistered_declared_ids) == set(unregistered)
    findings = tuple(f for f in report.findings if f.rule == "declared-check-not-registered")
    assert {f.check for f in findings} == set(unregistered)
    assert report.verdict == "fail"
    assert report.exit_code == EXIT_FAIL
    for check in unregistered:
        assert check in report.reason


@given(drift=st.integers(min_value=1, max_value=9))
def test_a_recorded_declared_gate_count_that_disagrees_with_the_gates_fails(
    drift: int,
) -> None:
    """The recorded count exists so a hand edit to ``gates:`` is itself detectable."""
    declared = (REGISTERED_IDS[0], REGISTERED_IDS[1])
    draft = DeclarationDraft(
        declared=declared, tools=(), declared_gates_override=len(declared) + drift
    )
    report = _fail_report(draft)

    findings = tuple(f for f in report.findings if f.rule == "completeness-count-drift")
    assert len(findings) == 1
    assert str(len(declared) + drift) in findings[0].detail
    assert str(len(declared)) in findings[0].detail
    assert report.verdict == "fail"
    assert report.exit_code == EXIT_FAIL


def test_an_unreadable_declaration_or_schema_is_unavailable_never_a_pass() -> None:
    """An absent declaration is an unavailable measurement, and never a pass."""
    with tempfile.TemporaryDirectory(prefix="declared-falsification-missing-") as tmp:
        absent = Path(tmp) / "gate-mutations.yaml"
        with pytest.raises(gfi.DeclarationError):
            gfi.evaluate(declaration_path=absent, schema_path=gfi.SCHEMA_FILE)

        unparseable = Path(tmp) / "broken.yaml"
        unparseable.write_text("gates: [unclosed\n", encoding="utf-8")
        with pytest.raises(gfi.DeclarationError):
            gfi.evaluate(declaration_path=unparseable, schema_path=gfi.SCHEMA_FILE)

        draft = DeclarationDraft(declared=(REGISTERED_IDS[0],), tools=())
        with pytest.raises(gfi.DeclarationError):
            gfi.evaluate(
                declaration_path=draft.write(Path(tmp)),
                schema_path=Path(tmp) / "absent.schema.json",
            )


# ---------------------------------------------------------------------------
# The committed declaration, checked against today's tree (static, no subprocess)
# ---------------------------------------------------------------------------


def test_the_committed_declaration_validates_and_names_only_registered_checks() -> None:
    """The precondition of the whole sweep: a valid, registry-consistent declaration."""
    assert gfi.schema_findings(COMMITTED_DOCUMENT, COMMITTED_SCHEMA) == ()
    assert COMMITTED.completeness.declared_gates == len(COMMITTED.gates)
    assert COMMITTED.completeness.enforced_by
    assert set(COMMITTED.declared_ids) <= set(REGISTERED_IDS)
    assert set(COMMITTED.reporting_tool_ids) <= set(REGISTERED_IDS)
    assert COMMITTED.gates, "the declaration records no gate at all"

    for gate in COMMITTED.gates:
        operator_ids = [operator.id for operator in gate.operators]
        assert len(set(operator_ids)) == len(operator_ids), (
            f"{gate.check} declares a duplicate operator id: {operator_ids}"
        )
        for operator in gate.operators:
            assert operator.expect_names, f"{gate.check}/{operator.id} expects no name"
            for name in operator.expect_names:
                assert name.isascii() and name.strip(), (
                    f"{gate.check}/{operator.id} declares a non-ASCII or blank name"
                )
            relative = Path(operator.file_target)
            assert not relative.is_absolute()
            assert ".." not in relative.parts
            assert operator.file_target == operator.target.split("::", 1)[0]


def _symbol_exists(module: ast.Module, symbol: str) -> bool:
    """Whether ``Class.func`` / ``func`` is defined in a parsed module.

    Written out here rather than borrowed from the harness so the mutated file is judged
    by something other than the code that produced it.
    """
    owner, _, name = symbol.rpartition(".")
    if owner:
        return any(
            isinstance(node, ast.ClassDef)
            and node.name == owner
            and any(
                isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name == name
                for child in node.body
            )
            for node in module.body
        )
    return any(
        isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name
        for node in ast.walk(module)
    )


@pytest.mark.parametrize(("check", "operator"), COMMITTED_OPERATORS, ids=COMMITTED_OPERATOR_IDS)
def test_every_committed_operator_still_applies_to_the_file_it_targets(
    check: str, operator: MutationOperator
) -> None:
    """A declaration that has drifted from the tree probes nothing (R1.2).

    Applicability is a separate obligation from falsification, and it is the one that
    rots: a renamed symbol or a reworded line silently turns an operator into a
    ``not-applied`` result that proves nothing about the gate. Each operator is applied
    inside a throwaway directory seeded with *only* the single file it targets - which
    needs no tree copy (I-0) and cannot write inside the working tree - and the real
    file's digest is compared before and after to prove it.
    """
    source = gfi.ROOT / operator.file_target
    before = digest_of(source) if source.is_file() else None

    with tempfile.TemporaryDirectory(prefix="declared-falsification-applies-") as tmp:
        tree = Path(tmp) / "synapse"
        tree.mkdir()
        target = tree / operator.file_target
        target.parent.mkdir(parents=True, exist_ok=True)

        if operator.operator is OperatorKind.CREATE_FILE:
            assert not source.exists(), (
                f"{check}/{operator.id} plants {operator.file_target}, which already "
                "exists in the tree, so the operator can never apply in a real copy"
            )
        else:
            assert source.is_file(), (
                f"{check}/{operator.id} targets {operator.file_target}, which is not a "
                "file in this tree: the declaration has drifted"
            )
            shutil.copy2(source, target)

        # Compared as decoded text, not bytes: the harness reads and writes with
        # ``encoding='utf-8'`` (E-S13-07), so a byte comparison on Windows would be
        # satisfied by newline normalisation alone and would pass vacuously.
        seeded = target.read_text(encoding="utf-8") if target.is_file() else None
        gfi.inject(operator, tree)

        if operator.operator is OperatorKind.CREATE_FILE:
            assert target.read_text(encoding="utf-8") == operator.body
        elif operator.operator is OperatorKind.DELETE_FILE:
            assert not target.exists()
        else:
            assert target.is_file()
            assert target.read_text(encoding="utf-8") != seeded, (
                f"{check}/{operator.id} changed nothing: a no-op mutation can falsify "
                "nothing, so the declaration has drifted from the tree"
            )

        if operator.operator is OperatorKind.REPLACE_FUNCTION_BODY:
            # The signature, decorators and annotations survive on purpose: the point is
            # a function that still looks right and does nothing, which is the shape a
            # substring-matching gate cannot see (the canonical AD-4 example).
            symbol = operator.symbol_target
            assert symbol is not None
            mutated = ast.parse(target.read_text(encoding="utf-8"))
            assert _symbol_exists(mutated, symbol)

    if before is not None:
        assert digest_of(source) == before, "the working tree was mutated by an audit"


def test_the_default_invocation_probes_nothing_and_cannot_report_a_pass() -> None:
    """R1.2 / I-0: the local default is honest about having proven nothing.

    Four modes, one exit status: ``--check`` only suppresses the trailing operator note,
    so a gate whose default invocation cannot fail is the hole this feature exists to
    close. Nothing is probed here, so no process is started; the sweep that would probe
    belongs to ``ci.yml::uplift-verify``.
    """
    for as_json, check in ((False, False), (False, True), (True, False), (True, True)):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = gfi.run(as_json=as_json, check=check)
        text = stdout.getvalue()

        assert code == EXIT_UNAVAILABLE
        assert code != EXIT_PASS

        if as_json:
            payload = json.loads(text)
            # Canonical serialisation: sorted keys, tight separators.
            assert text.strip() == json.dumps(payload, sort_keys=True, separators=(",", ":"))
            assert payload["verdict"] == "unavailable"
            assert payload["probed"] is False
            assert payload["pass_eligible_ids"] == []
            assert payload["declared_ids"] == list(COMMITTED.declared_ids)
        else:
            assert "UNAVAILABLE" in text
            assert "--sweep" in text
            assert f"DECLARED={len(COMMITTED.declared_ids)}" in text
            # The un-suppressed note is the one that tells a reader this exit status
            # must not be wrapped in a discarding construct.
            assert ("|| true" in text) is (not check)


# ---------------------------------------------------------------------------
# The real thing: one gate, one subprocess, one tree copy. CI only.
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_a_real_subprocess_probe_agrees_with_the_declared_decision_table() -> None:
    """R1.2, R9.5: the falsification claim, asserted against a real gate process.

    Everything above drives the classifier over synthesised runs. This is the case that
    produces a real one: the tree is copied, the gate is run unmutated, a committed
    operator is applied, and the gate is run again - in another operating-system
    process, importing the *mutated* copy's own registry. There is no seam in which a
    stub could be substituted, which is exactly R9.5's obligation.

    What is asserted is the relationship, not today's verdict. ``gate-mutations.yaml``
    discloses which declarations do not yet bite (C28 until its 2026-10-01 measured-bound
    clause, C44 while its baseline was red), so asserting universal falsification here would
    make this file red for a reason the declaration already records honestly. Turning that
    shortfall into a gate is ``--sweep`` in ``ci.yml::uplift-verify`` (task 12.2). What this
    proves is that the real launcher produces runs the classifier handles exactly as E2.1
    declares, that the mutation lands, and that the working tree does not move.

    ``@pytest.mark.slow``: a full tree copy plus two gate subprocesses is a CI workload,
    excluded locally by ``-m "not slow"`` (I-0). The launcher is wrapped only to keep the
    mutated run's output, so the restatement can read the runner's status line as R1.5a
    requires; the wrapper calls the real launcher, which still starts the real gate process.
    """
    check, operator = COMMITTED_OPERATORS[0]
    subject = gfi.ROOT / operator.file_target
    before = digest_of(subject) if subject.is_file() else None
    real_launcher = gfi.run_gate
    mutated_runs: list[GateRun] = []

    def recording_launcher(
        gate: str,
        tree_root: Path,
        *,
        timeout: float = gfi.DEFAULT_TIMEOUT_S,
        command: Sequence[str] | None = None,
    ) -> GateRun:
        run = real_launcher(gate, tree_root, timeout=timeout, command=command)
        mutated_runs.append(run)
        return run

    with gfi.tree_copy() as tree, pytest.MonkeyPatch.context() as mp:
        assert tree.resolve() != gfi.ROOT.resolve()
        assert not (tree / ".git").exists()

        baseline = real_launcher(check, tree, timeout=gfi.DEFAULT_TIMEOUT_S)
        assert baseline.check == check
        assert baseline.command == gfi._gate_command(check)
        assert baseline.passed is (baseline.exit_code == 0 and not baseline.timed_out)

        mp.setattr(gfi, "run_gate", recording_launcher)
        result = gfi.falsifies(
            check, operator, tree=tree, baseline=baseline, timeout=gfi.DEFAULT_TIMEOUT_S
        )
        # The probe restored its own target, so the copy is reusable by the next one.
        if subject.is_file():
            assert (tree / operator.file_target).is_file()
            assert digest_of(tree / operator.file_target) == digest_of(subject)

    # The unmutated run is the gate's own verdict on the copy, and it names the check it
    # was asked about - the only thing the subprocess was told.
    if baseline.exit_code is not None and not baseline.timed_out:
        assert check in baseline.output

    assert result.applied, (
        f"{check}/{operator.id} did not land in a real tree copy: {result.detail}"
    )
    assert result.outcome in OUTCOMES
    assert result.falsified is (result.outcome == "falsified")
    assert result.outcome == declared_outcome(
        check=check,
        applied=result.applied,
        timed_out=result.timed_out,
        exit_code=result.exit_code,
        mutated_output="\n".join(run.output for run in mutated_runs),
        missing_names=result.missing_names,
        baseline=baseline,
    )
    assert result.baseline_probed is True
    assert result.baseline_exit_code == baseline.exit_code
    if result.falsified:
        assert result.missing_names == ()
        assert result.non_zero_exit
        for name in operator.expect_names:
            assert name in result.detail

    if before is not None:
        assert digest_of(subject) == before, "a real probe mutated the working tree"
