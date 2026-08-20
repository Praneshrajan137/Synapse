"""Property-based test for the measured-threshold gate (design E1.8; R7.3, R7.6, R7.7).

Feature: purpose-achievement-audit, Property 8: A measured threshold gate reflects the
measurement

    *For any* measured value of the KV-cache hit rate, the tier-routing accuracy, or the
    frontend mutation score, the gate exits non-zero iff the value is below the floor read
    from its committed configuration file, and reports the measured value and the floor;
    when the measurement cannot be taken the gate reports unavailable and never ``PASS``.

Why a property and not examples. The audit's finding here is an *absence*: the KV-cache
``0.70`` and tier-routing ``0.80`` floors have been documented in ``CLAUDE.md`` since
Sprint 9 with no assertion anywhere in ``scripts/**`` or ``.github/workflows/**``, and
``infrastructure/quality/ratchets.json`` records both as ``status: unmeasured``. A gate
written to close an absence has two easy ways to be vacuous, and neither is visible from
a single example: it can pass on any input (a floor nothing is compared against), or it
can pass when no measurement was taken (absence of proof read as proof). So the property
quantifies over the whole ``(measurement, floor)`` space and asserts three things a
vacuous gate cannot satisfy - the verdict *tracks* the measurement, the classification is
*total*, and an untaken measurement is ``unavailable`` and never a pass (I-7).

Ground truth. Each expectation is recomputed here from the generated case with a plain
``measured < floor`` comparison rather than imported from the gate, so the test compares
two implementations of the rule instead of asking the gate to agree with itself. The
floors the gate reports are compared against the values *written into the generated YAML*,
which is what makes "read from configuration" distinguishable from "hardcoded": change the
file and the reported floor must change with it.

Hermetic roots, per the pattern task 2.11 established. ``replay_metrics.evaluate`` already
takes a ``root`` for the tree it reads and a ``measurers`` mapping for where the numbers
come from, both with production defaults, so every generated case writes its own
``replay-floors.yaml`` and its own trace directory into a ``tempfile.TemporaryDirectory``
and is removed on the way out. No module global is patched and no generated path can bind
to a committed file. No root parameter had to be added.

**The 200 golden traces are never replayed here.** Design E1.8 runs this gate in
``ci.yml::quality-gates`` only, and a golden-trace replay is named in **I-0** as a CI
workload. The ``measurers`` seam exists precisely so the verdict can be driven on
synthetic measurements; this file reads and writes a handful of small files and executes
no replay, no harness, no subprocess and no suite.

``max_examples`` is never set here - the budget comes from the root ``conftest.py``
profiles (``dev``=10, ``heavy``=100, ``ci``/``default``=500, ``nightly``=5000).

**Validates: Requirements 7.3, 7.6, 7.7**
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import yaml
from hypothesis import given
from hypothesis import strategies as st

from scripts.audit import replay_metrics as rm
from scripts.audit.replay_metrics import Outcome
from tests.verify.strategies import threshold_sequences

#: Where the generated tree puts its traces. Any relative path works - the gate resolves
#: ``replay.traces_dir`` against the root it is given - so this mirrors the committed
#: layout only to keep the generated tree readable.
TRACES_RELPATH: Final[str] = "tests/eval/golden_traces"

#: Severity order used for the monotonicity assertion. A pass is the best a measured
#: value can do; a breach is the worst. ``UNAVAILABLE`` never participates: it is not a
#: point on the measurement axis, it is the absence of one.
SEVERITY: Final[dict[Outcome, int]] = {Outcome.PASS: 0, Outcome.FAIL: 1}

#: The floors CLAUDE.md has documented since Sprint 9, as committed to the YAML this gate
#: reads. Asserted against the committed file so the two numbers the audit found ungated
#: (R7.6, R7.7) stay pinned to a file a gate actually reads.
COMMITTED_FLOORS: Final[dict[str, float]] = {
    rm.KV_CACHE_METRIC: 0.70,
    rm.TIER_ROUTING_METRIC: 0.80,
}


# ---------------------------------------------------------------------------
# The generated case
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplayCase:
    """One generated ``(floors, measurements)`` pair for the two replay metrics.

    ``measurements[metric] is None`` models the measurement that could not be taken -
    traces absent, harness unimportable, or a gauge carrying no sample - which R7.3
    obliges the gate to report as ``unavailable`` rather than as a number.
    """

    floors: Mapping[str, float]
    measurements: Mapping[str, float | None]
    trace_count: int

    def expected_outcome(self, metric: str) -> Outcome:
        """The verdict the rule mandates, restated independently of the gate."""
        measured = self.measurements.get(metric)
        if metric not in self.floors or measured is None:
            return Outcome.UNAVAILABLE
        return Outcome.FAIL if measured < self.floors[metric] else Outcome.PASS

    @property
    def expected_gate_outcome(self) -> Outcome:
        """A breach outranks an absence, and an absence outranks a pass (I-7)."""
        outcomes = [self.expected_outcome(metric) for metric in rm.METRIC_ORDER]
        if Outcome.FAIL in outcomes:
            return Outcome.FAIL
        if Outcome.UNAVAILABLE in outcomes:
            return Outcome.UNAVAILABLE
        return Outcome.PASS


def _distinct_pair(pair: tuple[float, ...]) -> tuple[float, float]:
    """Turn a generated pair into a strictly ordered ``(lower, higher)`` pair.

    Constructed rather than filtered: two-decimal floats in ``[0, 1]`` tie often enough
    (Hypothesis favours ``0.0`` and ``1.0``) that an ``assume`` would throw away a large
    share of the budget.
    """
    lower, higher = min(pair), max(pair)
    if lower == higher:
        higher = round(min(higher + 0.01, 1.0), 2)
        if lower == higher:  # the pair was pinned at the top of the range
            lower = round(higher - 0.01, 2)
    return lower, higher


@st.composite
def replay_cases(
    draw: st.DrawFn,
    *,
    allow_unavailable: bool = True,
    below_floor: bool | None = None,
) -> ReplayCase:
    """A ``(floors, measurements)`` case over both metrics.

    ``below_floor=True`` forces every metric strictly below its floor, ``False`` forces
    every metric at or above it, and ``None`` lets the relation fall out of the draw so
    the boundary case ``measured == floor`` (a pass) is reachable.
    """
    floors: dict[str, float] = {}
    measurements: dict[str, float | None] = {}
    for metric in rm.METRIC_ORDER:
        pair = draw(threshold_sequences(min_size=2, max_size=2, low=0.0, high=1.0))
        if below_floor is None:
            floor, measured = pair[0], pair[1]
        else:
            lower, higher = _distinct_pair(pair)
            floor, measured = (higher, lower) if below_floor else (lower, higher)
        floors[metric] = floor
        unavailable = allow_unavailable and draw(st.booleans())
        measurements[metric] = None if unavailable else measured
    return ReplayCase(
        floors=floors,
        measurements=measurements,
        trace_count=draw(st.integers(min_value=1, max_value=4)),
    )


# ---------------------------------------------------------------------------
# The hermetic tree and the synthetic measurement seam
# ---------------------------------------------------------------------------


def committed_seed() -> str:
    """The generator's own seed, read from the generator (never restated).

    ``resolve_traces`` compares the configured seed against
    ``tests.eval.generate_traces.SEED``, so a generated tree that wants an *available*
    measurement has to record the real seed. Importing the generator reads module-level
    constants only: it generates nothing (I-0).
    """
    from tests.eval.generate_traces import SEED

    return hex(int(SEED))


def write_tree(
    root: Path,
    case: ReplayCase,
    *,
    seed: str | None = None,
    direction: str = rm.DIRECTION_AT_OR_ABOVE,
    write_traces: bool = True,
    trace_count_on_disk: int | None = None,
) -> Path:
    """Render this case's ``replay-floors.yaml`` and trace directory under ``root``."""
    floors_file = rm.floors_path(root)
    floors_file.parent.mkdir(parents=True, exist_ok=True)
    body: dict[str, object] = {
        "version": 1,
        "replay": {
            "generator": "tests/eval/generate_traces.py",
            "traces_dir": TRACES_RELPATH,
            "trace_count": case.trace_count,
            "seed": committed_seed() if seed is None else seed,
            "runs_in": ".github/workflows/ci.yml::quality-gates",
        },
        "floors": {
            metric: {
                "value": value,
                "unit": "fraction",
                "documented_in": "CLAUDE.md",
                "direction": direction,
            }
            for metric, value in case.floors.items()
        },
    }
    floors_file.write_text(
        yaml.safe_dump(body, sort_keys=True, allow_unicode=False), encoding="utf-8"
    )
    if write_traces:
        traces_dir = root / TRACES_RELPATH
        traces_dir.mkdir(parents=True, exist_ok=True)
        count = case.trace_count if trace_count_on_disk is None else trace_count_on_disk
        for index in range(count):
            (traces_dir / f"trace_{index:03d}.json").write_text(
                json.dumps({"trace_id": f"t{index:03d}"}), encoding="utf-8"
            )
    return floors_file


