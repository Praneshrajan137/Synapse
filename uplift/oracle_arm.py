"""Arm O -- the structure-aware base-stock arm (decision-quality-proof leaf 16.1, Property 92).

A NON-ANTICIPATIVE policy that uses exactly the information the new world offers -- the declared
demand profile (structure 1), the supplier roster and its realised lead-time history (structure
3), and inventory position -- and nothing about the future. It plays two roles: B-prime's third
arm (``E - O`` is the achievable information value, a LOWER bound on what information is worth;
``O - D`` is what remains even for a structure-aware planner) and E3's positive-control arm
against arm E. It is not ``uplift/regret.py::ORACLE_ARM``, which names arm D (``hindsight``).

It is NOT claimed optimal: no closed-form optimum exists for lost sales with a lead time (Karlin &
Scarf 1958; Morton 1969/1971; Zipkin 2008, OR 56(5)). Order-up-to policies are asymptotically
optimal as the shortage-to-holding ratio b/h -> infinity for CONSTANT lead times and i.i.d.
demand (Huh, Janakiraman, Muckstadt & Rusmevichientong 2009, Management Science 55(3):404-420,
Theorem 15(b) in the authors' version); here lead times are stochastic and demand is
non-stationary, so its quality is MEASURED (``E - O`` against the ceiling ``E - D``), never
assumed.

**What it can see.** ``decide`` takes one :class:`~uplift.interfaces.Observation` and nothing
else. The arm holds the DECLARED world -- profiles and supplier parameters -- never the engine,
its lead-time path or its seeds, so no realisation that has not happened is reachable from it.
Realised lead times arrive only through ``Observation.supplier_lead_time_history``, which the
engine fills with LANDED orders only.

**The rule**, at ``t = obs.sim_time``, per SKU in sorted order: ``position = on_hand +
on_order``; ``L_hat`` from :meth:`StructureAwareBaseStock.lead_time_estimate`; ``lam`` the
expected demand over ``[t, t + L_hat + R)``; ``cr`` from :func:`critical_ratio`; ``S_t =
poisson_quantile(lam, cr)``; order ``max(0, S_t - position)``. No randomness, so identical
observations give identical actions. Each approximation is stated where it is made.

Imports stay stdlib (``math`` for the arithmetic) beyond the interfaces it implements; the
objective reader and ``TwinConfig`` are imported inside :func:`build_structure_aware_arm` only.
"""

from __future__ import annotations

import dataclasses
import math
import random
from typing import TYPE_CHECKING, Final

from uplift.interfaces import Observation, PolicyAction

if TYPE_CHECKING:  # pragma: no cover - typing only
    from digital_twin.simulation.world import ResolvedWorld

__all__ = [
    "STRUCTURE_AWARE_ARM",
    "BaseStockTarget",
    "CostRatio",
    "StructureAwareBaseStock",
    "build_structure_aware_arm",
    "critical_ratio",
    "poisson_quantile",
]

#: The arm's label: the comparator's key for it and the name every artifact reports it under.
STRUCTURE_AWARE_ARM: Final[str] = "structure_aware"


def _is_positive_finite(value: float) -> bool:
    return math.isfinite(value) and value > 0.0


# ---------------------------------------------------------------------------
# The cost ratio and the critical ratio
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CostRatio:
    """The two marginal costs the critical ratio reads, derived from the committed objective.

    ``shortage_per_unit`` prices one unmet demand event and ``holding_per_unit_min`` one on-hand
    unit held one simulated minute, both in the objective's own units, both derived by
    :func:`build_structure_aware_arm` and never chosen here. Each must be finite and > 0: with no
    holding cost every ratio is one and the target unbounded, and with no shortage cost stocking
    anything is a loss -- either is a different policy, not this one.
    """

    shortage_per_unit: float  # w_unmet / expected demand events over the horizon
    holding_per_unit_min: float  # w_on_hand / (on_hand_normaliser * horizon_min)

    def __post_init__(self) -> None:
        for name, value in (
            ("shortage_per_unit", self.shortage_per_unit),
            ("holding_per_unit_min", self.holding_per_unit_min),
        ):
            if not _is_positive_finite(value):
                raise ValueError(f"CostRatio.{name} = {value!r} must be finite and > 0")


