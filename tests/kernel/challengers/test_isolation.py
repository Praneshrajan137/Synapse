"""The challenger's process of its own: what it is given, what it can reach, what it cannot keep.

Truth session 6, gate item 9 and the gate's attack (findings 13, 14, 16, 21). Each test is a claim
about the harness in ``scripts/challengers``; the planted cases show each one able to fail:

* a challenger in a child process decides exactly as in-process, and both replays (the outcome from
  the logged orders, the orders from the logged observations) agree;
* the child receives the same spawn arguments, environment and request whatever the cell;
* once serving, the child refuses file access, writes, sockets, subprocesses, frame inspection,
  garbage-collector walks and new imports (each tried in a fresh process: a hook cannot be removed);
* no scenario exists in the child to be found, while in one process it could be;
* a policy carries nothing from one replicate to the next (a planted memory is caught).
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.release import seeds
from synapse_kernel.release.engine import run
from synapse_kernel.release.harness import price, scenarios
from synapse_kernel.release.incumbent import load_incumbent_tables
from synapse_kernel.release.scenario import build_scenario
from synapse_kernel.release.world import load_release_world

ROOT = Path(__file__).resolve().parents[3]
SEED = seeds.explore_seed(64)


@pytest.fixture(scope="module")
def isolate() -> Any:
    from scripts.challengers import isolate as module

    return module


def test_a_child_decides_as_in_process_and_both_replays_agree(isolate: Any) -> None:
    world, tables = load_release_world(), load_incumbent_tables()
    for cell in ("N", "L"):
        got = isolate.run_one(isolate.Spec("lane_incumbent"), cell, SEED)
        lane = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
        want = price(world, scenarios(world, cell, [SEED]), lane).costs[0]
        assert got["cost"] == want
        assert got["outcome_replay"] is True and got["decision_replay"] is True


def test_the_child_is_given_the_same_whatever_the_cell(isolate: Any) -> None:
    spec = isolate.Spec("lane_incumbent")
    first = isolate.run_one(spec, "N", SEED, replay_decisions=False)
    second = isolate.run_one(spec, "S1", SEED, replay_decisions=False)
    same = ("spec", "environment", "argv", "workdir_empty")
    assert {k: first["handshake"][k] for k in same} == {k: second["handshake"][k] for k in same}
    assert first["handshake"]["workdir_empty"] == "True"
    assert first["handshake"]["pid"] != second["handshake"]["pid"]  # a fresh child each time


_REFUSALS = {
    "open a file": "open(sys.executable, 'rb')",
    "write a file": "open('planted.txt', 'w')",
    "a socket": "import socket; socket.socket()",
    "a subprocess": "import subprocess; subprocess.Popen(['python', '-c', '0'])",
    "a frame": "import sys; sys._getframe()",
    "the garbage collector": "import gc; gc.get_objects()",
    "a new import": "import xml.dom.minidom",
    "exec": "exec('x = 1')",
}


@pytest.mark.parametrize("label", sorted(_REFUSALS))
def test_a_serving_child_refuses(label: str) -> None:
    body = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from scripts.challengers import child
        child.close_off([])
        try:
            {_REFUSALS[label]}
        except PermissionError:
            print("REFUSED")
        else:
            print("ALLOWED")
        """
    )
    done = subprocess.run(
        [sys.executable, "-c", body], capture_output=True, text=True, cwd=ROOT, timeout=60
    )
    assert "REFUSED" in done.stdout, (label, done.stdout, done.stderr)


def test_no_scenario_is_reachable_in_the_child_though_one_is_in_process() -> None:
    import gc

    world = load_release_world()
    scenario = build_scenario(world, "N", SEED)
    found = [o for o in gc.get_objects() if type(o).__name__ == "Scenario"]
    assert scenario in found  # in one process, a policy could find the future
    body = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from scripts.challengers import child
        world, tables, files = child.load("W")
        child.close_off(files)
        try:
            import gc
            gc.get_objects()
        except PermissionError:
            print("NO WALK")
        """
    )
    done = subprocess.run(
        [sys.executable, "-c", body], capture_output=True, text=True, cwd=ROOT, timeout=60
    )
    assert "NO WALK" in done.stdout, done.stdout + done.stderr


class _Remembers:
    """Planted: a policy whose class keeps the first replicate's sales for later ones."""

    seen: list[Any] = []

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)

    def decide(self, obs: Any) -> Any:
        orders = self.inner.decide(obs)
        if self.seen:
            orders = orders + obs.deciding[None, :].astype(np.int64)
        else:
            self.seen.append(obs.sales.copy())
        return orders


def _orders(policy: Any, world: Any, cell: str) -> list[Any]:
    log: list[Any] = []

    class Log:
        def start(self, replicates: int) -> None:
            policy.start(replicates)

        def decide(self, obs: Any) -> Any:
            out = policy.decide(obs)
            log.append(np.asarray(out).copy())
            return out

    run(world, [build_scenario(world, cell, SEED)], Log())
    return log


def test_nothing_carries_from_one_replicate_to_the_next() -> None:
    world, tables = load_release_world(), load_incumbent_tables()
    used = LaneIncumbent(world, tables["I2-P"], tables["I2-L"])
    _orders(used, world, "N")  # seed j in cell N first, the same policy object kept
    again = _orders(used, world, "S1")
    fresh = _orders(LaneIncumbent(world, tables["I2-P"], tables["I2-L"]), world, "S1")
    assert all(np.array_equal(a, b) for a, b in zip(again, fresh, strict=True))
    _Remembers.seen.clear()
    planted = _Remembers(LaneIncumbent(world, tables["I2-P"], tables["I2-L"]))
    _orders(planted, world, "N")
    leaked = _orders(planted, world, "S1")
    _Remembers.seen.clear()
    clean = _orders(_Remembers(LaneIncumbent(world, tables["I2-P"], tables["I2-L"])), world, "S1")
    assert not all(np.array_equal(a, b) for a, b in zip(leaked, clean, strict=True))
