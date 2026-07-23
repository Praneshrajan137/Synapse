"""
SYNAPSE Decision-Integrity Uplift Proof — the closed-loop counterfactual harness (R2).

The :class:`UpliftHarness` drives the existing SimPy digital twin
(:class:`digital_twin.simulation.engine.SupplyChainSimulation`) through its ADR-052
actuation levers — ``start`` / ``advance`` / ``set_policy`` / ``inject_shock`` /
``inject_orders`` / ``add_stock`` — never rebuilding any simulation physics. On top of
those levers it runs the closed loop the feature is named for (R2.2): at each twin
step, and *before* advancing, it observes the twin state, asks the active
:class:`~uplift.interfaces.DecisionPolicy` to :meth:`decide`, applies the returned
:class:`~uplift.interfaces.PolicyAction` back into the twin, and only then advances one
step — forming the observe → decide → apply → advance loop.

Three entry points (design "UpliftHarness (R2)"):

- :meth:`UpliftHarness.run_scenario` — one closed-loop ``(arm, seed)`` run, returning a
  :class:`~uplift.interfaces.ScenarioRun` (a failed run on any policy error, never a
  fabricated KPI).
- :meth:`UpliftHarness.run_arm` — ``n`` replicate closed-loop runs of one policy on one
  scenario (parallelised with :class:`concurrent.futures.ProcessPoolExecutor` mirroring
  ``MonteCarloRunner``), aggregated into an :class:`~uplift.interfaces.ArmResult` with
  per-KPI mean/std over the completed set and completed/failed counts. Requesting fewer
  than ``MIN_SCENARIOS`` (1000) raises :class:`ValueError` (INV-TW-002 under-power guard).
- :meth:`UpliftHarness.run` — every arm on every scenario, with the *same* per-scenario
  replicate seed sequence across arms (the attribution guarantee, R2.1/R2.5), persisting
  every recorded run via :mod:`uplift.persistence` (R2.6) and returning a
  :class:`HarnessResult`.

**Attribution by construction (R2.1/R2.5, Property 6).** Replicate seeds are derived by
:func:`replicate_seed` from *only* ``(scenario.seed, replicate_index)`` — never from the
arm — so replicate ``i`` of every arm is fed the identical seeded demand realization and
shock. The only difference between arms is which policy produces the per-step decisions,
so any KPI delta is attributable to the decision policy alone.

**Honest failure (R2.7).** A policy that raises (or is unavailable — the in-process
consensus arm surfaces this as :class:`~uplift.consensus_arm.ConsensusArmUnavailable`)
yields a failed :class:`~uplift.interfaces.ScenarioRun` with the error string; failed
runs are excluded from aggregation and the remaining scenarios continue. Completed and
failed counts always sum to the number of attempts (Property 9).

Result assembly, adversarial classification, the all-wins self-scrutiny warning, and the
fidelity-co-located report are **task 10.1** and extend this same module — the
:class:`HarnessResult` intentionally retains the per-``(scenario, arm)`` runs and
aggregates 10.1 needs to assemble the :class:`~uplift.interfaces.UpliftResult`.
"""
from __future__ import annotations

import dataclasses
import math
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable, Sequence

import numpy as np
import structlog

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams

from uplift.contract import MetricContract, relative_pct_change
from uplift.fidelity import FidelityReport
from uplift.interfaces import (
    ArmResult,
    DecisionPolicy,
    Direction,
    KpiVector,
    Observation,
    Outcome,
    PolicyAction,
    Scenario,
    ScenarioRun,
    UpliftResult,
)
from uplift.kpi import (
    DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY,
    AppliedDecisions,
    DeliveredOrder,
    KpiExtractor,
)
from uplift.persistence import save_runs

logger = structlog.get_logger(__name__)

# The KpiVector field names, in declaration order, so aggregation stays in lock-step
# with the interface if a KPI is ever added/removed.
KPI_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(KpiVector))

# The canonical name of the SYNAPSE consensus arm (``ConsensusArm.name`` default);
# result assembly (task 10.1) identifies the consensus arm by this name and treats
# every other arm as a baseline arm.
DEFAULT_CONSENSUS_ARM: str = "consensus"

# The neutral (unshocked) shock; an ``Observation.active_shock`` of ``None`` signals an
# unshocked step so the consensus arm's tier routing does not spuriously escalate.
_NEUTRAL_SHOCK: ShockParams = ShockParams()

# The twin's canonical SKU set (``SupplyChainSimulation.start`` seeds ``sku_0..sku_9``).
# Unit costs are derived from this fixed set so pricing/margin remain well-defined even
# in the cold-start scenario (which empties *inventory*, not the SKU catalogue).
_CANONICAL_SKUS: tuple[str, ...] = tuple(f"sku_{i}" for i in range(10))

# Demand elasticity bounds for the price -> demand_mult coupling (bounded so an extreme
# price cannot drive the twin into a degenerate demand regime). Arm-symmetric.
_MIN_DEMAND_MULT: float = 0.5
_MAX_DEMAND_MULT: float = 2.0


