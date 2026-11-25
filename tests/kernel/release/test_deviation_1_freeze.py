"""Deviation 1's freeze holds, and its run-time check refuses a W-d1 changed on disk or in memory.

``docs/truth/sealed/check_deviation_1.py`` is the standard-library check CI runs; the plants that
show it failing (an edited world, an edited statement, a broken chain to freeze W) are recorded in
truth session 6's log. :mod:`synapse_kernel.deviation1` is the run-time guard a comparison on W-d1
uses.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from synapse_kernel import deviation1
from synapse_kernel.release.integrity import FrozenKernelError
from synapse_kernel.release.world import load_release_world

ROOT = Path(__file__).resolve().parents[3]


def test_deviation_1s_checker_holds() -> None:
    done = subprocess.run(
        [sys.executable, "-I", str(ROOT / "docs/truth/sealed/check_deviation_1.py")],
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "OK deviation 1 holds" in done.stdout


def test_w_d1_loads_through_its_run_time_check() -> None:
    world, tables = deviation1.load()
    assert sorted({item.shelf_life_hours for item in world.items}) == [12, 24, 36, 61, 85]
    assert world.warmup_days == 5  # the longest life 85 h plus the longest lead 12 h, whole days
    assert sorted(tables) == ["I1-L", "I1-N", "I1-P", "I2-L", "I2-N", "I2-P"]


def test_w_d1_is_freeze_ws_world_but_for_its_shelf_lives_and_name() -> None:
    world, _ = deviation1.load()
    frozen = load_release_world()
    assert world.name == f"{frozen.name}-d1"
    assert world.suppliers == frozen.suppliers
    assert dict(world.profiles) == dict(frozen.profiles)
    assert world.day_item_factors == frozen.day_item_factors
    assert world.day_store_factors == frozen.day_store_factors
    for mine, theirs in zip(world.items, frozen.items, strict=True):
        assert dataclasses.replace(mine, shelf_life_hours=theirs.shelf_life_hours) == theirs
        assert mine.shelf_life_hours <= theirs.shelf_life_hours


def test_a_w_d1_altered_in_memory_is_refused() -> None:
    world, tables = deviation1.load()
    first = dataclasses.replace(
        world.items[0], shelf_life_hours=world.items[0].shelf_life_hours + 1
    )
    changed = dataclasses.replace(world, items=(first, *world.items[1:]))
    with pytest.raises(FrozenKernelError, match="not deviation 1's world"):
        deviation1.assert_world(changed)
    tables["I2-P"].factors[0, 0] += 1.0
    with pytest.raises(FrozenKernelError, match="not W-d1's"):
        deviation1.assert_tables(tables)


def test_freeze_ws_world_is_not_w_d1() -> None:
    with pytest.raises(FrozenKernelError):
        deviation1.assert_world(load_release_world())