def measurers_for(measurements: Mapping[str, float | None]) -> dict[str, rm.Measurer]:
    """Synthetic measurers: a fixed value, or the documented unavailability signal.

    A measurer returning ``(value, detail)`` stands in for the replay; one raising the
    module's unavailability exception stands in for every way the measurement cannot be
    taken (harness unimportable, gauge with no samples). No replay is performed.
    """

    def taken(value: float) -> rm.Measurer:
        def measurer() -> tuple[float, str]:
            return value, f"synthetic measurement {value:.4f}"

        return measurer

    def untaken() -> tuple[float, str]:
        raise rm._Unavailable("synthetic: no measurement was taken (harness absent)")

    return {
        metric: untaken if value is None else taken(value)
        for metric, value in measurements.items()
    }


@contextmanager
def hermetic_root() -> Iterator[Path]:
    """A throwaway tree. Nothing generated here can bind to a committed file."""
    with tempfile.TemporaryDirectory(prefix="replay-metrics-") as tmp:
        yield Path(tmp)


def evaluate_case(case: ReplayCase, **kwargs: object) -> rm.ReplayReport:
    """Write the case into a temporary tree and take the gate's verdict over it."""
    with hermetic_root() as root:
        write_tree(root, case, **kwargs)  # type: ignore[arg-type]
        return rm.evaluate(root=root, measurers=measurers_for(case.measurements))


