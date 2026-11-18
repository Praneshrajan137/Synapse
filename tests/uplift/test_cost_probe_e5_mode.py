"""The cost probe's E5 mode: its arithmetic and its record, with a fake arm and no twin.

Feature: decision-quality-proof, finding 116. ``python -m uplift.cost_probe e5`` times E5's own
path in CI (``.github/workflows/uplift-cost-probe.yml``), and these tests pin what it reports.
The arm is a run-scoped fake, the closed loop is a fake injected through ``e5_cost_report``'s
``run_loop`` seam, and ``uplift.cost_probe``'s clock is replaced, so every duration is exact and
every number is compared with ``==``.

What would make each test wrong:

* the arithmetic test, if a replicate's wall or decision seconds, a dispatch bucket, the summed
  tally or the projection came from anything but what the replicates recorded;
* the two failure tests, if a failed replicate were dropped, its tally or wall summed with the
  completed ones', or a projection stated over no completed replicate;
* the refusal tests, if a reading began for an arm with no tally or an empty or repeated seed
  list, or the command accepted fewer than one replicate;
* the two command tests, if the stand-in were timed or its own reason lost, or the command
  timed anything but E5's scenario, loop and replicate seeds.

Not ``slow``: no twin, no consensus network and no ``run_consensus``.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING, Final

import pytest

from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams
from orchestrator.consensus.tier_router import TierRouter
from uplift import cost_probe, e5_suite, harness
from uplift.consensus_arm import observation_to_decision_request
from uplift.e5_suite import E5_LOOP, E5_SCENARIO_NAME, E5_SCENARIO_SEED
from uplift.harness import LoopConfig, replicate_seed
from uplift.interfaces import (
    DecisionCounts,
    Observation,
    PolicyAction,
    RunScoped,
    Scenario,
    ScenarioRun,
)
from uplift.policies import UnavailableConsensusArm

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from uplift.interfaces import DecisionPolicy

#: Six one-hour steps, reorders only: E5's cadence and levers over a quarter of its horizon.
_LOOP: Final[LoopConfig] = LoopConfig(duration_hours=6.0, step_hours=1.0, levers="reorders_only")

#: What decision ``k`` of a run costs the fake arm, in seconds, at ``k % 6``. Over a run the mean
#: (1.0), median (0.75) and max (3.0) all differ, and every sum is exact in binary floating point.
_DECIDE_SECONDS: Final[tuple[float, ...]] = (0.25, 0.25, 0.5, 1.0, 1.0, 3.0)

#: The bucket decision ``k`` of a run lands in, at ``k % 6``: 3, 2, 1 and 0 a run, so no two of
#: R7.20's four buckets hold one count, and a report that swapped two would show it.
_BUCKETS: Final[tuple[str, ...]] = (
    "dispatched",
    "dispatched",
    "dispatched",
    "withheld_for_confidence",
    "withheld_for_confidence",
    "guardrail_blocked",
)

#: Seconds the fake loop spends after each decision: the twin's advance, as a number.
_STEP_SECONDS: Final[float] = 0.5

#: The replicates' seeds, each with the seconds the fake loop spends before its first step (what
#: building a twin costs here). A completed replicate's wall is that plus 6.0 s deciding and 3.0 s
#: stepping: 9.0, 9.5 and 11.5 s, whose mean, 10.0, equals none of them.
_SETUP_SECONDS: Final[dict[int, float]] = {11: 0.0, 12: 0.5, 13: 2.5}
_SEEDS: Final[tuple[int, ...]] = tuple(_SETUP_SECONDS)

#: One completed run's ``decision_seconds`` and ``dispatch``, read off the two tables above.
_RUN_SECONDS: Final[dict[str, float | int]] = {
    "count": 6,
    "total_seconds": 6.0,
    "mean_seconds": 1.0,
    "median_seconds": 0.75,
    "max_seconds": 3.0,
}
_RUN_DISPATCH: Final[dict[str, int]] = {
    "dispatched": 3,
    "withheld_for_confidence": 2,
    "guardrail_blocked": 1,
    "untranslatable": 0,
    "total": 6,
}

_SCENARIO_NAME: Final[str] = "e5-cost-probe-under-test"

#: What the projection says it does not cover.
_EXCLUDES: Final[tuple[str, ...]] = ("pathway probe", "B-prime reproduction", "arms E and E'")


class _Clock:
    """``uplift.cost_probe``'s ``time``, reduced to a ``perf_counter`` that only the fakes move."""

    def __init__(self) -> None:
        self._now = 0.0

    def perf_counter(self) -> float:
        """The current reading; it moves only through :meth:`advance`."""
        return self._now

    def advance(self, seconds: float) -> None:
        """Move the clock forward by ``seconds``."""
        self._now += seconds


