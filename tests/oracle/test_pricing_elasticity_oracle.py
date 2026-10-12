"""Oracle Layer 6: Pricing Oracle elasticity vs the Digital Twin's demand response.

Feature: purpose-achievement-audit, task 5.5 (R12.1, R12.2, R12.6, R12.7).

This is the genuine Layer 6 oracle the audit found missing. Membership is derived
by ``scripts/audit/oracle_truth.py`` from four observable properties, and this
module is written to earn each one rather than to claim it:

* **imports the subject** - ``agents.pricing_oracle.inference.serving_model``, the
  served elasticity path the inference pipeline calls as its causal estimator
  (``pipeline.py::_estimate_elasticities``);
* **invokes it on the asserted path** - ``LinearElasticityModel.estimate_elasticity``
  produces ``agent_elasticity``, which is the only source of the predicted value in
  the assertion. Perturb that method and the assertion moves;
* **reference computed independently** - the value the agent is judged against is
  the twin's *measured* delivered-order response. The twin knows nothing about
  price, elasticity, or the pricing agent, and the arm it runs is driven by
  ``TRUE_ELASTICITY``, the ground truth of the observational sample, never by the
  agent's estimate. Nothing on the reference side executes the subject;
* **tolerance constrains** - ``RATIO_TOLERANCE`` bounds an absolute difference
  between two ratios and sits far inside the ceiling committed in
  ``infrastructure/quality/oracle-layers.yaml``.

The two sides can therefore disagree. An elasticity error larger than
``RATIO_TOLERANCE / PRICE_CHANGE`` (0.30) fails the test, which is what makes the
tolerance a bound rather than a decoration.

**I-0 (local compute).** Two 1000-scenario Monte-Carlo batches drive the real SimPy
twin across a process pool, so this test is ``@pytest.mark.slow`` and belongs to
``.github/workflows/policy.yml::twin-oracle``. It is never run on the development
laptop.
"""
from __future__ import annotations

import numpy as np
import pytest

from agents.pricing_oracle.inference.serving_model import LinearElasticityModel
from digital_twin.simulation.monte_carlo import MonteCarloRunner, ShockParams

#: Ground truth of the observational sample the agent's elasticity model is fitted
#: on. It is the experiment's constant: the twin arm below is driven by it, and the
#: agent never sees it. Recovering it is the agent's job, not the test's gift.
TRUE_ELASTICITY = -0.8

#: Relative price move whose demand consequence both sides describe (+50%).
PRICE_CHANGE = 0.50

#: Absolute band on the delivered-order ratio. Ceiling is 0.50 (see
#: ``infrastructure/quality/oracle-layers.yaml``); 0.15 leaves room for Monte-Carlo
#: dispersion and the twin's mild congestion non-linearity while still failing for
#: any elasticity error above 0.30.
RATIO_TOLERANCE = 0.15

CONTROL_FEATURES = 4
SAMPLE_SIZE = 800
SAMPLE_NOISE = 0.02
SEED = 0xC0FFEE
SCENARIOS = 1000
DURATION_HOURS = 4.0


@pytest.mark.slow
@pytest.mark.oracle(subject="agents.pricing_oracle", layer=6)
class TestPricingElasticityOracle:
    def test_agent_elasticity_predicts_twin_demand_response(
        self, twin_runner: MonteCarloRunner
    ) -> None:
        """The pricing agent's served elasticity predicts the twin's measured demand
        response to a +50% price move within an absolute 0.15 of the delivered-order
        ratio.

        The agent estimates an elasticity from a seeded observational sample; that
        elasticity alone yields the predicted ratio of delivered orders after the
        price move. The twin independently simulates the ratio it actually delivers
        when demand shifts by the sample's ground truth. The assertion fails when the
        two ratios differ by more than the tolerance.
        """
        # --- The subject: the pricing agent's served elasticity path -------------
        rng = np.random.default_rng(SEED)
        controls = rng.uniform(0.0, 1.0, size=(SAMPLE_SIZE, CONTROL_FEATURES))
        sample = np.full(SAMPLE_SIZE, TRUE_ELASTICITY) + rng.normal(
            0.0, SAMPLE_NOISE, size=SAMPLE_SIZE
        )
        design = np.column_stack([controls, np.ones(SAMPLE_SIZE)])
        coefficients, *_ = np.linalg.lstsq(design, sample, rcond=None)

        elasticity_model = LinearElasticityModel(
            weights=[float(c) for c in coefficients[:CONTROL_FEATURES]],
            bias=float(coefficients[CONTROL_FEATURES]),
        )
        context = np.full((1, CONTROL_FEATURES), 0.5)
        agent_elasticity = float(elasticity_model.estimate_elasticity(context).flatten()[0])
        predicted_ratio = 1.0 + agent_elasticity * PRICE_CHANGE

        # --- The reference: the twin, which never runs the pricing agent ---------
        ground_truth_multiplier = 1.0 + TRUE_ELASTICITY * PRICE_CHANGE
        before = twin_runner.run_scenarios(n=SCENARIOS, duration_hours=DURATION_HOURS)
        after = twin_runner.run_scenarios(
            n=SCENARIOS,
            shock_params=ShockParams(demand_multiplier=ground_truth_multiplier),
            duration_hours=DURATION_HOURS,
        )
        base_delivered = before.kpi_means["orders_delivered"]
        shifted_delivered = after.kpi_means["orders_delivered"]
        assert base_delivered > 0, "twin baseline delivered no orders, so no ratio exists"
        observed_ratio = shifted_delivered / base_delivered

        # --- The comparison ------------------------------------------------------
        assert abs(predicted_ratio - observed_ratio) <= RATIO_TOLERANCE, (
            f"the pricing agent's elasticity {agent_elasticity:.4f} predicts a delivered-order "
            f"ratio of {predicted_ratio:.4f}, but the twin delivered {observed_ratio:.4f} "
            f"(base_delivered={base_delivered:.2f}, shifted_delivered={shifted_delivered:.2f}); "
            f"the gap exceeds the {RATIO_TOLERANCE} tolerance"
        )
