"""What one consensus decision costs, measured by tier, so E5 is sized from a reading (finding 70).

``uplift.yml::uplift-proof`` had never run when this was written, and its cost was only ever an
extrapolation from a test docstring (about 20 s per shocked Tier-4 decision, which at 1000
replicates x 3 shocked scenarios x 24 hourly decisions is roughly 400 core-hours).
``.kiro/steering/execution-routing.md`` forbids sizing a workload against an unmeasured cost, so
this module measures it: a small number of replicates of each adversarial scenario, driven
through the REAL consensus arm on the harness's own closed loop
(:func:`uplift.harness.run_closed_loop`), timing every ``decide`` call and recording the tier
:class:`~orchestrator.consensus.tier_router.TierRouter` assigns to the request that call carries.
A transparent baseline arm is timed on the same seeds as the reference for what a non-consensus
arm-replicate costs.

**It measures and does not judge.** No verdict, no gate, no claim about decision quality: the
numbers it reports are seconds. A consensus arm that cannot be assembled is reported
``unavailable`` and the command exits 2 -- it is never timed as if it had run (I-7) -- and a
replicate whose closed loop failed is reported failed with its error, not dropped.

**The E5 mode (finding 116).** ``python -m uplift.cost_probe e5 --replicates N --output PATH``
measures E5's own path instead of the adversarial suite: :func:`uplift.e5_suite.e5_scenario` (the
primary world cell, unshocked), the arm :func:`uplift.e5_suite.e5_consensus_policy` assembles
(reorders only) and :data:`uplift.e5_suite.E5_LOOP` (24 hourly decisions), at E5's first ``N``
replicate seeds. It records each decision's wall seconds, the arm's own dispatch tally per
replicate (R7.20's four buckets) and the consensus arm's serial share of E5 at ``MIN_SCENARIOS``
replicates (:func:`e5_cost_report`). A command line whose first argument is not ``e5`` is the
adversarial mode, parsed and reported exactly as before.

CI only (``.github/workflows/uplift-cost-probe.yml``): the real arm stands up the eight agents and
the twin's A2A handler, and a Tier-4 decision runs the twin's Monte Carlo at INV-TW-002's floor.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import math
import statistics
import sys
import time
from typing import TYPE_CHECKING, Final

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from orchestrator.consensus.tier_router import TierRouter
    from uplift.harness import LoopConfig
    from uplift.interfaces import (
        DecisionCounts,
        DecisionPolicy,
        Observation,
        PolicyAction,
        Scenario,
        ScenarioRun,
    )

    #: ``uplift.harness.run_closed_loop``'s five positional arguments: the E5 mode's loop seam.
    LoopRunner = Callable[[Scenario, DecisionPolicy, int, str, LoopConfig], ScenarioRun]

#: A GitHub-hosted job is terminated at six hours; sizing leaves one hour of margin per job.
JOB_BUDGET_SECONDS: Final[float] = 5.0 * 3600.0

#: Standard public-repository ``ubuntu-latest`` runners carry four vCPUs (GitHub's runner
#: reference, read 2026-09-30); the projection reports both serial and four-worker figures.
RUNNER_VCPUS: Final[int] = 4

#: The first command-line argument that selects the E5 mode (:func:`main_e5`).
E5_MODE: Final[str] = "e5"


@dataclasses.dataclass(frozen=True)
class DecisionRecord:
    """One timed ``decide`` call: when, which tier the router assigned, how long, whether done."""

    sim_time_min: float
    tier: str
    seconds: float
    completed: bool


class _TimedArm:
    """Wraps a :class:`DecisionPolicy`, timing each ``decide`` and recording the routed tier."""

    def __init__(self, inner: DecisionPolicy, router: TierRouter) -> None:
        self.name = inner.name
        self._inner = inner
        self._router = router
        self.records: list[DecisionRecord] = []

    def decide(self, obs: Observation) -> PolicyAction:
        from uplift.consensus_arm import observation_to_decision_request

        tier = str(self._router.classify(observation_to_decision_request(obs)).tier)
        started = time.perf_counter()
        completed = False
        try:
            action = self._inner.decide(obs)
            completed = True
            return action
        finally:
            self.records.append(
                DecisionRecord(
                    sim_time_min=float(obs.sim_time),
                    tier=tier,
                    seconds=time.perf_counter() - started,
                    completed=completed,
                )
            )


class _RunScopedTimedArm(_TimedArm):
    """A :class:`_TimedArm` over a run-scoped arm, forwarding ``begin_run`` and ``end_run``.

    So :func:`uplift.harness.run_closed_loop` opens and closes the arm's own tally exactly as
    E5's harness does, and a completed run carries it as ``decision_counts``. The adversarial
    mode keeps the plain :class:`_TimedArm`, unchanged.

    Raises:
        TypeError: ``inner`` is not :class:`~uplift.interfaces.RunScoped`, so it keeps no tally
            to read the dispatch buckets from.
    """

    def __init__(self, inner: DecisionPolicy, router: TierRouter) -> None:
        from uplift.interfaces import RunScoped

        if not isinstance(inner, RunScoped):
            raise TypeError(
                f"{type(inner).__name__} is not RunScoped: it keeps no dispatch tally, so E5's "
                "four buckets cannot be read from it"
            )
        super().__init__(inner, router)
        self._scoped: RunScoped = inner

    def begin_run(self, seed: int) -> None:
        """Open the wrapped arm's run at twin ``seed``."""
        self._scoped.begin_run(seed)

    def end_run(self) -> DecisionCounts:
        """Close the wrapped arm's run and return its tally."""
        return self._scoped.end_run()