class _TallyingArm:
    """A run-scoped arm that decides nothing, costs ``_DECIDE_SECONDS`` and tallies ``_BUCKETS``.

    ``fail_at`` maps a seed to the decision that raises there, after its cost is spent and
    before it is tallied. A second ``begin_run`` while a run is open, or an ``end_run`` with none
    open, is refused, so a reading that mispaired them would fail rather than read a stale tally.
    """

    name = "fake-consensus"

    def __init__(self, clock: _Clock, fail_at: Mapping[int, int] | None = None) -> None:
        self._clock = clock
        self._fail_at = dict(fail_at or {})
        self._seed: int | None = None
        self._decided = 0
        self._tally: Counter[str] = Counter()

    def begin_run(self, seed: int) -> None:
        """Open a run at ``seed`` with an empty tally."""
        if self._seed is not None:
            raise RuntimeError(f"the run at seed {self._seed} is still open")
        self._seed = seed
        self._decided = 0
        self._tally = Counter()

    def decide(self, obs: Observation) -> PolicyAction:
        """Spend this decision's seconds, then fail if told to, else tally it and do nothing."""
        seed = self._open_seed()
        step = self._decided
        self._decided += 1
        self._clock.advance(_DECIDE_SECONDS[step % len(_DECIDE_SECONDS)])
        if self._fail_at.get(seed) == step:
            raise RuntimeError(f"the fake arm's decision {step} of seed {seed} failed")
        self._tally[_BUCKETS[step % len(_BUCKETS)]] += 1
        return PolicyAction()

    def end_run(self) -> DecisionCounts:
        """Close the open run and return its tally."""
        self._open_seed()
        self._seed = None
        return DecisionCounts(
            dispatched=self._tally["dispatched"],
            withheld_for_confidence=self._tally["withheld_for_confidence"],
            guardrail_blocked=self._tally["guardrail_blocked"],
            untranslatable=self._tally["untranslatable"],
        )

    def _open_seed(self) -> int:
        if self._seed is None:
            raise RuntimeError("no run is open")
        return self._seed


class _FakeLoop:
    """``run_closed_loop``'s contract with no twin, recording each run it is asked for.

    As the harness does it: ``begin_run(seed)``, one ``decide`` per step of the loop, then
    ``end_run()``, whose tally a completed run carries. A ``decide`` that raises fails the run
    with ``"<type>: <message>"`` and no tally, its run still closed. A completed run carries no
    KPIs: there is no twin to read them from, and the report reads none.
    """

    def __init__(self, clock: _Clock, setup_seconds: Mapping[int, float]) -> None:
        self._clock = clock
        self._setup = dict(setup_seconds)
        self.calls: list[tuple[str, int, str, LoopConfig]] = []

    def __call__(
        self,
        scenario: Scenario,
        policy: DecisionPolicy,
        seed: int,
        arm_name: str,
        loop: LoopConfig,
    ) -> ScenarioRun:
        self.calls.append((scenario.name, seed, arm_name, loop))
        assert isinstance(policy, RunScoped), "a reading must hand the loop a run-scoped arm"
        self._clock.advance(self._setup[seed])
        policy.begin_run(seed)
        try:
            for step in range(loop.n_steps):
                policy.decide(_observation(step, loop))
                self._clock.advance(_STEP_SECONDS)
        except RuntimeError as exc:
            policy.end_run()
            return ScenarioRun(
                arm=arm_name,
                seed=seed,
                kpis=None,
                failed=True,
                error=f"{type(exc).__name__}: {exc}",
            )
        return ScenarioRun(
            arm=arm_name,
            seed=seed,
            kpis=None,
            failed=False,
            error=None,
            decision_counts=policy.end_run(),
        )