def critical_ratio(cost: CostRatio, *, lead_time_min: float, review_min: float) -> float:
    """Huh et al.'s ratio for ``S^{B*}(h, b + tau h)``: ``(b + tau h) / (b + (tau + 1) h)``.

    ``b = cost.shortage_per_unit``; ``h = cost.holding_per_unit_min * review_min``, the holding
    cost of one unit over one review period; ``tau = lead_time_min / review_min``, the lead time
    in review periods. Strictly inside ``(0, 1)`` over the reals; a ratio that rounding carries to
    an endpoint is refused by :func:`poisson_quantile` rather than ordered against.

    Raises:
        ValueError: If ``review_min`` is not finite and > 0, or ``lead_time_min`` is not finite
            and >= 0.
    """
    if not _is_positive_finite(review_min):
        raise ValueError(f"review_min = {review_min!r} must be finite and > 0")
    if not (math.isfinite(lead_time_min) and lead_time_min >= 0.0):
        raise ValueError(f"lead_time_min = {lead_time_min!r} must be finite and >= 0")
    shortage = cost.shortage_per_unit
    holding = cost.holding_per_unit_min * review_min
    tau = lead_time_min / review_min
    return (shortage + tau * holding) / (shortage + (tau + 1.0) * holding)


# ---------------------------------------------------------------------------
# The Poisson quantile, in log space
# ---------------------------------------------------------------------------


def _log_add(a: float, b: float) -> float:
    """``log(exp(a) + exp(b))`` without leaving log space."""
    high, low = (a, b) if a >= b else (b, a)
    return high + math.log1p(math.exp(low - high))


def poisson_quantile(lam: float, cr: float) -> int:
    """The smallest integer ``k`` with ``P(N <= k) >= cr`` for ``N ~ Poisson(lam)``; 0 at lam 0.

    Computed in LOG space -- ``log P(N = k) = k log(lam) - lam - lgamma(k + 1)``, accumulated by
    incremental log-sum-exp -- so no term underflows or overflows: in linear space ``exp(-lam)``
    is already zero past ``lam ~ 745``. The scan is ``O(lam)``, which the arm's windows keep
    small.

    **Domain of exactness (R2.10).** The log pmf cancels three terms of size about
    ``k |log(lam)|``, so it carries a relative error of order ``1e-12`` at ``lam = 400`` and
    ``1e-11`` at ``2000`` -- estimated from that cancellation, not measured. The returned ``k`` is
    the exact quantile except where ``cr`` lies within that relative distance of a CDF value;
    Property 92 pins it against a 50-digit decimal scan.

    Raises:
        ValueError: If ``lam`` is negative or not finite; if ``cr`` is not strictly inside
            ``(0, 1)``; or if ``cr`` is so close to one that the float CDF converges below it --
            the level is then not determined in double precision, and none is guessed.
    """
    if not (math.isfinite(lam) and lam >= 0.0):
        raise ValueError(f"expected demand lam = {lam!r} must be finite and >= 0")
    if not (math.isfinite(cr) and 0.0 < cr < 1.0):
        raise ValueError(f"critical ratio cr = {cr!r} must lie strictly inside (0, 1)")
    if lam == 0.0:
        return 0
    log_lam = math.log(lam)
    log_target = math.log(cr)
    k = 0
    log_cdf = -lam  # log P(N <= 0) = log P(N = 0), exactly
    while log_cdf < log_target:
        k += 1
        grown = _log_add(log_cdf, k * log_lam - lam - math.lgamma(k + 1))
        # Past the mode every later term is smaller, and rounding is monotone, so a term that no
        # longer moves the float sum proves no later term will: the CDF has converged below cr.
        if grown == log_cdf and k > lam:
            raise ValueError(
                f"critical ratio cr = {cr!r} is within rounding of one at lam = {lam!r}: the "
                f"float Poisson CDF converges at exp({log_cdf!r}), below cr, so no level is "
                "determined"
            )
        log_cdf = grown
    return k


# ---------------------------------------------------------------------------
# Arm O
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class BaseStockTarget:
    """One SKU's order-up-to computation at one decision, every intermediate kept.

    Recorded rather than folded into the order, so a reader can see WHY the arm ordered what it
    did: which lead time it assumed, over which window, at which ratio.
    """

    sku: str
    lead_time_min: float  # L_hat
    window_min: float  # L_hat + review_min
    expected_demand: float  # lam over [t, t + window_min)
    critical_ratio: float  # cr
    order_up_to: int  # S_t
    position: float  # on hand + on order
    order: float  # max(0, S_t - position)