# ---------------------------------------------------------------------------
# Loop configuration
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class LoopConfig:
    """Closed-loop cadence: total horizon and the per-step advance duration (R2.2).

    ``duration_hours`` is the scenario horizon; the loop advances in ``step_hours``
    increments, so it runs ``round(duration_hours / step_hours)`` observe → decide →
    apply → advance cycles. Both arms use the identical cadence (arm symmetry).
    """

    duration_hours: float = 4.0
    step_hours: float = 1.0

    @property
    def n_steps(self) -> int:
        return max(1, int(round(self.duration_hours / self.step_hours)))


# ---------------------------------------------------------------------------
# Deterministic replicate seeding (the attribution guarantee, Property 6)
# ---------------------------------------------------------------------------
def replicate_seed(base_seed: int, index: int) -> int:
    """Derive replicate ``index``'s twin seed from ``base_seed`` alone (R2.1/R2.5).

    The derivation depends only on ``(base_seed, index)`` — never on the arm — so
    replicate ``i`` of the consensus arm and of every baseline arm is driven by the
    identical twin RNG stream (Property 6). Uses :class:`numpy.random.SeedSequence`
    for a well-distributed, reproducible 32-bit seed.
    """
    seq = np.random.SeedSequence([int(base_seed), int(index)])
    return int(seq.generate_state(1, dtype=np.uint32)[0])


# ---------------------------------------------------------------------------
# Unit-cost derivation (shared identically by both arms)
# ---------------------------------------------------------------------------
def _derive_unit_costs() -> dict[str, float]:
    """Deterministic per-SKU unit cost over the canonical SKU set.

    Fixed and arm-symmetric so margin differences between arms are caused by the
    policy's pricing decision, never by differing costs.
    """
    return {sku: round(1.0 + index * 0.5, 2) for index, sku in enumerate(_CANONICAL_SKUS)}


def _mean_unit_cost(unit_costs: dict[str, float]) -> float:
    if not unit_costs:
        return 0.0
    return math.fsum(unit_costs.values()) / len(unit_costs)


# ---------------------------------------------------------------------------
# Twin construction + actuation helpers
# ---------------------------------------------------------------------------
def _build_twin(scenario: Scenario, seed: int) -> SupplyChainSimulation:
    """Build and ``start`` the twin for ``scenario`` at ``seed`` (mirrors MonteCarloRunner).

    The shock's demand/lead-time multipliers map onto ``TwinConfig`` exactly as
    ``MonteCarloRunner._run_single_scenario`` maps them, and the failure/spoilage
    multipliers are passed to the engine constructor, so the harness and the twin's
    own Monte Carlo path realise a shock identically.
    """
    shock = scenario.shock
    config = TwinConfig(
        order_arrival_rate=2.0 * shock.demand_multiplier,
        pick_pack_mean_min=8.0 * shock.lead_time_multiplier,
    )
    sim = SupplyChainSimulation(
        config=config,
        seed=seed,
        failure_rate_multiplier=shock.failure_rate_multiplier,
        spoilage_rate_multiplier=shock.spoilage_rate_multiplier,
    )
    sim.start()
    if scenario.cold_start:
        _apply_cold_start(sim)
    return sim


def _apply_cold_start(sim: SupplyChainSimulation) -> None:
    """Empty the twin's initial inventory/freshness for the cold-start-city scenario.

    ``SupplyChainSimulation.start`` warms every canonical SKU to 100 units / full
    freshness; the cold-start-city scenario models a brand-new city with no warm
    history. The engine exposes no public "empty" lever, so this clears the engine's
    inventory/freshness maps directly. Kept as a single, documented seam.
    """
    try:
        sim._inventory.clear()  # noqa: SLF001 — no public lever to empty initial stock
        sim._freshness.clear()  # noqa: SLF001
    except AttributeError:  # pragma: no cover — engine shape changed
        logger.warning("uplift_cold_start_unavailable")


def _apply_price(sim: SupplyChainSimulation, price: float, reference_price: float) -> None:
    """Couple a pricing decision into the twin via demand elasticity (design R2.2 mapping).

    A price above the reference (cost basis) softens demand; a price below it lifts
    demand. Implemented as a bounded ``demand_mult = reference / price`` fed to
    ``set_policy`` so the pricing lever has a real, arm-symmetric effect on the world.
    """
    if not math.isfinite(price) or price <= 0.0 or reference_price <= 0.0:
        return
    demand_mult = reference_price / price
    demand_mult = min(_MAX_DEMAND_MULT, max(_MIN_DEMAND_MULT, demand_mult))
    sim.set_policy(demand_mult=demand_mult)


def _apply_reorders(sim: SupplyChainSimulation, reorder_quantities) -> None:
    """Apply per-SKU reorder quantities to the twin via ``add_stock`` (R2.2 mapping)."""
    for sku, qty in reorder_quantities.items():
        try:
            quantity = float(qty)
        except (TypeError, ValueError):
            continue
        if math.isfinite(quantity) and quantity > 0.0:
            sim.add_stock(str(sku), quantity)