def _observation(step: int, loop: LoopConfig) -> Observation:
    """What a twin would show at ``step``: one stocked SKU and no shock, as every E5 state has."""
    return Observation(
        inventory={"sku-a": 10 + step},
        sim_time=step * loop.step_hours * 60.0,
        delivery_count=step,
        spoilage_count=0,
        stockout_count=0,
        unit_costs={"sku-a": 2.5},
    )


def _scenario() -> Scenario:
    """A named scenario and nothing more: the fake loop builds no twin from it."""
    return Scenario(name=_SCENARIO_NAME, seed=E5_SCENARIO_SEED, shock=ShockParams())


def _unshocked_tier() -> str:
    """The tier the probe's router gives an unshocked request: every decision's tier here."""
    request = observation_to_decision_request(_observation(0, _LOOP))
    return str(TierRouter().classify(request).tier)


def _use_clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    """Install a :class:`_Clock` as ``uplift.cost_probe``'s ``time``, and return it."""
    clock = _Clock()
    monkeypatch.setattr(cost_probe, "time", clock)
    return clock


def _canonical(payload: object) -> str:
    """The repository's one canonical JSON form."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _completed_row(index: int, seed: int, wall: float) -> dict[str, object]:
    """A completed replicate's row: six decisions in one tier, and the fake arm's tally."""
    return {
        "index": index,
        "seed": seed,
        "failed": False,
        "error": None,
        "decisions": 6,
        "wall_seconds": wall,
        "decision_seconds": _RUN_SECONDS,
        "by_tier": {_unshocked_tier(): _RUN_SECONDS},
        "dispatch": _RUN_DISPATCH,
    }


def _failed_row(
    index: int, seed: int, wall: float, step: int, seconds: Mapping[str, float | int]
) -> dict[str, object]:
    """A replicate whose decision ``step`` raised: kept, with its error and its timed decisions."""
    return {
        "index": index,
        "seed": seed,
        "failed": True,
        "error": f"RuntimeError: the fake arm's decision {step} of seed {seed} failed",
        "decisions": step + 1,
        "wall_seconds": wall,
        "decision_seconds": seconds,
        "by_tier": {_unshocked_tier(): seconds},
        "dispatch": None,
    }


def _projection(mean_wall: float) -> dict[str, object]:
    """The projection to ``MIN_SCENARIOS`` replicates from the completed replicates' mean wall."""
    return {
        "replicates_per_arm": MIN_SCENARIOS,
        "decisions": 6 * MIN_SCENARIOS,
        "mean_wall_seconds_per_replicate": mean_wall,
        "projected_consensus_wall_seconds": mean_wall * MIN_SCENARIOS,
        "projected_consensus_wall_hours": mean_wall * MIN_SCENARIOS / 3600.0,
        "excludes": list(_EXCLUDES),
    }


