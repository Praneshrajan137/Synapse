"""SYNAPSE Orchestrator — Meta-RL weight learning tests (I-2)."""
from __future__ import annotations

import numpy as np
import pytest

from orchestrator.meta_rl.meta_agent import OBJECTIVES, MetaRLAgent


class TestWeightInitialisation:
    def test_initial_weights_uniform(self) -> None:
        agent = MetaRLAgent()
        assert np.allclose(agent.weights, 1.0)

    def test_weights_sum_to_n_objectives(self) -> None:
        agent = MetaRLAgent()
        weights = agent.get_weights({})
        assert sum(weights.values()) == pytest.approx(8.0, abs=0.01)


class TestAdaptiveWeights:
    def test_disruption_boosts_disruption_readiness(self) -> None:
        agent = MetaRLAgent()
        normal = agent.get_weights({"active_disruptions": 0})
        boosted = agent.get_weights({"active_disruptions": 2})
        assert boosted["disruption_readiness"] > normal["disruption_readiness"]

    def test_low_fill_rate_boosts_inventory(self) -> None:
        agent = MetaRLAgent()
        normal = agent.get_weights({"avg_fill_rate": 0.95})
        boosted = agent.get_weights({"avg_fill_rate": 0.85})
        assert boosted["inventory_fill_rate"] > normal["inventory_fill_rate"]

    def test_peak_hour_boosts_routing(self) -> None:
        agent = MetaRLAgent()
        offpeak = agent.get_weights({"hour_of_day": 8})
        peak = agent.get_weights({"hour_of_day": 12})
        assert peak["route_efficiency"] > offpeak["route_efficiency"]


class TestPolicyGradient:
    def test_no_update_with_small_history(self) -> None:
        agent = MetaRLAgent()
        initial = agent.weights.copy()
        for i in range(5):
            agent.update({"demand_accuracy": 0.4})
        assert np.allclose(agent.weights, initial)

    def test_update_adjusts_underperforming(self) -> None:
        agent = MetaRLAgent()
        for _ in range(15):
            outcome = {obj: 0.3 for obj in OBJECTIVES}
            outcome["demand_accuracy"] = 0.9
            agent.update(outcome)
        # demand_accuracy should have decreased weight (over-performing)
        # others should have increased
        assert agent.weights[0] < agent.weights[1]

    def test_independent_of_agent_rewards(self) -> None:
        """I-2: Meta-RL learns weight vectors, never agent reward functions."""
        agent = MetaRLAgent()
        assert not hasattr(agent, "agent_rewards")
        assert not hasattr(agent, "reward_function")