def reports_by_metric(report: rm.ReplayReport) -> dict[str, rm.MetricReport]:
    return {metric.metric: metric for metric in report.metrics}


def assert_total_and_consistent(report: rm.ReplayReport, case: ReplayCase) -> None:
    """Totality plus the two invariants every verdict must satisfy.

    Totality is the whole defence against a vacuous gate: a gate that silently dropped a
    metric it could not classify, or returned ``PASS`` for one, would satisfy every naming
    obligation below and gate nothing.
    """
    assert tuple(metric.metric for metric in report.metrics) == rm.METRIC_ORDER
    assert report.outcome is rm.aggregate(report.metrics)
    assert report.exit_code == rm.exit_code_for(report.outcome)
    assert (report.exit_code == rm.EXIT_PASS) is (report.outcome is Outcome.PASS)

    for metric in report.metrics:
        assert metric.outcome in set(Outcome)
        # A number is reported iff a measurement was taken; the two are never separable.
        assert (metric.measured is None) is (metric.outcome is Outcome.UNAVAILABLE)
        assert metric.detail
        assert metric.outcome is case.expected_outcome(metric.metric)


# ---------------------------------------------------------------------------
# The verdict tracks the measurement
# ---------------------------------------------------------------------------


# Feature: purpose-achievement-audit, Property 8: A measured threshold gate reflects the
# measurement
@given(case=replay_cases())
def test_the_verdict_tracks_the_measurement_over_the_generated_space(
    case: ReplayCase,
) -> None:
    """R7.6, R7.7: fail iff below floor, and the floor is the one in the file.

    The two halves are inseparable. "Exits non-zero when below floor" alone is satisfied
    by a gate that always exits non-zero; "exits zero when at or above" alone is satisfied
    by the gate that does not exist today. Only the ``iff`` says the verdict is a function
    of the measurement.
    """
    report = evaluate_case(case)
    assert_total_and_consistent(report, case)
    assert report.outcome is case.expected_gate_outcome

    for metric, entry in reports_by_metric(report).items():
        # The floor is the value written into the generated YAML - not a constant the gate
        # carries, and not the committed 0.70/0.80.
        assert entry.floor == case.floors[metric]
        expected = case.measurements[metric]
        if expected is None:
            continue
        assert entry.measured == expected
        assert entry.direction == rm.DIRECTION_AT_OR_ABOVE
        assert (entry.outcome is Outcome.FAIL) is (expected < case.floors[metric])

    # The trace count the gate reports is the count it read from the file and found on
    # disk, so a drifted corpus cannot be measured as if it were the committed one.
    assert report.traces_expected == case.trace_count
    assert report.traces_found == case.trace_count
    assert report.seed == committed_seed()


