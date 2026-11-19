"""The kernel reproduces the legacy E5 harness to the bit (truth program session 3, stage C).

What is compared, on E5's own first twelve replicate seeds (``uplift.e5_suite.e5_replicate_seeds``):
the cost ``uplift.e5_suite.production_arm_cost`` gives each arm, against the kernel's
``run_replicate`` priced by ``replicate_cost``, as ``float.hex`` -- equality to the last bit, not a
tolerance. Floating point is deterministic for one sequence of operations on one platform; the port
keeps every operation and its order, so any difference is a real divergence of the two programs.

What would make this file wrong: the legacy side and the kernel side sharing code, so that both
moved together. They share nothing at run time -- the kernel imports nothing from the repository
outside ``synapse_kernel`` (``test_closure.py``) -- and the constants the port inlined are pinned
against the legacy definitions below.

The legacy side imports the uplift harness, whose package init assembles the consensus arm, so
this file needs the full dependency closure (CI: the kernel workflow's parity job).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from synapse_kernel import drive, objective
from synapse_kernel.drive import run_replicate
from synapse_kernel.engine import KernelConfig
from synapse_kernel.objective import replicate_cost
from synapse_kernel.policies.tuned import GroupParLevelReorder, Levels, sku_groups
from synapse_kernel.world import LEGACY_PRIMARY, load_world, world_to_document

REPO = Path(__file__).resolve().parents[2]
SEED_COUNT = 12


@pytest.fixture(scope="module")
def legacy() -> dict[str, Any]:
    from uplift import e5_suite
    from uplift.bprime_record import read_bprime_record

    record = read_bprime_record(REPO)
    return {"suite": e5_suite, "record": record, "world": e5_suite.e5_world()}


def _kernel_arm_e(record: Any) -> GroupParLevelReorder:
    world = load_world()
    tuned = record.arm_e_levels().levels
    levels = {group: Levels(point.s, point.S) for group, point in tuned.items()}
    return GroupParLevelReorder(levels, sku_groups(world, drive.CANONICAL_SKUS))


def test_the_exported_world_is_the_legacy_primary_cell(legacy: dict[str, Any]) -> None:
    expected = world_to_document(legacy["world"])
    committed = json.loads(LEGACY_PRIMARY.read_text(encoding="utf-8"))
    assert committed == expected, "regenerate: python -m scripts.kernel.export_legacy_world"


def test_the_inlined_constants_are_the_legacy_ones() -> None:
    from digital_twin.config import TwinConfig
    from digital_twin.simulation.policy import comparator_restock_threshold
    from uplift.foresight import FORESIGHT_WINDOW_MIN
    from uplift.harness import _CANONICAL_SKUS, _derive_unit_costs
    from uplift.kpi import committed_objective
    from uplift.regret import OBJECTIVE_TERMS

    legacy_objective = committed_objective()
    assert objective.TERMS == OBJECTIVE_TERMS
    assert legacy_objective.weights == objective.WEIGHTS
    assert legacy_objective.on_hand_normaliser == objective.ON_HAND_NORMALISER
    assert legacy_objective.delivery_normaliser == objective.DELIVERY_NORMALISER
    assert comparator_restock_threshold() == drive.RESTOCK_THRESHOLD
    assert drive.DECISION_WINDOW_MIN == FORESIGHT_WINDOW_MIN
    assert drive.CANONICAL_SKUS == _CANONICAL_SKUS
    assert drive.unit_costs() == _derive_unit_costs()
    defaults = {name: field.default for name, field in TwinConfig.model_fields.items()}
    kernel = KernelConfig()
    for name in ("order_arrival_rate", "pick_pack_mean_min", "pick_pack_std_min"):
        assert getattr(kernel, name) == defaults[name], name
    assert kernel.simpy_default_duration_hours == defaults["simpy_default_duration_hours"]


def test_arm_e_costs_equal_the_harness_to_the_bit_on_e5s_seeds(legacy: dict[str, Any]) -> None:
    suite, record = legacy["suite"], legacy["record"]
    seeds = suite.e5_replicate_seeds(SEED_COUNT, record)
    legacy_policy = suite.e5_baseline_arms(record)[0].policy
    kernel_policy = _kernel_arm_e(record)
    world = load_world()
    mismatched = []
    for seed in seeds:
        expected = suite.production_arm_cost(seed, legacy_policy, legacy["world"])
        got = replicate_cost(run_replicate(seed, kernel_policy, world))
        if got.hex() != expected.hex():
            mismatched.append((seed, expected, got))
    assert not mismatched, f"kernel != harness at {len(mismatched)} seed(s): {mismatched[:3]}"


def test_arm_o_costs_equal_the_harness_to_the_bit_on_e5s_seeds(legacy: dict[str, Any]) -> None:
    """Arm O, the structure-aware base stock, built per seed as ``e5_suite`` builds it."""
    from synapse_kernel.policies.base_stock import build_structure_aware_arm

    suite, record = legacy["suite"], legacy["record"]
    seeds = suite.e5_replicate_seeds(SEED_COUNT, record)
    world = load_world()
    slices, slice_hours = drive.cadence(drive.E5_HOURS)
    mismatched = []
    for seed in seeds:
        legacy_arm = suite._structure_aware_arm(legacy["world"], seed)
        expected = suite.production_arm_cost(seed, legacy_arm, legacy["world"])
        kernel_arm = build_structure_aware_arm(
            world,
            seed=seed,
            hours=drive.E5_HOURS,
            review_min=slice_hours * 60.0,
            n_skus=len(drive.CANONICAL_SKUS),
        )
        got = replicate_cost(run_replicate(seed, kernel_arm, world))
        if got.hex() != expected.hex():
            mismatched.append((seed, expected, got))
    assert slices == 24
    assert not mismatched, f"kernel != harness at {len(mismatched)} seed(s): {mismatched[:3]}"


def test_the_kernel_repeats_itself_exactly() -> None:
    from uplift.bprime_record import read_bprime_record

    policy = _kernel_arm_e(read_bprime_record(REPO))
    world = load_world()
    first = run_replicate(4248394379, policy, world)
    again = run_replicate(4248394379, policy, world)
    assert replicate_cost(first).hex() == replicate_cost(again).hex()
    assert first.metrics.to_dict() == again.metrics.to_dict()
    assert first.demand_trace.as_tuples() == again.demand_trace.as_tuples()


_ONE_SEED = """
import sys
from pathlib import Path
from uplift import e5_suite
from uplift.bprime_record import read_bprime_record
record = read_bprime_record(Path(sys.argv[1]))
seed = e5_suite.e5_replicate_seeds(1, record)[0]
policy = e5_suite.e5_baseline_arms(record)[0].policy
print(e5_suite.production_arm_cost(seed, policy, e5_suite.e5_world()).hex())
"""

_ONE_SEED_KERNEL = """
import sys
from pathlib import Path
from uplift.bprime_record import read_bprime_record
from synapse_kernel import drive
from synapse_kernel.drive import run_replicate
from synapse_kernel.objective import replicate_cost
from synapse_kernel.policies.tuned import GroupParLevelReorder, Levels, sku_groups
from synapse_kernel.world import load_world
record = read_bprime_record(Path(sys.argv[1]))
world = load_world()
levels = {g: Levels(p.s, p.S) for g, p in record.arm_e_levels().levels.items()}
policy = GroupParLevelReorder(levels, sku_groups(world, drive.CANONICAL_SKUS))
print(replicate_cost(run_replicate(4248394379, policy, world)).hex())
"""


def _run(code: str, extra_env: dict[str, str]) -> str:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("TW_")}
    env.update(extra_env)
    done = subprocess.run(
        [sys.executable, "-c", code, str(REPO)],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip().splitlines()[-1]


def test_a_tw_variable_moves_the_legacy_twin_and_not_the_kernel_finding_f33() -> None:
    """F-33, shown: ``TwinConfig`` reads ``TW_*``; the kernel's constants are code."""
    plain_legacy = _run(_ONE_SEED, {})
    moved_legacy = _run(_ONE_SEED, {"TW_ORDER_ARRIVAL_RATE": "2.2"})
    plain_kernel = _run(_ONE_SEED_KERNEL, {})
    moved_kernel = _run(_ONE_SEED_KERNEL, {"TW_ORDER_ARRIVAL_RATE": "2.2"})
    assert moved_legacy != plain_legacy, "the legacy twin ignored TW_ORDER_ARRIVAL_RATE"
    assert moved_kernel == plain_kernel, "the kernel read an environment variable"
    assert plain_kernel == plain_legacy, "the kernel and the legacy twin disagree at seed 0"
