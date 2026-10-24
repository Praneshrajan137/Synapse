"""
SYNAPSE Decision-Integrity Uplift Proof — core interfaces and data models.

Defines the single ``DecisionPolicy`` protocol implemented by every baseline policy
and by the in-process consensus arm (R1.6), the immutable ``Observation`` fed at each
twin step, the ``PolicyAction`` applied back into the twin, and the shared data models
used throughout the harness (Direction, Outcome, KpiVector, Scenario, ScenarioRun,
ArmResult, UpliftResult) per the design Data Models section.

The harness loop is arm-agnostic: it only ever sees ``DecisionPolicy.decide(obs)``.
Any KPI delta between arms is therefore attributable to the decision policy alone.

decision-quality-proof tasks 15.5 and 29.4 add three vocabulary items here, because this is the
module every other one already shares: :data:`ArmRole` and :class:`ArmSpec` (an arm is
registered WITH the role it plays in a contrast, never with a defaulted one), and
:data:`HeadlineVerdict` (the four-valued interval verdict R7.19 declares).
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import TYPE_CHECKING, Final, Literal, Mapping, Protocol, runtime_checkable

from digital_twin.simulation.monte_carlo import ShockParams

if TYPE_CHECKING:  # avoid a runtime import cycle; fidelity.py is built in a later task
    from uplift.fidelity import FidelityReport
    from uplift.interval import Interval


# ---------------------------------------------------------------------------
# Observation building blocks (routing needs an order destination + store set)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Store:
    """An eligible fulfillment store with a location, for routing decisions."""

    store_id: int
    location: tuple[float, float]


@dataclasses.dataclass(frozen=True)
class PendingOrder:
    """An order awaiting a routing assignment, with its delivery destination."""

    order_id: str
    destination: tuple[float, float]


# ---------------------------------------------------------------------------
# Observation — immutable snapshot of the twin fed to a policy at each step
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class Observation:
    """Immutable snapshot of twin state supplied to ``DecisionPolicy.decide`` (R2.2).

    ``inventory`` and ``unit_costs`` are keyed by SKU. Delivery/spoilage/stockout
    counters are the running twin tallies observed so far this scenario. ``active_shock``
    is the shock descriptor in effect (``None`` when unshocked). ``pending_order`` and
    ``eligible_stores`` are populated only when a routing decision is required.

    decision-quality-proof task 13.1 appends five fields. Each is something a real planner
    knows, so exposing it hands no arm an oracle:

    * ``on_order`` -- units ordered and not yet arrived, per SKU (absent = nothing in transit).
      A planner knows its open purchase orders; it is what makes inventory position computable.
    * ``supplier_lead_time_history`` -- each supplier's realised lead times, in arrival order.
      A planner knows how long past deliveries took; never how long a future one will.
    * ``demand_to_date`` -- demand events generated so far this run, per SKU. A planner knows
      its own sales history.
    * ``sku_supplier`` -- which supplier each SKU is ordered from. A planner knows its vendors.
    * ``start_weekday`` -- the weekday the run started on (0 = Monday), or ``None`` when demand
      has no weekly shape. A planner knows what day it is.

    All five default to empty (or ``None``), which is what the twin reports with no world, so
    every existing construction site, and every arm that ignores them, is unchanged.
    """

    inventory: Mapping[str, int]
    sim_time: float
    delivery_count: int
    spoilage_count: int
    stockout_count: int
    unit_costs: Mapping[str, float]
    active_shock: ShockParams | None = None
    pending_order: PendingOrder | None = None
    eligible_stores: tuple[Store, ...] = ()
    on_order: Mapping[str, float] = dataclasses.field(default_factory=dict)
    supplier_lead_time_history: Mapping[str, tuple[float, ...]] = dataclasses.field(
        default_factory=dict
    )
    demand_to_date: Mapping[str, int] = dataclasses.field(default_factory=dict)
    sku_supplier: Mapping[str, str] = dataclasses.field(default_factory=dict)
    start_weekday: int | None = None


# ---------------------------------------------------------------------------
# PolicyAction — decisions applied back into the twin (may be partial)
# ---------------------------------------------------------------------------
@dataclasses.dataclass(frozen=True)
class RoutingAssignment:
    """A routing decision. ``store_id is None`` with ``unroutable=True`` (R1.11) means
    the order could not be assigned and its routing state must be left unchanged."""

    order_id: str
    store_id: int | None = None
    unroutable: bool = False
    error: str | None = None


@dataclasses.dataclass(frozen=True)
class PolicyAction:
    """Decisions returned by a policy, in the twin's actuation vocabulary (R2.2).

    A ``PolicyAction`` MAY be partial: a pricing-only policy sets only ``price``; a
    reorder-only policy sets only ``reorder_quantities``. Unset levers are left at
    their neutral defaults so the harness applies nothing for that lever.
    """

    reorder_quantities: Mapping[str, float] = dataclasses.field(default_factory=dict)
    price: float | None = None
    routing_assignment: RoutingAssignment | None = None
    disruption_actions: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# DecisionPolicy — the single arm-agnostic decision interface (R1.6)
# ---------------------------------------------------------------------------
@runtime_checkable
class DecisionPolicy(Protocol):
    """The decision interface implemented by every baseline and the consensus arm.

    The harness drives every arm through this identical interface, so the only
    difference between arms is which policy produces the per-step decisions.

    ``name`` is declared READ-ONLY, because that is all the harness ever does with it: it
    reads it to register, key and label an arm. A settable protocol member would reject
    every frozen-dataclass policy (``Static_Pricing``, ``GroupParLevelReorder``) at the type
    level while accepting it at run time -- a declaration that misled the checker, repaired
    here rather than at the call sites that reported it.
    """

    @property
    def name(self) -> str:
        """The arm identifier the harness registers, keys and labels this policy by."""
        ...

    def decide(self, obs: Observation) -> PolicyAction:
        """Return the ``PolicyAction`` to apply to the twin for this ``Observation``."""
        ...


# ---------------------------------------------------------------------------
# Arm registration -- every arm declares the role it plays (AD-16, task 15.5)
# ---------------------------------------------------------------------------
#: What an arm is FOR in a contrast. ``consensus`` is the subject a headline is about;
#: ``baseline`` arms are the only ones a pooled comparator may absorb; an ``oracle`` (the
#: positive control's arm O) and an ``excluded`` arm are recorded but never pooled, so neither
#: can move the consensus contrast's comparator or its completeness verdict.
ArmRole = Literal["consensus", "baseline", "oracle", "excluded"]

#: Every admissible :data:`ArmRole`, for runtime refusal: a ``Literal`` is not checked at run
#: time, and a role read from a caller is exactly the value that must be checked.
ARM_ROLES: Final[tuple[ArmRole, ...]] = ("consensus", "baseline", "oracle", "excluded")


@dataclasses.dataclass(frozen=True)
class ArmSpec:
    """One registered arm: the policy it runs and the role it plays in a contrast.

    **There is no default role, by design.** The pooled comparator used to absorb every
    non-consensus arm, so an Oracle_Arm added to a run was silently pooled into the baseline
    and one failed oracle replicate could mark the consensus contrast incomplete (AD-16). A
    role declared beside the policy at registration is what lets pooling refuse an oracle, and
    an absent role is a refusal rather than a guess. A later suite declares its arms the same
    way: ``ArmSpec(policy, "baseline")``, ``ArmSpec(policy, "oracle")``.
    """

    policy: DecisionPolicy
    role: ArmRole

    def __post_init__(self) -> None:
        if self.role not in ARM_ROLES:
            raise ValueError(
                f"arm {getattr(self.policy, 'name', self.policy)!r} declares role "
                f"{self.role!r}; the admissible roles are {list(ARM_ROLES)}"
            )

    @property
    def name(self) -> str:
        """The arm identifier: the policy's own ``name``, so an arm has exactly one name."""
        return self.policy.name


