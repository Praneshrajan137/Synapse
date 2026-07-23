"""
SYNAPSE Decision-Integrity Uplift Proof — core interfaces and data models.

Defines the single ``DecisionPolicy`` protocol implemented by every baseline policy
and by the in-process consensus arm (R1.6), the immutable ``Observation`` fed at each
twin step, the ``PolicyAction`` applied back into the twin, and the shared data models
used throughout the harness (Direction, Outcome, KpiVector, Scenario, ScenarioRun,
ArmResult, UpliftResult) per the design Data Models section.

The harness loop is arm-agnostic: it only ever sees ``DecisionPolicy.decide(obs)``.
Any KPI delta between arms is therefore attributable to the decision policy alone.
"""
from __future__ import annotations

import dataclasses
from enum import Enum
from typing import TYPE_CHECKING, Mapping, Protocol, runtime_checkable

from digital_twin.simulation.monte_carlo import ShockParams

if TYPE_CHECKING:  # avoid a runtime import cycle; fidelity.py is built in a later task
    from uplift.fidelity import FidelityReport


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
    """

    name: str

    def decide(self, obs: Observation) -> PolicyAction:
        """Return the ``PolicyAction`` to apply to the twin for this ``Observation``."""
        ...


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


@dataclasses.dataclass(frozen=True)
class KpiVector:
    """The business KPIs recorded for one completed run (R2.3).

    ``fill_rate``, ``spoilage_rate``, and ``stockout_rate`` are fractions in
    ``[0.0, 1.0]``; ``avg_delivery_time_min`` is a non-negative number of minutes;
    ``margin`` and ``co2_estimate`` are numeric values.
    """

    fill_rate: float
    spoilage_rate: float
    stockout_rate: float
    avg_delivery_time_min: float
    margin: float
    co2_estimate: float


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
    """The assembled uplift outcome with mandatory fidelity context (R3–R5)."""

    per_kpi: dict[str, Outcome]
    per_scenario: dict[tuple[str, str], Outcome]
    secondary_kpis: list[str]
    headline_uplift: float
    fidelity: "FidelityReport"
    all_wins_warning: bool
    incomplete: bool
