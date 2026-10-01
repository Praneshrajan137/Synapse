"""What one consensus decision costs, measured by tier, so E5 is sized from a reading (finding 70).

``uplift.yml::uplift-proof`` has never run, and its cost was only ever an extrapolation from a
test docstring (about 20 s per shocked Tier-4 decision, which at 1000 replicates x 3 shocked
scenarios x 24 hourly decisions is roughly 400 core-hours). ``.kiro/steering/execution-routing.md``
forbids sizing a workload against an unmeasured cost, so this module measures it: a small number
of replicates of each adversarial scenario, driven through the REAL consensus arm on the
harness's own closed loop (:func:`uplift.harness.run_closed_loop`), timing every ``decide`` call
and recording the tier :class:`~orchestrator.consensus.tier_router.TierRouter` assigns to the
request that call carries. A transparent baseline arm is timed on the same seeds as the
reference for what a non-consensus arm-replicate costs.

**It measures and does not judge.** No verdict, no gate, no claim about decision quality: the
numbers it reports are seconds. A consensus arm that cannot be assembled is reported
``unavailable`` and the command exits 2 -- it is never timed as if it had run (I-7) -- and a
replicate whose closed loop failed is reported failed with its error, not dropped.

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
    from collections.abc import Sequence

    from orchestrator.consensus.tier_router import TierRouter
    from uplift.interfaces import DecisionPolicy, Observation, PolicyAction

#: A GitHub-hosted job is terminated at six hours; sizing leaves one hour of margin per job.
JOB_BUDGET_SECONDS: Final[float] = 5.0 * 3600.0

#: Standard public-repository ``ubuntu-latest`` runners carry four vCPUs (GitHub's runner
#: reference, read 2026-09-30); the projection reports both serial and four-worker figures.
RUNNER_VCPUS: Final[int] = 4


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


def main(argv: Sequence[str] | None = None) -> int:
    """Time the real consensus arm per decision and per tier; exit 2 if it cannot be built."""
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
    # Mirrors `uplift.regret.main`: ERROR level, to stderr, CLI-only (process-global config).
    # Measured locally without it: ~500 MB of engine debug lines in one simulated hour.
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.ERROR),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )

    from digital_twin.simulation.monte_carlo import MIN_SCENARIOS
    from orchestrator.consensus.tier_router import TierRouter
    from uplift.baselines.par_level_reorder import Par_Level_Reorder
    from uplift.consensus_arm import build_consensus_arm
    from uplift.harness import LoopConfig, replicate_seed, run_closed_loop
    from uplift.scenarios import adversarial_suite

    def emit(report: dict[str, object]) -> None:
        from pathlib import Path

        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
        )
        print(f"cost_probe status={report.get('status')} output={target.as_posix()}")

    try:
        arm = build_consensus_arm()
    except Exception as exc:  # noqa: BLE001 - every assembly failure is reported, never timed
        emit({"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"})
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

    emit(
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
        }
    )
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())