def _apply_action(
    sim: SupplyChainSimulation,
    action: PolicyAction,
    reference_price: float,
    current_price: float | None,
) -> float | None:
    """Apply a :class:`PolicyAction`'s twin levers; return the (possibly updated) price.

    Concrete twin levers are actuated here: ``price`` -> demand elasticity + margin
    bookkeeping (the returned ``current_price`` carries the latest applied price for the
    margin accumulator), and ``reorder_quantities`` -> ``add_stock``. ``routing_assignment``
    and ``disruption_actions`` have no direct twin actuation lever in the current engine
    and are intentionally recorded-but-not-actuated here (a documented seam a later
    disruption-mitigation mapping can extend); a partial action leaves unset levers
    untouched.
    """
    if action.price is not None:
        current_price = float(action.price)
        _apply_price(sim, current_price, reference_price)
    if action.reorder_quantities:
        _apply_reorders(sim, action.reorder_quantities)
    return current_price


# ---------------------------------------------------------------------------
# The closed loop (module-level so it is usable in ProcessPoolExecutor workers)
# ---------------------------------------------------------------------------
def run_closed_loop(
    scenario: Scenario,
    policy: DecisionPolicy,
    seed: int,
    arm_name: str,
    loop_config: LoopConfig,
    emission_factor: float = DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY,
) -> ScenarioRun:
    """Run one closed-loop ``(arm, seed)`` scenario and return its :class:`ScenarioRun`.

    The loop (R2.2): build + ``start`` the twin at ``seed`` with the scenario's shock,
    then for each step observe twin state → ``policy.decide(obs)`` → apply the
    :class:`PolicyAction` → ``advance(step)``. Between steps it accumulates the
    arm-applied decision effects (delivered-order pricing for margin, and an
    arm-symmetric unmet-demand counter for stockout rate) and finally derives the
    :class:`~uplift.interfaces.KpiVector` via the shared :class:`KpiExtractor`.

    On *any* exception — most importantly ``policy.decide`` raising or the policy being
    unavailable — the run is recorded as failed with the error string and no KPIs are
    ever fabricated (R2.7).
    """
    try:
        sim = _build_twin(scenario, seed)
        unit_costs = _derive_unit_costs()
        reference_price = _mean_unit_cost(unit_costs)
        active_shock = scenario.shock if scenario.shock != _NEUTRAL_SHOCK else None
        extractor = KpiExtractor(emission_factor)

        current_price: float | None = None
        delivered_orders: list[DeliveredOrder] = []
        unmet_demand_events = 0
        prev_delivered = int(sim.metrics.orders_delivered)

        for _ in range(loop_config.n_steps):
            metrics = sim.metrics
            inventory = sim.inventory
            obs = Observation(
                inventory={sku: int(level) for sku, level in inventory.items()},
                sim_time=sim.sim_time_min,
                delivery_count=int(metrics.orders_delivered),
                spoilage_count=int(metrics.orders_spoiled),
                stockout_count=unmet_demand_events,
                unit_costs=unit_costs,
                active_shock=active_shock,
            )

            # observe -> decide (may raise -> honest failed run, R2.7)
            action = policy.decide(obs)

            # decide -> apply (before advancing, closing the loop, R2.2)
            current_price = _apply_action(sim, action, reference_price, current_price)

            # apply -> advance one step
            sim.advance(loop_config.step_hours)

            # post-step accounting for margin + stockout (arm-symmetric observations)
            delivered_now = int(sim.metrics.orders_delivered)
            newly_delivered = max(0, delivered_now - prev_delivered)
            effective_price = current_price if current_price is not None else reference_price
            for _order in range(newly_delivered):
                delivered_orders.append(
                    DeliveredOrder(applied_price=effective_price, unit_cost=reference_price)
                )
            prev_delivered = delivered_now
            # A SKU drawn to zero represents unmet demand at that step (design R2.3).
            unmet_demand_events += sum(1 for level in sim.inventory.values() if level <= 0.0)

        applied = AppliedDecisions(
            delivered_orders=tuple(delivered_orders),
            unmet_demand_events=unmet_demand_events,
            demand_events=int(sim.metrics.orders_created),
            delivered_volume=float(sim.metrics.orders_delivered),
        )
        kpis = extractor.extract(sim.metrics, applied)
        return ScenarioRun(arm=arm_name, seed=seed, kpis=kpis, failed=False, error=None)
    except Exception as exc:  # noqa: BLE001 — every failure is an honest failed run (R2.7)
        return ScenarioRun(
            arm=arm_name,
            seed=seed,
            kpis=None,
            failed=True,
            error=f"{type(exc).__name__}: {exc}",
        )


