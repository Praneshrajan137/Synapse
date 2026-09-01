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
    from uplift.interfaces import Observation

__all__ = [
    "ForesightPolicy",
    "NoOpRecordingPolicy",
    "TwoPassResult",
    "run_two_pass",
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
class TwoPassResult:
    """Both passes of one replicate, with the invariant that links them recorded.

    ``demand_identical`` is not decoration. It is the check that makes the whole protocol sound:
    if pass two's demand differed from pass one's, the foresight policy was optimising against
    demand that never arrived, and the regret would be an artefact of the substreams rather than
    a fact about the world.
    """

    seed: int
    trace: DemandTrace
    baseline: SupplyChainSimulation
    foresight: SupplyChainSimulation
    demand_identical: bool

    @property
    def usable(self) -> bool:
        """A replicate whose two passes saw different demand is not usable evidence."""
        return self.demand_identical and len(self.trace) > 0


def run_two_pass(
    seed: int,
    *,
    hours: float,
    restock_threshold: float,
    build: object = None,
) -> TwoPassResult:
    """Run pass one (no-op, recording) then pass two (foresight) at the **same seed**.

    ``restock_threshold`` is passed explicitly rather than read here, so the caller -- which
    already resolved it from the committed policy file -- remains the single place that decides
    it. A second read inside this function would be a second opinion about a committed value.

    ``build`` is an injection seam for tests; ``None`` constructs a plain engine. The harness
    supplies its own builder so the shock mapping stays in one place.
    """

    def _make() -> SupplyChainSimulation:
        if build is not None:
            made = build(seed)  # type: ignore[operator]
            assert isinstance(made, SupplyChainSimulation)
            return made
        sim = SupplyChainSimulation(seed=seed)
        sim.start()
        sim.set_policy(restock_threshold=restock_threshold)
        return sim

    # ── Pass one: observe the world's own demand path ────────────────────────────────
    baseline = _make()
    baseline.advance(hours)
    recorded = baseline.demand_trace

    # ── Pass two: same seed, foresight constructed FROM the completed trace ──────────
    foresight_sim = _make()
    policy = ForesightPolicy(trace=recorded)
    # Step in window-sized slices so the policy gets to act repeatedly, which is what makes it
    # a policy rather than a single up-front provisioning decision.
    slices = max(1, int((hours * 60.0) // FORESIGHT_WINDOW_MIN))
    slice_hours = hours / slices
    for _ in range(slices):
        obs_time = foresight_sim.sim_time_min
        foreseen = policy.demand_in_window(obs_time)
        for sku, units in foreseen.items():
            on_hand = float(foresight_sim.inventory.get(sku, 0.0))
            if units - on_hand > 0.0:
                foresight_sim.add_stock(sku, units - on_hand)
        foresight_sim.advance(slice_hours)

    return TwoPassResult(
        seed=seed,
        trace=recorded,
        baseline=baseline,
        foresight=foresight_sim,
        demand_identical=(
            recorded.as_tuples() == foresight_sim.demand_trace.as_tuples()
        ),
    )
