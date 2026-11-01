"""The foresight comparator: six arms at one seed, one cadence, one world cell (R5.1, R5.37).

Feature: decision-quality-proof, task 10.2. Implements **AD-18**.

**Read this first if the module name or ``run_three_pass`` misleads you.** The comparator was
authored as two passes, gained the ``(s, S)`` reference arm in session 5 (conflict M), the
hindsight arm in session 9 (ADR-055 **D2.5.4**), the tuned static arm E in session 10 (D2.6) and
the structure-aware arm O in task 13.7b, so it now runs **six** -- every one of them in the world
cell it is handed (``world``; ``None`` is the world before structures 1 and 3). The function
keeps the name ``run_three_pass`` because every caller and landed property imports it under that
name; the rename is owed and is recorded here rather than hidden.

**Foresight is a recorded trace, not a re-derivation.** ``DecisionPolicy.decide(obs)`` sees only
present state, so a perfect-foresight policy cannot exist without knowing future demand. Two
ways to get it, and only one is sound:

* **Chosen:** run the scenario once with a no-op policy, record the ``DemandTrace``, then replay
  the **same seed** with a policy constructed *from that completed trace*. The demand path is
  drawn from the ``demand`` and ``sku_choice`` substreams, which no arm's actions consume
  (Property 52), so pass two's demand is provably identical to pass one's.
* **Refused:** re-derive the demand path by replaying the generator. That couples the comparator
  to the arrival process's internals and breaks the moment E2c changes it -- and E2c changes it
  five times.

**The seam that must NOT be used, and why.** ``start(external_demand=True)`` +
``inject_orders(n)`` looks like a foresight seam and is not: it takes a bare **count**, discards
the per-SKU identity, and *replaces* the endogenous demand process. A run using it is not the
unmodified twin, so a regret measured through it would answer a different question than R5.1
asks.

**Stated cost.** The two-pass protocol **doubles** the twin cost of every comparator replicate.
That is why the regret measurement gets its own ``uplift.yml`` job rather than sharing
``uplift-proof``'s 350-minute budget, and why it is a category-4 workload under I-0 that never
runs on a development machine.
"""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING, Final

from digital_twin.simulation.engine import DemandTrace, SupplyChainSimulation
from uplift.interfaces import PolicyAction

if TYPE_CHECKING:  # annotation-only
    from collections.abc import Callable, Mapping

    from digital_twin.simulation.world import ResolvedWorld
    from uplift.interfaces import DecisionPolicy, Observation

__all__ = [
    "ForesightPolicy",
    "HindsightOraclePolicy",
    "NoOpRecordingPolicy",
    "ThreePassResult",
    "run_single_arm",
    "run_three_pass",
    "stocked_skus",
]

#: How far ahead the foresight policy provisions, in simulated minutes. Matches the engine's
#: own restock check interval (5.0 min) times a small horizon, so the policy replenishes on the
#: same cadence the twin can actually act on. Not a tuning knob: a longer window would let
#: foresight hold stock it does not need yet and pay holding cost the optimum would not.
FORESIGHT_WINDOW_MIN: Final[float] = 60.0


class NoOpRecordingPolicy:
    """Pass one: change nothing, so the recorded demand is the world's own.

    Deliberately not "a policy that does something harmless". Any action at all would consume
    from the ``pick_pack``/``travel``/``restock`` substreams and, more importantly, would change
    the stock trajectory -- and pass one exists solely to observe the demand path, not to
    perform well. Its KPIs are never scored.
    """

    name = "no_op_recording"

    def decide(self, obs: Observation) -> PolicyAction:  # noqa: ARG002 - protocol signature
        return PolicyAction()


@dataclasses.dataclass
class ForesightPolicy:
    """Pass two: an oracle that knows exactly what will be demanded, and orders exactly that.

    Constructed **from a completed trace**. At each decision point it looks ahead
    :data:`FORESIGHT_WINDOW_MIN` simulated minutes, sums the demand per SKU in that window, and
    reorders the shortfall against present stock -- no more, no less.

    That is the right shape for the objective ADR-055 declares: ordering less causes stockouts
    (weighted 8.0), ordering more causes holding cost (weighted 1.0) and, once structure 4
    lands, spoilage. Ordering exactly the shortfall minimises their sum. It is an *oracle*
    rather than a provable optimum under lead time, and that limit is stated rather than
    implied: with a non-zero lead time the true optimum would order earlier, so this policy is
    a **lower bound on achievable performance**, which makes the regret it induces a
    **conservative** estimate. A conservative regret is the safe direction here -- it can only
    understate how much room intelligence has, never overstate it.
    """

    trace: DemandTrace
    name: str = "perfect_foresight"
    window_min: float = FORESIGHT_WINDOW_MIN

    def demand_in_window(self, start_min: float) -> dict[str, float]:
        """Per-SKU demanded units in ``[start_min, start_min + window)``."""
        end = start_min + self.window_min
        totals: dict[str, float] = {}
        for event in self.trace.events:
            if start_min <= event.t_min < end:
                totals[event.sku] = totals.get(event.sku, 0.0) + event.units
        return totals

    def decide(self, obs: Observation) -> PolicyAction:
        """Order the shortfall between foreseen demand and present stock."""
        foreseen = self.demand_in_window(float(obs.sim_time))
        reorders: dict[str, float] = {}
        for sku, units in foreseen.items():
            on_hand = float(obs.inventory.get(sku, 0))
            shortfall = units - on_hand
            if shortfall > 0.0:
                reorders[sku] = shortfall
        return PolicyAction(reorder_quantities=reorders)


