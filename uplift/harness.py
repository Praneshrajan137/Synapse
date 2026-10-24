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
fidelity-co-located report extend this same module — the :class:`HarnessResult`
intentionally retains the per-``(scenario, arm)`` runs and aggregates needed to assemble
the :class:`~uplift.interfaces.UpliftResult`.

**Run provenance and the persisted artifact.** :class:`UpliftProvenance` records the
arms, replicates-per-arm, source revision, run identifier, seed set, and write instant
for a run; :class:`UpliftArtifact` is the Pydantic model the C60 gate evaluates, written
through :meth:`UpliftArtifact.write` with the repo-canonical
``json.dumps(obj, sort_keys=True, separators=(',',':'))`` serialisation so two runs of
the same seed set are byte-comparable. :func:`canonical_arm_aggregates` is the
byte-comparable arm-KPI surface that guarantee is stated over, and
:attr:`UpliftArtifact.unavailable_reasons` names every reason an artifact is not a
completed powered proof rather than letting a gate read a headline number out of an
incomplete run.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import os
import statistics
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Final, Iterable, Literal, Mapping, Sequence

import numpy as np
import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from digital_twin.config import TwinConfig
from digital_twin.simulation.engine import SupplyChainSimulation
from digital_twin.simulation.monte_carlo import MIN_SCENARIOS, ShockParams
from digital_twin.simulation.policy import comparator_restock_threshold

from uplift.contract import (
    DECISION_RULE_TEXT,
    OBJECTIVE_KPI,
    MetricContract,
    interval_verdict,
    outcome_for_verdict,
)
from uplift.fidelity import FidelityReport
from uplift.interfaces import (
    ARM_ROLES,
    ArmResult,
    ArmRole,
    ArmSpec,
    DecisionPolicy,
    HeadlineVerdict,
    KpiVector,
    Observation,
    Outcome,
    PolicyAction,
    Scenario,
    ScenarioRun,
    UpliftResult,
)
from uplift.interval import Interval, IntervalUnavailableError
from uplift.kpi import (
    DEFAULT_EMISSION_FACTOR_KG_PER_DELIVERY,
    AppliedDecisions,
    DeliveredOrder,
    KpiExtractor,
    committed_objective,
)
from uplift.persistence import save_runs
from uplift.uplift_floor import MIN_POWERED_REPLICATES, PoweredProof

logger = structlog.get_logger(__name__)

# The KpiVector field names, in declaration order, so aggregation stays in lock-step
# with the interface if a KPI is ever added/removed.
KPI_FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(KpiVector))

# The canonical name of the SYNAPSE consensus arm (``ConsensusArm.name`` default);
# result assembly identifies the consensus arm by this name. What it is compared against is
# decided by the arms' declared roles (:class:`~uplift.interfaces.ArmSpec`), never by being
# "every other arm" (AD-16, task 15.5).
DEFAULT_CONSENSUS_ARM: str = "consensus"

#: The prefix of a pooled comparator's recorded label: ``"pooled:"`` plus the sorted pooled
#: baseline-role arm names, comma-joined. A named comparator is recorded as its bare name, so
#: a reader can always tell which of the two contrasts an artifact measured (AD-16).
POOLED_COMPARATOR_PREFIX: Final[str] = "pooled:"

#: The headline recorded when NO interval could be estimated. Not a measurement: such a result
#: carries ``interval=None`` and ``headline_verdict=None``, and the artifact names the absence
#: in ``unavailable_reasons`` and is never proof-grade. Pinned by the artifact model, so a
#: headline can only ever be an interval's point or this sentinel -- never an unintervalled
#: number (I-7).
NO_ESTIMATE_HEADLINE: Final[float] = 0.0

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
    own Monte Carlo path realise a shock identically, save that the lead-time multiplier also
    reaches ``set_policy`` for structure 3's ``place_order`` (inert without a world; see below).
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
    # ── decision-quality-proof task 9.6 (R5.36) ───────────────────────────────────
    # THE BIAS THIS REMOVES. `start()` leaves `_restock_threshold` at its constructor
    # default of 50.0, so a compared `(s, S)` policy reaching the twin through this
    # harness was measured STACKED ON TOP OF the twin's own endogenous `(s, S)`
    # restock. That biases regret toward zero independently of whether the world is
    # easy -- and a null result would then be uninterpretable in exactly the way this
    # phase exists to prevent.
    #
    # The value is READ from `digital_twin/simulation/policy.yaml`, never inlined
    # (AD-13), and the resolved value is recorded so a run whose recorded threshold
    # differs from the committed one is inadmissible.
    # Task 13.1: the shock's lead-time multiplier must also reach `place_order`, or structure 3
    # never sees a shock. Byte-identical with structure 3 off: `_lead_time_mult` is read only by
    # `_restock` (never draws at threshold 0.0) and, structure 3 on, by `place_order` and
    # `arrival_time_for`. The pick-pack mapping above is kept unchanged.
    sim.set_policy(
        restock_threshold=comparator_restock_threshold(),
        lead_time_mult=shock.lead_time_multiplier,
    )
    if scenario.cold_start:
        _apply_cold_start(sim)
    return sim


def _apply_cold_start(sim: SupplyChainSimulation) -> None:
    """Zero the twin's initial stock for the cold-start-city scenario.

    ``SupplyChainSimulation.start`` warms every canonical SKU to 100 units / full
    freshness; the cold-start-city scenario models a brand-new city with no warm
    history. The engine exposes no public "empty" lever, so this reaches the engine's
    inventory/freshness maps directly. Kept as a single, documented seam.

    **decision-quality-proof task 9.6 -- this used to `.clear()` the inventory dict, and
    that became wrong the moment a stockout started costing something.** A brand-new city
    still *stocks* these SKUs; it simply has none of them yet. Those are different facts:

    * levels zeroed, keys kept  -> demand names a SKU, finds it at zero, and every event is
      correctly recorded as unmet demand. `stockout_rate` -> 1.0, which is the truth.
    * keys deleted              -> `_draw_demanded_sku` has nothing to draw, no demand event
      is recorded at all, and `demand_events == 0` makes BOTH `fill_rate` and
      `stockout_rate` report 0.0 -- a scenario in which every order fails, reporting a
      stockout rate of zero.

    The second reading is the insensitive-instrument failure this whole phase exists to
    prevent, and it was invisible before task 9.1 because a stockout cost nothing either way.
    An empty *catalogue* is still distinct from empty *stock*, and the engine keeps that
    distinction: `WorldRuntime` passes an empty mapping for a genuinely absent world, and
    nothing is demanded of a catalogue that does not exist.

    Freshness IS cleared: there is no stock on the shelf to spoil, so accruing spoilage
    against an empty shelf would manufacture waste that did not happen.
    """
    try:
        for sku in list(sim._inventory):  # noqa: SLF001 — no public lever to empty stock
            sim._inventory[sku] = 0.0  # noqa: SLF001
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


def _apply_reorders(sim: SupplyChainSimulation, reorder_quantities: Mapping[str, float]) -> None:
    """Apply per-SKU reorder quantities to the twin via ``place_order`` (R2.2 mapping).

    decision-quality-proof task 13.1 (finding 66): orders go through ``place_order``, which IS
    ``add_stock`` whenever structure 3 is off -- and it is off in every twin this harness builds
    today, because ``_build_twin`` passes no world -- so every seeded expectation is unchanged.
    With structure 3 on, the stock lands after its supplier's lead time instead of at once: the
    delay lives where arms order, rather than in an engine loop the comparator switches off.

    The annotation is the one ``mypy --strict`` had been asking for at this signature (it
    was one of the seven pre-existing ``uplift/`` errors, in a tree CI's mypy scope never
    reads). Typed at the declaration rather than silenced at the call sites, which is the
    direction conflict F settled. ``Mapping[str, float]`` is what
    ``PolicyAction.reorder_quantities`` declares; the defensive conversion below stays,
    because a policy that violates its own contract at runtime should be skipped per SKU
    rather than crash a whole replicate.
    """
    for sku, qty in reorder_quantities.items():
        try:
            quantity = float(qty)
        except (TypeError, ValueError):
            continue
        if math.isfinite(quantity) and quantity > 0.0:
            sim.place_order(str(sku), quantity)