# ---------------------------------------------------------------------------
# Data models (design "Data Models" section)
# ---------------------------------------------------------------------------
class Direction(Enum):
    """Improvement direction for a KPI (R3.1)."""

    HIGHER_IS_BETTER = "higher"
    LOWER_IS_BETTER = "lower"


class Outcome(Enum):
    """The one-of-three verdict for a comparison (R3.5)."""

    SYNAPSE_WINS = "synapse_wins"
    BASELINE_WINS = "baseline_wins"
    TIE_INCONCLUSIVE = "tie_inconclusive"


#: The four-valued headline verdict (R7.19, task 29.4), read off the ``1 - alpha`` interval on
#: the mean paired objective difference against the committed materiality margin ``m``, with
#: STRICT bounds: ``win`` iff ``low > m``; ``sub_margin_gain`` iff ``0 < low <= m``;
#: ``inconclusive`` iff ``low <= 0 <= high``; ``baseline_wins`` iff ``high < 0``. Exhaustive and
#: mutually exclusive for any admissible interval (``low <= high``) and margin (``m > 0``).
HeadlineVerdict = Literal["win", "sub_margin_gain", "inconclusive", "baseline_wins"]

#: Every :data:`HeadlineVerdict`, in the order the rule is stated.
HEADLINE_VERDICTS: Final[tuple[HeadlineVerdict, ...]] = (
    "win",
    "sub_margin_gain",
    "inconclusive",
    "baseline_wins",
)


