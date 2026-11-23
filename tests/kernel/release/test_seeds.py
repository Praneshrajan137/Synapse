"""The kernel derives the exploratory seeds exactly as the sealed pre-registration states them."""

from __future__ import annotations

import json
from pathlib import Path

from synapse_kernel.release import seeds

PREREG = Path(__file__).resolve().parents[3] / "docs" / "truth" / "sealed" / "prereg-1.json"


def test_the_derivation_reproduces_every_sealed_vector() -> None:
    explore = json.loads(PREREG.read_text(encoding="utf-8"))["seeds"]["explore"]
    assert explore["label"].encode() == seeds.LABEL
    assert list(explore["tuning"]) == [seeds.TUNING.start, seeds.TUNING.stop]
    assert list(explore["validation"]) == [seeds.VALIDATION.start, seeds.VALIDATION.stop]
    assert explore["development_from"] == seeds.DEVELOPMENT_FROM
    for k, value in explore["vectors"].items():
        assert seeds.explore_seed(int(k)) == value


def test_tuning_and_validation_seeds_are_distinct_63_bit_integers() -> None:
    tuning = seeds.explore_seeds(seeds.TUNING)
    validation = seeds.explore_seeds(seeds.VALIDATION)
    assert len(set(tuning) | set(validation)) == 64
    assert all(0 <= s < 2**63 for s in tuning + validation)