@given(
    pair=threshold_sequences(min_size=2, max_size=2, low=0.0, high=1.0),
    floor=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False).map(
        lambda value: round(value, 2)
    ),
    trace_count=st.integers(min_value=1, max_value=3),
)
def test_the_verdict_is_monotone_in_the_measurement(
    pair: tuple[float, ...],
    floor: float,
    trace_count: int,
) -> None:
    """R7.6, R7.7: raising a measured value never worsens the verdict.

    Monotonicity is what makes the gate a *floor* rather than a band. A gate that failed
    on a high value - a mis-signed comparison, or a ceiling written where a floor was
    meant - would still satisfy an ``iff`` test written against its own comparison. This
    one is written against the ordering of the measurements alone.
    """
    lower, higher = min(pair), max(pair)
    floors = {metric: floor for metric in rm.METRIC_ORDER}

    def outcome_for(value: float) -> Outcome:
        case = ReplayCase(
            floors=floors,
            measurements={metric: value for metric in rm.METRIC_ORDER},
            trace_count=trace_count,
        )
        report = evaluate_case(case)
        assert_total_and_consistent(report, case)
        return report.outcome

    worse, better = outcome_for(lower), outcome_for(higher)
    assert SEVERITY[better] <= SEVERITY[worse]
    # ... and the ordering is not vacuous: the floor decides where the flip happens.
    assert (worse is Outcome.FAIL) is (lower < floor)
    assert (better is Outcome.FAIL) is (higher < floor)


@given(case=replay_cases(allow_unavailable=False, below_floor=True))
def test_a_measured_breach_fails_naming_the_metric_the_measurement_and_the_floor(
    case: ReplayCase,
) -> None:
    """R7.6, R7.7: exit ``1`` and print all three facts the requirement names.

    R7.6/R7.7 ask for a failed conclusion; the naming obligation is what makes the failure
    actionable rather than a bare red. Asserting it against the rendered summary is the
    only way to know the numbers reach an operator's eyes and not just the model.
    """
    report = evaluate_case(case)
    assert_total_and_consistent(report, case)

    assert report.outcome is Outcome.FAIL
    assert report.exit_code == rm.EXIT_FAIL
    assert report.exit_code != rm.EXIT_PASS

    rendered = "\n".join(rm._format(report))
    for metric, entry in reports_by_metric(report).items():
        assert entry.outcome is Outcome.FAIL
        assert entry.measured is not None
        assert metric in rendered
        assert f"{entry.measured:.4f}" in rendered
        assert f"{case.floors[metric]:.4f}" in rendered


@given(case=replay_cases(allow_unavailable=False, below_floor=False))
def test_a_measurement_at_or_above_its_floor_passes(case: ReplayCase) -> None:
    """R7.6, R7.7: the converse guard, including the ``measured == floor`` boundary.

    Without this the file would be satisfied by a gate that fails on everything, which is
    not a gate either - it is a permanently red build that gets switched off.
    """
    report = evaluate_case(case)
    assert_total_and_consistent(report, case)

    assert report.outcome is Outcome.PASS
    assert report.exit_code == rm.EXIT_PASS
    assert all(entry.outcome is Outcome.PASS for entry in report.metrics)


# ---------------------------------------------------------------------------
# An untaken measurement is unavailable, never a pass (R7.3, I-7)
# ---------------------------------------------------------------------------


@given(case=replay_cases(allow_unavailable=False, below_floor=False))
def test_missing_traces_are_unavailable_and_never_a_pass(case: ReplayCase) -> None:
    """R7.3, I-7: no corpus, no measurement - even when the measurers would pass it.

    Every case here carries measurers that report *above* their floors, so a gate that
    reached them without a corpus would report a green it never measured. That is the
    exact shape of the fabricated pass I-7 forbids. All three corpus absences are covered:
    no directory, an empty directory, and a count that drifted from the committed one.
    """
    for kwargs in (
        {"write_traces": False},
        {"trace_count_on_disk": 0},
        {"trace_count_on_disk": case.trace_count + 1},
    ):
        report = evaluate_case(case, **kwargs)

        assert report.outcome is Outcome.UNAVAILABLE
        assert report.exit_code == rm.EXIT_UNAVAILABLE
        assert report.exit_code != rm.EXIT_PASS
        assert all(entry.outcome is Outcome.UNAVAILABLE for entry in report.metrics)
        assert all(entry.measured is None for entry in report.metrics)
        # The floor is still reported: the operator learns which floor went unmeasured.
        for metric, entry in reports_by_metric(report).items():
            assert entry.floor == case.floors[metric]
        assert "UNAVAILABLE" in "\n".join(rm._format(report))