def observe(
    sim: SupplyChainSimulation,
    *,
    unit_costs: Mapping[str, float],
    active_shock: ShockParams | None = None,
) -> Observation:
    """Snapshot twin state as the :class:`Observation` a ``DecisionPolicy`` decides on.

    **Extracted so there is exactly ONE construction site.** ``run_closed_loop`` built this
    inline, and session 5's three-pass comparator needs the identical snapshot for its
    ``(s, S)`` reference arm. Two implementations of "what a policy is allowed to see" would
    drift, and the arm that drifted would be the one the whole of checkpoint A is about --
    an arm observing a different world is not the arm R5.1 names, however transparent its
    rule is.
    """
    metrics = sim.metrics
    return Observation(
        inventory={sku: int(level) for sku, level in sim.inventory.items()},
        sim_time=sim.sim_time_min,
        delivery_count=int(metrics.orders_delivered),
        spoilage_count=int(metrics.orders_spoiled),
        stockout_count=int(metrics.unmet_demand_events),
        unit_costs=unit_costs,
        active_shock=active_shock,
        # decision-quality-proof task 13.1: what a real planner also knows. With no world,
        # `on_order`, `supplier_lead_time_history` and `sku_supplier` are empty and
        # `start_weekday` is None; `demand_to_date` counts demand in every world. An arm that
        # ignores all five decides exactly as it did before they existed.
        on_order=sim.on_order,
        supplier_lead_time_history=sim.supplier_lead_time_history,
        demand_to_date=sim.demand_to_date,
        sku_supplier=sim.sku_supplier,
        start_weekday=sim.start_weekday,
    )