@dataclasses.dataclass
class HindsightOraclePolicy:
    """Arm D: an oracle by CONSTRUCTION rather than by label (ADR-055 D2.5.4).

    **NOT `frozen=True`, and the reason is the interface rather than taste.**
    ``uplift/interfaces.py::DecisionPolicy`` declares ``name: str`` as a settable variable, so a
    frozen dataclass does not satisfy the protocol every arm is driven through -- ``mypy --strict``
    reports it at the ``_drive`` call site. ``ForesightPolicy`` is a plain dataclass for the same
    reason. The repair is at this declaration and not at the call site, and it costs nothing real:
    ``frozen=True`` was claiming an immutability this class never had, because ``trace`` holds a
    mutable ``DemandTrace`` whose ``events`` list is a live reference.

    **The label names the mechanism on purpose.** ``perfect_foresight`` was a name that outran
    its behaviour for four sessions -- run ``34590696403`` measured that arm leaving **8.2% of
    demand unmet** while the incumbent left none (finding 59) -- so this arm is named after what
    it does: it covers **cumulative** generated-but-not-yet-consumed demand.

    **Why arm C's rule cannot serve, walked to the code rather than cited.**
    ``DemandTrace.record`` is called from ``engine.py::_order_arrival`` at demand GENERATION
    time. Stock is decremented, and ``unmet_demand_events`` incremented, at the bottom of
    ``engine.py::_delivery`` -- after ``_pick_pack_dispatch``'s ``normal(8.0, 2.0)`` timeout and
    ``_delivery``'s own ``uniform(10.0, 45.0) + normal(0.0, 3.0)`` travel timeout. So fulfilment
    lags generation by a mean of about ``8.0 + 27.5 = 35.5`` simulated minutes at the committed
    ``TwinConfig`` defaults -- roughly **59% of a 60-minute window, and on a draw it can exceed
    the window entirely.** ``ForesightPolicy`` sizes stock against the units GENERATED in
    ``[t, t + window)`` and holds no buffer, while the units actually CONSUMED in that interval
    were generated in roughly ``[t - 35.5, t + window - 35.5)``. The two sets differ, the arm
    carries nothing to absorb the difference, and the shortfall is charged at weight 8.0 twice
    (finding 60). **Perfect foresight of window totals is not perfect foresight of arrival
    order.**

    **The rule, and why it needs no inventory reading and no chosen constant.** Let ``G(x)`` be
    the units the trace records as generated strictly before ``x``, ``I`` the opening stock, and
    ``w`` the interval until this arm's next decision. Every unit consumed in ``[t, t + w)`` was
    generated before ``t + w``, so holding ``G(t + w) - consumed(t)`` units at ``t`` is
    **sufficient** to serve every fulfilment that can arrive before the next decision. Because
    ``add_stock`` is instantaneous and the only other mover of stock is ``_delivery``'s
    one-unit decrement, ``on_hand(t) = I + supplied(t) - consumed(t)``; substituting it,
    ``consumed`` and ``on_hand`` both **cancel** and the target reduces to

    ``cumulative supply through t + w = max(I, G(t + w))``

    which is a function of the recorded trace and the opening stock alone. Two consequences that
    are the whole point:

    * **It reads no inventory**, so the ``Mapping[str, int]`` truncation D2.5.1 records cannot
      bias it in either direction -- and it can therefore be driven through the SAME
      observe-decide-apply loop as arms A and B, which arm C is not (see ``run_three_pass``).
      The only field of the ``Observation`` it touches is ``sim_time``, a float ``observe``
      passes through unmodified.
    * **It contains no additive buffer term at all.** ``max(I, G)`` is the pointwise-least
      cumulative supply that satisfies coverage: ``I`` is forced because ``add_stock`` cannot
      remove stock, and ``G(t + w)`` is the coverage requirement itself. A comparator is allowed
      no chosen constant, and this one has none --
      ``tests/uplift/test_hindsight_oracle_admissibility_property.py`` asserts the absence
      rather than promising it.

    **The domain the optimality claim holds over, stated so it is not overclaimed.** The arm is
    optimal given **instantaneous replenishment and no ordering lead time**, which is the twin's
    committed comparator configuration (``comparator.restock_threshold: 0.0`` disables the
    engine's own ``_restock`` lead time, and ``_apply_reorders`` applies stock through
    ``sim.add_stock``). Under a non-zero lead time the true optimum would order earlier, and the
    trace records generation times only -- never the pick/pack and travel draws that decide
    *when* a unit is consumed -- so a policy able to observe fulfilment times could hold strictly
    less. This arm is therefore a **lower bound on achievable performance** and the regret it
    induces is **conservative**: it can only understate how much room intelligence has, never
    overstate it. That is the safe direction, and unlike arm C's identical claim it is not
    contradicted by the arm losing to its subject on the service terms -- it attains their exact
    floor.

    **Under a replenishment delay (structure 3, task 13.7b) the same argument moves one step.**
    An order placed at ``t`` lands at ``a(t)``, where ``a`` is THIS arm's own engine's
    ``arrival_time_for`` -- a function of seed, supplier and placement time alone, identical for
    every arm at one seed and non-decreasing in ``t`` at a fixed shock multiplier
    (``digital_twin/simulation/lead_time.py``), so reading it is the same perfect information
    about the world the demand trace already is, not leakage. Stock placed at ``t`` must then
    serve every fulfilment until the NEXT order lands at ``a(t + w)``, so the target becomes
    ``max(I, G(c))`` with ``c = min(a(t + w), horizon)`` -- capped because nothing fulfilled after
    the run ends is measured -- and the first decision starts from ``I`` alone, since no earlier
    order exists. With ``arrival_time_for`` ``None`` the arm is the rule above, byte for byte.
    Its unmet demand is then the FLOOR, not zero: only demand fulfilled before a SKU's first
    arrival ``a(0)`` can go unmet, and before ``a(0)`` every arm holds the same opening stock
    against the same fulfilments, so no arm can do better there and this arm does no worse
    anywhere after it.

    **What would make this arm wrong.** Instantaneous replenishment: ``unmet_demand_events > 0``
    in any replicate, which ``cost_decomposition.hindsight_attains_zero_unmet`` reports. Under a
    delay: any arm leaving strictly LESS demand unmet than this one at any replicate, which
    ``hindsight_unmet_pointwise_least`` reports. Both are per-run, so the falsifier is mechanical
    rather than remembered.
    """

    trace: DemandTrace
    #: The twin's OPENING per-SKU levels, read from ``sim.inventory`` before the first advance.
    #: Read rather than chosen: the engine's ``start()`` literal is not restated here, and a run
    #: whose world opens with different stock produces a different -- correct -- schedule.
    opening_stock: Mapping[str, float]
    name: str = "hindsight_cumulative_cover"
    #: The interval until this arm's NEXT decision, which is what coverage must span. Defaults
    #: to :data:`FORESIGHT_WINDOW_MIN` so a standalone construction matches arm C's horizon;
    #: ``run_three_pass`` passes the REALISED slice length instead, because the two differ
    #: whenever the horizon does not divide evenly by the window and a window shorter than the
    #: cadence leaves a coverage hole -- the same class of defect as arm C's generation offset.
    window_min: float = FORESIGHT_WINDOW_MIN
    #: When an order for a SKU placed at a given minute LANDS, bound to this arm's own engine
    #: (``SupplyChainSimulation.arrival_time_for``). ``None`` means stock lands when ordered --
    #: structure 3 off -- and :meth:`orders_at` is then the instantaneous rule, byte for byte.
    arrival_time_for: Callable[[str, float], float] | None = None
    #: The run's last simulated minute, which caps coverage under a delay. REQUIRED with
    #: ``arrival_time_for`` and refused without it, rather than defaulted: a cap nobody stated
    #: would be a chosen constant inside a comparator that is allowed none.
    horizon_min: float | None = None

    def __post_init__(self) -> None:
        """Refuse a horizon that caps nothing, and a delay with no horizon, by construction."""
        if self.arrival_time_for is None:
            if self.horizon_min is not None:
                raise ValueError(
                    f"horizon_min = {self.horizon_min!r} is given without arrival_time_for; it "
                    "caps a delayed arrival and would cap nothing here, so it is refused rather "
                    "than read as if it had"
                )
            return
        horizon = self.horizon_min
        if horizon is None or not math.isfinite(horizon) or horizon <= 0.0:
            raise ValueError(
                f"arrival_time_for is set but horizon_min = {horizon!r}; a delayed hindsight arm "
                "needs the run's last minute, finite and positive, and it is not defaulted"
            )

    def generated_before(self, end_min: float) -> dict[str, float]:
        """Per-SKU units the trace records as GENERATED strictly before ``end_min``.

        Strictly before, because a unit generated at exactly ``end_min`` cannot be consumed at
        or before it: ``_delivery`` runs after two positive timeouts.
        """
        totals: dict[str, float] = {}
        for event in self.trace.events:
            if event.t_min < end_min:
                totals[event.sku] = totals.get(event.sku, 0.0) + event.units
        return totals

    def generated_before_each(self, ends: Mapping[str, float]) -> dict[str, float]:
        """:meth:`generated_before` with one cut-off PER SKU; SKUs absent from ``ends`` skipped.

        Summed in the same event order, so a SKU whose cut-off equals ``generated_before``'s
        receives the identical float. Needed because, under a delay, each SKU's coverage ends
        when ITS supplier's next order lands.
        """
        totals: dict[str, float] = {}
        for event in self.trace.events:
            end = ends.get(event.sku)
            if end is not None and event.t_min < end:
                totals[event.sku] = totals.get(event.sku, 0.0) + event.units
        return totals

    def coverage_end(self, sku: str, next_order_min: float) -> float:
        """Until when supply must cover demand, if the next order for ``sku`` is placed then.

        No delay: ``next_order_min`` itself. Under a delay: when that order LANDS, never past the
        run's end -- ``min(a(next_order_min), horizon)``.
        """
        arrival = self.arrival_time_for
        if arrival is None:
            return next_order_min
        horizon = self.horizon_min
        if horizon is None:  # refused in __post_init__; restated so the type narrows
            raise ValueError("a delayed hindsight arm needs horizon_min")
        return min(arrival(sku, next_order_min), horizon)

    def supply_target(self, sku: str, *, generated: Mapping[str, float]) -> float:
        """Cumulative units supplied for ``sku`` once ``generated`` demand must be covered.

        ``max(opening, generated)`` -- the closed form the class docstring derives. Exposed as a
        method rather than inlined so the property test can assert that the telescoping sum of
        :meth:`orders_at` reaches it, which is the link between mechanism and closed form.
        """
        return max(float(self.opening_stock.get(sku, 0.0)), float(generated.get(sku, 0.0)))

    def orders_at(self, start_min: float) -> dict[str, float]:
        """Raise cumulative supply to cover every unit generated before the next decision.

        Stateless: the cumulative supply already placed by the previous decision is
        ``max(I, G(start_min))`` by the same closed form, so this arm needs no order history and
        two arms constructed from one trace decide identically. Non-positive increments are
        omitted rather than sent as zeros, because ``add_stock`` clamps at zero and a zero-valued
        reorder would make ``_apply_reorders``'s skip do the work of the decision.

        Under a delay the previous decision covered through ``coverage_end(sku, start_min)`` --
        when THIS decision's order lands -- which is read at ``start_min`` itself rather than
        rebuilt from ``start_min - window``, so the telescoping is exact on the driver's
        accumulated clock. Before the run's first minute no order exists, so the decision at
        ``0.0`` starts from the opening stock alone.
        """
        if self.arrival_time_for is not None:
            return self._delayed_orders_at(start_min)
        held = self.generated_before(start_min)
        due = self.generated_before(start_min + self.window_min)
        orders: dict[str, float] = {}
        # `due` keys are a superset of `held` keys, so iterating `due` is total.
        for sku in due:
            target_now = self.supply_target(sku, generated=held)
            target_next = self.supply_target(sku, generated=due)
            if target_next > target_now:
                orders[sku] = target_next - target_now
        return orders

    def _delayed_orders_at(self, start_min: float) -> dict[str, float]:
        """:meth:`orders_at` under a delay: per-SKU coverage ends, opening stock at minute 0."""
        skus = sorted({event.sku for event in self.trace.events})
        due = self.generated_before_each(
            {sku: self.coverage_end(sku, start_min + self.window_min) for sku in skus}
        )
        held = (
            self.generated_before_each({sku: self.coverage_end(sku, start_min) for sku in skus})
            if start_min > 0.0
            else {}
        )
        orders: dict[str, float] = {}
        # `coverage_end` is non-decreasing in its instant, so `due` covers `held` per SKU.
        for sku in skus:
            target_now = self.supply_target(sku, generated=held)
            target_next = self.supply_target(sku, generated=due)
            if target_next > target_now:
                orders[sku] = target_next - target_now
        return orders

    def decide(self, obs: Observation) -> PolicyAction:
        """Order the cumulative shortfall. Reads ``obs.sim_time`` and nothing else.

        Deliberately blind to ``obs.inventory``: that is what makes this arm immune to the
        ``Mapping[str, int]`` truncation asymmetry recorded in ADR-055 D2.5.1, and
        ``test_the_arm_reads_no_inventory_at_all`` asserts the blindness rather than trusting
        this sentence.
        """
        return PolicyAction(reorder_quantities=self.orders_at(float(obs.sim_time)))


