"""
SYNAPSE Digital Twin — SimPy discrete-event simulation engine.

Models the full order lifecycle: arrival → pick/pack/dispatch → delivery → restock → spoilage.
Each process draws from calibrated distributions and integrates with agent signals.
"""
from __future__ import annotations

import dataclasses
import random
from typing import TYPE_CHECKING, Any

import numpy as np
import simpy
import structlog

from digital_twin.config import TwinConfig

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Mapping

logger = structlog.get_logger(__name__)


@dataclasses.dataclass
class SimulationMetrics:
    """Accumulated metrics from a single simulation run."""

    orders_created: int = 0
    orders_delivered: int = 0
    orders_spoiled: int = 0
    restocks_triggered: int = 0
    total_delivery_time_min: float = 0.0
    total_pick_pack_time_min: float = 0.0

    # ── decision-quality-proof task 9.1 (R5.38) ──────────────────────────────
    #: Demand events that reached the fulfilment point -- i.e. attempted to consume
    #: stock. The DENOMINATOR of `stockout_rate`. Distinct from `orders_created`,
    #: which counts arrivals: an order created near the end of a run may never
    #: reach fulfilment, and dividing unmet demand by arrivals would then
    #: understate the stockout rate by counting orders that were never tried.
    demand_events: int = 0
    #: Demand events that found their drawn SKU at zero stock. The NUMERATOR of
    #: `stockout_rate`. Before this field a stockout cost NOTHING measurable:
    #: `_delivery` incremented `orders_delivered` unconditionally *before*
    #: depleting stock, so all six KpiVector fields were blind to availability and
    #: `fill_rate` could not fall. That contradicted `uplift/kpi.py`'s docstring and
    #: `digital_twin/world/runtime.py`'s claim that with auto-restock disabled
    #: "stock genuinely runs out and fill_rate falls" -- which was false.
    unmet_demand_events: int = 0

    # ── decision-quality-proof task 9.3 (R5.40) ──────────────────────────────
    #: Time-weighted on-hand inventory, in unit-minutes: the integral of
    #: `sum(levels)` over simulated time. Pure accounting -- it draws nothing and
    #: changes no timing. This is the HOLDING term of ADR-055's regret objective and
    #: the KPI R5.28's third single-objective policy minimises. Without it the
    #: classic (s,S) cost objective is not derivable at all: `SimulationMetrics`
    #: carried six counters and no inventory-TIME term, so "how much stock did we
    #: hold, for how long" had no answer.
    inventory_minutes: float = 0.0

    @property
    def stockout_rate(self) -> float:
        """Unmet demand events over demand events (R5.38).

        This is what `uplift/kpi.py:85-86` already documented and what nothing
        computed. The harness previously derived a stockout numerator as a per-step
        count of SKUs sitting at zero, which scales with `n_steps * |SKU|` and
        saturates its own clamp -- a number about the shape of the run rather than
        about unmet demand.
        """
        if self.demand_events == 0:
            return 0.0
        return self.unmet_demand_events / self.demand_events

    @property
    def fill_rate(self) -> float:
        """Fulfilled demand events over demand events.

        The exact complement of :attr:`stockout_rate`, and it can now FALL -- which
        is the entire point of task 9.1.
        """
        if self.demand_events == 0:
            return 0.0
        return (self.demand_events - self.unmet_demand_events) / self.demand_events

    def avg_on_hand_units(self, sim_time_min: float) -> float:
        """Mean on-hand units over the elapsed simulated time (R5.40).

        Takes the clock as an argument rather than storing it, because the integral
        and the horizon it is divided by belong to different objects: the engine owns
        the clock, and duplicating it here would let the two drift.
        """
        if sim_time_min <= 0.0:
            return 0.0
        return self.inventory_minutes / sim_time_min

    @property
    def avg_delivery_time_min(self) -> float:
        """End-to-end customer-visible delivery time = pick/pack + travel.

        Fix for E-DT-004: previously this returned only travel time, leaving
        the metric unresponsive to supplier-failure shocks (which scale
        ``pick_pack_mean_min`` via ``lead_time_multiplier``). The customer
        experiences pick+pack+travel as a single wait, so the SLA metric
        must include both stages.

        decision-quality-proof task 9.1: both totals now accumulate ONLY on a
        fulfilled delivery. An order whose SKU was out of stock contributes to
        neither the numerator nor the denominator, because a customer who was not
        served did not experience a delivery time. Accumulating its pick/pack effort
        into the numerator while excluding it from the denominator would inflate this
        KPI precisely when service got worse -- a metric moving the wrong way.
        """
        if self.orders_delivered == 0:
            return 0.0
        return (
            self.total_pick_pack_time_min + self.total_delivery_time_min
        ) / self.orders_delivered

    @property
    def avg_travel_time_min(self) -> float:
        """Travel-only component (preserved for diagnostics/breakdown)."""
        if self.orders_delivered == 0:
            return 0.0
        return self.total_delivery_time_min / self.orders_delivered

    @property
    def avg_pick_pack_time_min(self) -> float:
        """Pick+pack-only component (preserved for diagnostics/breakdown)."""
        if self.orders_delivered == 0:
            return 0.0
        return self.total_pick_pack_time_min / self.orders_delivered

    @property
    def spoilage_rate(self) -> float:
        if self.orders_created == 0:
            return 0.0
        return self.orders_spoiled / self.orders_created

    def to_dict(self) -> dict[str, Any]:
        return {
            "orders_created": self.orders_created,
            "orders_delivered": self.orders_delivered,
            "orders_spoiled": self.orders_spoiled,
            "restocks_triggered": self.restocks_triggered,
            "avg_delivery_time_min": round(self.avg_delivery_time_min, 2),
            "avg_travel_time_min": round(self.avg_travel_time_min, 2),
            "avg_pick_pack_time_min": round(self.avg_pick_pack_time_min, 2),
            "spoilage_rate": round(self.spoilage_rate, 4),
            # decision-quality-proof tasks 9.1 / 9.3. Reported so a run's own output
            # shows whether stock availability was observable at all: a run with
            # `demand_events == 0` has measured nothing about fill rate, and that is
            # visible here rather than hidden behind a 0.0 ratio (I-7).
            "demand_events": self.demand_events,
            "unmet_demand_events": self.unmet_demand_events,
            "stockout_rate": round(self.stockout_rate, 4),
            "fill_rate": round(self.fill_rate, 4),
            "inventory_minutes": round(self.inventory_minutes, 2),
        }