def _apply_action(
    sim: SupplyChainSimulation,
    action: PolicyAction,
    reference_price: float,
    current_price: float | None,
) -> float | None:
    """Apply a :class:`PolicyAction`'s twin levers; return the (possibly updated) price.

    Concrete twin levers are actuated here: ``price`` -> demand elasticity + margin
    bookkeeping (the returned ``current_price`` carries the latest applied price for the
    margin accumulator), and ``reorder_quantities`` -> ``place_order``, which IS ``add_stock``
    while structure 3 is off (:func:`_apply_reorders`). ``routing_assignment``
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
    ever fabricated (R2.7). That includes an objective the extractor refuses
    (:class:`~uplift.kpi.ObjectiveUnavailableError`): a replicate with no admissible cost is a
    failed replicate, never a zero-cost one.

    **The objective is read once per process, not per replicate (task 29.4).** The extractor is
    handed :func:`~uplift.kpi.committed_objective`, which reads ``policy.yaml`` through
    ``uplift.regret.load_objective`` on first use in each process and returns the same object
    thereafter. This signature is unchanged on purpose: ``uplift/cost_probe.py`` calls it with
    five positional arguments.
    """
    try:
        sim = _build_twin(scenario, seed)
        unit_costs = _derive_unit_costs()
        reference_price = _mean_unit_cost(unit_costs)
        active_shock = scenario.shock if scenario.shock != _NEUTRAL_SHOCK else None
        extractor = KpiExtractor(emission_factor, objective=committed_objective())

        current_price: float | None = None
        delivered_orders: list[DeliveredOrder] = []
        prev_delivered = int(sim.metrics.orders_delivered)

        for _ in range(loop_config.n_steps):
            obs = observe(sim, unit_costs=unit_costs, active_shock=active_shock)

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
            # ── decision-quality-proof task 9.6 (R5.38) ─────────────────────────
            # DELETED from here: `unmet_demand_events += sum(1 for level in
            # sim.inventory.values() if level <= 0.0)`. That was a per-STEP count of
            # SKUs sitting at zero, so its numerator scaled with `n_steps * |SKU|`
            # until `_clamp_fraction` saturated it -- a number about the shape of the
            # run rather than about unmet demand, and one that counted the same
            # standing stockout once per step.
            #
            # The twin now counts unmet demand at the point it occurs, per demand
            # event, which is what `uplift/kpi.py:85-86` already documented. Read
            # once after the loop rather than accumulated here, because the engine's
            # counter is already cumulative and adding to it per step would
            # double-count.

        applied = AppliedDecisions(
            delivered_orders=tuple(delivered_orders),
            unmet_demand_events=int(sim.metrics.unmet_demand_events),
            demand_events=int(sim.metrics.demand_events),
            delivered_volume=float(sim.metrics.orders_delivered),
        )
        kpis = extractor.extract(sim.metrics, applied, sim_time_min=sim.sim_time_min)
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

    **Order-independent by construction (R2.5).** The completed runs are sorted by seed
    before aggregation. ``numpy`` sums in list order and floating-point pairwise
    summation is *not* order-invariant, so aggregating in arrival order would make the
    KPI mean/std depend on worker scheduling — two processes replaying the identical
    seed set could then differ in the low bits and the arm aggregates would not be
    byte-comparable. Sorting by seed removes that dependence entirely.
    """
    completed = sorted(
        (r for r in runs if not r.failed and r.kpis is not None),
        key=lambda run: (run.seed, run.arm),
    )
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

    ``arm_roles`` maps every registered arm to the role it declared (AD-16, task 15.5).
    Construction REFUSES an arm with no declared role, a role for an arm that is not
    registered, an inadmissible role, and two arms with one name -- because the comparator is
    resolved from these roles, and a guessed role is how an oracle used to be pooled.
    """

    arm_results: dict[tuple[str, str], ArmResult]
    runs_by_pair: dict[tuple[str, str], list[ScenarioRun]]
    all_runs: list[ScenarioRun]
    results_path: Path | None
    scenarios: tuple[Scenario, ...]
    arm_names: tuple[str, ...]
    arm_roles: Mapping[str, ArmRole]

    def __post_init__(self) -> None:
        duplicated = sorted({arm for arm in self.arm_names if self.arm_names.count(arm) > 1})
        if duplicated:
            raise ValueError(
                f"arms {duplicated} are registered more than once; two arms with one name "
                "would share one (scenario, arm) record and silently overwrite each other"
            )
        undeclared = sorted(set(self.arm_names) - set(self.arm_roles))
        stray = sorted(set(self.arm_roles) - set(self.arm_names))
        if undeclared or stray:
            raise ValueError(
                f"every registered arm must declare exactly one role and no role may name an "
                f"unregistered arm: undeclared={undeclared}, unregistered={stray}. A missing "
                "role is refused rather than defaulted (AD-16)"
            )
        invalid = {arm: role for arm, role in self.arm_roles.items() if role not in ARM_ROLES}
        if invalid:
            raise ValueError(
                f"inadmissible arm roles {invalid}; the admissible roles are {list(ARM_ROLES)}"
            )
        self.arm_roles = dict(self.arm_roles)

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
# Arm registration (AD-16, task 15.5)
# ---------------------------------------------------------------------------
def registered_roles(arms: Sequence[ArmSpec]) -> dict[str, ArmRole]:
    """Each registered arm's declared role, keyed by arm name -- or a refusal.

    The one place a run's arm list becomes its role map, shared by :meth:`UpliftHarness.run`
    and the CLI's reduced-cost path so the two cannot disagree about what registration means.
    Refuses an arm passed without a role (a bare ``DecisionPolicy`` is not a registration) and
    two arms with one name.

    Raises:
        ValueError: On an entry that is not an :class:`~uplift.interfaces.ArmSpec`, or a
            duplicated arm name.
    """
    roles: dict[str, ArmRole] = {}
    for spec in arms:
        if not isinstance(spec, ArmSpec):
            raise ValueError(
                f"arm {getattr(spec, 'name', spec)!r} was registered without a role. Register "
                "it as ArmSpec(policy, role) with role one of "
                f"{list(ARM_ROLES)}; a missing role is refused, never defaulted (AD-16)"
            )
        if spec.name in roles:
            raise ValueError(f"arm {spec.name!r} is registered more than once")
        roles[spec.name] = spec.role
    return roles


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
        arms: Iterable[ArmSpec],
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

        Every arm is an :class:`~uplift.interfaces.ArmSpec` declaring its role; the roles are
        resolved BEFORE any replicate runs, so a missing role costs no twin work (AD-16).
        """
        scenario_list = list(scenarios)
        arm_list = list(arms)
        roles = registered_roles(arm_list)

        arm_results: dict[tuple[str, str], ArmResult] = {}
        runs_by_pair: dict[tuple[str, str], list[ScenarioRun]] = {}
        all_runs: list[ScenarioRun] = []

        for scenario in scenario_list:
            for spec in arm_list:
                runs = self._run_arm_runs(
                    scenario, spec.policy, n_per_arm, parallel=parallel
                )
                pair = (scenario.name, spec.name)
                runs_by_pair[pair] = runs
                arm_results[pair] = aggregate_arm(spec.name, runs)
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
            arm_names=tuple(spec.name for spec in arm_list),
            arm_roles=roles,
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
            # Collected in *submission* (i.e. seed) order rather than completion order,
            # so the recorded run sequence — and therefore the persisted runs file and
            # the arm aggregates derived from it — does not depend on worker scheduling
            # (R2.5 byte-comparability). Every future is awaited either way.
            runs.extend(future.result() for future in futures)
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


def _refuse_ambiguous_arm_name(arm: str) -> None:
    """Refuse an arm name a recorded comparator label could not state unambiguously."""
    if not arm or "," in arm or arm.startswith(POOLED_COMPARATOR_PREFIX):
        raise ValueError(
            f"arm name {arm!r} cannot be recorded in a comparator label: it is empty, contains "
            f"',', or starts with {POOLED_COMPARATOR_PREFIX!r}"
        )


def comparator_label(baseline_arm: str | None, baseline_arms: Sequence[str]) -> str:
    """The recorded name of the comparator a contrast measured against (AD-16).

    A named comparator is recorded as its bare name; a pooled one as
    :data:`POOLED_COMPARATOR_PREFIX` plus the sorted pooled arm names, comma-joined. The two
    forms cannot be confused, so an artifact always says which contrast it measured -- the
    pooled default is RECORDED as a pool, never left implicit.
    """
    for arm in baseline_arms:
        _refuse_ambiguous_arm_name(arm)
    if baseline_arm is not None:
        return baseline_arm
    return POOLED_COMPARATOR_PREFIX + ",".join(sorted(baseline_arms))


def _resolve_baseline_arms(
    harness_result: HarnessResult,
    consensus_arm: str,
    baseline_arm: str | None,
) -> list[str]:
    """Resolve which arm(s) form the comparator the subject arm is compared against.

    The subject is identified *by name* (``consensus_arm``, the ``ConsensusArm.name`` default
    ``"consensus"``; the positive control names the oracle here instead). AD-16 / task 15.5:

    * **A named comparator is never pooled.** ``baseline_arm`` returns exactly
      ``[baseline_arm]``, whatever role it declared -- naming is the explicit contrast. It is
      refused if it is not a registered arm, or if it IS the subject (a contrast of an arm with
      itself is identically zero and can only ever report a null).
    * **Pooling absorbs only declared baselines.** With no named comparator, the comparator is
      every arm whose declared role is ``"baseline"``, other than the subject. An ``oracle`` or
      ``excluded`` arm is NEVER absorbed, so the pooled default means "every arm declared a
      baseline", which is what it always claimed to mean. An empty pool is refused rather than
      compared against nothing.

    Raises:
        ValueError: On a subject arm that is not registered, a named comparator that is
            unregistered or is the subject, or a pool with no baseline-role arm in it.
    """
    if consensus_arm not in harness_result.arm_names:
        # Refused rather than read as "no replicate completed": an unregistered subject has no
        # runs at all, so assembly would otherwise report an incomplete contrast for a run that
        # never named the arm it claims to measure (finding 97).
        raise ValueError(
            f"the subject arm {consensus_arm!r} is not a registered arm "
            f"(registered: {list(harness_result.arm_names)}); a contrast cannot be measured for "
            "an arm the run never registered"
        )
    if baseline_arm is not None:
        if baseline_arm == consensus_arm:
            raise ValueError(
                f"the named comparator {baseline_arm!r} is the subject arm itself; a contrast "
                "of an arm with itself is zero by construction and measures nothing"
            )
        if baseline_arm not in harness_result.arm_names:
            raise ValueError(
                f"the named comparator {baseline_arm!r} is not a registered arm "
                f"(registered: {list(harness_result.arm_names)})"
            )
        return [baseline_arm]
    pooled = [
        arm
        for arm in harness_result.arm_names
        if arm != consensus_arm and harness_result.arm_roles[arm] == "baseline"
    ]
    if not pooled:
        raise ValueError(
            "the pooled comparator found no baseline-role arm other than the subject "
            f"{consensus_arm!r} (roles: {dict(harness_result.arm_roles)}); name one with "
            "baseline_arm= or register a baseline"
        )
    return pooled


def _objective_by_replicate(runs: Sequence[ScenarioRun]) -> dict[tuple[int, int], float]:
    """Each completed replicate's objective, keyed by ``(seed, occurrence of that seed)``.

    **Paired on SEED, never on list position (task 29.4).** Replicate ``i`` of every arm runs
    at ``replicate_seed(scenario.seed, i)`` and nothing else, so the seed is what identifies
    "the same demand realisation" across arms. The occurrence index only disambiguates the
    vanishingly rare case of two replicate indices deriving one 32-bit seed; it counts EVERY
    recorded run, failed ones included, so a failure upstream of a duplicate cannot shift
    which occurrence a later run is paired as.
    """
    seen: dict[int, int] = {}
    keyed: dict[tuple[int, int], float] = {}
    for run in runs:
        occurrence = seen.get(run.seed, 0)
        seen[run.seed] = occurrence + 1
        if not run.failed and run.kpis is not None:
            keyed[(run.seed, occurrence)] = float(run.kpis.objective)
    return keyed


def _paired_objectives(
    harness_result: HarnessResult,
    scenario_names: Sequence[str],
    subject: str,
    comparators: Sequence[str],
) -> tuple[list[float], list[float]]:
    """``(subject, comparator)`` objective samples, paired element by element on seed.

    For every scenario, only replicates that COMPLETED in the subject and in every comparator
    arm are paired. A named comparator contributes its own per-replicate objective; a pooled
    comparator contributes the per-replicate MEAN over its baseline-role arms (``fmean`` of
    one value is that value exactly). Pairs are emitted per scenario, in ascending key order.

    Raises:
        ValueError: On an empty comparator list -- there is nothing to pair against.
    """
    if not comparators:
        raise ValueError("cannot pair a subject against an empty comparator")
    subject_values: list[float] = []
    comparator_values: list[float] = []
    for scenario_name in scenario_names:
        subject_map = _objective_by_replicate(
            harness_result.runs_by_pair.get((scenario_name, subject), [])
        )
        comparator_maps = [
            _objective_by_replicate(harness_result.runs_by_pair.get((scenario_name, arm), []))
            for arm in comparators
        ]
        shared = set(subject_map)
        for comparator_map in comparator_maps:
            shared &= set(comparator_map)
        for key in sorted(shared):
            subject_values.append(subject_map[key])
            comparator_values.append(
                statistics.fmean(comparator_map[key] for comparator_map in comparator_maps)
            )
    return subject_values, comparator_values


def _pair_is_incomplete(
    harness_result: HarnessResult, scenario_name: str, arm: str
) -> bool:
    """True if the ``(scenario, arm)`` pair did not complete *every* replicate.

    A pair is incomplete when it recorded no runs at all, at least one **failed**
    replicate (a *partial* pair — some but not all replicates completed), or no
    completed replicate at all.

    R2.4 (zero completed replicates) and R2.5 (some but not all replicates completed —
    at least one failed replicate) are the same predicate here: in both cases the pair's
    surviving completed samples are not a trustworthy measurement of that arm on that
    scenario, so the pair must never be credited to SYNAPSE and resolves to
    ``TIE_INCONCLUSIVE`` while the run is marked incomplete (design C5).
    """
    runs = harness_result.runs_by_pair.get((scenario_name, arm), [])
    if not runs:
        return True
    if any(run.failed for run in runs):
        return True
    return not harness_result.completed_runs(scenario_name, arm)


def _run_is_incomplete(harness_result: HarnessResult) -> bool:
    """The WHOLE-RUN predicate: any registered arm failed to complete any scenario.

    Retained and reported as ``run_incomplete`` (task 15.5), but never read by the verdict:
    an oracle or excluded arm that failed a replicate makes the run incomplete without being
    any part of the consensus contrast. :func:`_contrast_is_incomplete` is what the verdict
    reads.
    """
    return any(
        _pair_is_incomplete(harness_result, scenario.name, arm)
        for scenario in harness_result.scenarios
        for arm in harness_result.arm_names
    )


def _contrast_is_incomplete(
    harness_result: HarnessResult,
    consensus_arm: str,
    baseline_arms: Sequence[str],
) -> bool:
    """True if the subject or any comparator arm failed to complete any scenario (R4.7).

    The CONTRAST predicate C60 reads through ``incomplete`` (task 15.5): a pair is incomplete
    when, for any scenario and any arm IN THIS CONTRAST, there is a failed run, no run at all,
    or no completed run. An arm outside the contrast -- an oracle, an excluded arm, or a
    baseline the named comparator did not choose -- cannot mark it incomplete.
    """
    return any(
        _pair_is_incomplete(harness_result, scenario.name, arm)
        for scenario in harness_result.scenarios
        for arm in (consensus_arm, *baseline_arms)
    )


def _estimate_interval(
    contract: MetricContract, subject: Sequence[float], comparator: Sequence[float]
) -> Interval | None:
    """The contract's ``1 - alpha`` interval on ``mean(comparator - subject)``, or ``None``.

    ``None`` is the honest state when no interval can be estimated (no paired replicate, a
    non-finite difference, an overflow, a degenerate bootstrap that does not bracket its own
    point): the caller then records no verdict, and the artifact names the absence (I-7).
    """
    try:
        return contract.interval(subject, comparator)
    except (IntervalUnavailableError, OverflowError) as error:
        logger.warning("uplift_interval_unavailable", reason=f"{type(error).__name__}: {error}")
        return None


def assemble_uplift_result(
    harness_result: HarnessResult,
    contract: MetricContract,
    *,
    fidelity: FidelityReport | None = None,
    consensus_arm: str = DEFAULT_CONSENSUS_ARM,
    baseline_arm: str | None = None,
) -> UpliftResult:
    """Assemble the :class:`~uplift.interfaces.UpliftResult` from a harness run (task 10.1).

    Applies the pre-registered metric contract's decision rule *exactly as declared* (R3.7).
    Under Metric_Contract v2 (task 29.4) that rule is the four-valued interval rule on the
    committed objective:

    * **The headline** is ``fmean`` over every paired ``(scenario, replicate)`` of
      ``comparator objective - subject objective`` -- objective units, positive means the
      subject is CHEAPER. It is computed ONCE, as the point of the contract's ``1 - alpha``
      paired interval (``uplift.interval``), and ``headline_uplift`` is set from
      ``interval.point``; nothing recomputes it. Replicates are paired on SEED
      (:func:`_paired_objectives`), never on list position. **An incomplete contrast has no
      headline**: no interval, no verdict, and the no-estimate sentinel, because its surviving
      replicates are the self-selected sample the per-scenario rule already refuses.
    * **The headline verdict** is :func:`uplift.contract.interval_verdict` of that interval
      against the contract's materiality margin; ``per_kpi`` maps it onto ``Outcome``.
    * **The per-(scenario, KPI) grid** classifies each scenario with the same interval rule
      over that scenario's pairs (R4.3), with no outcome-based filtering (R4.4).

    The comparator is resolved by :func:`_resolve_baseline_arms`: a named ``baseline_arm`` is
    used alone; otherwise only declared ``baseline``-role arms are pooled, per replicate (AD-16).
    ``incomplete`` is :func:`_contrast_is_incomplete` -- the subject and the comparator arms
    only -- so a failed oracle replicate cannot break the consensus verdict; the whole-run
    predicate is reported as ``run_incomplete``. An affected scenario pair is *never* credited
    to SYNAPSE: it resolves to ``TIE_INCONCLUSIVE`` and marks the contrast incomplete (R4.7).
    Every non-primary KPI is labelled secondary (R3.8); the all-wins self-scrutiny warning is
    emitted iff every classified pair is ``SYNAPSE_WINS`` (R4.5). The
    :class:`~uplift.fidelity.FidelityReport` is attached so the headline carries its KL
    value, threshold comparison, and confidence annotation (R5.2/R5.6); when no report is
    supplied it is read from the live C34 gauge.

    Raises:
        ValueError: If the comparator cannot be resolved (see :func:`_resolve_baseline_arms`).
    """
    scenario_names = [scenario.name for scenario in harness_result.scenarios]
    baseline_arms = _resolve_baseline_arms(harness_result, consensus_arm, baseline_arm)
    comparator = comparator_label(baseline_arm, baseline_arms)
    kpi = contract.objective_kpi

    incomplete = _contrast_is_incomplete(harness_result, consensus_arm, baseline_arms)
    run_incomplete = _run_is_incomplete(harness_result)

    # R4.3 / R4.4: classify every (scenario, primary KPI) pair exactly once, with no
    # outcome-based filtering.
    #
    # R2.4 / R2.5 / R4.7 (design C5): a pair is *affected* when the subject arm or any
    # comparator arm did not complete every replicate for that scenario — zero completed
    # replicates (R2.4) **or** some-but-not-all replicates completed, i.e. at least one
    # failed replicate (R2.5). An affected pair is never credited to SYNAPSE: it resolves to
    # TIE_INCONCLUSIVE and marks the contrast incomplete, rather than being classified over
    # the surviving completed samples (which could otherwise report SYNAPSE_WINS off a
    # partial, self-selected sample).
    per_scenario: dict[tuple[str, str], Outcome] = {}
    for scenario_name in scenario_names:
        affected = any(
            _pair_is_incomplete(harness_result, scenario_name, arm)
            for arm in (consensus_arm, *baseline_arms)
        )
        subject, paired = _paired_objectives(
            harness_result, [scenario_name], consensus_arm, baseline_arms
        )
        if affected or not subject:
            per_scenario[(scenario_name, kpi)] = Outcome.TIE_INCONCLUSIVE
            incomplete = True
        else:
            per_scenario[(scenario_name, kpi)] = contract.classify(subject, paired, kpi)

    # The headline: ONE interval over every paired replicate, and everything else read off it.
    #
    # NO HEADLINE ON AN INCOMPLETE CONTRAST (R2.4, R2.5, R4.7), and the reason is the per-scenario
    # rule above, applied once more at the level it was missing from. A scenario whose subject or
    # comparator lost a replicate is never classified over its surviving replicates, because those
    # are a self-selected sample. Pooling those same survivors into the headline would re-admit,
    # through the headline, the sample the grid refuses. It could also render `verdict: win` beside
    # `incomplete: true`. So an incomplete contrast records no interval and no verdict, and its
    # headline is the no-estimate sentinel. The artifact names both absences, and the per-arm
    # aggregates still carry every completed replicate as description (I-7). Finding 96.
    subject_all, paired_all = _paired_objectives(
        harness_result, scenario_names, consensus_arm, baseline_arms
    )
    interval = (
        _estimate_interval(contract, subject_all, paired_all)
        if subject_all and not incomplete
        else None
    )
    headline_verdict: HeadlineVerdict | None = (
        contract.verdict(interval) if interval is not None else None
    )
    headline_uplift = interval.point if interval is not None else NO_ESTIMATE_HEADLINE
    per_kpi: dict[str, Outcome] = {
        kpi: (
            outcome_for_verdict(headline_verdict)
            if headline_verdict is not None
            else Outcome.TIE_INCONCLUSIVE
        )
    }

    # R3.8: every reported KPI that is not a declared primary KPI is labelled secondary
    # (set difference over the KpiVector fields guarantees no KPI is labelled both).
    secondary_kpis = [field for field in KPI_FIELDS if field not in contract.primary_kpis]

    # R4.5: warn iff every classified pair is SYNAPSE_WINS (an empty grid never warns).
    all_wins_warning = bool(per_scenario) and all(
        outcome is Outcome.SYNAPSE_WINS for outcome in per_scenario.values()
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
        interval=interval,
        headline_verdict=headline_verdict,
        materiality_margin=contract.materiality_margin,
        comparator=comparator,
        run_incomplete=run_incomplete,
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
    """An uplift number co-located with its interval, verdict and fidelity context.

    Every uplift number the harness surfaces is rendered through this report so no
    number is ever presented without its context: the ``1 - alpha`` interval and the
    four-valued verdict it licenses against the materiality margin (R7.14, R7.19), the
    comparator it was measured against (AD-16), the KL-divergence value, its comparison to
    the C34 re-sync threshold, the resulting confidence annotation, and the fixed statement
    that the number's validity is bounded by twin fidelity (R5.2/R5.6).
    """

    headline_uplift: float
    primary_kpi: str
    kl_divergence: float | None
    threshold: float
    within_fidelity_bound: bool | None
    confidence: str
    fidelity_bound_statement: str
    interval: Interval | None
    headline_verdict: HeadlineVerdict | None
    materiality_margin: float
    comparator: str

    def render(self) -> str:
        """Render the uplift number and its full context as co-located text (R5.6, R7.14).

        ASCII only (E-S13-07). The headline is in objective units under Metric_Contract v2:
        it is a cost difference, comparator minus subject, never a percentage.
        """
        if self.kl_divergence is None:
            kl = "unavailable"
            comparison = "unavailable"
        else:
            kl = f"{self.kl_divergence:.6f}"
            comparison = (
                "<= threshold" if self.within_fidelity_bound else "> threshold"
            )
        if self.interval is None:
            interval_line = (
                "interval: unavailable -- no interval was estimated, so the headline is not "
                "a measurement and no verdict is reported"
            )
        else:
            interval_line = f"interval: {self.interval.describe()}"
        verdict = self.headline_verdict if self.headline_verdict is not None else "unavailable"
        return (
            f"headline uplift: {self.headline_uplift:+.4f} objective units "
            f"(primary KPI: {self.primary_kpi}; comparator: {self.comparator}; "
            "positive = subject cheaper)\n"
            f"{interval_line}\n"
            f"verdict: {verdict} (materiality margin {self.materiality_margin:.6g} objective "
            f"units; {DECISION_RULE_TEXT})\n"
            f"twin KL divergence: {kl} "
            f"(C34 re-sync threshold {self.threshold:.6f}; {comparison})\n"
            f"fidelity confidence: {self.confidence}\n"
            f"{self.fidelity_bound_statement}"
        )


def build_uplift_report(
    result: UpliftResult, *, primary_kpi: str | None = None
) -> UpliftReport:
    """Build the co-located :class:`UpliftReport` for an assembled result (R5.6, R7.14).

    Pairs ``result.headline_uplift`` with its interval, verdict, comparator and
    :class:`~uplift.fidelity.FidelityReport` so the reported number carries all of them, and
    the fixed fidelity-bound statement, in one place.
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
        interval=result.interval,
        headline_verdict=result.headline_verdict,
        materiality_margin=result.materiality_margin,
        comparator=result.comparator,
    )