@dataclasses.dataclass(frozen=True)
class ThreePassResult:
    """All arms of one replicate, with the invariant that links them recorded.

    **WHY THERE ARE THREE ARMS AND NOT TWO -- CONFLICT M, SESSION 5.** The committed
    two-pass form ran a no-op against perfect foresight and reported the difference as the
    ``(s, S)`` regret R5.1 asks for. Run ``34366766968`` measured
    ``regret = 8.937888952967558`` with ``comparator_headroom`` equal to it **to every
    digit**, and that equality was not a coincidence -- it was an identity. ``regret`` is
    ``aggregate(policy) - aggregate(reference)`` and the headroom was
    ``mean_baseline - mean_foresight`` over the same two arms, so they were the same
    subtraction. Two consequences:

    1. The measured quantity was the NO-OP's regret. In service-point equivalents
       ``8.9379`` is about 112 points, against an incumbent whose recorded shortfall against
       its own newsvendor target is about 3.3. It described a different subject.
    2. ``digital_twin/simulation/policy.py``'s ``must_be_below_measured_headroom`` guard,
       which exists to keep ``material`` reachable-but-not-inevitable, admitted exactly the
       margins BELOW the regret they would be judged against. Every margin inside ADR-055
       D2.5's own bracket (``0.264``-``0.709`` objective units) therefore forced
       ``material`` by construction, and ``material`` is the verdict that stops this spec.
       **A verdict that cannot be anything else is not a verdict.**

    Adding the reference arm fixes (1). Retaining the no-op arm is what fixes (2): the
    judged contrast becomes ``reference - foresight`` while the bound stays
    ``no_op - foresight``, and the bound no longer contains the quantity it bounds.
    ``HANDOFF.md``'s note that landing the reference arm would by itself make the two "stop
    being the same expression" was wrong, and that correction is why this arm survives
    rather than being replaced.

    **``demand_identical`` is not decoration and is now six-way.** If any arm's demand path
    differed from the others', the arms were not compared on the same world and the regret
    would be an artefact of the substreams. Arms B to E and O act, which consumes from the
    ``pick_pack``/``travel`` substreams; ``demand`` and ``sku_choice`` are independent of
    those (Property 52), so identity is expected -- and it is CHECKED per replicate rather
    than assumed, with a differing replicate excluded as unusable rather than averaged in.
    """

    seed: int
    trace: DemandTrace
    #: Arm A. No decisions at all. Supplies the INDEPENDENT bound the margin guard needs.
    noop: SupplyChainSimulation
    #: Arm B. The committed ``(s, S)`` reference policy -- the SUBJECT of R5.1 and task 11.
    reference: SupplyChainSimulation
    #: Arm C. The perfect-foresight oracle. RETAINED, not replaced: two committed runs
    #: (``34570166681``, ``34590696403``) were measured against it, and deleting it would make
    #: those runs unreadable. It is no longer the judged comparator -- see ``hindsight``.
    foresight: SupplyChainSimulation
    demand_identical: bool
    #: Arm O, the structure-aware base-stock arm (``uplift/oracle_arm.py``, task 16.1), wired in
    #: task 13.7b. A DECOMPOSITION arm like E: it splits E - D into the information value a
    #: non-anticipative planner can reach (E - O) and what remains beyond it (O - D). REQUIRED,
    #: unlike D and E below, because ``run_three_pass`` builds it unconditionally and the one
    #: hand-built construction site was corrected to supply it rather than this field defaulted.
    structure_aware: SupplyChainSimulation
    #: Arm D. The hindsight oracle, and from session 9 the JUDGED comparator (ADR-055 D2.5.4).
    #:
    #: **Optional only because of a same-commit coupling this repair may not take.**
    #: ``tests/uplift/test_three_arm_comparator_property.py`` constructs this dataclass with the
    #: six fields above, and that file belongs to task 10.2's property surface which this repair
    #: is not permitted to edit. A field without a default would break it at collection time. A
    #: default of ``None`` is source-compatible with both construction sites, and
    #: ``run_three_pass`` always populates it -- so in production the ``None`` branch is a guard
    #: that can only fire on a bug, never a path a real measurement takes.
    hindsight: SupplyChainSimulation | None = None
    #: Arm E. The TUNED STATIC par-level control, added in session 10 (ADR-055 D2.6).
    #:
    #: It is not an oracle and it is not a candidate for the judged contrast. Its only job is to
    #: split the judged regret into two terms that mean different things:
    #:
    #:     regret(B - D) = [cost(B) - cost(E)] + [cost(E) - cost(D)]
    #:                   =  tuning gap         +  information ceiling
    #:
    #: The first term is closable by a grid search -- no agent, no forecast, no consensus. The
    #: second is EVPI in its textbook sense, perfect information minus the best here-and-now
    #: decision, and is therefore a CEILING on everything a forecaster or a consensus system
    #: could ever win. Before arm E the artifact reported their SUM and called it the headroom
    #: that licenses the project.
    #:
    #: `None` for the same reason arm D is, and the reason is unchanged: the two landed property
    #: files that construct this dataclass by hand supply neither arm, and a field without a
    #: default would break them at collection time. `run_three_pass` populates it whenever it is
    #: given a policy, so in production the `None` branch is a guard that can only fire on a bug.
    tuned_static: SupplyChainSimulation | None = None

    @property
    def usable(self) -> bool:
        """A replicate whose arms saw different demand is not usable evidence.

        **Deliberately NOT extended to require arm D.** Its subject is the demand-path identity,
        and ``test_a_replicate_is_usable_only_when_all_three_arms_shared_a_demand_path`` pins
        this exact predicate against a hand-built result with no arm D. Adding the clause here
        would fail that property for a reason unrelated to what it asserts, in a file this
        repair may not touch. The extra requirement is a separate predicate below, and
        extending this one is owed to that property's owner.
        """
        return self.demand_identical and len(self.trace) > 0

    @property
    def usable_for_judged_contrast(self) -> bool:
        """Usable, AND carrying the oracle arm the judged contrast is computed against.

        A replicate without arm D cannot contribute to ``regret``, so counting it would pair
        199 reference costs against 200 oracle costs -- an unpaired difference, which
        ``RegretObjective.regret`` refuses outright because it is a different estimator with a
        different variance.
        """
        return self.usable and self.hindsight is not None

    @property
    def usable_for_tuning_gap(self) -> bool:
        """Usable for the judged contrast, AND carrying the tuned static control (arm E).

        A THIRD predicate rather than a widened second one, for exactly the reason the second
        exists rather than a widened first: `usable_for_judged_contrast` is what pairs
        `reference_costs` against `hindsight_costs`, and requiring arm E there would drop a
        replicate from the JUDGED contrast because a decomposition arm was missing. The judged
        number must not move when a subsidiary arm does.

        So the decomposition is reported over the subset of replicates that carry all six arms
        (arm O is always built, so arm E is the one that can be missing), and `_measure` refuses
        rather than reports if that subset is not the whole usable set -- a decomposition over a
        different denominator from the number it decomposes would sum to something that is not
        the regret.
        """
        return self.usable_for_judged_contrast and self.tuned_static is not None