def _summary(seconds: Sequence[float]) -> dict[str, float | int]:
    """Count, total, mean, median and max of a sample of durations (empty -> count 0 only)."""
    if not seconds:
        return {"count": 0}
    return {
        "count": len(seconds),
        "total_seconds": math.fsum(seconds),
        "mean_seconds": statistics.fmean(seconds),
        "median_seconds": statistics.median(seconds),
        "max_seconds": max(seconds),
    }


def _by_tier(records: Sequence[DecisionRecord]) -> dict[str, dict[str, float | int]]:
    tiers = sorted({record.tier for record in records})
    return {
        tier: _summary([record.seconds for record in records if record.tier == tier])
        for tier in tiers
    }


def _projection(
    consensus_seconds_by_scenario: dict[str, float],
    baseline_seconds_by_scenario: dict[str, float],
    *,
    replicates: int,
) -> dict[str, float | int]:
    """E5's cost at ``replicates`` per arm, from the measured mean seconds per replicate.

    Serial seconds are the sum over scenarios of (consensus + one baseline arm) x replicates; the
    job count is what keeps every job inside :data:`JOB_BUDGET_SECONDS` when each job runs
    :data:`RUNNER_VCPUS` replicates concurrently. A projection, labelled as one: it assumes the
    per-replicate cost measured here is the per-replicate cost at scale.
    """
    serial = math.fsum(
        (consensus_seconds_by_scenario[name] + baseline_seconds_by_scenario[name]) * replicates
        for name in consensus_seconds_by_scenario
    )
    parallel_seconds = serial / RUNNER_VCPUS
    return {
        "replicates_per_arm": replicates,
        "projected_serial_seconds": serial,
        "projected_core_hours": serial / 3600.0,
        "projected_jobs_at_4_workers": max(1, math.ceil(parallel_seconds / JOB_BUDGET_SECONDS)),
        "job_budget_seconds": JOB_BUDGET_SECONDS,
    }


def _dispatch(tallies: Sequence[DecisionCounts]) -> dict[str, int]:
    """R7.20's four buckets summed over ``tallies``, and the decisions they count."""
    return {
        "dispatched": sum(tally.dispatched for tally in tallies),
        "withheld_for_confidence": sum(tally.withheld_for_confidence for tally in tallies),
        "guardrail_blocked": sum(tally.guardrail_blocked for tally in tallies),
        "untranslatable": sum(tally.untranslatable for tally in tallies),
        "total": sum(tally.total for tally in tallies),
    }


def _e5_projection(
    completed_walls: Sequence[float], *, decisions_per_replicate: int, replicates: int
) -> dict[str, object] | None:
    """The consensus arm's share of E5 at ``replicates``, from its completed replicates' walls.

    Serial, because E5 runs this arm in one process: the harness falls back to sequential runs
    for an arm it cannot pickle, and the assembled arm holds the local audit-session factory of
    ``uplift.consensus_arm._in_process_session_factory`` (read, not measured). A projection,
    labelled as one: it assumes the mean measured here is the mean at scale, and ``excludes``
    names the E5 work it does not cover. ``None`` when no replicate completed: a mean over
    nothing is no mean.
    """
    if not completed_walls:
        return None
    mean = statistics.fmean(completed_walls)
    serial = mean * replicates
    return {
        "replicates_per_arm": replicates,
        "decisions": decisions_per_replicate * replicates,
        "mean_wall_seconds_per_replicate": mean,
        "projected_consensus_wall_seconds": serial,
        "projected_consensus_wall_hours": serial / 3600.0,
        "excludes": ["pathway probe", "B-prime reproduction", "arms E and E'"],
    }