# ---------------------------------------------------------------------------
# Run provenance + the canonical result artifact
# (purpose-achievement-audit task 10.1 — distinct from the "task 10.1" of the earlier
#  core-purpose-uplift spec referenced by the result-assembly section above)
#
# R2.3  a completed powered run writes an artifact carrying ``incomplete: false``, a
#       finite numeric ``headline_uplift``, a numeric ``kl_divergence``, a boolean
#       ``within_fidelity_bound``, the replicates-per-arm count, and a provenance
#       record naming the run identifier, the source revision, the seed set, and the
#       arm identifiers.
# R2.5  two runs of the same seed set produce byte-identical arm KPI aggregates.
# R2.8  the gate can compare a stored provenance record against the run it performed.
#
# ADR-054 D5 note. Uplift measured *before* and *after* the dispatch choke point
# (tasks 8.5 / 8.7) is not comparable: the choke point changes what the system
# dispatches, so it changes the KPIs the consensus arm produces. ``revision`` is the
# field that carries that discontinuity — an artifact whose ``revision`` predates the
# choke-point commit is evidence about a different decision apparatus, and the powered
# baseline must be re-measured after 8.5/8.7 rather than compared across the boundary.
# ---------------------------------------------------------------------------

#: The honest sentinel recorded when the source revision or run identifier cannot be
#: resolved from the environment. The repository already uses ``"unknown"`` this way
#: (``scripts/deploy/verify_live.py`` treats ``""``/``"dev"``/``"unknown"`` as "not a
#: CD build"): we record that the attribution is unknown rather than inventing one
#: (I-7). An artifact carrying this sentinel can never satisfy R2.8's provenance
#: match, so it is structurally inadmissible as proof — see
#: :attr:`UpliftProvenance.is_attributed`.
UNATTRIBUTED: Final[str] = "unknown"

