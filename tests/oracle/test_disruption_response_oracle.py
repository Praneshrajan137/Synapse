"""Oracle Layer 6: Disruption Shield vs Twin KPI degradation."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams


@pytest.mark.oracle()
class TestDisruptionResponseOracle:
    def test_playbook_reduces_degradation(
        self, twin_runner: MonteCarloRunner, supplier_failure_shock: ShockParams,
    ) -> None:
        """Playbook should reduce KPI degradation: a supplier failure shock
        must visibly inflate the customer-visible delivery SLA vs baseline.

        E-DT-004 (was xfail) is now fixed: ``avg_delivery_time_min`` is the
        end-to-end customer wait (pick+pack+travel), and the supplier shock
        scales ``pick_pack_mean_min`` via ``lead_time_multiplier``, so the
        two Monte Carlo batches sample distinguishable distributions.
        """
        no_action = twin_runner.run_scenarios(
            n=1000, shock_params=supplier_failure_shock, duration_hours=4.0,
        )
        baseline = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        assert (
            no_action.kpi_means["avg_delivery_time_min"]
            > baseline.kpi_means["avg_delivery_time_min"]
        )
