"""The two-pass perfect-foresight comparator (R5.1, R5.37).

Feature: decision-quality-proof, task 10.2. Implements **AD-18**.

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
from typing import TYPE_CHECKING, Final

from digital_twin.simulation.engine import DemandTrace, SupplyChainSimulation
from uplift.interfaces import PolicyAction

if TYPE_CHECKING:  # annotation-only
    from uplift.interfaces import DecisionPolicy, Observation

__all__ = [
    "ForesightPolicy",
    "NoOpRecordingPolicy",
    "ThreePassResult",
    "run_three_pass",
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


@dataclasses.dataclass(frozen=True)
class ThreePassResult:
    """All three arms of one replicate, with the invariant that links them recorded.

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

    **``demand_identical`` is not decoration and is now three-way.** If any arm's demand path
    differed from the others', the arms were not compared on the same world and the regret
    would be an artefact of the substreams. Arms B and C act, which consumes from the
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
    #: Arm C. The perfect-foresight oracle.
    foresight: SupplyChainSimulation
    demand_identical: bool

    @property
    def usable(self) -> bool:
        """A replicate whose arms saw different demand is not usable evidence."""
        return self.demand_identical and len(self.trace) > 0


def run_three_pass(
    seed: int,
    *,
    hours: float,
    restock_threshold: float,
    reference_policy: DecisionPolicy,
    build: object = None,
) -> ThreePassResult:
    """Run the no-op, ``(s, S)`` reference and foresight arms at the **same seed**.

    ``restock_threshold`` is passed explicitly rather than read here, so the caller -- which
    already resolved it from the committed policy file -- remains the single place that decides
    it. A second read inside this function would be a second opinion about a committed value.
    **All three arms receive it**, which keeps the twin's own endogenous ``(s, S)`` disabled in
    every arm -- exactly what R5.36 requires once an arm supplies its own ``(s, S)`` through
    ``decide``, and why ``comparator.restock_threshold`` needed no amendment.

    ``reference_policy`` is injected for the same reason: the caller resolves it from
    ``comparator.reference_policy``, and a policy constructed here would be a second opinion
    about the subject of the measurement.

    ``build`` is an injection seam for tests; ``None`` constructs a plain engine. The harness
    supplies its own builder so the shock mapping stays in one place.
    """
    # Imported here rather than at module scope, for the reason `regret.py` imports this
    # module lazily: `uplift.harness` pulls numpy, pydantic and (through `uplift.contract`)
    # scipy, and `regret.py` is imported by the fast property suite. The functions are the
    # harness's own on purpose -- see `observe`'s docstring. Two implementations of "what an
    # arm may see" and "how a reorder reaches the twin" would drift, and the arm that
    # drifted would be the one task 11's verdict is about.
    from uplift.harness import _apply_reorders, _derive_unit_costs, observe

    def _make() -> SupplyChainSimulation:
        if build is not None:
            made = build(seed)  # type: ignore[operator]
            assert isinstance(made, SupplyChainSimulation)
            return made
        sim = SupplyChainSimulation(seed=seed)
        sim.start()
        sim.set_policy(restock_threshold=restock_threshold)
        return sim

    # ONE CADENCE FOR ALL THREE ARMS. The committed two-pass form advanced pass one with a
    # single `advance(hours)` while pass two stepped in window-sized slices, so the two arms
    # being subtracted did not share a cadence. Slicing all three removes that asymmetry and
    # changes nothing measurable: `_accrue_inventory_time` is exact accounting
    # (`sum(levels) * delta` at every mutation and every advance boundary, and its own
    # docstring records that it "draws nothing, schedules nothing, and cannot change
    # timing"), so extra boundaries between mutations integrate to the same total.
    slices = max(1, int((hours * 60.0) // FORESIGHT_WINDOW_MIN))
    slice_hours = hours / slices
    unit_costs = _derive_unit_costs()

    def _drive(sim: SupplyChainSimulation, policy: DecisionPolicy) -> None:
        """observe -> decide -> apply -> advance: the loop `uplift/harness.py` names (R2.2)."""
        for _ in range(slices):
            action = policy.decide(observe(sim, unit_costs=unit_costs))
            if action.reorder_quantities:
                _apply_reorders(sim, action.reorder_quantities)
            sim.advance(slice_hours)

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
    for _ in range(slices):
        obs_time = foresight_sim.sim_time_min
        foreseen = policy.demand_in_window(obs_time)
        for sku, units in foreseen.items():
            on_hand = float(foresight_sim.inventory.get(sku, 0.0))
            if units - on_hand > 0.0:
                foresight_sim.add_stock(sku, units - on_hand)
        foresight_sim.advance(slice_hours)

    baseline_path = recorded.as_tuples()
    return ThreePassResult(
        seed=seed,
        trace=recorded,
        noop=noop,
        reference=reference,
        foresight=foresight_sim,
        demand_identical=(
            baseline_path == reference.demand_trace.as_tuples()
            and baseline_path == foresight_sim.demand_trace.as_tuples()
        ),
    )