#: Environment variables consulted for the source revision, in priority order.
_REVISION_ENV_KEYS: Final[tuple[str, ...]] = ("SYNAPSE_REVISION", "GITHUB_SHA")

#: Environment variables consulted for the run identifier, in priority order.
_RUN_ID_ENV_KEYS: Final[tuple[str, ...]] = ("SYNAPSE_RUN_ID", "GITHUB_RUN_ID")


def canonical_json(payload: object) -> str:
    """Canonical JSON: sorted keys, tight separators — the repo-wide convention.

    ``json.dumps(obj, sort_keys=True, separators=(',',':'))`` is the serialisation
    every persisted SYNAPSE payload uses (``orchestrator/audit/models.py``,
    ``packages/synapse_common/audit_chain.py``). Key order and whitespace are the two
    ways an otherwise identical payload can differ byte-wise; fixing both is what makes
    two runs of the same seed set byte-comparable (R2.5) instead of merely equal after
    parsing.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _utc_now() -> str:
    """ISO-8601 UTC to the second, ``Z``-suffixed (matches ``coverage_ratchet``)."""
    return (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _from_env(keys: Sequence[str]) -> str | None:
    for key in keys:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


class UpliftProvenance(BaseModel):
    """Who ran what, on which revision, over which seeds (R2.3, R2.8).

    Attributes:
        arms: The arm identifiers compared, sorted so the record is canonical.
        arm_roles: The role each registered arm DECLARED (AD-16, task 15.5), so a reader
            can see which arms a pooled comparator was allowed to absorb and that an oracle
            was not among them. Required: a provenance record that cannot say what each arm
            was for cannot say what its comparator was.
        replicates_per_arm: Replicates each arm ran (power evidence, INV-TW-002).
        revision: The source revision the harness ran at, or :data:`UNATTRIBUTED`.
        run_id: The run the measurement was taken in, or :data:`UNATTRIBUTED`.
        seeds: The scenario base seed *set*, sorted and de-duplicated. The full
            replicate seed sequence is reconstructible from this set: replicate ``i``
            of every arm uses :func:`replicate_seed(base, i)`, which depends on nothing
            else (the attribution guarantee), so recording the base seeds plus
            ``replicates_per_arm`` fixes every seed the run used.
        written_at: ISO-8601 UTC instant the artifact was written.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    arms: tuple[str, ...]
    arm_roles: dict[str, ArmRole]
    replicates_per_arm: int = Field(ge=0)
    revision: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    seeds: tuple[int, ...]
    written_at: str = Field(min_length=1)

    @field_validator("arms")
    @classmethod
    def _canonical_arms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Sort the arm identifiers; the consensus arm is identified by name, never
        by position, so ordering carries no information and sorting removes a way two
        otherwise identical runs could serialise differently (R2.5)."""
        return tuple(sorted(value))

    @field_validator("seeds")
    @classmethod
    def _canonical_seed_set(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        """Normalise to a sorted, de-duplicated *set* — R2.5/R2.8 compare seed sets."""
        return tuple(sorted(set(value)))

    @field_validator("arm_roles")
    @classmethod
    def _canonical_roles(cls, value: dict[str, ArmRole]) -> dict[str, ArmRole]:
        """Order the role map by arm name, as ``arms`` is sorted, so the in-memory record and
        its canonical serialisation agree and two runs cannot differ by insertion order."""
        return dict(sorted(value.items()))

    @model_validator(mode="after")
    def _every_arm_declares_one_role(self) -> UpliftProvenance:
        """Refuse a role map that does not cover exactly the recorded arms (AD-16).

        Every value is already one of :data:`~uplift.interfaces.ARM_ROLES`, because the
        ``ArmRole`` literal refuses any other. This checks the keys: an arm recorded with no
        role, or a role recorded for an arm the run did not register, is a comparator no reader
        can reconstruct.
        """
        undeclared = sorted(set(self.arms) - set(self.arm_roles))
        stray = sorted(set(self.arm_roles) - set(self.arms))
        if undeclared or stray:
            raise ValueError(
                "arm_roles must name exactly the recorded arms: "
                f"undeclared={undeclared}, unregistered={stray}"
            )
        return self

    @property
    def is_attributed(self) -> bool:
        """True iff both the revision and the run identifier were actually resolved.

        An unattributed record is honest (it says so) but can never match the run
        performed in an evaluating job, so R2.8 rejects it.
        """
        return self.revision != UNATTRIBUTED and self.run_id != UNATTRIBUTED

    def matches(self, other: "UpliftProvenance") -> bool:
        """True iff the revision, seed set, arm identifiers and arm roles agree (R2.8).

        Both records must be attributed: two ``"unknown"`` revisions are not an
        agreement, they are two absences of evidence. The roles are compared too (task
        15.5): the same arms registered in different roles resolve a different comparator,
        so the two records do not describe the same run.
        """
        return (
            self.is_attributed
            and other.is_attributed
            and self.revision == other.revision
            and self.seeds == other.seeds
            and self.arms == other.arms
            and self.arm_roles == other.arm_roles
        )

    def to_canonical_json(self) -> str:
        """Canonical serialisation of this record."""
        return canonical_json(self.model_dump(mode="json"))


def resolve_provenance(
    *,
    arms: Sequence[str],
    arm_roles: Mapping[str, ArmRole],
    replicates_per_arm: int,
    seeds: Sequence[int],
    revision: str | None = None,
    run_id: str | None = None,
    written_at: str | None = None,
) -> UpliftProvenance:
    """Build an :class:`UpliftProvenance`, recording absence rather than inventing it.

    ``revision`` falls back to ``$SYNAPSE_REVISION`` then ``$GITHUB_SHA``; ``run_id``
    to ``$SYNAPSE_RUN_ID`` then ``$GITHUB_RUN_ID``. When neither resolves, the field is
    recorded as :data:`UNATTRIBUTED` — the artifact then truthfully states that it
    cannot be attributed to a revision or a run, and R2.8 rejects it as proof, which is
    the honest outcome for a run taken outside a CI job (I-7). ``arm_roles`` is required
    and never inferred: it is what the run's arms DECLARED (``HarnessResult.arm_roles``).
    """
    return UpliftProvenance(
        arms=tuple(arms),
        arm_roles=dict(arm_roles),
        replicates_per_arm=replicates_per_arm,
        revision=(revision or "").strip() or _from_env(_REVISION_ENV_KEYS) or UNATTRIBUTED,
        run_id=(run_id or "").strip() or _from_env(_RUN_ID_ENV_KEYS) or UNATTRIBUTED,
        seeds=tuple(seeds),
        written_at=(written_at or "").strip() or _utc_now(),
    )


class ArmAggregate(BaseModel):
    """One ``(scenario, arm)`` KPI aggregate as persisted in the artifact (R2.5).

    This is the byte-comparable surface: every field is derived from the seeded twin
    runs, so two processes replaying the same seed set produce identical values, and
    :func:`canonical_arm_aggregates` serialises them identically.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario: str
    arm: str
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    kpi_mean: dict[str, float]
    kpi_std: dict[str, float]

    @field_validator("kpi_mean", "kpi_std")
    @classmethod
    def _finite_kpis(cls, value: dict[str, float]) -> dict[str, float]:
        for kpi, number in value.items():
            if not math.isfinite(number):
                raise ValueError(f"KPI aggregate {kpi!r} is not finite: {number!r}")
        return value

    def to_canonical_json(self) -> str:
        """Canonical serialisation of this aggregate."""
        return canonical_json(self.model_dump(mode="json"))