@dataclasses.dataclass(frozen=True)
class KpiVector:
    """The business KPIs recorded for one completed run (R2.3).

    ``fill_rate``, ``spoilage_rate``, and ``stockout_rate`` are fractions in
    ``[0.0, 1.0]``; ``avg_delivery_time_min`` is a non-negative number of minutes;
    ``margin`` and ``co2_estimate`` are numeric values.

    decision-quality-proof task 29.4 appends two fields, so positional construction of the
    first six is unchanged:

    * ``avg_on_hand_units`` -- mean on-hand units over the run (R5.40), the holding input of
      the committed objective that this vector lacked.
    * ``objective`` -- the ADR-055 D2 scalar cost of this replicate, lower is better, computed
      by :meth:`uplift.regret.RegretObjective.cost` from the five engine reads
      ``uplift.regret._measure`` uses. It is Metric_Contract v2's sole primary KPI; every other
      field here is secondary (R7.19).

    **``objective`` is NOT a function of this vector's own ``fill_rate``.** Its unmet-service
    term reads the ENGINE's fill rate (fulfilled over demand events), while this vector's
    ``fill_rate`` is the extractor's delivered-over-created -- two inequivalent definitions
    that Property 64 clause 3 pins apart. Recompute the objective from the engine metrics,
    never from these six fields.
    """

    fill_rate: float
    spoilage_rate: float
    stockout_rate: float
    avg_delivery_time_min: float
    margin: float
    co2_estimate: float
    avg_on_hand_units: float
    objective: float


@dataclasses.dataclass(frozen=True)
class Scenario:
    """A seeded, replayable demand realization plus shock parameters.

    Identical ``seed`` ⇒ identical demand realization + ``shock`` across all arms
    (the attribution guarantee, R2.1/R2.5). ``cold_start`` empties initial
    inventory/freshness for the cold-start-city scenario.
    """

    name: str
    seed: int
    shock: ShockParams
    cold_start: bool = False


@dataclasses.dataclass(frozen=True)
class ScenarioRun:
    """The result of one (arm, seed) run. ``kpis`` is ``None`` when the run failed."""

    arm: str
    seed: int
    kpis: KpiVector | None
    failed: bool
    error: str | None


@dataclasses.dataclass
class ArmResult:
    """Per-arm aggregate over all completed runs (R2.8, R2.9)."""

    arm: str
    completed: int
    failed: int
    kpi_mean: dict[str, float]
    kpi_std: dict[str, float]


@dataclasses.dataclass
class UpliftResult:
    """The assembled uplift outcome with mandatory fidelity context (R3–R5).

    Under Metric_Contract v2 (task 29.4) ``headline_uplift`` is the mean paired difference of
    the committed objective, comparator minus subject, in objective units -- positive means the
    subject (consensus) arm is CHEAPER -- and it is exactly ``interval.point`` whenever an
    interval was estimated. ``interval`` is ``None`` only when no interval could be estimated,
    and then ``headline_verdict`` is ``None`` too and the headline is the no-estimate sentinel,
    never a measurement (I-7).

    ``incomplete`` is the CONTRAST predicate (task 15.5): the subject or a comparator arm did
    not complete every replicate. ``run_incomplete`` is the whole-run predicate over every
    registered arm, retained and reported but never read by the verdict, so a failed oracle
    replicate cannot break the consensus contrast it is not part of. ``comparator`` names the
    arm compared against, or ``"pooled:"`` plus the sorted pooled baseline-role arms.
    """

    per_kpi: dict[str, Outcome]
    per_scenario: dict[tuple[str, str], Outcome]
    secondary_kpis: list[str]
    headline_uplift: float
    fidelity: "FidelityReport"
    all_wins_warning: bool
    incomplete: bool
    interval: Interval | None
    headline_verdict: HeadlineVerdict | None
    materiality_margin: float
    comparator: str
    run_incomplete: bool