def e5_cost_report(
    arm: DecisionPolicy,
    scenario: Scenario,
    seeds: Sequence[int],
    loop: LoopConfig,
    *,
    run_loop: LoopRunner,
) -> dict[str, object]:
    """Time ``arm`` per decision over one closed loop per seed, with its tally per replicate.

    Seed ``seeds[i]`` is replicate ``i``: ``run_loop(scenario, timed, seed, arm.name, loop)``,
    where ``timed`` is ``arm`` inside a :class:`_RunScopedTimedArm`, so the loop opens and closes
    the arm's own tally and a completed run carries it. ``run_loop`` is REQUIRED: production
    passes :func:`uplift.harness.run_closed_loop`, and a fast test injects one that builds no
    twin.

    The report keeps every replicate, failed ones included, with its error. A failed run carries
    no tally (``ScenarioRun``'s rule), so the summed ``dispatch`` and the projection read the
    completed replicates only, and any failure makes the status ``failed``.

    Raises:
        TypeError: ``arm`` keeps no tally (it is not ``RunScoped``); refused before any loop.
        ValueError: ``seeds`` is empty or names one seed twice; refused before any loop.
    """
    from digital_twin.simulation.monte_carlo import MIN_SCENARIOS
    from orchestrator.consensus.tier_router import TierRouter

    ordered = list(seeds)
    if not ordered:
        raise ValueError("an E5 cost reading needs at least one seed")
    if len(set(ordered)) != len(ordered):
        raise ValueError(
            f"seeds {ordered} name one seed twice, so one realisation would be timed twice"
        )

    replicates: list[dict[str, object]] = []
    records: list[DecisionRecord] = []
    tallies: list[DecisionCounts] = []
    completed_walls: list[float] = []
    for index, seed in enumerate(ordered):
        timed = _RunScopedTimedArm(arm, TierRouter())
        started = time.perf_counter()
        run = run_loop(scenario, timed, seed, timed.name, loop)
        wall = time.perf_counter() - started
        records.extend(timed.records)
        if not run.failed:
            completed_walls.append(wall)
        if run.decision_counts is not None:
            tallies.append(run.decision_counts)
        replicates.append(
            {
                "index": index,
                "seed": seed,
                "failed": run.failed,
                "error": run.error,
                "decisions": len(timed.records),
                "wall_seconds": wall,
                "decision_seconds": _summary([record.seconds for record in timed.records]),
                "by_tier": _by_tier(timed.records),
                "dispatch": (
                    None if run.decision_counts is None else _dispatch([run.decision_counts])
                ),
            }
        )
    return {
        "mode": E5_MODE,
        "status": "measured" if len(completed_walls) == len(ordered) else "failed",
        "scenario": scenario.name,
        "hours": loop.duration_hours,
        "step_hours": loop.step_hours,
        "loop_levers": loop.levers,
        "decisions_per_replicate": loop.n_steps,
        "replicates_measured": len(ordered),
        "replicates_completed": len(completed_walls),
        "replicates": replicates,
        "decision_seconds": _summary([record.seconds for record in records]),
        "by_tier": _by_tier(records),
        "dispatch": _dispatch(tallies),
        "projection_at_min_scenarios": _e5_projection(
            completed_walls, decisions_per_replicate=loop.n_steps, replicates=MIN_SCENARIOS
        ),
    }


def _quiet_logging() -> None:
    """Configure structlog at ERROR level, to stderr, before the twin is imported.

    Mirrors ``uplift.regret.main``; CLI-only, because the configuration is process-global.
    Measured locally without it: ~500 MB of engine debug lines in one simulated hour.
    """
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


def _emit(output: str, report: Mapping[str, object]) -> None:
    """Write ``report`` to ``output`` as canonical JSON and a newline; name it in one line."""
    from pathlib import Path

    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(f"cost_probe status={report.get('status')} output={target.as_posix()}")


