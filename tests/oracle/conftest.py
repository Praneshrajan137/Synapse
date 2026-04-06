"""SYNAPSE Oracle Tests — Twin simulation fixtures."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from digital_twin.simulation.monte_carlo import (  # noqa: E402
    MonteCarloOutput,
    MonteCarloRunner,
    ShockParams,
)


@pytest.fixture()
def twin_runner() -> MonteCarloRunner:
    return MonteCarloRunner()


@pytest.fixture()
def baseline_shock() -> ShockParams:
    return ShockParams()


@pytest.fixture()
def demand_spike_shock() -> ShockParams:
    return ShockParams(demand_multiplier=2.0)


@pytest.fixture()
def supplier_failure_shock() -> ShockParams:
    return ShockParams(lead_time_multiplier=2.0, failure_rate_multiplier=3.0)