def _cadence(hours: float) -> tuple[int, float]:
    """``(slices, slice_hours)``: one decision per :data:`FORESIGHT_WINDOW_MIN`, at least one."""
    slices = max(1, int((hours * 60.0) // FORESIGHT_WINDOW_MIN))
    return slices, hours / slices


def _new_arm_engine(
    seed: int,
    *,
    restock_threshold: float,
    world: ResolvedWorld | None,
    build: Callable[[int], SupplyChainSimulation] | None,
) -> SupplyChainSimulation:
    """One arm's engine, started: the ONE construction site every arm and the tuner share.

    ``world`` reaches the engine constructor here and nowhere else, so no arm at a seed can run a
    world cell the others did not. A ``build`` seam whose engine runs a different world is refused
    rather than measured, because the artifact would then name a world no arm ran.
    """
    if build is not None:
        made = build(seed)
        if made.world != world:
            raise ValueError(
                f"the injected builder's engine runs world {made.world!r}, not the requested "
                f"{world!r}; every arm must run the cell the artifact names"
            )
        return made
    sim = SupplyChainSimulation(seed=seed, world=world)
    sim.start()
    sim.set_policy(restock_threshold=restock_threshold)
    return sim


def _drive_arm(
    sim: SupplyChainSimulation,
    policy: DecisionPolicy,
    *,
    slices: int,
    slice_hours: float,
    unit_costs: Mapping[str, float],
) -> None:
    """observe -> decide -> apply -> advance: the loop `uplift/harness.py` names (R2.2).

    The one driver loop: `run_three_pass` and `run_single_arm` both call it, so an arm's levels
    cannot be SELECTED under one cadence and MEASURED under another.
    """
    # Imported here rather than at module scope, for the reason `regret.py` imports this module
    # lazily: `uplift.harness` pulls numpy, pydantic and (through `uplift.contract`) scipy, and
    # `regret.py` is imported by the fast property suite. The functions are the harness's own on
    # purpose -- see `observe`'s docstring.
    from uplift.harness import _apply_reorders, observe

    for _ in range(slices):
        action = policy.decide(observe(sim, unit_costs=unit_costs))
        if action.reorder_quantities:
            _apply_reorders(sim, action.reorder_quantities)
        sim.advance(slice_hours)


def stocked_skus(seed: int, *, world: ResolvedWorld | None) -> tuple[str, ...]:
    """The SKUs an arm's engine opens with in ``world``, sorted, READ from a started engine.

    Read rather than restated: ``SupplyChainSimulation.start`` decides the catalogue and the
    demanded SKU is drawn uniformly from it (``_draw_demanded_sku``), so it is what a per-SKU
    demand rate divides by. Started in the same world an arm's engine runs, so a world that refuses
    an unsupplied SKU refuses here, before any tuning is spent. The catalogue is the ``start()``
    literal and depends on no seed; ``seed`` is taken so the probe is as reproducible as an arm.
    """
    probe = SupplyChainSimulation(seed=seed, world=world)
    probe.start()
    return tuple(sorted(probe.inventory))


def run_single_arm(
    seed: int,
    *,
    hours: float,
    restock_threshold: float,
    policy: DecisionPolicy,
    world: ResolvedWorld | None,
    build: Callable[[int], SupplyChainSimulation] | None = None,
) -> SupplyChainSimulation:
    """Drive ONE arm at one seed, through the same construction and cadence as `run_three_pass`.

    Session 10, for `uplift/tuning.py`'s search (ADR-055 D2.6). The search needs to evaluate a
    candidate at a seed WITHOUT building the other five arms, and the alternative was a second
    driver loop inside the tuner.

    **That alternative is the one thing this repair must not do.** Two code paths that both claim
    to "drive an arm" is how a comparator stops comparing: the tuned levels would be selected
    under one set of physics and then measured under another, and the resulting tuning gap would
    be an artefact of the difference. So this calls `_new_arm_engine` and `_drive_arm`, exactly
    as `run_three_pass` does -- the sharing is now a call graph rather than two copies that
    happened to agree -- and there is one place where an arm's world, cadence, unit costs and
    restock threshold are decided. ``world`` is REQUIRED: arm E is tuned in the world it is then
    measured in, and ``None`` names the world before structures 1 and 3 rather than defaulting.

    It returns the simulation rather than a cost, for the same reason `run_three_pass` does: the
    objective lives in `uplift/regret.py` and this module does not import it.
    """
    # Lazy, exactly as `run_three_pass` does it and for the same reason: keeping numpy, pydantic
    # and scipy out of the fast suite's import closure.
    from uplift.harness import _derive_unit_costs

    slices, slice_hours = _cadence(hours)
    sim = _new_arm_engine(seed, restock_threshold=restock_threshold, world=world, build=build)
    _drive_arm(sim, policy, slices=slices, slice_hours=slice_hours, unit_costs=_derive_unit_costs())
    return sim


def run_three_pass(
    seed: int,
    *,
    hours: float,
    restock_threshold: float,
    reference_policy: DecisionPolicy,
    world: ResolvedWorld | None,
    tuned_static_policy: DecisionPolicy | None = None,
    build: Callable[[int], SupplyChainSimulation] | None = None,
) -> ThreePassResult:
    """Run every comparator arm at the **same seed**, in the **same world cell**.

    **Six arms, and the name is understated.** Session 5 added arm B (conflict M), session 9 arm
    D, the hindsight oracle that supplies the judged contrast (ADR-055 D2.5.4), session 10 arm E
    and task 13.7b arm O. The name is kept because every caller imports it; the rename is owed.

    ``world`` is REQUIRED and reaches every arm's engine through `_new_arm_engine`: ``None`` names
    the world before structures 1 and 3, and a resolved cell runs its structures in all six arms
    alike. Arm D reads its own engine's lead-time path exactly when structure 3 is on, and is the
    instantaneous rule byte for byte when it is off.

    **The stated cost of the fourth arm.** Each arm is a full twin replicate, so the twin cost of
    a comparator replicate rises from three to four -- **+33%** on the dominant term of
    ``uplift.yml::twin-regret``. It is paid rather than avoided because retaining arm C is what
    lets ONE run report both the old and the new oracle: the repair's effect becomes measurable
    within a single run instead of across two runs at two shas, and
    ``comparator_headroom_vs_foresight`` remains available as the arm-independence check that
    session 7's prediction 1 established. Dropping arm C to hold the count at three would forfeit
    both and would leave ``ForesightPolicy`` executed by nothing -- the "declared but instantiated
    nowhere" defect finding 39 recorded.

    ``restock_threshold`` is passed explicitly rather than read here, so the caller -- which
    already resolved it from the committed policy file -- remains the single place that decides
    it. A second read inside this function would be a second opinion about a committed value.
    **Every arm receives it**, which keeps the twin's own endogenous ``(s, S)`` disabled in
    every arm -- exactly what R5.36 requires once an arm supplies its own ``(s, S)`` through
    ``decide``, and why ``comparator.restock_threshold`` needed no amendment.

    ``reference_policy`` is injected for the same reason: the caller resolves it from
    ``comparator.reference_policy``, and a policy constructed here would be a second opinion
    about the subject of the measurement.

    ``build`` is an injection seam for tests; ``None`` constructs a plain engine. An injected
    engine must run ``world``, or it is refused.
    """
    # Imported here rather than at module scope, for the reason `regret.py` imports this
    # module lazily: `uplift.harness` pulls numpy, pydantic and (through `uplift.contract`)
    # scipy, and `regret.py` is imported by the fast property suite. The functions are the
    # harness's own on purpose -- see `observe`'s docstring. Two implementations of "what an
    # arm may see" and "how a reorder reaches the twin" would drift, and the arm that
    # drifted would be the one task 11's verdict is about. `uplift.oracle_arm` reads the
    # committed objective through `uplift.regret`, which is why it is lazy too.
    from uplift.harness import _derive_unit_costs
    from uplift.oracle_arm import build_structure_aware_arm

    def _make() -> SupplyChainSimulation:
        return _new_arm_engine(seed, restock_threshold=restock_threshold, world=world, build=build)

    # ONE CADENCE FOR ALL SIX ARMS. The committed two-pass form advanced pass one with a
    # single `advance(hours)` while pass two stepped in window-sized slices, so the two arms
    # being subtracted did not share a cadence. Slicing every arm removes that asymmetry and
    # changes nothing measurable: `_accrue_inventory_time` is exact accounting
    # (`sum(levels) * delta` at every mutation and every advance boundary, and its own
    # docstring records that it "draws nothing, schedules nothing, and cannot change
    # timing"), so extra boundaries between mutations integrate to the same total.
    slices, slice_hours = _cadence(hours)
    unit_costs = _derive_unit_costs()

    def _drive(sim: SupplyChainSimulation, policy: DecisionPolicy) -> None:
        """observe -> decide -> apply -> advance, through the one shared loop (`_drive_arm`)."""
        _drive_arm(sim, policy, slices=slices, slice_hours=slice_hours, unit_costs=unit_costs)

    # -- Arm A: observe the world's own demand path, deciding nothing --------------------
    # `NoOpRecordingPolicy` is now the mechanism rather than a documented intention. It was
    # declared by task 10.2 and instantiated NOWHERE in the tree, so "pass one changes
    # nothing" was a comment rather than a behaviour -- and nothing objected when the arm it
    # described became the wrong comparator. Driving it through the same loop as the others
    # makes the claim structural: identical cadence, identical observation, and an empty
    # `PolicyAction` that `_apply_reorders` skips.
    noop = _make()
    _drive(noop, NoOpRecordingPolicy())
    recorded = noop.demand_trace

    # -- Arm B: the committed (s, S) reference policy -- THE SUBJECT ---------------------
    reference = _make()
    _drive(reference, reference_policy)

    # -- Arm C: the oracle, constructed FROM arm A's completed trace ---------------------
    foresight_sim = _make()
    policy = ForesightPolicy(trace=recorded)
    # NOT routed through `_drive`, and the reason is a measurement fact rather than a
    # convenience. `Observation.inventory` is declared `Mapping[str, int]`, so `observe`
    # truncates the twin's float levels; `ForesightPolicy.decide` would then read a level up
    # to 1.0 unit low per SKU per decision and order that much extra. Over 10 SKUs and 24
    # decisions that is up to ~240 surplus units against a committed normaliser of 1000.0 at
    # weight 1.0 -- up to ~0.24 objective units of holding cost, the same order as the 0.40
    # margin. It would move the oracle's cost UP and the measured regret DOWN, which is the
    # SELF-SERVING direction (a smaller regret is sub-margin, which lets the spec proceed).
    # Not a change to make as a side effect of a refactor. Arm C therefore keeps the exact
    # arithmetic run `34366766968` measured, which also keeps the two runs comparable.
    #
    # RECORDED AS AN ASYMMETRY FOR ITS OWNER rather than silently accepted: the oracle
    # observes more precision than any arm it is compared against. Closing it means either
    # widening `Observation.inventory` to floats -- a schema change touching every fixture
    # that carries it (same-commit coupling 3) and every arm's behaviour including the
    # consensus arm's -- or accepting a documented bias. Neither belongs in this repair.
    #
    # ORDERS THROUGH `place_order`, NEVER `add_stock` (task 13.7b; finding 66's seam). With
    # structure 3 off `place_order` IS `add_stock` -- same mutation, same accrual, nothing drawn
    # or scheduled -- so every number arm C has produced is unchanged; with it on, arm C's stock
    # lands after its supplier's lead time like every other arm's. Its rule still reads ON-HAND
    # stock, so under a delay it re-orders its own pipeline each window (finding 67's defect):
    # recorded, not repaired, because arm C is retired and nothing is judged against it.
    for _ in range(slices):
        obs_time = foresight_sim.sim_time_min
        foreseen = policy.demand_in_window(obs_time)
        for sku, units in foreseen.items():
            on_hand = float(foresight_sim.inventory.get(sku, 0.0))
            if units - on_hand > 0.0:
                foresight_sim.place_order(sku, units - on_hand)
        foresight_sim.advance(slice_hours)

    baseline_path = recorded.as_tuples()

    # -- Arm D: the hindsight oracle -- THE JUDGED COMPARATOR (ADR-055 D2.5.4) -----------
    # Constructed AFTER arms A, B and C and from arm A's completed trace, so arms A-C are
    # bit-for-bit what run 34570166681 measured: each `_make()` builds an independent
    # `SupplyChainSimulation` whose six substreams are spawned from `SeedSequence(seed)`, and
    # an arm's realisation is a function of that seed and its own actions only. Session 7's
    # prediction 1 confirmed this to sixteen significant figures when arm B was added; the
    # same check is available here, because `_measure` reports
    # `comparator_headroom_vs_foresight` and it must still read 8.937888952967558.
    #
    # ROUTED THROUGH `_drive`, unlike arm C, and that is the repair rather than an oversight.
    # `_drive` observes through `uplift/harness.py::observe`, which truncates float levels to
    # int; arm C is kept out of that loop because it reads `obs.inventory` and would over-order
    # by up to ~0.24 objective units in the SELF-SERVING direction (D2.5.1). This arm reads
    # only `obs.sim_time`, so the truncation cannot reach it, and it therefore observes the
    # world through exactly the seam arms A and B do. The asymmetry is closed rather than
    # documented.
    #
    # THE WINDOW IS THE REALISED CADENCE, NOT THE NOMINAL ONE. Coverage must span the interval
    # until this arm's next decision. At the committed configuration the two coincide exactly
    # (24.0 h -> 24 slices of 60.0 min == FORESIGHT_WINDOW_MIN), so nothing about the judged
    # run changes; they diverge whenever `hours * 60.0` is not a multiple of the window, and
    # there a nominal window shorter than the slice would leave demand uncovered and this arm
    # would stop being an oracle for the same reason arm C is not one.
    #
    # UNDER STRUCTURE 3 IT READS ITS OWN ENGINE'S LEAD-TIME PATH (task 13.7b). `arrival_time_for`
    # is bound to `hindsight_sim` -- a function of seed, supplier and placement time alone, so it
    # is the same supply world every other arm faces -- and the horizon caps coverage at the
    # run's end. With structure 3 off both are `None`, so the arm is the instantaneous rule byte
    # for byte and every number it produced before this change is unchanged.
    delayed = world is not None and world.structure_3_on
    hindsight_sim = _make()
    _drive(
        hindsight_sim,
        HindsightOraclePolicy(
            trace=recorded,
            opening_stock=hindsight_sim.inventory,
            window_min=slice_hours * 60.0,
            arrival_time_for=hindsight_sim.arrival_time_for if delayed else None,
            horizon_min=hours * 60.0 if delayed else None,
        ),
    )

    # ARM E, THE TUNED STATIC CONTROL (session 10, ADR-055 D2.6). Constructed AFTER arms A-D, and
    # that is not stylistic: `SeedSequence.spawn` derives child streams BY INDEX, so an arm built
    # before the others would shift their substreams and silently move numbers three sessions
    # have confirmed to sixteen significant figures. Arm D was appended for the same reason.
    #
    # Its policy is injected: from task 13.7b it is `uplift/tuned_static.py`'s per-supplier-group
    # par-level rule with levels the caller DERIVED by a search in THIS world cell, at seeds
    # disjoint from these. Arm B's levels are READ from the engine's own defaults.
    tuned_static_sim: SupplyChainSimulation | None = None
    if tuned_static_policy is not None:
        tuned_static_sim = _make()
        _drive(tuned_static_sim, tuned_static_policy)

    # ARM O, THE STRUCTURE-AWARE BASE-STOCK ARM (task 16.1, wired by task 13.7b). Constructed LAST
    # for arm E's reason, so arms A-E are untouched by its arrival and the prediction-1 check
    # (`comparator_headroom_vs_foresight`) keeps working. Non-anticipative by construction: it
    # sees only the `Observation`, never `recorded`. Its review period is the REALISED cadence,
    # for arm D's reason above -- equal to FORESIGHT_WINDOW_MIN at every committed configuration
    # -- and its SKU count is read from its own engine rather than restated.
    structure_aware_sim = _make()
    _drive(
        structure_aware_sim,
        build_structure_aware_arm(
            world,
            seed=seed,
            hours=hours,
            review_min=slice_hours * 60.0,
            n_skus=len(structure_aware_sim.inventory),
        ),
    )

    # The identity clause is extended UNCONDITIONALLY over the arms that exist. Arm E is checked
    # exactly as arms B, C, D and O are; the `is not None` is a construction guard, not a
    # tolerated exception, because the clause cannot be evaluated against an arm never built.
    paths_identical = (
        baseline_path == reference.demand_trace.as_tuples()
        and baseline_path == foresight_sim.demand_trace.as_tuples()
        and baseline_path == hindsight_sim.demand_trace.as_tuples()
        and baseline_path == structure_aware_sim.demand_trace.as_tuples()
    )
    if tuned_static_sim is not None:
        paths_identical = paths_identical and (
            baseline_path == tuned_static_sim.demand_trace.as_tuples()
        )

    return ThreePassResult(
        seed=seed,
        trace=recorded,
        noop=noop,
        reference=reference,
        foresight=foresight_sim,
        hindsight=hindsight_sim,
        tuned_static=tuned_static_sim,
        structure_aware=structure_aware_sim,
        demand_identical=paths_identical,
    )
