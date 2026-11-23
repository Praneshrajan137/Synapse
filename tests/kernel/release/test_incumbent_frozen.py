"""The incumbent freeze W fixes: its tables, its report and the world agree, to the bit where exact.

``synapse_kernel/worlds/incumbent_tables.json`` and ``docs/truth/world/incumbent-report.json`` were
written by one run of ``scripts/kernel/tune_incumbent.py`` (truth session 5, stage D). These tests
read them back: the six tuned versions load with the sealed lattice and shapes; their evaluation
counts and the selection agree with the report; the selected N version, priced again on the
validation seeds of the frozen world, gives the report's mean cost and waste share; and ``D_c``
and ``M_c`` follow from the world's declared parameters by the sealed rules.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from scripts.kernel.tune_incumbent import expected_demand
from synapse_kernel.release import seeds
from synapse_kernel.release.harness import price, scenarios
from synapse_kernel.release.incumbent import PARTS, Incumbent, load_incumbent_tables
from synapse_kernel.release.world import HOURS_PER_WEEK, load_release_world

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "docs" / "truth" / "world" / "incumbent-report.json"
VERSIONS = {"I1-N", "I1-L", "I1-P", "I2-N", "I2-L", "I2-P"}
RANK = {"I1-N": 0, "I1-L": 0, "I1-P": 1, "I2-N": 2, "I2-L": 2, "I2-P": 3}


def _report() -> dict[str, Any]:
    report: dict[str, Any] = json.loads(REPORT.read_text(encoding="utf-8"))
    return report


def test_the_six_versions_load_on_the_sealed_lattice() -> None:
    world = load_release_world()
    tables = load_incumbent_tables()
    assert set(tables) == VERSIONS
    for name, version in tables.items():
        assert version.name == name
        assert version.waste_aware is name.startswith("I2")
        assert version.factors.shape == (len(world.items), PARTS)
        assert version.mean_table.shape == (HOURS_PER_WEEK, len(world.items))
        assert bool((version.factors >= 0).all())
        assert bool((version.factors * 32 == np.round(version.factors * 32)).all())


def test_the_counts_and_the_selection_agree_with_the_report() -> None:
    report = _report()
    tables_doc = json.loads(
        (ROOT / "synapse_kernel" / "worlds" / "incumbent_tables.json").read_text(encoding="utf-8")
    )
    for name in VERSIONS:
        counted = report["versions"][name]["replicate_evaluations"]
        assert tables_doc[name]["replicate_evaluations"] == counted
    for chosen in report["selection"].values():
        costs = chosen["validation_mean_cost"]
        assert chosen["selected"] == min(costs, key=lambda n: (costs[n], RANK[n]))
    pooled = report["contest_pooled_validation_cost"]
    assert report["contest_incumbent"] == min(pooled, key=lambda n: (pooled[n], RANK[n]))


def test_the_selected_n_version_reprices_to_the_report() -> None:
    report = _report()
    world = load_release_world()
    name = report["selection"]["N"]["selected"]
    batch = scenarios(world, "N", seeds.explore_seeds(seeds.VALIDATION))
    priced = price(world, batch, Incumbent(world, load_incumbent_tables()[name]))
    recorded = report["selection"]["N"]["validation_mean_cost"][name]
    assert math.isclose(math.fsum(priced.costs) / len(priced.costs), recorded, rel_tol=1e-12)
    assert math.isclose(
        math.fsum(priced.waste) / len(priced.waste), report["waste_share_N_selected"], rel_tol=1e-12
    )


def test_d_c_and_m_c_follow_from_the_declared_world() -> None:
    report = _report()
    demand = expected_demand(load_release_world())
    for cell, value in demand.items():
        assert math.isclose(report["D_c"][cell], value, rel_tol=1e-12)
        assert report["p_c"][cell] == 1.0
        assert math.isclose(report["M_c"][cell], 0.01 * value * 0.38, rel_tol=1e-12)