@dataclasses.dataclass(frozen=True)
class DemandEvent:
    """One generated unit of demand, named at the moment it is generated (R5.37, R5.39).

    ``sku`` is the load-bearing field. Before task 9.2 demand never named a SKU at all:
    ``_delivery`` picked the depleting SKU by ``rng.choice(...)`` *after* the delivery had
    already been counted, so there was no per-SKU demand path to forecast, to price, or to
    hold stock against. A `demand_prophet` cannot forecast a series that does not exist.
    """

    t_min: float
    sku: str
    units: float = 1.0


@dataclasses.dataclass
class DemandTrace:
    """The realised demand path of one scenario, recorded AS IT IS GENERATED (R5.37).

    **Why a recorded trace rather than a re-derivation.** A perfect-foresight policy needs to
    know future demand. ``DecisionPolicy.decide(obs)`` sees only present state, so foresight
    cannot exist without this. The alternative -- re-deriving the demand path by replaying the
    generator -- would couple the comparator to the generator's internals and break the moment
    E2c changes the arrival process, which is exactly what E2c does.

    Recorded at generation time, not at consumption time: an event that is generated but never
    fulfilled is still demand, and a trace built from fulfilments would silently omit precisely
    the stockouts the experiment is about.
    """

    events: list[DemandEvent] = dataclasses.field(default_factory=list)

    def record(self, t_min: float, sku: str, units: float = 1.0) -> None:
        self.events.append(DemandEvent(t_min=t_min, sku=sku, units=units))

    def __len__(self) -> int:
        return len(self.events)

    @property
    def total_units(self) -> float:
        return sum(event.units for event in self.events)

    def units_by_sku(self) -> dict[str, float]:
        """Total demanded units per SKU, in first-seen order."""
        totals: dict[str, float] = {}
        for event in self.events:
            totals[event.sku] = totals.get(event.sku, 0.0) + event.units
        return totals

    def as_tuples(self) -> tuple[tuple[float, str, float], ...]:
        """Canonical, comparable form -- what Property 51's replay clause asserts on."""
        return tuple((event.t_min, event.sku, event.units) for event in self.events)


