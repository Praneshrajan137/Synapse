"""The Sentinel alone, in the kernel, costs what the eight-agent consensus arm costs (stage A).

The consensus arm's twelve costs on E5's first replicate seeds are committed in
``infrastructure/quality/verdict-pins.json``, and the verdict re-measures them on every run, so this
file compares the kernel's port with those pins as ``float.hex``: equality to the last bit. It needs
nothing beyond numpy and simpy, so it runs in the kernel workflow's light job; the decision-by-
decision comparison with the legacy agent code is ``test_sentinel_parity.py`` (full closure).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from synapse_kernel import drive
from synapse_kernel.drive import observe, run_replicate
from synapse_kernel.objective import replicate_cost
from synapse_kernel.observation import Observation
from synapse_kernel.policies import sentinel
from synapse_kernel.policies.sentinel import SentinelAlone
from synapse_kernel.world import load_world

PINS = Path(__file__).resolve().parents[2] / "infrastructure" / "quality" / "verdict-pins.json"


def _pins() -> tuple[list[int], dict[str, str]]:
    document = json.loads(PINS.read_text(encoding="utf-8"))
    return [int(seed) for seed in document["seeds"]], dict(document["costs"]["consensus"])


def test_the_sentinel_alone_costs_what_the_consensus_arm_costs_on_e5s_twelve_seeds() -> None:
    seeds, consensus = _pins()
    world = load_world()
    assert len(seeds) == 12
    mismatched = []
    for seed in seeds:
        got = replicate_cost(run_replicate(seed, SentinelAlone(), world)).hex()
        if got != consensus[str(seed)]:
            mismatched.append((seed, consensus[str(seed)], got))
    assert not mismatched, f"the port differs from the consensus pins at {mismatched}"


def test_the_comparison_can_fail_a_review_period_one_minute_longer_moves_the_costs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A guard against a vacuous comparison: one constant moved by one minute moves the costs."""
    seeds, consensus = _pins()
    monkeypatch.setattr(sentinel, "REVIEW_PERIOD_MIN", 61.0)
    world = load_world()
    moved = sum(
        replicate_cost(run_replicate(seed, SentinelAlone(), world)).hex() != consensus[str(seed)]
        for seed in seeds[:3]
    )
    assert moved == 3


def test_the_newsvendor_fractile_and_its_quantile_are_the_agents() -> None:
    assert sentinel.critical_fractile() == 8.0 / 9.0
    # The central branch of Acklam's approximation, pinned: the quantile the agent orders at.
    assert sentinel.inverse_normal(8.0 / 9.0).hex() == "0x1.387be2c5d219cp+0"
    assert (
        sentinel.newsvendor_quantity(4.0, 2.0, 8.0 / 9.0)
        == 4.0 + sentinel.inverse_normal(8.0 / 9.0) * 2.0
    )
    assert sentinel.newsvendor_quantity(1.0, 3.0, 1.0 / 9.0) == 0.0


def test_a_sku_with_no_observed_demand_gets_the_agents_default_forecast() -> None:
    world = load_world()
    sim = drive.SupplyChainSimulation(seed=7, world=world)
    sim.start()
    obs = observe(sim, costs=drive.unit_costs())
    assert obs.sim_time == 0.0
    quantities = SentinelAlone().quantities(obs)
    default = round(sentinel.newsvendor_quantity(10.0, 3.0, 8.0 / 9.0) - 100.0, 2)
    assert set(quantities) == set(obs.inventory)
    assert all(q == max(0.0, default) for q in quantities.values())


def test_the_rule_refuses_any_observation_but_the_legacy_worlds() -> None:
    class Elsewhere(Observation):
        pass

    world = load_world()
    sim = drive.SupplyChainSimulation(seed=7, world=world)
    sim.start()
    obs = observe(sim, costs=drive.unit_costs())
    foreign = Elsewhere(**{field: getattr(obs, field) for field in obs.__dataclass_fields__})
    with pytest.raises(TypeError, match="legacy world"):
        SentinelAlone().quantities(foreign)