def _scenario_worker(
    scenario: Scenario,
    seed: int,
    arm_name: str,
    loop_config: LoopConfig,
    emission_factor: float,
    policy: DecisionPolicy | None,
    policy_factory: "Callable[[], DecisionPolicy] | None",
) -> ScenarioRun:
    """Top-level ProcessPoolExecutor worker: resolve the policy and run the closed loop.

    A picklable ``policy`` is used directly; a picklable ``policy_factory`` is called
    in-worker to build a policy that need not itself be picklable (e.g. the consensus
    arm). All arguments are plain picklable values so the worker survives spawn-start
    (Windows) as well as fork.
    """
    resolved = policy_factory() if policy_factory is not None else policy
    if resolved is None:  # pragma: no cover — guarded before submission
        return ScenarioRun(
            arm=arm_name, seed=seed, kpis=None, failed=True, error="no policy resolved"
        )
    return run_closed_loop(scenario, resolved, seed, arm_name, loop_config, emission_factor)


# ---------------------------------------------------------------------------
# Aggregation (Property 9 / Property 10)
# ---------------------------------------------------------------------------
def aggregate_arm(arm_name: str, runs: Sequence[ScenarioRun]) -> ArmResult:
    """Aggregate an arm's runs into an :class:`ArmResult` (R2.7/R2.8/R2.9).

    Failed runs are excluded from the KPI aggregation; the per-KPI mean and standard
    deviation (population std, ``ddof=0``, matching ``MonteCarloRunner``) are computed
    over exactly the completed runs (Property 10). ``completed`` + ``failed`` always
    sum to ``len(runs)`` — the number of attempts (Property 9).
    """
    completed = [r for r in runs if not r.failed and r.kpis is not None]
    failed_count = len(runs) - len(completed)

    kpi_mean: dict[str, float] = {}
    kpi_std: dict[str, float] = {}
    for field in KPI_FIELDS:
        if completed:
            values = np.array(
                [float(getattr(run.kpis, field)) for run in completed], dtype=float
            )
            kpi_mean[field] = float(np.mean(values))
            kpi_std[field] = float(np.std(values))
        else:
            kpi_mean[field] = 0.0
            kpi_std[field] = 0.0

    return ArmResult(
        arm=arm_name,
        completed=len(completed),
        failed=failed_count,
        kpi_mean=kpi_mean,
        kpi_std=kpi_std,
    )


# ---------------------------------------------------------------------------
# HarnessResult (retains what task 10.1 needs to assemble the UpliftResult)
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class HarnessResult:
    """The full output of :meth:`UpliftHarness.run` (R2.6/R2.8/R2.9).

    Retains both the per-``(scenario, arm)`` aggregate :class:`ArmResult`s and the raw
    per-``(scenario, arm)`` :class:`ScenarioRun` lists, so task 10.1 can compute
    effect sizes over the completed KPI samples and apply the metric-contract decision
    rule. ``all_runs`` is the flat list persisted to ``results_path`` (R2.6).
    """

    arm_results: dict[tuple[str, str], ArmResult]
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]]
    all_runs: list[ScenarioRun]
    results_path: Path | None
    scenarios: tuple[Scenario, ...]
    arm_names: tuple[str, ...]

    def completed_runs(self, scenario_name: str, arm_name: str) -> list[ScenarioRun]:
        """The completed (non-failed) runs for a ``(scenario, arm)`` pair."""
        pair = (scenario_name, arm_name)
        return [r for r in self.runs_by_pair.get(pair, []) if not r.failed and r.kpis is not None]

    def kpi_samples(self, scenario_name: str, arm_name: str, kpi: str) -> list[float]:
        """The completed per-scenario samples of one KPI for a ``(scenario, arm)`` pair.

        This is the input task 10.1 feeds to ``MetricContract.classify`` (consensus vs
        baseline sample arrays) for each primary KPI.
        """
        return [
            float(getattr(run.kpis, kpi))
            for run in self.completed_runs(scenario_name, arm_name)
        ]