#: The six named RNG substreams (decision-quality-proof task 9.4, R5.30/R5.37).
#:
#: THE CHANGE THAT MAKES E2c POSSIBLE. With one shared generator, the realised demand path is
#: a function of the GLOBAL draw order across all five processes -- so adding a queue in
#: structure 2 perturbs the demand stream, and every seeded expectation in the PRESERVE list
#: breaks for a reason unrelated to the structure being added. With substreams, the demand
#: path is provably independent of any arm's actions, which is what makes
#: `test_arms_receive_identical_seeded_demand` a stronger statement rather than a weaker one.
#:
#: Order is fixed and MUST NOT be reordered: `SeedSequence.spawn` derives each child from the
#: parent's entropy plus its INDEX, so inserting a name in the middle silently re-seeds every
#: substream after it.
SUBSTREAM_NAMES: tuple[str, ...] = (
    "demand",
    "pick_pack",
    "travel",
    "restock",
    "spoilage",
    "sku_choice",
)


class SupplyChainSimulation:
    """SimPy-based discrete-event simulation of the supply chain.

    Processes:
      - order_arrival: Poisson inter-arrival times
      - pick_pack_dispatch: Normal(mean=8, std=2) minutes
      - delivery: OSRM travel time estimate + Gaussian noise
      - restock: Triggered when inventory drops below safety stock (Inventory Sentinel)
      - spoilage: Freshness Guardian quality decay model
    """

    def __init__(
        self,
        config: TwinConfig | None = None,
        seed: int | None = None,
        failure_rate_multiplier: float = 1.0,
        spoilage_rate_multiplier: float = 1.0,
    ) -> None:
        self._config = config or TwinConfig()
        self._seed = seed
        # ── task 9.4 (R5.30, R5.37): named substreams, not one shared generator ──
        # `self._rng` is RETAINED as the `sku_choice` substream so that any caller
        # reaching into it still gets a generator rather than an AttributeError, but
        # every process below draws from its OWN named stream. STATED COST: this
        # changes every realised number on the seeded path. That is the single largest
        # expected-value churn in this design and it is unavoidable -- see
        # SUBSTREAM_NAMES for why.
        self._streams: dict[str, np.random.Generator] = self._spawn_streams(seed)
        self._rng = self._streams["sku_choice"]
        self._metrics = SimulationMetrics()
        self._inventory: dict[str, float] = {}
        self._freshness: dict[str, float] = {}
        # ── task 9.5 (R5.37): the replayable demand path ──
        self._demand_trace = DemandTrace()
        # ── task 9.3 (R5.40): lazy integration state for the on-hand measure ──
        # Accrued at every mutation and at every advance boundary rather than by a
        # sampling process, deliberately: a new SimPy process would add events to the
        # queue and could reorder same-timestamp callbacks, which is exactly the kind
        # of incidental perturbation task 9.4 exists to eliminate.
        self._last_accrual_min = 0.0
        # ShockParams fields not currently in TwinConfig.
        # Bounded to avoid degenerate distributions under aggressive shocks.
        self._failure_rate_multiplier = max(1.0, float(failure_rate_multiplier))
        self._spoilage_rate_multiplier = max(0.0, float(spoilage_rate_multiplier))
        # Persistent stepping state (E-DT fix: previously run() re-initialised
        # everything on every call, so the Gym wrapper's state never persisted
        # across steps). start()/advance() keep one env alive.
        self._env: simpy.Environment | None = None
        self._sim_time_min = 0.0
        # Policy levers an RL agent controls. Neutral defaults reproduce the
        # historical behaviour exactly, so run()-based tests are unchanged.
        self._dispatch_speed = 1.0       # >1 = faster pick/pack → lower latency
        self._restock_threshold = 50.0   # safety-stock level that triggers restock
        self._order_qty_mult = 1.0       # scales the restock amount
        # ADR-052 actuation levers (neutral defaults reproduce historical behaviour
        # exactly, so the run()-based determinism tests are unaffected).
        self._demand_mult = 1.0          # >1 = more demand (e.g. a price cut)
        self._lead_time_mult = 1.0       # >1 = slower supplier restock lead time
        self._order_seq = 0              # id counter for externally-injected orders

    @staticmethod
    def _spawn_streams(seed: int | None) -> dict[str, np.random.Generator]:
        """One independent generator per named process (task 9.4, R5.30).

        ``SeedSequence(seed).spawn(n)`` derives n statistically independent child sequences.
        ``seed=None`` is supported and draws OS entropy, so an unseeded run still gets
        independent streams rather than falling back to a shared one.
        """
        children = np.random.SeedSequence(seed).spawn(len(SUBSTREAM_NAMES))
        return {
            name: np.random.default_rng(child)
            for name, child in zip(SUBSTREAM_NAMES, children, strict=True)
        }

    def _accrue_inventory_time(self, now_min: float) -> None:
        """Integrate ``sum(levels)`` up to ``now_min`` (task 9.3, R5.40).

        Called immediately BEFORE every inventory mutation and at every advance boundary, so
        the level being integrated is the level that actually held over the interval. Calling
        it after a mutation would attribute the new level to the old interval.

        Pure accounting: draws nothing, schedules nothing, and cannot change timing. Guarded
        against a non-monotonic clock so a caller that rewinds cannot subtract inventory-time.
        """
        delta = now_min - self._last_accrual_min
        if delta <= 0.0:
            return
        self._metrics.inventory_minutes += sum(self._inventory.values()) * delta
        self._last_accrual_min = now_min

    def _now(self) -> float:
        """Current env clock in minutes, or the stepped clock when no env exists yet."""
        return float(self._env.now) if self._env is not None else self._sim_time_min

    @property
    def streams(self) -> dict[str, np.random.Generator]:
        """The named RNG substreams (read accessor for Property 52)."""
        return dict(self._streams)

    @property
    def demand_trace(self) -> DemandTrace:
        """The realised demand path recorded so far (task 9.5, R5.37)."""
        return self._demand_trace

    def set_policy(
        self,
        *,
        dispatch_speed: float | None = None,
        restock_threshold: float | None = None,
        order_qty_mult: float | None = None,
        demand_mult: float | None = None,
        lead_time_mult: float | None = None,
    ) -> None:
        """Update the supply-policy levers an RL agent / live decision controls.

        The running SimPy processes read these on each iteration, so a policy
        change mid-episode takes effect on subsequent dispatches/restocks — this
        is what makes the Gym env's action (and an agent's live ``execute()``)
        genuinely affect the dynamics.
        """
        if dispatch_speed is not None:
            self._dispatch_speed = max(0.1, float(dispatch_speed))
        if restock_threshold is not None:
            self._restock_threshold = max(0.0, float(restock_threshold))
        if order_qty_mult is not None:
            self._order_qty_mult = max(0.1, float(order_qty_mult))
        if demand_mult is not None:
            self._demand_mult = max(0.01, float(demand_mult))
        if lead_time_mult is not None:
            self._lead_time_mult = max(0.1, float(lead_time_mult))

    def inject_shock(
        self,
        *,
        failure_rate_multiplier: float | None = None,
        spoilage_rate_multiplier: float | None = None,
        lead_time_multiplier: float | None = None,
    ) -> None:
        """Apply a disruption shock to the running world (ADR-052 actuation).

        Unlike the constructor shocks (set once at episode start), these mutate the
        LIVE world mid-run so a disruption-shield decision visibly degrades delivery
        / spoilage / lead time — and the next perceive() reflects it.
        """
        if failure_rate_multiplier is not None:
            self._failure_rate_multiplier = max(1.0, float(failure_rate_multiplier))
        if spoilage_rate_multiplier is not None:
            self._spoilage_rate_multiplier = max(0.0, float(spoilage_rate_multiplier))
        if lead_time_multiplier is not None:
            self._lead_time_mult = max(0.1, float(lead_time_multiplier))

    def inject_orders(self, n: int) -> None:
        """Schedule ``n`` exogenous orders on the running env (ADR-052 WorldSource path).

        When ``start(external_demand=True)`` is used, the endogenous Poisson process is
        off and demand comes only from here — this is how a pluggable ``WorldSource``
        (SimWorldSource now, ExternalFeedSource later) drives the SAME downstream
        dynamics (pick/pack → delivery → inventory depletion).
        """
        if n <= 0:
            return
        if self._env is None:
            self.start(external_demand=True)
        assert self._env is not None
        for _ in range(int(n)):
            self._order_seq += 1
            self._metrics.orders_created += 1
            # task 9.2/9.5: an injected order is demand too, so it names a SKU and lands in
            # the trace on the same terms as an endogenous arrival. Omitting it here would
            # make the foresight comparator blind to exactly the externally-driven demand a
            # `WorldSource` exists to supply.
            sku = self._draw_demanded_sku()
            if sku is not None:
                self._demand_trace.record(float(self._env.now), sku)
            self._env.process(self._pick_pack_dispatch(self._env, self._order_seq, sku))

    def add_stock(self, sku_id: str, quantity: float) -> float:
        """Replenish a SKU's stock (ADR-052 reorder actuation). Returns the new level."""
        # task 9.3: integrate the pre-mutation level over the interval it held.
        self._accrue_inventory_time(self._now())
        self._inventory[sku_id] = self._inventory.get(sku_id, 0.0) + max(0.0, float(quantity))
        return self._inventory[sku_id]

    # ── Public read accessors (so callers need not reach into privates) ──

    @property
    def inventory(self) -> dict[str, float]:
        """A copy of the current per-SKU stock levels."""
        return dict(self._inventory)

    @property
    def metrics(self) -> SimulationMetrics:
        """The live accumulated metrics object."""
        return self._metrics

    @property
    def sim_time_min(self) -> float:
        """Current simulation clock, in minutes."""
        return self._sim_time_min

    @property
    def demand_mult(self) -> float:
        """Current demand multiplier (1.0 = neutral)."""
        return self._demand_mult

    def _init_env(self) -> simpy.Environment:
        if self._seed is not None:
            random.seed(self._seed)
        return simpy.Environment()

    def _draw_demanded_sku(self) -> str | None:
        """Name the SKU this demand event is for (task 9.2, R5.39).

        Drawn from the ``sku_choice`` substream at DEMAND-GENERATION time. Previously the
        depleting SKU was chosen inside ``_delivery`` by
        ``rng.choice(list(self._inventory.keys()))`` *after* the delivery had been counted, so
        demand never named a SKU and there was no per-SKU demand series to forecast or price.

        Returns ``None`` only when there are no SKUs at all, which is a genuinely empty world
        (``WorldRuntime`` passes an empty mapping for a non-seeded source) rather than a
        stockout -- and the caller must not record it as unmet demand, because nothing was
        demanded of a catalogue that does not exist.
        """
        if not self._inventory:
            return None
        return str(self._streams["sku_choice"].choice(list(self._inventory.keys())))

    def _order_arrival(self, env: simpy.Environment) -> Any:
        """Poisson-distributed order arrivals, each naming the SKU it demands."""
        order_id = 0
        while True:
            inter_arrival = self._streams["demand"].exponential(
                1.0 / (self._config.order_arrival_rate * self._demand_mult)
            )
            yield env.timeout(inter_arrival)
            order_id += 1
            self._metrics.orders_created += 1
            sku = self._draw_demanded_sku()
            if sku is not None:
                # task 9.5: recorded AS GENERATED, before any fulfilment outcome is known.
                self._demand_trace.record(float(env.now), sku)
            env.process(self._pick_pack_dispatch(env, order_id, sku))

    def _pick_pack_dispatch(
        self, env: simpy.Environment, order_id: int, sku: str | None = None
    ) -> Any:
        """Pick, pack, and dispatch — Normal(mean, std) minutes.

        The mean is divided by ``_dispatch_speed``: a higher-priority dispatch
        policy (the agent's action[2]) packs faster → lower delivery latency →
        higher reward. With the neutral default 1.0 the mean is unchanged.

        task 9.1: the duration is CARRIED to ``_delivery`` rather than accumulated here, so
        that an order whose SKU turns out to be unavailable contributes to neither side of
        ``avg_delivery_time_min``. Accumulating it here would inflate that KPI exactly when
        service degraded -- a metric moving the wrong way.
        """
        mean = self._config.pick_pack_mean_min / self._dispatch_speed
        duration = max(
            1.0,
            self._streams["pick_pack"].normal(mean, self._config.pick_pack_std_min),
        )
        yield env.timeout(duration)
        logger.debug("pick_pack_done", order_id=order_id, duration_min=round(duration, 2))
        env.process(self._delivery(env, order_id, sku, duration))

    def _delivery(
        self,
        env: simpy.Environment,
        order_id: int,
        sku: str | None = None,
        pick_pack_min: float = 0.0,
    ) -> Any:
        """Delivery, conditional on the demanded SKU actually being in stock.

        **task 9.1 (R5.38) -- the change that makes a stockout cost something.** The stock
        check happens FIRST. If the demanded SKU is at zero, this records an unmet demand
        event and returns WITHOUT touching ``orders_delivered`` or either time total. Before
        this, both incremented unconditionally *before* the line
        ``self._inventory[sku] = max(0.0, ... - 1.0)``, so a stockout was free and all six
        KpiVector fields were blind to stock availability.

        The refused alternative, named so it is not revisited: leaving this unconditional and
        deriving stockouts harness-side is the state this replaces, and that state produced a
        KPI vector that could not see its own subject.

        ``failure_rate_multiplier`` (>=1.0) raises the probability of a delivery retry, which
        adds the original travel time again. With the default multiplier of 1.0 the failure
        probability is 0.0 — i.e. baseline behavior is unchanged.
        """
        travel_stream = self._streams["travel"]
        base_travel_min = travel_stream.uniform(10.0, 45.0)
        noise = travel_stream.normal(0.0, 3.0)
        travel_time = max(5.0, base_travel_min + noise)
        yield env.timeout(travel_time)
        # Probabilistic delivery retry under shock.
        failure_prob = min(0.5, 0.05 * (self._failure_rate_multiplier - 1.0))
        if failure_prob > 0.0 and travel_stream.random() < failure_prob:
            yield env.timeout(travel_time)
            travel_time *= 2.0

        # An empty catalogue is not a stockout: nothing was demanded of it. Recording one
        # would manufacture unmet demand out of an absent world (I-7).
        if sku is None or sku not in self._inventory:
            logger.debug("delivery_uncounted", order_id=order_id, reason="no-sku")
            return

        self._metrics.demand_events += 1
        if self._inventory[sku] <= 0.0:
            self._metrics.unmet_demand_events += 1
            logger.debug("unmet_demand", order_id=order_id, sku=sku)
            return

        self._metrics.orders_delivered += 1
        self._metrics.total_delivery_time_min += travel_time
        self._metrics.total_pick_pack_time_min += pick_pack_min
        self._accrue_inventory_time(float(env.now))
        self._inventory[sku] = max(0.0, self._inventory[sku] - 1.0)
        logger.debug("delivery_done", order_id=order_id, travel_min=round(travel_time, 2))

    def _restock(self, env: simpy.Environment) -> Any:
        """Inventory Sentinel-triggered restock when stock falls below safety level.

        ``safety_stock`` and ``restock_amount`` come from the policy levers
        (action[1]/action[0]): a higher threshold restocks earlier (fewer
        stockouts, more holding/spoilage). Neutral defaults (50, 200) reproduce
        the historical behaviour.
        """
        check_interval = 5.0

        while True:
            yield env.timeout(check_interval)
            safety_stock = self._restock_threshold
            restock_amount = 200.0 * self._order_qty_mult
            for sku, level in list(self._inventory.items()):
                if level < safety_stock:
                    lead_time = self._streams["restock"].uniform(30.0, 120.0) * self._lead_time_mult
                    yield env.timeout(lead_time)
                    # task 9.3: integrate the OLD level over the interval it actually held,
                    # before replacing it.
                    self._accrue_inventory_time(float(env.now))
                    self._inventory[sku] = level + restock_amount
                    self._metrics.restocks_triggered += 1
                    logger.debug("restock", sku=sku, new_level=self._inventory[sku])

    def _spoilage(self, env: simpy.Environment) -> Any:
        """Freshness Guardian — quality degrades over time; spoiled items are flagged.

        ``spoilage_rate_multiplier`` scales the per-tick decay rate so monsoon /
        cold-chain shocks visibly inflate the spoilage KPI.
        """
        decay_rate = 0.01 * self._spoilage_rate_multiplier
        spoilage_threshold = 0.3
        check_interval = 10.0

        while True:
            yield env.timeout(check_interval)
            for sku in list(self._freshness.keys()):
                self._freshness[sku] -= decay_rate * check_interval
                if self._freshness[sku] < spoilage_threshold:
                    self._metrics.orders_spoiled += 1
                    self._freshness[sku] = 1.0
                    logger.debug("spoilage", sku=sku)

    def start(
        self,
        external_demand: bool = False,
        initial_inventory: Mapping[str, float] | None = None,
    ) -> SupplyChainSimulation:
        """Create one persistent SimPy env + processes and reset accumulators.

        Unlike the old run()-per-call shape, the env survives across advance()
        calls so the Gym wrapper's state (inventory, metrics) persists between
        steps. Returns self for chaining.

        ``external_demand=True`` (ADR-052) turns OFF the endogenous Poisson arrival
        process so demand comes only from ``inject_orders()`` — the path a pluggable
        ``WorldSource`` uses to drive the world. The default (False) is the
        historical self-generating behaviour the existing tests depend on.

        ``initial_inventory`` (purpose-achievement-audit R4.9) is the opening stock the
        caller's world source supplied. Omitting it keeps the historical literal
        ``{sku_i: 100.0 for i in range(10)}``, which stays correct for a *seeded* world:
        there the opening stock is a declared component of the scenario. It must NOT be
        substituted when a non-seeded source supplies nothing — ``WorldRuntime`` passes an
        empty mapping in that case, so the world starts genuinely empty and perceives as
        degraded rather than reporting invented stock as if a real store had reported it.
        """
        self._metrics = SimulationMetrics()
        if initial_inventory is None:
            self._inventory = {f"sku_{i}": 100.0 for i in range(10)}
        else:
            self._inventory = {sku: float(level) for sku, level in initial_inventory.items()}
        self._freshness = {sku: 1.0 for sku in self._inventory}
        self._order_seq = 0
        # tasks 9.3 / 9.5: reset the integral and the trace with the rest of the
        # accumulators. A trace surviving a restart would attribute one scenario's demand to
        # the next, and a stale accrual baseline would credit inventory-time to a run that
        # did not hold it.
        self._demand_trace = DemandTrace()
        self._last_accrual_min = 0.0
        env = self._init_env()
        if not external_demand:
            env.process(self._order_arrival(env))
        env.process(self._restock(env))
        env.process(self._spoilage(env))
        self._env = env
        self._sim_time_min = 0.0
        return self

    def advance(self, duration_hours: float) -> SimulationMetrics:
        """Step the persistent env forward by ``duration_hours`` (no reset)."""
        if self._env is None:
            self.start()
        assert self._env is not None
        self._sim_time_min += duration_hours * 60.0
        self._env.run(until=self._sim_time_min)
        # task 9.3: close the integral at the advance boundary, so inventory held over an
        # interval with no mutation in it is still counted. Without this, a run whose stock
        # never moved would report zero inventory-minutes -- i.e. no holding cost for holding
        # stock, which is the opposite of the truth.
        self._accrue_inventory_time(self._sim_time_min)
        return self._metrics

    def run(self, duration_hours: float | None = None) -> SimulationMetrics:
        """One-shot run for the given duration (start + single advance).

        Behaviour is identical to the historical implementation under the neutral
        default policy — existing determinism/monotonicity tests are unaffected.
        """
        duration = duration_hours or self._config.simpy_default_duration_hours
        self.start()
        metrics = self.advance(duration)
        logger.info(
            "simulation_complete",
            duration_hours=duration,
            **metrics.to_dict(),
        )
        return metrics