def arm_aggregates(harness_result: HarnessResult) -> tuple[ArmAggregate, ...]:
    """Project a run's per-``(scenario, arm)`` aggregates, sorted canonically (R2.5)."""
    return tuple(
        ArmAggregate(
            scenario=scenario,
            arm=arm,
            completed=aggregate.completed,
            failed=aggregate.failed,
            kpi_mean=dict(aggregate.kpi_mean),
            kpi_std=dict(aggregate.kpi_std),
        )
        for (scenario, arm), aggregate in sorted(
            harness_result.arm_results.items(), key=lambda item: item[0]
        )
    )


def canonical_arm_aggregates(aggregates: Sequence[ArmAggregate]) -> str:
    """Canonical serialisation of the arm KPI aggregates alone (R2.5).

    This is the string R2.5 compares: it excludes ``run_id`` and ``written_at``, the
    only two artifact fields that legitimately differ between two runs of the same seed
    set. Two OS processes replaying the same seeds must produce this string byte for
    byte — which is what task 10.6's cross-process property test asserts.
    """
    ordered = sorted(aggregates, key=lambda aggregate: (aggregate.scenario, aggregate.arm))
    return canonical_json([aggregate.model_dump(mode="json") for aggregate in ordered])


def arm_aggregates_digest(aggregates: Sequence[ArmAggregate]) -> str:
    """SHA-256 over :func:`canonical_arm_aggregates` — a one-line equality check."""
    return _digest(canonical_arm_aggregates(aggregates))


class ArtifactFidelity(BaseModel):
    """The fidelity block co-located with the headline number (R2.3, R5.2/R5.6).

    ``kl_divergence`` and ``within_fidelity_bound`` are ``None`` when fidelity was
    unavailable. R2.3 requires a *numeric* ``kl_divergence`` and a *boolean*
    ``within_fidelity_bound`` for a completed powered run; the nullable types are what
    keep an incomplete run honest instead of fabricating a measurement (I-7), and
    :attr:`UpliftArtifact.unavailable_reasons` names the absence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kl_divergence: float | None
    threshold: float
    confidence: str
    within_fidelity_bound: bool | None
    fidelity_bound_statement: str

    @field_validator("kl_divergence", "threshold")
    @classmethod
    def _finite(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError(f"fidelity value must be finite, got {value!r}")
        return value


#: The one :class:`UpliftArtifact` schema this module writes and reads (AD-15, tasks 15.1 and
#: 29.4). Version 2 carries the interval block, the four-valued verdict, the margin it was
#: judged against, the comparator and the whole-run completeness flag. Every other version is
#: REFUSED, never migrated: a version-1 headline was a fill-rate relative percentage and a
#: version-2 headline is a cost difference in objective units, so reading one as the other is
#: the unit confusion Metric_Contract v2 exists to remove.
ARTIFACT_SCHEMA_VERSION: Final[Literal[2]] = 2


class ArtifactInterval(BaseModel):
    """The headline's ``1 - alpha`` interval as persisted (R6.13, R7.14, AD-15).

    The SERIALISATION form of :class:`uplift.interval.Interval`, which is the computation form
    (design E3.1): the seven field names are the same, and :meth:`from_interval` copies them
    rather than recomputing anything. Admissibility is DELEGATED to ``Interval`` -- the
    validator rebuilds one -- so this model refuses exactly what the estimator's record refuses
    (a non-finite bound or point, ``low > high``, a point outside ``[low, high]``, fewer than
    one resample) and cannot drift from it. It also refuses a non-finite ``alpha``, the one
    field ``Interval`` leaves unchecked, because a non-finite number cannot survive the
    canonical JSON round trip R7.17 requires; the estimator never produces one.

    ``extra="forbid"``: an unknown key inside the block is a refusal, never a dropped field.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    method: str
    alpha: float
    resamples: int = Field(ge=1)
    seed: int
    low: float
    high: float
    point: float

    @model_validator(mode="after")
    def _admissible(self) -> ArtifactInterval:
        if not math.isfinite(self.alpha):
            raise ValueError(
                f"interval alpha={self.alpha!r} is not finite, so it names no confidence level "
                "and cannot survive the canonical round trip"
            )
        try:
            self.to_interval()
        except IntervalUnavailableError as error:
            raise ValueError(f"inadmissible interval: {error}") from error
        return self

    @classmethod
    def from_interval(cls, interval: Interval) -> ArtifactInterval:
        """The persisted form of an estimated interval: its seven fields, copied by name."""
        return cls.model_validate(interval.as_dict())

    def to_interval(self) -> Interval:
        """The computation form, so a reader re-derives a verdict from the record alone."""
        return Interval(
            method=self.method,
            alpha=self.alpha,
            resamples=self.resamples,
            seed=self.seed,
            low=self.low,
            high=self.high,
            point=self.point,
        )