# ---------------------------------------------------------------------------
# UpliftHarness
# ---------------------------------------------------------------------------
class UpliftHarness:
    """Closed-loop counterfactual harness over the SimPy twin (R2).

    Construct with an optional :class:`TwinConfig` (for worker count), a
    :class:`LoopConfig` (closed-loop cadence), the CO2 emission factor, and an optional
    ``results_path`` where :meth:`run` persists every recorded run (R2.6).
    """

    def __init__(
        self,
        *,
        config: TwinConfig | None = None,
        loop_config: LoopConfig | None = None,
        emission_factor: float = DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY,
        results_path: str | Path | None = None,
        max_workers: int | None = None,
    ) -> None:
        self._config = config or TwinConfig()
        self._loop = loop_config or LoopConfig()
        self._emission_factor = emission_factor
        self._results_path = Path(results_path) if results_path is not None else None
        self._max_workers = max_workers or self._config.monte_carlo_max_workers

    # -- single scenario ----------------------------------------------------
    def run_scenario(self, scenario: Scenario, policy: DecisionPolicy) -> ScenarioRun:
        """Run one closed-loop scenario for ``policy`` at the scenario's own seed (R2.2).

        Returns a completed :class:`ScenarioRun` with a derived :class:`KpiVector`, or a
        failed run on any policy error (R2.7) — never a fabricated KPI.
        """
        return run_closed_loop(
            scenario,
            policy,
            scenario.seed,
            policy.name,
            self._loop,
            self._emission_factor,
        )

    # -- one arm ------------------------------------------------------------
    def run_arm(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None = None,
        n: int = MIN_SCENARIOS,
        *,
        policy_factory: "Callable[[], DecisionPolicy] | None" = None,
        arm_name: str | None = None,
        parallel: bool = True,
    ) -> ArmResult:
        """Run ``n`` replicate closed-loop scenarios of one policy and aggregate (R2.4/R2.8).

        Requesting fewer than ``MIN_SCENARIOS`` (1000) raises :class:`ValueError` — the
        INV-TW-002 under-power guard, matching ``MonteCarloRunner`` — so an
        under-powered aggregation can never be produced. Failed runs are excluded from
        aggregation and reported in the returned :class:`ArmResult`'s ``failed`` count
        (R2.7/R2.9).
        """
        runs = self._run_arm_runs(
            scenario, policy, n, policy_factory=policy_factory, arm_name=arm_name, parallel=parallel
        )
        resolved_name = self._resolve_arm_name(policy, arm_name)
        return aggregate_arm(resolved_name, runs)

    # -- full matrix --------------------------------------------------------
    def run(
        self,
        scenarios: Iterable[Scenario],
        arms: Iterable[DecisionPolicy],
        n_per_arm: int = MIN_SCENARIOS,
        *,
        parallel: bool = True,
    ) -> HarnessResult:
        """Run every arm on every scenario and persist the recorded runs (R2.1/R2.6).

        For each scenario, every arm is driven with the identical per-scenario replicate
        seed sequence (arms differ only in policy — the attribution guarantee, R2.1/R2.5).
        Every recorded run is persisted to ``results_path`` (when configured) with its
        arm identifier and scenario seed (R2.6). Returns a :class:`HarnessResult` carrying
        per-``(scenario, arm)`` aggregates and raw runs for downstream assembly (task 10.1).
        """
        scenario_list = list(scenarios)
        arm_list = list(arms)

        arm_results: dict[tuple[str, str], ArmResult] = {}
        runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
        all_runs: list[ScenarioRun] = []

        for scenario in scenario_list:
            for policy in arm_list:
                runs = self._run_arm_runs(
                    scenario, policy, n_per_arm, parallel=parallel
                )
                pair = (scenario.name, policy.name)
                runs_by_pair[pair] = runs
                arm_results[pair] = aggregate_arm(policy.name, runs)
                all_runs.extend(runs)

        results_path: Path | None = None
        if self._results_path is not None:
            results_path = save_runs(all_runs, self._results_path)

        return HarnessResult(
            arm_results=arm_results,
            runs_by_pair=runs_by_pair,
            all_runs=all_runs,
            results_path=results_path,
            scenarios=tuple(scenario_list),
            arm_names=tuple(policy.name for policy in arm_list),
        )

    # -- result assembly (task 10.1) ----------------------------------------
    def assemble(
        self,
        harness_result: HarnessResult,
        contract: MetricContract,
        *,
        fidelity: FidelityReport | None = None,
        consensus_arm: str = DEFAULT_CONSENSUS_ARM,
        baseline_arm: str | None = None,
    ) -> UpliftResult:
        """Assemble the :class:`~uplift.interfaces.UpliftResult` from a completed run.

        Convenience wrapper over :func:`assemble_uplift_result` applying the metric
        contract's decision rule exactly as declared (R3.7); see that function for the
        full behavior contract.
        """
        return assemble_uplift_result(
            harness_result,
            contract,
            fidelity=fidelity,
            consensus_arm=consensus_arm,
            baseline_arm=baseline_arm,
        )

    # -- internals ----------------------------------------------------------
    @staticmethod
    def _check_power(n: int) -> None:
        """Raise :class:`ValueError` if fewer than 1000 scenarios are requested (R2.4)."""
        if n < MIN_SCENARIOS:
            raise ValueError(
                f"INV-TW-002 violated: n={n} < {MIN_SCENARIOS}. "
                f"Each arm requires >= {MIN_SCENARIOS} completed scenarios per arm."
            )

    @staticmethod
    def _resolve_arm_name(
        policy: DecisionPolicy | None, arm_name: str | None
    ) -> str:
        if arm_name is not None:
            return arm_name
        if policy is not None:
            return policy.name
        raise ValueError("run_arm requires a policy or an explicit arm_name")

    def _run_arm_runs(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None,
        n: int,
        *,
        policy_factory: "Callable[[], DecisionPolicy] | None" = None,
        arm_name: str | None = None,
        parallel: bool = True,
    ) -> list[ScenarioRun]:
        """Execute ``n`` replicate closed-loop runs, parallel with a sequential fallback.

        Enforces the INV-TW-002 guard, derives the identical-across-arms replicate seed
        sequence, and runs the closed loop for each. Parallel execution uses a
        :class:`ProcessPoolExecutor`; if the policy/args cannot be pickled or a worker
        process cannot be spawned in this environment, it degrades honestly to
        sequential in-process execution so the harness is always correct.
        """
        if policy is None and policy_factory is None:
            raise ValueError("_run_arm_runs requires a policy or a policy_factory")
        self._check_power(n)
        resolved_name = self._resolve_arm_name(policy, arm_name)
        seeds = [replicate_seed(scenario.seed, index) for index in range(n)]

        if parallel and self._max_workers > 1:
            try:
                return self._run_parallel(scenario, policy, policy_factory, resolved_name, seeds)
            except Exception as exc:  # noqa: BLE001 — honest degrade to sequential
                logger.warning(
                    "uplift_parallel_fallback",
                    arm=resolved_name,
                    scenario=scenario.name,
                    error=f"{type(exc).__name__}: {exc}",
                )
        return self._run_sequential(scenario, policy, policy_factory, resolved_name, seeds)

    def _run_parallel(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None,
        policy_factory: "Callable[[], DecisionPolicy] | None",
        arm_name: str,
        seeds: Sequence[int],
    ) -> list[ScenarioRun]:
        runs: list[ScenarioRun] = []
        workers = min(self._max_workers, max(1, len(seeds)))
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(
                    _scenario_worker,
                    scenario,
                    seed,
                    arm_name,
                    self._loop,
                    self._emission_factor,
                    policy,
                    policy_factory,
                )
                for seed in seeds
            ]
            for future in as_completed(futures):
                runs.append(future.result())
        return runs

    def _run_sequential(
        self,
        scenario: Scenario,
        policy: DecisionPolicy | None,
        policy_factory: "Callable[[], DecisionPolicy] | None",
        arm_name: str,
        seeds: Sequence[int],
    ) -> list[ScenarioRun]:
        resolved = policy_factory() if policy_factory is not None else policy
        if resolved is None:  # pragma: no cover — guarded upstream
            raise ValueError("no policy resolved for sequential run")
        return [
            run_closed_loop(
                scenario, resolved, seed, arm_name, self._loop, self._emission_factor
            )
            for seed in seeds
        ]