@given(case=replay_cases(allow_unavailable=False, below_floor=False))
def test_a_missing_harness_is_unavailable_and_never_a_pass(case: ReplayCase) -> None:
    """R7.3, I-7: a measurer that cannot measure yields ``unavailable``, not ``0.0``.

    Two distinct absences, because the gate distinguishes them: a measurer that raises
    (harness unimportable, or a cache gauge with no sample because Ollama is offline) and
    a metric with no measurer registered at all. Reporting ``0.0`` for either would turn
    an absence into a breach, which is a different lie from the same root.
    """
    with hermetic_root() as root:
        write_tree(root, case)
        raising = rm.evaluate(
            root=root,
            measurers=measurers_for(dict.fromkeys(rm.METRIC_ORDER, None)),
        )
        unregistered = rm.evaluate(root=root, measurers={})

    for report in (raising, unregistered):
        assert report.outcome is Outcome.UNAVAILABLE
        assert report.exit_code == rm.EXIT_UNAVAILABLE
        assert report.exit_code != rm.EXIT_PASS
        assert all(entry.outcome is Outcome.UNAVAILABLE for entry in report.metrics)
        assert all(entry.measured is None for entry in report.metrics)
        assert all(entry.detail for entry in report.metrics)


@given(case=replay_cases(allow_unavailable=False, below_floor=True))
def test_a_measured_breach_outranks_an_unrelated_absence(case: ReplayCase) -> None:
    """R7.6, R7.7: one absent metric must not mask the other's regression.

    The tier-routing measurement comes from the replay and the KV-cache measurement from a
    gauge that is empty whenever Ollama is offline. If an absence swallowed the verdict,
    an offline model server would silently disable the routing floor - the failure mode
    this ordering exists to prevent.
    """
    for present, absent in ((rm.TIER_ROUTING_METRIC, rm.KV_CACHE_METRIC),
                            (rm.KV_CACHE_METRIC, rm.TIER_ROUTING_METRIC)):
        partial = ReplayCase(
            floors=case.floors,
            measurements={present: case.measurements[present], absent: None},
            trace_count=case.trace_count,
        )
        report = evaluate_case(partial)
        assert_total_and_consistent(report, partial)

        assert report.outcome is Outcome.FAIL
        assert report.exit_code == rm.EXIT_FAIL
        assert reports_by_metric(report)[present].outcome is Outcome.FAIL
        assert reports_by_metric(report)[absent].outcome is Outcome.UNAVAILABLE


@given(
    case=replay_cases(allow_unavailable=False, below_floor=False),
    direction=st.sampled_from(("at-or-below", "below", "", "AT-OR-ABOVE")),
)
def test_a_configuration_the_gate_cannot_read_is_unavailable_and_never_a_pass(
    case: ReplayCase,
    direction: str,
) -> None:
    """R7.3: an unreadable floor is not a floor of zero.

    Three ways the committed configuration can fail to yield a floor - absent file, a
    floor direction this gate does not evaluate, and a seed that drifted from the
    generator's - each of which a gate could paper over by defaulting. Defaulting to zero
    would make every measurement pass; defaulting to one would make every measurement
    fail. Both are fabrications, so both are refused.
    """
    with hermetic_root() as root:
        absent_config = rm.evaluate(root=root, measurers=measurers_for(case.measurements))

    unsupported = evaluate_case(case, direction=direction)
    drifted_seed = evaluate_case(case, seed="0x1")

    for report in (absent_config, unsupported, drifted_seed):
        assert report.outcome is Outcome.UNAVAILABLE
        assert report.exit_code == rm.EXIT_UNAVAILABLE
        assert report.exit_code != rm.EXIT_PASS
        assert all(entry.outcome is Outcome.UNAVAILABLE for entry in report.metrics)
        assert all(entry.detail for entry in report.metrics)

    # An unsupported direction is reported per metric, so the operator learns which floor
    # the gate declined to evaluate rather than only that something was unreadable.
    assert any(direction in entry.detail for entry in unsupported.metrics)