class StructureAwareBaseStock:
    """Arm O: order up to the critical-ratio Poisson quantile of the protection window.

    Implements :class:`uplift.interfaces.DecisionPolicy`. The seed is held only for the
    construction contract the baseline suite shares, mirroring ``Par_Level_Reorder``: an
    instance-local generator exists and nothing ever draws from it.

    Args:
        world: The resolved cell the engine runs, or ``None`` for HEAD's world (both structures
            off). The arm cannot see the engine's world, so the caller must hand it the same one.
        cost: The marginal costs, as :func:`build_structure_aware_arm` derives them.
        review_min: Minutes between decisions -- the comparator's slice.
        rate_per_sku_per_min: Expected demand events per SKU per minute at intensity one.
        seed: The construction seed. Never drawn from.

    Raises:
        ValueError: If ``review_min`` or ``rate_per_sku_per_min`` is not finite and > 0.
    """

    #: Stable label the comparator reports this arm under.
    name: str = STRUCTURE_AWARE_ARM

    def __init__(
        self,
        *,
        world: ResolvedWorld | None,
        cost: CostRatio,
        review_min: float,
        rate_per_sku_per_min: float,
        seed: int,
    ) -> None:
        if not _is_positive_finite(review_min):
            raise ValueError(f"review_min = {review_min!r} must be finite and > 0")
        if not _is_positive_finite(rate_per_sku_per_min):
            raise ValueError(
                f"rate_per_sku_per_min = {rate_per_sku_per_min!r} must be finite and > 0"
            )
        self._world = world
        self._cost = cost
        self._review_min = float(review_min)
        self._rate = float(rate_per_sku_per_min)
        self._seed = seed
        # Instance-local and never drawn from: the shared seed-stable construction contract
        # (R1.9) with no hidden global state. The rule itself is deterministic.
        self._rng = random.Random(seed)

    @property
    def world(self) -> ResolvedWorld | None:
        """The declared world the arm plans against; compare it with the engine's ``world``."""
        return self._world

    @property
    def cost(self) -> CostRatio:
        """The marginal costs the critical ratio is built from."""
        return self._cost

    @property
    def review_min(self) -> float:
        """Minutes between decisions."""
        return self._review_min

    @property
    def rate_per_sku_per_min(self) -> float:
        """Expected demand events per SKU per minute at intensity one."""
        return self._rate

    @property
    def seed(self) -> int:
        """The deterministic construction seed."""
        return self._seed

    def lead_time_estimate(self, obs: Observation, sku: str) -> float:
        """``L_hat`` for ``sku`` at ``obs.sim_time``, from declared values and landed history only.

        ``0.0`` with structure 3 off. With it on, for ``sku``'s supplier ``j``: the declared mean
        times the declared coupling factor ``max(coupling_floor, 1 + demand_coupling (I(t) - 1))``
        (``I = 1`` with structure 1 off), times ``f_hat = exp(mean(log(L_i / mean_j)))`` over
        ``j``'s realised lead times (``1.0`` while none has landed), floored at
        ``min_lead_time_min``. An order in transit has no realised lead time, so it cannot move
        the estimate.

        **A documented, bounded bias.** Placement times are not in the history, so each past lead
        time still carries the coupling factor of ITS placement hour, and the current factor is
        applied on top. The excess is a factor between the smallest and the largest coupling
        factor the declared profile reaches -- at most the coupling range.

        Raises:
            ValueError: With structure 3 on, if the observation names no supplier for ``sku``,
                names one this arm's world does not declare, or reports a realised lead time
                that is not finite and > 0; with structure 1 on, if it carries no weekday.
        """
        supply = None if self._world is None else self._world.supply
        if supply is None:
            return 0.0
        supplier = obs.sku_supplier.get(sku)
        if supplier is None:
            raise ValueError(
                f"structure 3 is on but the observation names no supplier for {sku!r}; the arm "
                "will not guess whose lead time protects it"
            )
        spec = supply.suppliers.get(supplier)
        if spec is None:
            raise ValueError(
                f"the observation orders {sku!r} from {supplier!r}, which this arm's world does "
                "not declare: the arm and the engine are not running one world"
            )
        landed = obs.supplier_lead_time_history.get(supplier, ())
        for lead in landed:
            if not _is_positive_finite(lead):
                raise ValueError(
                    f"{supplier!r} reports a realised lead time of {lead!r} minutes; a landed "
                    "order took a finite, positive time, so this history is refused"
                )
        mean = spec.mean_lead_time_min
        intensity = self._intensity(obs.sim_time, obs.start_weekday)
        coupling = max(supply.coupling_floor, 1.0 + supply.demand_coupling * (intensity - 1.0))
        factor = (
            math.exp(math.fsum(math.log(lead / mean) for lead in landed) / len(landed))
            if landed
            else 1.0
        )
        return max(supply.min_lead_time_min, mean * coupling * factor)

    def target(
        self,
        *,
        sku: str,
        t_min: float,
        lead_time_min: float,
        start_weekday: int | None,
        position: float,
    ) -> BaseStockTarget:
        """The order-up-to level for ``sku`` at ``t_min`` under an assumed lead time.

        The protection window is ``[t, t + lead_time_min + review_min)``: an order placed now
        must cover demand until the NEXT order can land. Its expected demand is the per-SKU rate
        times the window with structure 1 off, and the declared profile's integral over it with
        structure 1 on.

        Raises:
            ValueError: If ``t_min`` is negative or not finite, ``position`` is not finite,
                ``lead_time_min`` is negative or not finite, or structure 1 is on and
                ``start_weekday`` is ``None``; and whatever :func:`poisson_quantile` refuses.
        """
        if not (math.isfinite(t_min) and t_min >= 0.0):
            raise ValueError(f"the simulated time t_min = {t_min!r} must be finite and >= 0")
        if not math.isfinite(position):
            raise ValueError(f"the inventory position of {sku!r} = {position!r} is not finite")
        ratio = critical_ratio(self._cost, lead_time_min=lead_time_min, review_min=self._review_min)
        window = lead_time_min + self._review_min
        lam = self._expected_demand(t_min, window, start_weekday)
        level = poisson_quantile(lam, ratio)
        return BaseStockTarget(
            sku=sku,
            lead_time_min=lead_time_min,
            window_min=window,
            expected_demand=lam,
            critical_ratio=ratio,
            order_up_to=level,
            position=position,
            order=max(0.0, float(level) - position),
        )

    def targets(self, obs: Observation) -> tuple[BaseStockTarget, ...]:
        """Every SKU's target at this observation, in sorted SKU order -- what ``decide`` acts on.

        ``position`` is on hand plus on order; a SKU absent from ``obs.on_order`` has nothing in
        transit, which is the ``Observation`` contract.
        """
        return tuple(
            self.target(
                sku=sku,
                t_min=obs.sim_time,
                lead_time_min=self.lead_time_estimate(obs, sku),
                start_weekday=obs.start_weekday,
                position=obs.inventory[sku] + obs.on_order.get(sku, 0.0),
            )
            for sku in sorted(obs.inventory)
        )

    def decide(self, obs: Observation) -> PolicyAction:
        """Order each SKU up to its target on inventory position: ``max(0, S_t - position)``."""
        return PolicyAction(
            reorder_quantities={target.sku: target.order for target in self.targets(obs)}
        )

    def _intensity(self, t_min: float, start_weekday: int | None) -> float:
        """The declared demand intensity at ``t_min``; ``1.0`` with structure 1 off."""
        demand = None if self._world is None else self._world.demand
        if demand is None:
            return 1.0
        return demand.intensity(t_min, _placed_in_week(start_weekday))

    def _expected_demand(self, t_min: float, window_min: float, start_weekday: int | None) -> float:
        """Expected demand for ONE SKU over ``[t_min, t_min + window_min)``.

        ``DemandShape.expected_units`` takes the FLAT per-minute rate as ``rate_per_min`` and
        returns ``rate_per_min`` times the profile's integral over the window, so the per-SKU rate
        is passed there directly -- bit-identical to ``rate * expected_units(..., 1.0)``.
        """
        demand = None if self._world is None else self._world.demand
        if demand is None:
            return self._rate * window_min
        return demand.expected_units(
            t0_min=t_min,
            t1_min=t_min + window_min,
            start_weekday=_placed_in_week(start_weekday),
            rate_per_min=self._rate,
        )