class UpliftArtifact(BaseModel):
    """The persisted uplift result the C60 gate evaluates (R2.3), schema version 2 (AD-15).

    Construction enforces what R2.3 requires *of the artifact's shape*: a finite
    numeric ``headline_uplift``, a boolean ``incomplete``, the replicates-per-arm count
    agreeing with the provenance record, and an arm-aggregate digest that matches the
    aggregates it is stored beside. Version 2 (tasks 15.1, 15.5, 29.4) adds the
    ``1 - alpha`` :class:`ArtifactInterval`, the four-valued ``headline_verdict``, the
    ``materiality_margin`` it was judged against, the ``comparator`` and ``run_incomplete``,
    and construction pins them to one another:

    * the headline IS the interval's point, compared exactly -- one number stored once, not a
      second computation of it -- and with no interval it is :data:`NO_ESTIMATE_HEADLINE`;
    * an interval and a verdict are recorded together or not at all, and the stored verdict is
      RE-DERIVED from the interval and the margin by :func:`uplift.contract.interval_verdict`,
      so a verdict the rule does not produce is refused rather than believed;
    * the primary KPI is the committed objective, the margin is strictly positive and finite,
      and the comparator is named.

    What it deliberately does **not** enforce is that the run was complete, powered, and
    within the fidelity bound -- an artifact must be able to state honestly that it was not
    (I-7). :attr:`is_proof_grade` and :attr:`unavailable_reasons` are the predicates over that,
    and task 10.3's ``admit()`` is their gate-side caller. ``incomplete`` is the CONTRAST
    predicate; ``run_incomplete`` is recorded beside it and is never a reason, so a failed
    oracle replicate cannot break the consensus contrast it is not part of (task 15.5).

    The interval block never moves :attr:`arm_aggregates_digest`, which covers
    :func:`canonical_arm_aggregates` only -- the property that makes AD-15 affordable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal[2]
    headline_uplift: float
    primary_kpi: str
    noise_tolerance_pp: float
    incomplete: bool
    all_wins_warning: bool
    #: Mirrored from ``provenance.replicates_per_arm`` at the top level because that is
    #: where ``PoweredProof.from_payload`` looks (``uplift_floor._REPLICATE_KEYS``).
    replicates_per_arm: int = Field(ge=0)
    fidelity: ArtifactFidelity
    provenance: UpliftProvenance
    interval: ArtifactInterval | None
    headline_verdict: HeadlineVerdict | None
    materiality_margin: float
    comparator: str
    run_incomplete: bool
    arm_aggregates: tuple[ArmAggregate, ...] = ()
    arm_aggregates_digest: str = ""

    @field_validator("schema_version", mode="before")
    @classmethod
    def _version_two_only(cls, value: Any) -> Any:
        """Refuse every schema but version 2, saying why; nothing is migrated (AD-15)."""
        if type(value) is not int or value != ARTIFACT_SCHEMA_VERSION:
            raise ValueError(
                f"artifact schema_version {value!r} is not {ARTIFACT_SCHEMA_VERSION}: a "
                "version-1 headline was a fill-rate relative percentage with no interval, a "
                "version-2 headline is the committed objective's paired difference with its "
                "1 - alpha interval, and one is never read as the other"
            )
        return value

    @model_validator(mode="before")
    @classmethod
    def _derive_digest(cls, data: Any) -> Any:  # noqa: ANN401 — pydantic pre-validator
        """Fill an absent aggregate digest so callers cannot store an unstated one."""
        if not isinstance(data, dict) or data.get("arm_aggregates_digest"):
            return data
        raw = data.get("arm_aggregates") or ()
        try:
            parsed = tuple(
                item if isinstance(item, ArmAggregate) else ArmAggregate.model_validate(item)
                for item in raw
            )
        except Exception:  # noqa: BLE001 — let the field validators report the real error
            return data
        return {**data, "arm_aggregates_digest": arm_aggregates_digest(parsed)}

    @model_validator(mode="after")
    def _internally_consistent(self) -> "UpliftArtifact":
        if not math.isfinite(self.headline_uplift):
            raise ValueError(
                f"headline_uplift must be finite (R2.3), got {self.headline_uplift!r}"
            )
        if not math.isfinite(self.noise_tolerance_pp):
            raise ValueError(
                f"noise_tolerance_pp must be finite, got {self.noise_tolerance_pp!r}"
            )
        if self.replicates_per_arm != self.provenance.replicates_per_arm:
            raise ValueError(
                f"replicates_per_arm {self.replicates_per_arm} disagrees with the "
                f"provenance record's {self.provenance.replicates_per_arm}"
            )
        expected = arm_aggregates_digest(self.arm_aggregates)
        if self.arm_aggregates_digest != expected:
            raise ValueError(
                f"arm_aggregates_digest {self.arm_aggregates_digest!r} does not match "
                f"the stored aggregates (recomputed {expected!r})"
            )
        self._check_headline_contract()
        return self

    def _check_headline_contract(self) -> None:
        """The version-2 pins between the headline, its interval, its verdict and its margin.

        Raises:
            ValueError: On a primary KPI other than the objective, a margin that is not
                strictly positive and finite, an unnamed comparator, an interval without a
                verdict (or the reverse), a headline that is not the interval's point (or, with
                no interval, not the no-estimate sentinel), or a stored verdict the rule does
                not derive from the stored interval and margin.
        """
        if self.primary_kpi != OBJECTIVE_KPI:
            raise ValueError(
                f"primary_kpi must be {OBJECTIVE_KPI!r} under schema version "
                f"{ARTIFACT_SCHEMA_VERSION}, got {self.primary_kpi!r}: the committed objective "
                "is the sole primary KPI and every other KpiVector field is secondary (R7.19)"
            )
        if not math.isfinite(self.materiality_margin) or self.materiality_margin <= 0.0:
            raise ValueError(
                f"materiality_margin must be strictly positive and finite, got "
                f"{self.materiality_margin!r}: against no positive margin every gain is a win"
            )
        if not self.comparator.strip():
            raise ValueError(
                "comparator must name the arm, or the pool, the headline was measured against"
            )
        if (self.interval is None) != (self.headline_verdict is None):
            raise ValueError(
                "an interval and a verdict are recorded together or not at all: interval is "
                f"{'absent' if self.interval is None else 'present'}, headline_verdict is "
                f"{self.headline_verdict!r}"
            )
        if self.interval is None and self.headline_uplift != NO_ESTIMATE_HEADLINE:
            raise ValueError(
                f"with no interval the headline must be the no-estimate sentinel "
                f"{NO_ESTIMATE_HEADLINE!r}, got {self.headline_uplift!r}: a headline nobody "
                "intervalled is not a measurement (I-7)"
            )
        if self.interval is not None:
            if self.headline_uplift != self.interval.point:
                raise ValueError(
                    f"headline_uplift {self.headline_uplift!r} is not the interval's point "
                    f"{self.interval.point!r}: the headline is that point, stored once"
                )
            derived = interval_verdict(
                self.interval.low, self.interval.high, margin=self.materiality_margin
            )
            if self.headline_verdict != derived:
                raise ValueError(
                    f"stored headline_verdict {self.headline_verdict!r} is not what the rule "
                    f"derives from interval [{self.interval.low!r}, {self.interval.high!r}] "
                    f"against margin {self.materiality_margin!r}: {derived!r}"
                )

    # -- honest classification (I-7) ----------------------------------------
    @property
    def unavailable_reasons(self) -> tuple[str, ...]:
        """Every reason this artifact is not a completed, powered, in-bound proof.

        Empty iff :attr:`is_proof_grade`. Task 10.3's gate prints these verbatim so an
        ``EXIT_UNAVAILABLE`` always names why the measurement was treated as
        unavailable (R2.1, R2.2).
        """
        reasons: list[str] = []
        if self.incomplete:
            reasons.append(
                "contrast is incomplete: the subject or a comparator arm did not complete "
                "every replicate of at least one scenario"
            )
        if self.interval is None:
            reasons.append(
                "no interval was estimated: the headline carries no 1 - alpha interval and no "
                f"verdict, so its value {NO_ESTIMATE_HEADLINE!r} is a sentinel rather than a "
                "measurement (R6.13, R7.14)"
            )
        if self.replicates_per_arm < MIN_POWERED_REPLICATES:
            reasons.append(
                f"under-powered: {self.replicates_per_arm} replicates per arm recorded, "
                f"{MIN_POWERED_REPLICATES} required (INV-TW-002)"
            )
        if self.fidelity.kl_divergence is None:
            reasons.append("twin fidelity unavailable: no kl_divergence was recorded")
        if self.fidelity.within_fidelity_bound is not True:
            reasons.append(
                f"not within the twin fidelity bound: within_fidelity_bound="
                f"{self.fidelity.within_fidelity_bound!r}"
            )
        if not self.provenance.is_attributed:
            reasons.append(
                f"unattributed run: revision={self.provenance.revision!r}, "
                f"run_id={self.provenance.run_id!r}"
            )
        return tuple(reasons)

    @property
    def is_proof_grade(self) -> bool:
        """True iff this artifact satisfies every R2.3 condition for a powered proof."""
        return not self.unavailable_reasons

    # -- serialisation (the pure round-trip surface task 10.2 tests) --------
    def to_payload(self) -> dict[str, Any]:
        """The plain JSON-able mapping this artifact serialises to.

        :meth:`uplift.uplift_floor.PoweredProof.from_payload` consumes four keys of it:
        ``headline_uplift``, ``incomplete``, a top-level ``replicates_per_arm``, and
        ``fidelity.within_fidelity_bound``. It ignores the version-2 keys (``interval``,
        ``headline_verdict``, ``materiality_margin``, ``comparator``, ``run_incomplete``,
        ``schema_version``), so it reads none of the interval.
        """
        payload: dict[str, Any] = self.model_dump(mode="json")
        return payload

    def to_canonical_json(self) -> str:
        """Canonical serialisation — sorted keys, tight separators (R2.5).

        Byte-stable for a fixed value, so two artifacts are equal iff their canonical
        strings are equal. The only fields that legitimately differ between two runs of
        the same seed set are ``provenance.run_id`` and ``provenance.written_at``;
        compare :func:`canonical_arm_aggregates` (or
        :attr:`arm_aggregates_digest`) when those must be excluded.
        """
        return canonical_json(self.to_payload())

    @classmethod
    def from_canonical_json(cls, text: str) -> "UpliftArtifact":
        """Parse an artifact from JSON text. Inverse of :meth:`to_canonical_json`.

        ``from_canonical_json(a.to_canonical_json()) == a`` and the round trip is
        idempotent at the byte level:
        ``from_canonical_json(s).to_canonical_json() == s`` for any canonical ``s``
        this class produced (Property 14).
        """
        return cls.model_validate(json.loads(text))

    def as_powered_proof(self) -> PoweredProof | None:
        """Build the :class:`~uplift.uplift_floor.PoweredProof` for this artifact.

        Delegates to :meth:`PoweredProof.from_payload` over :meth:`to_payload` so the
        harness and the gate read the artifact through one implementation. Returns
        ``None`` only when the payload cannot evidence its own power at all; a powered
        proof that is merely *unproven* is returned and rejected downstream by
        :func:`~uplift.uplift_floor.is_proven_uplift`.
        """
        return PoweredProof.from_payload(self.to_payload())

    def write(self, path: str | Path) -> Path:
        """Write the canonical serialisation to ``path`` and return it.

        The file bytes are exactly :meth:`to_canonical_json` — no indentation and no
        trailing newline — so two runs of the same seed set at the same revision
        produce byte-identical files, and a diff of two artifacts is a diff of their
        measurements rather than of their formatting.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_canonical_json(), encoding="utf-8")
        logger.info(
            "uplift_artifact_written",
            path=str(target),
            schema_version=self.schema_version,
            headline_uplift=self.headline_uplift,
            headline_verdict=self.headline_verdict,
            comparator=self.comparator,
            incomplete=self.incomplete,
            run_incomplete=self.run_incomplete,
            replicates_per_arm=self.replicates_per_arm,
            revision=self.provenance.revision,
            run_id=self.provenance.run_id,
            arm_aggregates_digest=self.arm_aggregates_digest,
            proof_grade=self.is_proof_grade,
        )
        return target

    @classmethod
    def read(cls, path: str | Path) -> "UpliftArtifact":
        """Read an artifact from ``path`` (``encoding='utf-8'``, E-S13-07)."""
        return cls.from_canonical_json(Path(path).read_text(encoding="utf-8"))