# ---------------------------------------------------------------------------
# Result assembly + fidelity-co-located reporting (task 10.1)
#
# R3.7  apply the contract decision rule exactly as declared
# R3.8  label every reported non-primary KPI as secondary
# R4.3  classify each (scenario, primary KPI) pair into exactly one outcome
# R4.4  report every executed scenario without outcome-based filtering
# R4.5  emit the all-wins self-scrutiny warning iff every pair is SYNAPSE_WINS
# R4.6  exit success for any completed run regardless of winner
# R4.7  incomplete scenario -> failed run, mark incomplete, never default to SYNAPSE_WINS
# R5.2  state, co-located, that validity is bounded by twin fidelity
# R5.6  co-locate the KL value, threshold comparison, and confidence annotation
# ---------------------------------------------------------------------------

#: Exit statuses for a completed harness run (R4.6). A run that produced at least one
#: completed scenario is a *success* regardless of which arm won; only a run with no
#: completed scenario at all is a failure (there is nothing to report).
EXIT_SUCCESS: int = 0
EXIT_NO_COMPLETED_RUN: int = 1


def _resolve_baseline_arms(
    harness_result: HarnessResult,
    consensus_arm: str,
    baseline_arm: str | None,
) -> list[str]:
    """Resolve which arm(s) form the baseline the consensus arm is compared against.

    Consensus-vs-baseline handling (documented design choice): the consensus arm is
    identified *by name* (``consensus_arm``, the ``ConsensusArm.name`` default
    ``"consensus"``). The baseline is every *other* arm. When a specific
    ``baseline_arm`` is named, only that arm is used; otherwise the completed samples
    of **all** non-consensus baseline arms are pooled into a single baseline
    distribution per ``(scenario, KPI)`` — a defensible aggregation representing "the
    transparent operator without SYNAPSE" as a whole, and one that uses every recorded
    baseline sample rather than privileging one policy.
    """
    if baseline_arm is not None:
        return [baseline_arm]
    return [arm for arm in harness_result.arm_names if arm != consensus_arm]


def _pooled_samples(
    harness_result: HarnessResult,
    arms: Sequence[str],
    scenario_names: Sequence[str],
    kpi: str,
) -> list[float]:
    """Pool completed per-scenario KPI samples across the given arms and scenarios."""
    samples: list[float] = []
    for scenario_name in scenario_names:
        for arm in arms:
            samples.extend(harness_result.kpi_samples(scenario_name, arm, kpi))
    return samples


