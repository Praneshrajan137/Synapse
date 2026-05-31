"""CI smoke-train test: the loop takes real gradient steps and learns (C37/C38).

Skipped on any runner without the ML stack (torch / torch_geometric) — it is the
runtime half of the training-truth gate and runs in the CI training-smoke job.
Locally the substance is covered torch-free by test_conformal_coverage.py (C40),
test_dataset.py (data core), and test_serve_wiring.py (C39).
"""

from __future__ import annotations

import pytest

pytest.importorskip("torch")
pytest.importorskip("torch_geometric")

from synapse_common.training_contract import TrainResult  # noqa: E402

from agents.demand_prophet.training.train import train  # noqa: E402


def test_smoke_train_takes_real_gradient_steps_and_learns() -> None:
    result = train(smoke=True)
    assert isinstance(result, TrainResult)
    assert result.agent == "demand_prophet"
    # C37: a real loop, not the old pipeline_validated no-op.
    assert result.gradient_steps > 0
    assert result.improvement >= 0.05  # loss fell — the model learned
    result.assert_learned()


def test_smoke_train_writes_a_loadable_checkpoint() -> None:
    result = train(smoke=True)
    # C38: checkpoint exists on disk and its sha matches (determinism).
    assert result.checkpoint_path is not None
    assert result.checkpoint_sha is not None
    result.assert_checkpoint()


def test_smoke_train_reports_a_coverage_metric() -> None:
    result = train(smoke=True)
    # C40 feeds on this: a real held-out conformal coverage number.
    assert "coverage_p90" in result.metrics
    assert 0.0 <= result.metrics["coverage_p90"] <= 1.0


def test_smoke_train_is_deterministic_checkpoint_sha() -> None:
    sha1 = train(smoke=True).checkpoint_sha
    sha2 = train(smoke=True).checkpoint_sha
    assert sha1 == sha2  # same seed, same code → same weights bytes
