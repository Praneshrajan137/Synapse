"""The composition: incumbent first, a challenger only where trusted, always behind the guard.

Truth session 6, stage C:

* with nothing trusted it is the lane incumbent to the bit, in every cell (the lanes-only
  composition, the reduced freeze C's fallback); without the lane rule it is I2-P everywhere;
* a trusted calm decider decides exactly as the guarded component alone where nothing is alarmed
  or flagged (cell N); planted: the same decider unguarded differs;
* its record replays: a fresh composition fed the same observations places the same orders and
  digests the same record; planted: one observation altered changes the digest;
* a map naming an entry that does not exist (lane L's surge or supply among them) or a decider not
  allowed there is refused.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import numpy as np
import pytest

from synapse_kernel.challengers.registry import build
from synapse_kernel.challengers.shelf import LaneIncumbent
from synapse_kernel.release import seeds
from synapse_kernel.release.engine import run
from synapse_kernel.release.incumbent import Incumbent, load_incumbent_tables
from synapse_kernel.release.scenario import build_scenario
from synapse_kernel.release.world import load_release_world

THRESHOLD = 2.0**12


@pytest.fixture(scope="module")
def world() -> Any:
    return load_release_world()


@pytest.fixture(scope="module")
def tables() -> Any:
    return load_incumbent_tables()


class _Log:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.observations: list[Any] = []
        self.orders: list[Any] = []

    def start(self, replicates: int) -> None:
        self.inner.start(replicates)

    def decide(self, obs: Any) -> Any:
        out = np.asarray(self.inner.decide(obs)).copy()
        self.observations.append(obs)
        self.orders.append(out)
        return out


def _same_outcome(a: Any, b: Any) -> bool:
    return all(
        np.array_equal(getattr(a, f.name), getattr(b, f.name)) for f in dataclasses.fields(a)
    )


@pytest.mark.parametrize("cell", ["N", "L", "S1", "S2", "S3"])
def test_with_nothing_trusted_it_is_the_lane_incumbent(cell: str, world: Any, tables: Any) -> None:
    scenario = [build_scenario(world, cell, seeds.explore_seed(64))]
    composition = build("synapse", world, tables, {"trust": {}})
    got = run(world, scenario, composition)
    want = run(world, scenario, LaneIncumbent(world, tables["I2-P"], tables["I2-L"]))
    assert _same_outcome(got, want)
    report = composition.report()  # type: ignore[attr-defined]
    assert report["deciders"] == ["incumbent"] and report["regimes_assessed"] is False
    assert sum(sum(row) for row in report["clipped"]) == 0


def test_without_the_lane_rule_it_is_i2_p_everywhere(world: Any, tables: Any) -> None:
    scenario = [build_scenario(world, "L", seeds.explore_seed(64))]
    got = run(world, scenario, build("synapse", world, tables, {"trust": {}, "lane_rule": False}))
    assert _same_outcome(got, run(world, scenario, Incumbent(world, tables["I2-P"])))
    lane = run(world, scenario, build("synapse", world, tables, {"trust": {}}))
    assert not _same_outcome(got, lane)  # in L the lane rule matters


def test_without_the_lane_rule_every_part_holds_lane_p(world: Any, tables: Any) -> None:
    from synapse_kernel.challengers.guarded import Guarded
    from synapse_kernel.challengers.shelf import LaneSensing

    params = {"trust": {"P/calm": "sensing"}, "surge_threshold": THRESHOLD, "lane_rule": False}
    composition = _Log(build("synapse", world, tables, params))

    def held(hold_decider: bool) -> _Log:
        sensing = LaneSensing(world, tables["I2-P"], tables["I2-L"])
        if hold_decider:
            sensing.base.hold_lane_p()
        guarded = Guarded(sensing, world, tables["I2-P"], tables["I2-L"], "sensing")
        guarded.lane.hold_lane_p()
        return _Log(guarded)

    want, planted = held(True), held(False)  # planted: the decider keeps its own lane
    for policy in (composition, want, planted):
        run(world, [build_scenario(world, "L", seeds.explore_seed(64))], policy)
    pairs = zip(composition.orders, want.orders, strict=True)
    assert all(np.array_equal(a, b) for a, b in pairs)
    pairs = zip(composition.orders, planted.orders, strict=True)
    assert not all(np.array_equal(a, b) for a, b in pairs)


def test_a_trusted_calm_decider_decides_as_the_guarded_component(world: Any, tables: Any) -> None:
    params = {"trust": {"P/calm": "sensing"}, "surge_threshold": THRESHOLD}
    composition = _Log(build("synapse", world, tables, params))
    guarded = _Log(build("sensing", world, tables, {"guard": True}))
    plain = _Log(build("sensing", world, tables, {}))
    for policy in (composition, guarded, plain):
        run(world, [build_scenario(world, "N", seeds.explore_seed(64))], policy)
    assert all(
        np.array_equal(a, b) for a, b in zip(composition.orders, guarded.orders, strict=True)
    )
    report = composition.inner.report()
    assert report["regimes_assessed"] is True
    assert report["regimes"][0][1] == 0 and report["regimes"][0][2] == 0  # N: all calm
    assert not all(
        np.array_equal(a, b) for a, b in zip(composition.orders, plain.orders, strict=True)
    )  # planted: without the guard the orders differ


def test_the_record_replays_and_an_altered_observation_shows(world: Any, tables: Any) -> None:
    params = {"trust": {"L/calm": "sensing"}}
    first = _Log(build("synapse", world, tables, params))
    run(world, [build_scenario(world, "L", seeds.explore_seed(65))], first)
    again = build("synapse", world, tables, params)
    again.start(1)
    orders = [np.asarray(again.decide(obs)) for obs in first.observations]
    assert all(np.array_equal(a, b) for a, b in zip(orders, first.orders, strict=True))
    assert again.report()["record_digest"] == first.inner.report()["record_digest"]  # type: ignore[attr-defined]
    altered = build("synapse", world, tables, params)
    altered.start(1)
    for d, obs in enumerate(first.observations):
        if d == 20:  # planted: five more units on hand of every item, in its oldest batch
            on_hand = np.asarray(obs.on_hand).copy()
            on_hand[:, :, 0] += 5
            obs = dataclasses.replace(obs, on_hand=on_hand)
        altered.decide(obs)
    assert altered.report()["record_digest"] != first.inner.report()["record_digest"]  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "trust",
    [
        {"L/surge": "surge_today"},
        {"L/supply": "supply"},
        {"P/calm": "surge_today"},
        {"P/surge": "sensing"},
        {"P/everything": "sensing"},
    ],
)
def test_a_map_outside_the_gate_is_refused(trust: dict[str, str], world: Any, tables: Any) -> None:
    with pytest.raises(ValueError, match="cannot decide|no such entry"):
        build("synapse", world, tables, {"trust": trust, "surge_threshold": THRESHOLD})


# -- stage C's acceptance: the fit's seeds, and the fitted composition's decisions ----------------

#: Seed ranges no fit may touch (gate item 4): validation, D3 (the dry run), D4 (the redesign's
#: check) and the pre-gate scoping range. Confirmatory seeds are not ``k``s at all.
PROTECTED = {
    "validation": range(32, 64),
    "D3": range(448, 648),
    "D4": range(648, 776),
    "scoping": range(1000, 1064),
}


def _overlaps(used: dict[str, range]) -> list[str]:
    return [
        f"{name} meets {other}"
        for name, span in used.items()
        for other, kept in PROTECTED.items()
        if set(span) & set(kept)
    ]


def test_the_fits_seeds_exclude_every_protected_range() -> None:
    from scripts.challengers import calibrate_surge, fit

    used = {
        "tuning": fit.TUNING,
        "trust D1": fit.D1,
        "trust D2": fit.D2,
        "threshold tuning": calibrate_surge.TUNING,
        "threshold D1": calibrate_surge.D1,
    }
    assert _overlaps(used) == []
    assert _overlaps({"planted": range(60, 70)}) == ["planted meets validation"]


def test_the_fitted_composition_decides_as_recorded() -> None:
    """Golden decisions of the fitted composition (W's parameters, S1, D1 seed k 67), recorded on
    Windows (numpy 2.4.4), for Linux CI to reproduce bit for bit (gate item 8)."""
    import hashlib
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    params = json.loads((root / "docs/truth/composition/params-W.json").read_text(encoding="utf-8"))
    world, tables = load_release_world(), load_incumbent_tables()
    log = _Log(build("synapse", world, tables, params))
    run(world, [build_scenario(world, "S1", seeds.explore_seed(67))], log)
    digest = hashlib.sha256()
    for orders in log.orders:
        digest.update(np.ascontiguousarray(orders, dtype=np.int64).tobytes())
    want = "9af66520a0d1bddc1f670c10d10d5f427fbccf6e05a0605526ad03d15d03147d"
    assert digest.hexdigest() == want, digest.hexdigest()