def main(argv: Sequence[str] | None = None) -> int:
    """Time the real consensus arm per decision and per tier; exit 2 if it cannot be built.

    A command line whose first argument is :data:`E5_MODE` is :func:`main_e5`'s; every other
    one is parsed here, exactly as before that mode existed.
    """
    supplied = list(sys.argv[1:] if argv is None else argv)
    if supplied[:1] == [E5_MODE]:
        return main_e5(supplied[1:])
    parser = argparse.ArgumentParser(
        prog="python -m uplift.cost_probe",
        description="Measure seconds per consensus decision, by tier (sizing E5, finding 70).",
    )
    parser.add_argument("--hours", type=float, required=True)
    parser.add_argument("--step-hours", type=float, required=True)
    parser.add_argument("--replicates", type=int, required=True)
    # A FILE, NOT STDOUT. Measured locally: the twin handler's Monte Carlo workers wrote about
    # 500 MB of debug lines to stdout in one simulated hour, so a report sharing stdout with them
    # is unparseable. Stdout carries one summary line; the canonical JSON goes here.
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    _quiet_logging()

    from digital_twin.simulation.monte_carlo import MIN_SCENARIOS
    from orchestrator.consensus.tier_router import TierRouter
    from uplift.baselines.par_level_reorder import Par_Level_Reorder
    from uplift.consensus_arm import build_consensus_arm
    from uplift.harness import LoopConfig, replicate_seed, run_closed_loop
    from uplift.scenarios import adversarial_suite

    try:
        arm = build_consensus_arm()
    except Exception as exc:  # noqa: BLE001 - every assembly failure is reported, never timed
        _emit(args.output, {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"})
        return 2

    loop = LoopConfig(duration_hours=args.hours, step_hours=args.step_hours)
    scenarios: list[dict[str, object]] = []
    consensus_mean: dict[str, float] = {}
    baseline_mean: dict[str, float] = {}
    all_records: list[DecisionRecord] = []
    any_failed = False
    for scenario in adversarial_suite():
        consensus_walls: list[float] = []
        baseline_walls: list[float] = []
        runs: list[dict[str, object]] = []
        for index in range(args.replicates):
            seed = replicate_seed(scenario.seed, index)
            timed = _TimedArm(arm, TierRouter())
            started = time.perf_counter()
            run = run_closed_loop(scenario, timed, seed, timed.name, loop)
            consensus_walls.append(time.perf_counter() - started)
            started = time.perf_counter()
            run_closed_loop(
                scenario, Par_Level_Reorder(s=50, S=100, seed=seed), seed, "baseline", loop
            )
            baseline_walls.append(time.perf_counter() - started)
            any_failed = any_failed or run.failed
            all_records.extend(timed.records)
            runs.append(
                {
                    "seed": seed,
                    "failed": run.failed,
                    "error": run.error,
                    "decisions": len(timed.records),
                    "consensus_wall_seconds": consensus_walls[-1],
                    "baseline_wall_seconds": baseline_walls[-1],
                    "by_tier": _by_tier(timed.records),
                }
            )
        consensus_mean[scenario.name] = statistics.fmean(consensus_walls)
        baseline_mean[scenario.name] = statistics.fmean(baseline_walls)
        scenarios.append({"scenario": scenario.name, "runs": runs})

    _emit(
        args.output,
        {
            "status": "failed" if any_failed else "measured",
            "hours": args.hours,
            "step_hours": args.step_hours,
            "replicates_measured": args.replicates,
            "scenarios": scenarios,
            "by_tier": _by_tier(all_records),
            "consensus_mean_wall_seconds_per_replicate": consensus_mean,
            "baseline_mean_wall_seconds_per_replicate": baseline_mean,
            "projection_at_min_scenarios": _projection(
                consensus_mean, baseline_mean, replicates=MIN_SCENARIOS
            ),
        },
    )
    return 1 if any_failed else 0


def main_e5(argv: Sequence[str]) -> int:
    """``python -m uplift.cost_probe e5``: E5's own path, timed per decision (finding 116).

    The scenario, the arm and the loop are the E5 suite's own:
    :func:`uplift.e5_suite.e5_scenario`, :func:`~uplift.e5_suite.e5_consensus_policy` and
    :data:`~uplift.e5_suite.E5_LOOP`. Replicate ``i`` runs at
    ``replicate_seed(E5_SCENARIO_SEED, i)``, the seed ``UpliftHarness.run`` gives E5's replicate
    ``i``. The three exits are the adversarial mode's: 0 measured, 1 a replicate failed
    (reported, not dropped), 2 the consensus arm could not be assembled -- the stand-in's own
    reason is recorded, and nothing is timed as if it had run (I-7).
    """
    parser = argparse.ArgumentParser(
        prog="python -m uplift.cost_probe e5",
        description=(
            "Measure E5's own path: the primary cell unshocked, the reorders-only consensus arm "
            "and 24 hourly decisions, at E5's first N replicate seeds (finding 116)."
        ),
    )
    parser.add_argument("--replicates", type=int, required=True)
    # A file, not stdout, for the reason the adversarial mode's `--output` gives.
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.replicates < 1:
        parser.error(f"--replicates must be at least 1, got {args.replicates}")
    _quiet_logging()

    from uplift.e5_suite import E5_LOOP, E5_SCENARIO_SEED, e5_consensus_policy, e5_scenario
    from uplift.harness import replicate_seed, run_closed_loop
    from uplift.policies import UnavailableConsensusArm

    arm = e5_consensus_policy()
    if isinstance(arm, UnavailableConsensusArm):
        _emit(args.output, {"mode": E5_MODE, "status": "unavailable", "reason": arm.reason})
        return 2
    seeds = [replicate_seed(E5_SCENARIO_SEED, index) for index in range(args.replicates)]
    report = e5_cost_report(arm, e5_scenario(), seeds, E5_LOOP, run_loop=run_closed_loop)
    _emit(args.output, report)
    return 0 if report["status"] == "measured" else 1


if __name__ == "__main__":
    sys.exit(main())
