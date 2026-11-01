"""Metamorphic Layer 4: twin revenue impact under a coupled price/demand shift.

Re-registered out of the Oracle layer by the purpose-achievement-audit remediation
(R12.2, R12.6). This test was titled as an oracle for the pricing agent and
imported no ``pricing_oracle`` module at all; its reference value is a closed-form
restatement of the twin's own behaviour, as the comment below has always said out
loud. That makes it a genuine and useful **metamorphic** property of the twin -
scale the demand multiplier, and revenue moves the way the algebra says - and not
an oracle for the pricing agent.

Layer membership is derived from four observable properties by
``scripts/audit/oracle_truth.py``, not from a file path or a title, so the honest
move is to register the test where it belongs rather than rename the finding away.
The genuine pricing oracle lives in ``test_pricing_elasticity_oracle.py``.
"""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams

# --- Deterministic pricing model (documented, seed-stable) -------------------
# Revenue is modelled as ``price_per_delivered_order * orders_delivered``. A
# price change is coupled to demand through a constant price elasticity, and the
# resulting demand multiplier is fed to the twin. The twin's ``orders_delivered``
# scales linearly with the demand multiplier (verified empirically against the
# SimPy engine), so the predicted revenue impact below is the twin's own
# behaviour expressed in closed form.
BASELINE_PRICE = 100.0      # revenue per delivered order at the baseline price
PRICE_INCREASE = 0.50       # +50% price intervention (relative)
PRICE_ELASTICITY = -0.4     # demand response per unit relative price change
TOLERANCE = 0.20            # R8.1: observed impact within 20% of predicted delta


@pytest.mark.metamorphic(layer=4)
class TestPricingImpactOracle:
    def test_price_change_revenue_within_predicted(self, twin_runner: MonteCarloRunner) -> None:
        """A +50% price increase with demand elasticity -0.4 drops demand to 0.80x
        baseline; because twin ``orders_delivered`` scales linearly with the demand
        multiplier, the predicted revenue impact is (1.50 * 0.80 - 1) = +20.0%.

        This test runs a seeded baseline arm and a seeded price-changed arm through
        the twin, computes the observed revenue impact, and asserts it is within 20%
        of that predicted +20.0% delta (i.e. in [16%, 24%]), failing otherwise.
        """
        new_price = BASELINE_PRICE * (1.0 + PRICE_INCREASE)
        # Elasticity couples the price change to the twin's demand multiplier.
        demand_mult = 1.0 + PRICE_ELASTICITY * PRICE_INCREASE  # -> 0.80
        predicted_impact = (new_price / BASELINE_PRICE) * demand_mult - 1.0  # -> +0.20

        # Both arms use the twin's deterministic seed sweep (range(n)), so the
        # comparison is reproducible run-to-run.
        baseline = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        priced = twin_runner.run_scenarios(
            n=1000,
            shock_params=ShockParams(demand_multiplier=demand_mult),
            duration_hours=4.0,
        )

        base_delivered = baseline.kpi_means["orders_delivered"]
        priced_delivered = priced.kpi_means["orders_delivered"]
        assert base_delivered > 0

        baseline_revenue = BASELINE_PRICE * base_delivered
        observed_revenue = new_price * priced_delivered
        observed_impact = observed_revenue / baseline_revenue - 1.0

        assert abs(observed_impact - predicted_impact) <= TOLERANCE * abs(predicted_impact), (
            f"observed revenue impact {observed_impact:.4f} is not within "
            f"{TOLERANCE:.0%} of the predicted delta {predicted_impact:.4f} "
            f"(baseline_delivered={base_delivered:.2f}, "
            f"priced_delivered={priced_delivered:.2f})"
        )