def _run_is_incomplete(
    harness_result: HarnessResult,
    scenario_names: Sequence[str],
    consensus_arm: str,
    baseline_arms: Sequence[str],
) -> bool:
    """True if any (scenario, arm) pair recorded a failed run or failed to complete.

    A run is incomplete (R4.7) when, for any scenario and any compared arm, there is a
    failed run, no run at all, or no completed run — i.e. an arm could not complete
    that scenario.
    """
    for scenario_name in scenario_names:
        for arm in (consensus_arm, *baseline_arms):
            runs = harness_result.runs_by_pair.get((scenario_name, arm), [])
            if not runs:
                return True
            if any(run.failed for run in runs):
                return True
            if not harness_result.completed_runs(scenario_name, arm):
                return True
    return False


def _headline_uplift(
    harness_result: HarnessResult,
    contract: MetricContract,
    consensus_arm: str,
    baseline_arms: Sequence[str],
    scenario_names: Sequence[str],
) -> float:
    """Relative % improvement of consensus over baseline on the headline primary KPI.

    The headline number is the relative percentage change (:func:`relative_pct_change`)
    of the consensus arm's mean over the baseline arm's mean on the contract's headline
    primary KPI — the *first* declared primary KPI — pooled across every scenario, in
    percentage points (the unit :data:`uplift.uplift_floor.UPLIFT_FLOOR` is expressed
    in). It is oriented by the KPI's improvement direction so a positive headline always
    means SYNAPSE is better: for a higher-is-better KPI the raw relative change is used
    directly; for a lower-is-better KPI it is negated (a lower consensus value is an
    improvement, so it reports as a positive uplift).
    """
    if not contract.primary_kpis:
        return 0.0
    kpi = next(iter(contract.primary_kpis))
    direction = contract.primary_kpis[kpi]
    consensus = _pooled_samples(harness_result, [consensus_arm], scenario_names, kpi)
    baseline = _pooled_samples(harness_result, baseline_arms, scenario_names, kpi)
    rel = relative_pct_change(consensus, baseline)
    return rel if direction is Direction.HIGHER_IS_BETTER else -rel


def assemble_uplift_result(
    harness_result: HarnessResult,
    contract: MetricContract,
    *,
    fidelity: FidelityReport | None = None,
    consensus_arm: str = DEFAULT_CONSENSUS_ARM,
    baseline_arm: str | None = None,
) -> UpliftResult:
    """Assemble the :class:`~uplift.interfaces.UpliftResult` from a harness run (task 10.1).

    Applies the pre-registered metric contract's decision rule *exactly as declared*
    (R3.7) — via :meth:`MetricContract.classify` — to classify each ``(scenario,
    primary KPI)`` pair into exactly one :class:`~uplift.interfaces.Outcome` (R4.3),
    consensus arm versus the pooled baseline arm(s). Every executed scenario is
    reported with no outcome-based filtering (R4.4). Every reported non-primary KPI is
    labelled secondary (R3.8). The all-wins self-scrutiny warning is emitted iff every
    classified pair is ``SYNAPSE_WINS`` (R4.5). If any scenario could not complete for
    an arm the result is marked ``incomplete`` and the affected pair is *never* credited
    to SYNAPSE — an incomplete pair resolves to ``TIE_INCONCLUSIVE`` (R4.7). The
    :class:`~uplift.fidelity.FidelityReport` is attached so the headline number carries
    its KL value, threshold comparison, and confidence annotation (R5.2/R5.6); when no
    report is supplied it is read from the live C34 gauge.
    """
    scenario_names = [scenario.name for scenario in harness_result.scenarios]
    baseline_arms = _resolve_baseline_arms(harness_result, consensus_arm, baseline_arm)
    primary_kpis = contract.primary_kpis

    incomplete = _run_is_incomplete(
        harness_result, scenario_names, consensus_arm, baseline_arms
    )

    # R4.3 / R4.4: classify every (scenario, primary KPI) pair exactly once, with no
    # outcome-based filtering. R4.7: an affected pair (an arm with no completed samples
    # for that scenario) is never credited to SYNAPSE — it resolves to TIE_INCONCLUSIVE.
    per_scenario: dict[tuple[str, str], Outcome] = {}
    for scenario_name in scenario_names:
        for kpi in primary_kpis:
            consensus = harness_result.kpi_samples(scenario_name, consensus_arm, kpi)
            baseline = _pooled_samples(
                harness_result, baseline_arms, [scenario_name], kpi
            )
            if not consensus or not baseline:
                per_scenario[(scenario_name, kpi)] = Outcome.TIE_INCONCLUSIVE
                incomplete = True
            else:
                per_scenario[(scenario_name, kpi)] = contract.classify(
                    consensus, baseline, kpi
                )

    # Per-primary-KPI verdict pooled across all scenarios (consensus vs baseline).
    per_kpi: dict[str, Outcome] = {}
    for kpi in primary_kpis:
        consensus = _pooled_samples(harness_result, [consensus_arm], scenario_names, kpi)
        baseline = _pooled_samples(harness_result, baseline_arms, scenario_names, kpi)
        if not consensus or not baseline:
            per_kpi[kpi] = Outcome.TIE_INCONCLUSIVE
        else:
            per_kpi[kpi] = contract.classify(consensus, baseline, kpi)

    # R3.8: every reported KPI that is not a declared primary KPI is labelled secondary
    # (set difference over the KpiVector fields guarantees no KPI is labelled both).
    secondary_kpis = [field for field in KPI_FIELDS if field not in primary_kpis]

    # R4.5: warn iff every classified pair is SYNAPSE_WINS (an empty grid never warns).
    all_wins_warning = bool(per_scenario) and all(
        outcome is Outcome.SYNAPSE_WINS for outcome in per_scenario.values()
    )

    headline_uplift = _headline_uplift(
        harness_result, contract, consensus_arm, baseline_arms, scenario_names
    )

    fidelity_report = fidelity if fidelity is not None else FidelityReport.from_metric()

    return UpliftResult(
        per_kpi=per_kpi,
        per_scenario=per_scenario,
        secondary_kpis=secondary_kpis,
        headline_uplift=headline_uplift,
        fidelity=fidelity_report,
        all_wins_warning=all_wins_warning,
        incomplete=incomplete,
    )


