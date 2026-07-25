"""Registry-record schema + serving-path proofs for the flagship checkpoint (R5).

Task 9.1 lands the *code* half of Requirement 5: the committed registry record has a
machine-checked shape, and a populated record's artifact loads through the production
serving path to a non-degraded, calibrated model — while an absent artifact degrades
honestly (I-7).

The other half is an operator step: the free-GPU train + HF Hub publication
(``docs/runbooks/train-and-publish-checkpoint.md``). Until it runs, the committed
registry stays a ``__placeholder__`` and C43 SKIPs. These tests assert exactly that
honest state, so no fabricated sha/coverage can slip in unchecked.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
from synapse_common.model_registry import ModelRegistry

from agents.demand_prophet.inference.serving_model import load_serving_model
from agents.demand_prophet.training.conformal import ConformalCalibrator
from scripts.audit.published_checkpoint_truth import (
    COVERAGE_FLOOR,
    REQUIRED_ENTRY_KEYS,
    SERVING_NAME,
    evaluate,
    registry_status,
    validate_entry,
)

if TYPE_CHECKING:
    from pathlib import Path

# A well-formed record of the shape the runbook's step-5 output produces. These are
# NOT claimed to be a published model — they exercise the validator only.
_WELL_FORMED: dict[str, Any] = {
    "repo": "example-owner/synapse-demand-prophet",
    "sha": "a1b2c3d",
    "coverage_p90": 0.91,
    "final_crps": 0.42,
    "trained_at": "2026-06-01T12:00:00Z",
    "rows": 1125000,
}


# --------------------------------------------------------------------------- #
# R5.2 — the registry entry schema is machine-checked
# --------------------------------------------------------------------------- #
def test_well_formed_entry_validates_and_declares_every_required_key() -> None:
    assert validate_entry(_WELL_FORMED) == []
    assert set(REQUIRED_ENTRY_KEYS) == set(_WELL_FORMED)
    assert registry_status({SERVING_NAME: _WELL_FORMED}).status == "populated"


@pytest.mark.parametrize("missing", REQUIRED_ENTRY_KEYS)
def test_entry_missing_any_required_key_is_invalid(missing: str) -> None:
    entry = {k: v for k, v in _WELL_FORMED.items() if k != missing}
    problems = validate_entry(entry)
    assert any(missing in p for p in problems), problems
    assert registry_status({SERVING_NAME: entry}).status == "invalid"


@pytest.mark.parametrize(
    ("key", "bad_value"),
    [
        ("repo", "no-owner-slash"),
        ("sha", "zzz"),  # not hex
        ("sha", "abc"),  # too short
        ("coverage_p90", COVERAGE_FLOOR - 0.01),  # uncalibrated
        ("coverage_p90", 1.5),  # not a probability
        ("final_crps", -1.0),
        ("final_crps", "0.4"),  # not a number
        ("trained_at", "someday"),
        ("rows", 0),
        ("rows", "1125000"),
    ],
)
def test_entry_with_an_implausible_value_is_invalid(key: str, bad_value: Any) -> None:
    problems = validate_entry({**_WELL_FORMED, key: bad_value})
    assert any(key in p for p in problems), problems


def test_non_object_entry_and_wrong_serving_name_are_invalid() -> None:
    assert validate_entry("published!") != []
    assert registry_status({"some_other_model": _WELL_FORMED}).status == "invalid"


# --------------------------------------------------------------------------- #
# R5.1 — until the operator publishes, the record says so (no fabricated truth)
# --------------------------------------------------------------------------- #
def test_committed_registry_is_an_honest_placeholder_and_c43_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repo's committed registry must be either a placeholder or a VALID entry.

    A placeholder means "no model published yet" and C43 SKIPs even with a repo
    configured — it never fabricates a pass. The moment a real entry lands, the
    schema check must pass, so a half-filled or invented record fails this test.
    """
    status = registry_status()
    assert status.status in {"placeholder", "populated"}, status.problems

    if status.status == "placeholder":
        monkeypatch.setenv("DP_HF_REPO", "example-owner/synapse-demand-prophet")
        probe = evaluate()
        assert probe.status == "skip"
        assert "placeholder" in probe.detail


# --------------------------------------------------------------------------- #
# R5.7 — a populated record's artifact serves non-degraded through the real path
# --------------------------------------------------------------------------- #
def _publish_locally(tmp: Path, *, smoke: bool) -> str:
    """Write the artifact pair a published checkpoint consists of; return its sha7."""
    from synapse_common.training_contract import save_checkpoint

    sha = save_checkpoint({"w": [1.0, 2.0, 3.0]}, tmp / f"{SERVING_NAME}.pt")

    calibrator = ConformalCalibrator()
    import numpy as np

    rng = np.random.default_rng(7)
    actual = rng.normal(100.0, 5.0, size=200)
    preds = np.stack([actual - 8.0, actual, actual + 8.0], axis=1)
    calibrator.fit({"1h": preds}, {"1h": actual})

    sidecar = {
        "version": f"{'smoke' if smoke else 'full'}_{sha[:7]}",
        "smoke": smoke,
        "arch": {},
        "calibrator": calibrator.to_state(),
    }
    (tmp / f"{SERVING_NAME}.serving.json").write_text(
        json.dumps(sidecar, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    return sha[:7]


def test_populated_record_loads_through_serving_path_non_degraded(tmp_path: Path) -> None:
    """The recorded artifact resolves to a real, calibrated serving model (R5.7).

    The checkpoint source is the same one the published path uses (``ModelRegistry``
    → sidecar → ``load_serving_model``); only the transport is local instead of HF,
    so the assertion is about the serving path, not about a model existing remotely.
    """
    sha7 = _publish_locally(tmp_path, smoke=False)
    entry = {**_WELL_FORMED, "sha": sha7}
    assert validate_entry(entry) == []

    registry = ModelRegistry(
        None, checkpoint_dir=tmp_path, model_builder=lambda artifact, _meta: artifact
    )
    loaded = registry.load(SERVING_NAME)
    assert loaded.is_real is True
    assert loaded.degraded is False
    # The record's sha is the one the published version string carries (the C43 pin).
    assert entry["sha"] in loaded.version

    model = load_serving_model(registry)
    assert model is not None, "populated record must not serve degraded output"
    assert model.calibrator is not None and model.calibrator.is_calibrated
    assert model.calibrator.last_coverage_p90 is not None
    assert model.calibrator.last_coverage_p90 >= COVERAGE_FLOOR


def test_absent_artifact_serves_honest_degraded(tmp_path: Path) -> None:
    """With nothing published, the serving path degrades instead of pretending (I-7)."""
    registry = ModelRegistry(
        None, checkpoint_dir=tmp_path, model_builder=lambda artifact, _meta: artifact
    )
    assert registry.load(SERVING_NAME).degraded is True
    assert load_serving_model(registry) is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
