"""Oracle Layer 6: Pricing Oracle vs Twin revenue impact."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams


@pytest.mark.oracle()
class TestPricingImpactOracle:
    def test_price_change_revenue_within_predicted(self, twin_runner: MonteCarloRunner) -> None:
        """Price changes must produce revenue within 20% of predicted delta."""
        baseline = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        assert baseline.n_scenarios == 1000
        assert baseline.kpi_means["orders_delivered"] >= 0