def _report(
    *,
    status: str,
    replicates: list[dict[str, object]],
    completed: int,
    decision_seconds: Mapping[str, float | int],
    dispatch: Mapping[str, int],
    projection: dict[str, object] | None,
) -> dict[str, object]:
    """The whole report over ``_LOOP`` and :func:`_scenario`, every decision in one tier."""
    return {
        "mode": "e5",
        "status": status,
        "scenario": _SCENARIO_NAME,
        "hours": 6.0,
        "step_hours": 1.0,
        "loop_levers": "reorders_only",
        "decisions_per_replicate": 6,
        "replicates_measured": len(replicates),
        "replicates_completed": completed,
        "replicates": replicates,
        "decision_seconds": decision_seconds,
        "by_tier": {_unshocked_tier(): decision_seconds},
        "dispatch": dispatch,
        "projection_at_min_scenarios": projection,
    }


# ---------------------------------------------------------------------------
# e5_cost_report
# ---------------------------------------------------------------------------
def test_the_e5_reading_times_each_decision_and_reports_each_replicates_own_tally(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _use_clock(monkeypatch)
    loop = _FakeLoop(clock, _SETUP_SECONDS)

    report = cost_probe.e5_cost_report(
        _TallyingArm(clock), _scenario(), _SEEDS, _LOOP, run_loop=loop
    )

    assert report == _report(
        status="measured",
        replicates=[
            _completed_row(0, 11, 9.0),
            _completed_row(1, 12, 9.5),
            _completed_row(2, 13, 11.5),
        ],
        completed=3,
        decision_seconds={
            "count": 18,
            "total_seconds": 18.0,
            "mean_seconds": 1.0,
            "median_seconds": 0.75,
            "max_seconds": 3.0,
        },
        dispatch={
            "dispatched": 9,
            "withheld_for_confidence": 6,
            "guardrail_blocked": 3,
            "untranslatable": 0,
            "total": 18,
        },
        projection=_projection(10.0),
    )
    assert json.loads(_canonical(report)) == report, "the report is not plain JSON"
    assert loop.calls == [(_SCENARIO_NAME, seed, _TallyingArm.name, _LOOP) for seed in _SEEDS]


def test_a_failed_replicate_is_kept_with_its_error_but_its_tally_and_wall_are_not_summed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Seed 12 fails at its fourth decision, 4.0 s in: 0.5 s setup, three steps, one decision."""
    clock = _use_clock(monkeypatch)
    loop = _FakeLoop(clock, _SETUP_SECONDS)

    report = cost_probe.e5_cost_report(
        _TallyingArm(clock, fail_at={12: 3}), _scenario(), _SEEDS, _LOOP, run_loop=loop
    )

    partial: dict[str, float | int] = {
        "count": 4,
        "total_seconds": 2.0,
        "mean_seconds": 0.5,
        "median_seconds": 0.375,
        "max_seconds": 1.0,
    }
    assert report == _report(
        status="failed",
        replicates=[
            _completed_row(0, 11, 9.0),
            _failed_row(1, 12, 4.0, 3, partial),
            _completed_row(2, 13, 11.5),
        ],
        completed=2,
        # Every decision timed is reported, the failed run's four included...
        decision_seconds={
            "count": 16,
            "total_seconds": 14.0,
            "mean_seconds": 0.875,
            "median_seconds": 0.5,
            "max_seconds": 3.0,
        },
        # ...but only the completed runs' tallies are summed, and only their walls projected.
        dispatch={
            "dispatched": 6,
            "withheld_for_confidence": 4,
            "guardrail_blocked": 2,
            "untranslatable": 0,
            "total": 12,
        },
        projection=_projection(10.25),
    )


def test_with_no_replicate_completed_there_is_no_projection_and_no_tally_is_summed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = _use_clock(monkeypatch)
    loop = _FakeLoop(clock, _SETUP_SECONDS)

    report = cost_probe.e5_cost_report(
        _TallyingArm(clock, fail_at={11: 0}), _scenario(), [11], _LOOP, run_loop=loop
    )

    one: dict[str, float | int] = {
        "count": 1,
        "total_seconds": 0.25,
        "mean_seconds": 0.25,
        "median_seconds": 0.25,
        "max_seconds": 0.25,
    }
    assert report == _report(
        status="failed",
        replicates=[_failed_row(0, 11, 0.25, 0, one)],
        completed=0,
        decision_seconds=one,
        dispatch=dict.fromkeys(_RUN_DISPATCH, 0),
        projection=None,
    )


def test_no_loop_starts_for_an_arm_with_no_tally_or_an_empty_or_repeated_seed_list() -> None:
    clock = _Clock()
    loop = _FakeLoop(clock, _SETUP_SECONDS)
    arm = _TallyingArm(clock)

    with pytest.raises(ValueError, match="at least one seed"):
        cost_probe.e5_cost_report(arm, _scenario(), [], _LOOP, run_loop=loop)
    with pytest.raises(ValueError, match="name one seed twice"):
        cost_probe.e5_cost_report(arm, _scenario(), [11, 11], _LOOP, run_loop=loop)
    # The stand-in keeps no tally, so E5's four buckets could not be read from it.
    with pytest.raises(TypeError, match="not RunScoped"):
        cost_probe.e5_cost_report(
            UnavailableConsensusArm("no network here"), _scenario(), [11], _LOOP, run_loop=loop
        )

    assert loop.calls == []


# ---------------------------------------------------------------------------
# python -m uplift.cost_probe e5
# ---------------------------------------------------------------------------
def test_the_e5_command_records_the_stand_ins_own_reason_exits_2_and_times_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stand_in = UnavailableConsensusArm("no network here")
    loop = _FakeLoop(_Clock(), _SETUP_SECONDS)
    monkeypatch.setattr(cost_probe, "_quiet_logging", lambda: None)
    monkeypatch.setattr(e5_suite, "e5_consensus_policy", lambda: stand_in)
    monkeypatch.setattr(harness, "run_closed_loop", loop)
    output = tmp_path / "cost-probe-e5.json"

    code = cost_probe.main(["e5", "--replicates", "2", "--output", str(output)])

    assert code == 2
    assert loop.calls == []
    record = {"mode": "e5", "status": "unavailable", "reason": "no network here"}
    assert output.read_text(encoding="utf-8") == _canonical(record) + "\n"


def test_the_e5_command_times_e5s_own_scenario_loop_and_seeds_into_canonical_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = _use_clock(monkeypatch)
    arm = _TallyingArm(clock)
    seeds = [replicate_seed(E5_SCENARIO_SEED, index) for index in range(3)]
    loop = _FakeLoop(clock, dict.fromkeys(seeds, 0.0))
    monkeypatch.setattr(cost_probe, "_quiet_logging", lambda: None)
    monkeypatch.setattr(e5_suite, "e5_consensus_policy", lambda: arm)
    monkeypatch.setattr(harness, "run_closed_loop", loop)
    output = tmp_path / "artifacts" / "cost-probe-e5.json"

    code = cost_probe.main(["e5", "--replicates", "3", "--output", str(output)])

    assert code == 0
    assert loop.calls == [(E5_SCENARIO_NAME, seed, arm.name, E5_LOOP) for seed in seeds]
    text = output.read_text(encoding="utf-8")
    report = json.loads(text)
    assert text == _canonical(report) + "\n"
    assert (report["mode"], report["status"]) == ("e5", "measured")
    assert report["scenario"] == E5_SCENARIO_NAME
    assert [row["seed"] for row in report["replicates"]] == seeds
    assert report["decisions_per_replicate"] == E5_LOOP.n_steps
    assert report["dispatch"]["total"] == len(seeds) * E5_LOOP.n_steps


def test_the_e5_command_refuses_fewer_than_one_replicate(tmp_path: Path) -> None:
    output = tmp_path / "cost-probe-e5.json"

    with pytest.raises(SystemExit) as refused:
        cost_probe.main(["e5", "--replicates", "0", "--output", str(output)])

    assert refused.value.code == 2
    assert not output.exists()