def _placed_in_week(start_weekday: int | None) -> int:
    """The run's start weekday, which structure 1 cannot do without; never assumed."""
    if start_weekday is None:
        raise ValueError(
            "structure 1 is on but the observation carries no start_weekday, so the declared "
            "profile cannot be placed in the week; no weekday is assumed"
        )
    return start_weekday


def build_structure_aware_arm(
    world: ResolvedWorld | None, *, seed: int, hours: float, review_min: float, n_skus: int
) -> StructureAwareBaseStock:
    """Arm O for a run of ``hours`` over ``n_skus`` SKUs, every number read rather than chosen.

    **holding_per_unit_min, from the definition it prices.** The objective's holding term is
    ``w_on_hand * avg_on_hand_units / on_hand_normaliser`` (``RegretObjective.contributions``).
    ``SimulationMetrics.avg_on_hand_units(H)`` is ``inventory_minutes / H``, ``inventory_minutes``
    integrates the summed ON-HAND levels over simulated minutes (``_accrue_inventory_time``,
    before every mutation and at every advance boundary), and the comparator evaluates it at the
    end-of-run clock ``H = hours * 60``. One unit held one more minute adds exactly one
    unit-minute, so it costs ``w_on_hand / (on_hand_normaliser * H)`` -- linear and exact, not a
    local approximation. Units on order cost nothing: the integral never reads the pipeline.

    **shortage_per_unit.** The service term is ``w_unmet * (1 - fill_rate)`` with ``1 - fill_rate
    = unmet_demand_events / demand_events``, so one unmet event costs ``w_unmet /
    demand_events``. The random denominator is replaced by the expected count at intensity one,
    ``rate * H``. Two departures, both bounded: an event still in pick-pack or travel when the
    run ends never reaches ``demand_events``, so the realised marginal is slightly larger; and the
    reader's rule makes each profile's mean exactly one over ITS OWN period, so with structure 1
    on, a horizon that is not whole weeks or that holds a promotion carries a different expected
    count. Either moves ``b`` by a bounded factor and ``cr`` by far less.

    **rate_per_sku.** ``TwinConfig().order_arrival_rate`` is the engine's Poisson rate per minute
    (``_order_arrival`` draws inter-arrival times at ``1 / rate``), and ``_draw_demanded_sku``
    names the demanded SKU uniformly over the stocked catalogue, so each of ``n_skus`` SKUs is
    demanded at ``rate / n_skus``. It is the UNSHOCKED rate, which is the rate the comparator's
    twins run; ``uplift/harness.py::_build_twin`` scales the rate by a scenario's demand
    multiplier, and this arm would not see that.

    Raises:
        ValueError: If ``hours`` is not finite and > 0 or ``n_skus`` is not a positive integer,
            and whatever :class:`CostRatio` or :class:`StructureAwareBaseStock` refuses.
        PolicyUnavailableError: If the committed objective cannot be read (``load_objective``).
    """
    if not _is_positive_finite(hours):
        raise ValueError(f"hours = {hours!r} must be finite and > 0")
    if isinstance(n_skus, bool) or n_skus < 1:
        raise ValueError(f"n_skus = {n_skus!r} must be a positive integer")
    # Lazy, so an import of this module adds nothing beyond the interfaces it implements: the
    # objective reader pulls the YAML policy reader, and TwinConfig pulls pydantic-settings.
    from digital_twin.config import TwinConfig
    from digital_twin.simulation.world import MINUTES_PER_HOUR
    from uplift.regret import load_objective

    objective = load_objective()
    rate = float(TwinConfig().order_arrival_rate)
    horizon_min = hours * MINUTES_PER_HOUR
    cost = CostRatio(
        shortage_per_unit=objective.weights["unmet_service"] / (rate * horizon_min),
        holding_per_unit_min=objective.weights["on_hand"]
        / (objective.on_hand_normaliser * horizon_min),
    )
    return StructureAwareBaseStock(
        world=world,
        cost=cost,
        review_min=review_min,
        rate_per_sku_per_min=rate / n_skus,
        seed=seed,
    )
