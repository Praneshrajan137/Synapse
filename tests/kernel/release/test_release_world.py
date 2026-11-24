"""The frozen release world: what freeze W fixes, checked against its fit report and its licence.

The world (``synapse_kernel/worlds/release_world.json``) and the report the fit wrote with it
(``docs/truth/world/fit-report.json``) must agree; every parameter group carries a provenance; the
CC BY 4.0 attribution travels with the world (decision D-19); and the masking check's verdict is
recorded as it came out (failing its pre-declared bar), not as one would like it.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from synapse_kernel.release.world import REQUIRED_PROVENANCE, load_release_world

ROOT = Path(__file__).resolve().parents[3]
REPORT = ROOT / "docs" / "truth" / "world" / "fit-report.json"
INCUMBENT_REPORT = ROOT / "docs" / "truth" / "world" / "incumbent-report.json"
REVISION = "c374e85975c82816c495acfa904cc55ab14a47d3"


def test_the_release_world_loads_with_every_rule_and_provenance() -> None:
    world = load_release_world()
    assert len(world.items) == 300
    assert {s.name for s in world.suppliers} == {"fresh_morning", "chilled_morning", "hub_twice"}
    assert set(REQUIRED_PROVENANCE) <= set(world.provenance)
    kinds = {key: p.kind for key, p in world.provenance.items()}
    assert kinds["profiles"] == kinds["items.rate_per_day"] == "fitted"
    assert kinds["items.shelf_life_hours"] == kinds["suppliers.lead_time_hours"] == "chosen"
    # The longest shelf life after calibration (119 hours) plus the longest lead time (12).
    assert world.warmup_days == math.ceil((119 + 12) / 24) == 6


def test_the_shelf_lives_carry_their_calibration() -> None:
    """The fit chose 1, 2, 3, 5 or 7 days; stage D's pre-declared calibration scaled them once."""
    world = load_release_world()
    report = json.loads(INCUMBENT_REPORT.read_text(encoding="utf-8"))
    scale = report["calibration_scale"]
    chosen = (24, 48, 72, 120, 168)  # scripts/world/fit_release_world.py, CHOICES
    lives = sorted({item.shelf_life_hours for item in world.items})
    assert lives == sorted({max(12, round(hours * scale)) for hours in chosen})
    assert "Calibrated before freeze W" in world.provenance["items.shelf_life_hours"].source
    shares = [step["waste_share"] for step in report["calibration"]]
    assert not 0.027 <= shares[0] <= 0.109
    assert 0.027 <= shares[-1] <= 0.109


def test_the_world_carries_its_attribution() -> None:
    attribution = load_release_world().attribution
    assert "FreshRetailNet-50K" in attribution
    assert "CC BY 4.0" in attribution
    assert REVISION in attribution
    assert "arXiv:2505.16319" in attribution


def test_the_world_agrees_with_its_fit_report() -> None:
    world = load_release_world()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report["dataset"]["revision"] == REVISION
    assert report["store"]["items"] == len(world.items)
    total = math.fsum(item.rate_per_day for item in world.items)
    assert abs(report["store"]["units_per_day"] - total) < 1e-6
    assert sorted(report["groups"]) == sorted(world.profiles)


def test_the_masking_checks_verdict_is_recorded_as_it_came_out() -> None:
    masking = json.loads(REPORT.read_text(encoding="utf-8"))["masking_check"]
    assert masking["passes"] is False and masking["fallback_passes"] is False
    assert masking["label"] == "failing"
    assert masking["used"] == "exposure_profile"
    worst = masking["worst_day_total_bias_over_predeclared_families"]
    assert worst["exposure_profile"] < worst["uniform_fill"]