def completed_run_count(harness_result: HarnessResult) -> int:
    """Total number of completed (non-failed) scenario runs across every pair."""
    return sum(
        1
        for runs in harness_result.runs_by_pair.values()
        for run in runs
        if not run.failed and run.kpis is not None
    )


def uplift_exit_code(harness_result: HarnessResult) -> int:
    """Exit status for a completed harness run (R4.6).

    Returns :data:`EXIT_SUCCESS` (``0``) whenever at least one scenario completed —
    a completed adversarial run is a valid outcome regardless of which arm wins — and
    :data:`EXIT_NO_COMPLETED_RUN` (``1``) only when nothing completed and there is no
    result to report.
    """
    return EXIT_SUCCESS if completed_run_count(harness_result) > 0 else EXIT_NO_COMPLETED_RUN


@dataclasses.dataclass(frozen=True)
class UpliftReport:
    """An uplift number co-located with its full twin-fidelity context (R5.2/R5.6).

    Every uplift number the harness surfaces is rendered through this report so no
    number is ever presented without its fidelity context: the KL-divergence value,
    its comparison to the C34 re-sync threshold, the resulting confidence annotation,
    and the fixed statement that the number's validity is bounded by twin fidelity.
    """

    headline_uplift: float
    primary_kpi: str
    kl_divergence: float | None
    threshold: float
    within_fidelity_bound: bool | None
    confidence: str
    fidelity_bound_statement: str

    def render(self) -> str:
        """Render the uplift number and its fidelity context as co-located text (R5.6)."""
        if self.kl_divergence is None:
            kl = "unavailable"
            comparison = "unavailable"
        else:
            kl = f"{self.kl_divergence:.6f}"
            comparison = (
                "<= threshold" if self.within_fidelity_bound else "> threshold"
            )
        return (
            f"headline uplift: {self.headline_uplift:+.4f} pp "
            f"(primary KPI: {self.primary_kpi})\n"
            f"twin KL divergence: {kl} "
            f"(C34 re-sync threshold {self.threshold:.6f}; {comparison})\n"
            f"fidelity confidence: {self.confidence}\n"
            f"{self.fidelity_bound_statement}"
        )


def build_uplift_report(
    result: UpliftResult, *, primary_kpi: str | None = None
) -> UpliftReport:
    """Build the fidelity-co-located :class:`UpliftReport` for an assembled result (R5.6).

    Pairs ``result.headline_uplift`` with its :class:`~uplift.fidelity.FidelityReport`
    so the reported number carries the KL value, the threshold comparison, the
    confidence annotation, and the fixed fidelity-bound statement in one place.
    """
    fidelity = result.fidelity
    kpi = primary_kpi or (next(iter(result.per_kpi)) if result.per_kpi else "")
    within = (
        None
        if fidelity.kl_divergence is None
        else fidelity.kl_divergence <= fidelity.threshold
    )
    return UpliftReport(
        headline_uplift=result.headline_uplift,
        primary_kpi=kpi,
        kl_divergence=fidelity.kl_divergence,
        threshold=fidelity.threshold,
        within_fidelity_bound=within,
        confidence=fidelity.confidence,
        fidelity_bound_statement=fidelity.fidelity_bound_statement,
    )


__all__ = [
    "DEFAULT_CONSENSUS_ARM",
    "EXIT_NO_COMPLETED_RUN",
    "EXIT_SUCCESS",
    "KPI_FIELDS",
    "HarnessResult",
    "LoopConfig",
    "UpliftHarness",
    "UpliftReport",
    "aggregate_arm",
    "assemble_uplift_result",
    "build_uplift_report",
    "completed_run_count",
    "replicate_seed",
    "run_closed_loop",
    "uplift_exit_code",
]
