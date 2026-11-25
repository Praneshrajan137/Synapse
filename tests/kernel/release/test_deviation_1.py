"""Deviation 1's calibration reading, checked without the hour of tuning it drives.

``scripts/kernel/deviation_1.py`` runs freeze W's calibration loop under the other reading of the
session-5 gate's rule (truth session 6, S6-D-03). These tests pin the reading on an injected share
function: the bisection pivots on 5.46%, never stops on entering the band, runs the six frozen
steps, and keeps the evaluated scale closest to 5.46% (ties: the larger). They also pin the guards:
no frozen file may be written, and steps 0 and 1 must reproduce freeze W's record exactly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest

from scripts.kernel import deviation_1 as d1
from scripts.kernel import tune_incumbent as frozen

ROOT = Path(__file__).resolve().parents[3]


def _fake(shares: dict[float, float] | None = None) -> tuple[list[float], Any]:
    """A share that rises as shelf lives shorten: 0.0238 / scale**2, unless ``shares`` says."""
    seen: list[float] = []

    def measure(scale: float) -> dict[str, Any]:
        seen.append(scale)
        share = (shares or {}).get(scale, 0.0238 / scale**2)
        return {"scale": scale, "better": "I2", "waste_share": share, "tuned": {}}

    return seen, measure


def test_the_bisection_pivots_on_5_46_percent_and_runs_every_frozen_step() -> None:
    seen, measure = _fake()
    steps = d1.bisect_toward_target(measure)
    assert len(steps) == frozen.MAX_CALIBRATIONS + 1 == 7
    assert seen[0] == 1.0
    assert seen[1] == math.sqrt(0.5)  # 2.38% < 5.46%: shorter lives, as freeze W's first step
    # 0.0238 / s**2 = 0.0546 at s = 0.660: the bisection must close in on it from both sides.
    target = math.sqrt(0.0238 / 0.0546)
    assert abs(d1.closest(steps)["scale"] - target) < 0.02
    assert any(s < target for s in seen[1:]) and any(s > target for s in seen[1:])


def test_the_bisection_does_not_stop_on_entering_the_band() -> None:
    # Freeze W's reading stops at step 1 (3.09% is inside [2.7%, 10.9%]); this one goes on.
    seen, measure = _fake({1.0: 0.0238, math.sqrt(0.5): 0.0309})
    d1.bisect_toward_target(measure)
    assert len(seen) == 7
    assert seen[2] < seen[1]  # 3.09% is still below 5.46%: shorter again


def test_a_share_above_the_target_moves_to_longer_shelf_lives() -> None:
    seen, measure = _fake({1.0: 0.08})
    d1.bisect_toward_target(measure)
    assert seen[1] == math.sqrt(1.0 * frozen.SCALE_BRACKET[1])


def test_the_closest_share_wins_and_ties_go_to_the_larger_scale() -> None:
    # Binary-exact shares, so the tie is a tie: 0.25 and 0.75 are both 0.25 from 0.5.
    steps = [
        {"scale": 0.75, "waste_share": 0.75},
        {"scale": 1.0, "waste_share": 0.25},
        {"scale": 0.5, "waste_share": 0.875},
    ]
    assert d1.closest(steps, target=0.5)["scale"] == 1.0
    steps[1]["waste_share"] = 0.125
    assert d1.closest(steps, target=0.5)["scale"] == 0.75
    assert d1.closest(steps)["scale"] == 1.0  # the default target is IFPA's 5.46%


def test_no_frozen_file_may_be_written() -> None:
    with pytest.raises(SystemExit, match="frozen file"):
        d1.refuse_frozen([ROOT / "synapse_kernel/worlds/release_world.json"])
    with pytest.raises(SystemExit, match="frozen file"):
        d1.refuse_frozen([ROOT / "docs/truth/world/incumbent-report.json"])
    d1.refuse_frozen([d1.WORLD_OUT, d1.TABLES_OUT, d1.REPORT_OUT])  # the new paths pass


def test_steps_0_and_1_must_reproduce_freeze_w_number_for_number() -> None:
    report = json.loads((ROOT / "docs/truth/world/incumbent-report.json").read_text("utf-8"))
    same = [
        {
            "scale": s["scale"],
            "better": s["better"],
            "waste_share": s["waste_share"],
            "tuned": {tag: tuple(v) for tag, v in s["tuned"].items()},
        }
        for s in report["calibration"]
    ]
    assert d1.reproduces_freeze_w(same, report)
    nudged = [dict(same[0]), dict(same[1])]
    nudged[1]["waste_share"] = math.nextafter(same[1]["waste_share"], 1.0)
    assert not d1.reproduces_freeze_w(nudged, report)
    other = [dict(same[0]), dict(same[1])]
    other[0]["tuned"] = {**same[0]["tuned"], "I1": (1.0, 0.0, 0)}
    assert not d1.reproduces_freeze_w(other, report)


def test_the_uncalibrated_world_rebuilds_freeze_ws_world() -> None:
    uncalibrated = ROOT / "synapse_kernel/worlds/release_world_uncalibrated.json"
    if not uncalibrated.is_file():
        pytest.skip("the uncalibrated world is committed with deviation 1's run")
    from synapse_kernel.release.world import load_release_world

    world = load_release_world(uncalibrated)
    assert d1.frozen_world_check(world, load_release_world(d1.FROZEN_WORLD))
    assert not d1.frozen_world_check(
        frozen.scaled(world, 0.75), load_release_world(d1.FROZEN_WORLD)
    )
