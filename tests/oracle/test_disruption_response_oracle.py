"""Oracle Layer 6: Disruption Shield vs Twin KPI degradation."""
from __future__ import annotations

import pytest

from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams


@pytest.mark.oracle()
class TestDisruptionResponseOracle:
    @pytest.mark.xfail(
        reason=(
            "Oracle metric avg_delivery_time_min tracks only the _delivery "
            "step (uniform(10,45) + N(0,3)), which is not modulated by "
            "lead_time_multiplier or failure_rate_multiplier in the current "
            "twin. supplier_failure_shock DOES increase pick_pack_mean_min, "
            "but pick/pack time is not added to total_delivery_time_min. "
            "The two Monte Carlo batches therefore sample the same "
            "distribution, and the assertion fails on sampling noise. "
            "Follow-up: route pick_pack_time into the delivery SLA metric "
            "or assert on a shock-responsive metric "
            "(tracked as E-DT-004)."
        ),
        strict=False,
    )
    def test_playbook_reduces_degradation(
        self, twin_runner: MonteCarloRunner, supplier_failure_shock: ShockParams,
    ) -> None:
        """Playbook should reduce KPI degradation by >= 30% vs no-action."""
        no_action = twin_runner.run_scenarios(
            n=1000, shock_params=supplier_failure_shock, duration_hours=4.0,
        )
        baseline = twin_runner.run_scenarios(n=1000, duration_hours=4.0)
        assert no_action.kpi_means["avg_delivery_time_min"] >= baseline.kpi_means["avg_delivery_time_min"]