@given(case=replay_cases(allow_unavailable=False, below_floor=False))
def test_a_floor_the_configuration_omits_is_unavailable_and_masks_nothing(
    case: ReplayCase,
) -> None:
    """R7.3: an unrecorded floor is that metric's absence, not the gate's silence."""
    for omitted in rm.METRIC_ORDER:
        remaining = {
            metric: value for metric, value in case.floors.items() if metric != omitted
        }
        partial = ReplayCase(
            floors=remaining, measurements=case.measurements, trace_count=case.trace_count
        )
        report = evaluate_case(partial)
        assert_total_and_consistent(report, partial)

        assert report.outcome is Outcome.UNAVAILABLE
        assert report.exit_code == rm.EXIT_UNAVAILABLE
        entries = reports_by_metric(report)
        assert entries[omitted].outcome is Outcome.UNAVAILABLE
        assert entries[omitted].floor is None
        assert omitted in entries[omitted].detail
        # The metric that *is* recorded still gets measured against its own floor.
        for metric in remaining:
            assert entries[metric].outcome is Outcome.PASS
            assert entries[metric].floor == remaining[metric]


# ---------------------------------------------------------------------------
# The floors are read from the committed file, not carried by the gate
# ---------------------------------------------------------------------------


@given(case=replay_cases(allow_unavailable=False, below_floor=False))
def test_the_reported_floor_is_the_file_and_the_empty_metric_set_is_unavailable(
    case: ReplayCase,
) -> None:
    """R7.6, R7.7: the floor follows the file, so the committed value is pinnable.

    This is what lets ``doc-number-pins.yaml`` pin the ``CLAUDE.md`` prose and
    ``ratchets.json`` ratchet the value: had the gate carried ``0.70`` and ``0.80``
    internally, both files would be decorative and a floor could be weakened in the YAML
    with the gate none the wiser. Raising a generated floor above the measurement flips
    the verdict, which is what proves the comparison reads the file.
    """
    report = evaluate_case(case)
    assert report.outcome is Outcome.PASS
    assert all(entry.floor == case.floors[entry.metric] for entry in report.metrics)

    # Same measurements, every floor raised just past them: the file alone decides.
    raised_floors: dict[str, float] = {}
    for metric in rm.METRIC_ORDER:
        measured = case.measurements[metric]
        assert measured is not None
        raised_floors[metric] = round(measured + 0.01, 2)
    raised = ReplayCase(
        floors=raised_floors,
        measurements=case.measurements,
        trace_count=case.trace_count,
    )
    raised_report = evaluate_case(raised)
    assert raised_report.outcome is Outcome.FAIL
    assert raised_report.exit_code == rm.EXIT_FAIL
    for entry in raised_report.metrics:
        assert entry.floor == raised.floors[entry.metric]

    # An empty metric set is unavailable, never a pass: the fold has no vacuous identity.
    assert rm.aggregate(()) is Outcome.UNAVAILABLE
    assert rm.exit_code_for(rm.aggregate(())) == rm.EXIT_UNAVAILABLE


def test_the_committed_floors_are_the_two_numbers_the_audit_found_ungated() -> None:
    """R7.6, R7.7 against the committed tree: a static read, no replay.

    The audit's finding is that ``CLAUDE.md``'s KV-cache ``0.70`` and tier-routing ``0.80``
    had no assertion anywhere. They are now in a file a gate reads; this confirms the gate
    reads *those* values, with the direction it knows how to evaluate. Nothing here
    measures anything - replaying the corpus is a ``ci.yml::quality-gates`` workload (I-0).
    """
    config = rm.load_config()
    for metric, expected in COMMITTED_FLOORS.items():
        floor, direction = rm.read_floor(config, metric)
        assert floor == expected
        assert direction == rm.DIRECTION_AT_OR_ABOVE
        # A zero floor would be the coverage-file failure mode (R7.2) in a new file.
        assert floor > 0.0

    replay = config["replay"]
    assert replay["traces_dir"] == TRACES_RELPATH
    assert int(str(replay["seed"]), 16) == int(committed_seed(), 16)
    assert replay["runs_in"] == ".github/workflows/ci.yml::quality-gates"