def build_uplift_artifact(
    result: UpliftResult,
    report: UpliftReport,
    provenance: UpliftProvenance,
    *,
    noise_tolerance_pp: float,
    harness_result: HarnessResult | None = None,
) -> UpliftArtifact:
    """Assemble the persisted :class:`UpliftArtifact` for a completed run (R2.3, AD-15).

    ``provenance`` supplies the replicates-per-arm count, so the artifact's top-level
    ``replicates_per_arm`` and its provenance record can never disagree.
    ``noise_tolerance_pp`` is passed in rather than imported so this module keeps a
    single source of truth for that committed constant (it lives in
    :data:`uplift.cli.NOISE_TOLERANCE_PP`). When ``harness_result`` is supplied the
    per-``(scenario, arm)`` KPI aggregates are recorded and digested, giving R2.5 its
    byte-comparable surface; without it the aggregates are empty and the artifact
    carries the digest of an empty set rather than an unstated one.

    Schema version 2: the interval (through :meth:`ArtifactInterval.from_interval`), the
    headline verdict, the materiality margin, the comparator and ``run_incomplete`` are COPIED
    from ``result``, never recomputed here, so the artifact's construction-time pins check the
    assembly's own numbers against one another.
    """
    fidelity = result.fidelity
    aggregates = arm_aggregates(harness_result) if harness_result is not None else ()
    interval = (
        ArtifactInterval.from_interval(result.interval) if result.interval is not None else None
    )
    return UpliftArtifact(
        schema_version=ARTIFACT_SCHEMA_VERSION,
        headline_uplift=float(result.headline_uplift),
        primary_kpi=report.primary_kpi,
        noise_tolerance_pp=float(noise_tolerance_pp),
        incomplete=bool(result.incomplete),
        all_wins_warning=bool(result.all_wins_warning),
        replicates_per_arm=provenance.replicates_per_arm,
        fidelity=ArtifactFidelity(
            kl_divergence=fidelity.kl_divergence,
            threshold=fidelity.threshold,
            confidence=fidelity.confidence,
            within_fidelity_bound=report.within_fidelity_bound,
            fidelity_bound_statement=fidelity.fidelity_bound_statement,
        ),
        provenance=provenance,
        interval=interval,
        headline_verdict=result.headline_verdict,
        materiality_margin=float(result.materiality_margin),
        comparator=result.comparator,
        run_incomplete=bool(result.run_incomplete),
        arm_aggregates=aggregates,
        arm_aggregates_digest=arm_aggregates_digest(aggregates),
    )


__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "DEFAULT_CONSENSUS_ARM",
    "EXIT_NO_COMPLETED_RUN",
    "EXIT_SUCCESS",
    "KPI_FIELDS",
    "NO_ESTIMATE_HEADLINE",
    "POOLED_COMPARATOR_PREFIX",
    "UNATTRIBUTED",
    "ArmAggregate",
    "ArtifactFidelity",
    "ArtifactInterval",
    "HarnessResult",
    "LoopConfig",
    "UpliftArtifact",
    "UpliftHarness",
    "UpliftProvenance",
    "UpliftReport",
    "aggregate_arm",
    "arm_aggregates",
    "arm_aggregates_digest",
    "assemble_uplift_result",
    "build_uplift_artifact",
    "build_uplift_report",
    "canonical_arm_aggregates",
    "canonical_json",
    "comparator_label",
    "completed_run_count",
    "registered_roles",
    "replicate_seed",
    "resolve_provenance",
    "run_closed_loop",
    "uplift_exit_code",
]
