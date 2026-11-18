"""The kernel on its own: runs, repeats, keeps its accounting, with nothing but numpy and simpy.

These tests import nothing from the repository outside ``synapse_kernel``, so they run in the
kernel workflow's light job, whose environment holds only numpy, simpy, pytest and hypothesis. The
pinned cost below was computed by this kernel at this commit and agrees with the legacy harness by
construction (``test_legacy_parity.py`` checks the kernel against the harness on twelve seeds); here
it catches any change to the kernel's arithmetic where the legacy code is not installed.
"""

from __future__ import annotations

import math

from hypothesis import given, settings
from hypothesis import strategies as st

from synapse_kernel import drive
from synapse_kernel.drive import run_replicate
from synapse_kernel.objective import replicate_cost
from synapse_kernel.policies.base_stock import StructureAwareBaseStock, build_structure_aware_arm
from synapse_kernel.policies.tuned import GroupParLevelReorder, Levels, sku_groups
from synapse_kernel.world import load_world

#: A fixed, illustrative (s, S) for every supplier group: not arm E's tuned levels.
LEVELS = {"sup_a": Levels(60, 140), "sup_b": Levels(60, 140), "sup_c": Levels(60, 140)}
SEED = 4248394379
#: ``replicate_cost`` of :data:`LEVELS` at :data:`SEED`, pinned at the kernel's creation.
PINNED_COST_HEX = "0x1.159439fc5a6d8p+2"  # 4.337172028006272


def _tuned() -> GroupParLevelReorder:
    return GroupParLevelReorder(LEVELS, sku_groups(load_world(), drive.CANONICAL_SKUS))


def test_a_replicate_costs_what_it_cost_when_the_kernel_was_written() -> None:
    cost = replicate_cost(run_replicate(SEED, _tuned(), load_world()))
    assert cost.hex() == PINNED_COST_HEX, f"kernel arithmetic moved: {cost.hex()} ({cost!r})"


@settings(max_examples=6, deadline=None)
@given(st.integers(min_value=0, max_value=2**32 - 1))
def test_any_seed_repeats_exactly_and_keeps_its_accounting(seed: int) -> None:
    world = load_world()
    first = run_replicate(seed, _tuned(), world)
    again = run_replicate(seed, _tuned(), world)
    assert replicate_cost(first).hex() == replicate_cost(again).hex()
    metrics = first.metrics
    assert metrics.demand_events > 0
    assert 0 <= metrics.unmet_demand_events <= metrics.demand_events
    assert 0.0 <= metrics.fill_rate <= 1.0
    assert math.isclose(metrics.fill_rate + metrics.stockout_rate, 1.0)
    assert metrics.inventory_minutes >= 0.0
    assert math.isfinite(replicate_cost(first))


def test_arm_o_runs_alone_and_repeats() -> None:
    world = load_world()
    slices, slice_hours = drive.cadence(drive.E5_HOURS)

    def arm() -> StructureAwareBaseStock:
        return build_structure_aware_arm(
            world,
            seed=SEED,
            hours=drive.E5_HOURS,
            review_min=slice_hours * 60.0,
            n_skus=len(drive.CANONICAL_SKUS),
        )

    first = replicate_cost(run_replicate(SEED, arm(), world))
    again = replicate_cost(run_replicate(SEED, arm(), world))
    assert slices == 24
    assert first.hex() == again.hex()
    assert math.isfinite(first)
