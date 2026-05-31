"""Tests for the training-truth contract (ADR-042).

Covers training_contract.py — the typed value object that proves a training run
took real gradient steps and the loss fell. Pure-Python (torch-optional): the
checkpoint I/O degrades to deterministic JSON/pickle when torch is absent, which
is exactly what these tests assert on the dev box.
"""

from __future__ import annotations

import numpy as np
import pytest

from synapse_common.training_contract import (
    ANALYTICAL,
    MIN_IMPROVEMENT,
    TrainingContractViolation,
    TrainResult,
    learning_curve_decreased,
    load_checkpoint,
    save_checkpoint,
)


def _gradient_result(**overrides) -> TrainResult:
    base = dict(
        agent="demand_prophet",
        gradient_steps=120,
        start_loss=2.0,
        end_loss=1.0,
        epochs=2,
        seed=42,
        smoke=True,
    )
    base.update(overrides)
    return TrainResult(**base)


class TestImprovement:
    def test_improvement_is_relative_loss_drop(self) -> None:
        r = _gradient_result(start_loss=2.0, end_loss=1.0)
        assert r.improvement == pytest.approx(0.5)

    def test_zero_start_loss_is_zero_improvement(self) -> None:
        assert _gradient_result(start_loss=0.0).improvement == 0.0

    def test_negative_improvement_when_loss_grows(self) -> None:
        assert _gradient_result(start_loss=1.0, end_loss=2.0).improvement < 0


class TestAssertLearned:
    def test_real_loop_passes(self) -> None:
        _gradient_result().assert_learned()  # does not raise

    def test_zero_gradient_steps_is_the_pipeline_validated_lie(self) -> None:
        r = _gradient_result(gradient_steps=0)
        with pytest.raises(TrainingContractViolation, match="0 gradient steps"):
            r.assert_learned()

    def test_vacuous_training_loop_runs_but_does_not_learn(self) -> None:
        # Optimizer steps, but the loss barely moves → vacuous (e.g. a broken
        # env where reward is independent of action, or a detached graph).
        r = _gradient_result(start_loss=1.0, end_loss=0.99, gradient_steps=50)
        with pytest.raises(TrainingContractViolation, match="does not learn"):
            r.assert_learned()

    def test_improvement_exactly_at_threshold_passes(self) -> None:
        r = _gradient_result(start_loss=1.0, end_loss=1.0 - MIN_IMPROVEMENT)
        r.assert_learned()  # boundary is inclusive

    def test_learned_property_matches_assert(self) -> None:
        assert _gradient_result().learned is True
        assert _gradient_result(gradient_steps=0).learned is False


class TestAnalyticalAgents:
    def test_analytical_is_learned_by_construction(self) -> None:
        r = TrainResult.analytical("inventory_sentinel", metrics={"pi_coverage": 0.91})
        assert r.kind == ANALYTICAL
        assert r.learned is True
        r.assert_learned()  # never demands a gradient loop from a closed-form model

    def test_analytical_carries_calibration_metrics(self) -> None:
        r = TrainResult.analytical("routing_navigator", metrics={"optimality_gap": 0.02})
        assert r.to_dict()["metrics"]["optimality_gap"] == 0.02


class TestLearningCurve:
    def test_decreasing_curve_is_learning(self) -> None:
        assert learning_curve_decreased([2.0, 1.5, 1.0, 0.8]) is True

    def test_flat_curve_is_not_learning(self) -> None:
        assert learning_curve_decreased([1.0, 1.0, 1.0]) is False

    def test_noisy_but_descending_curve_counts(self) -> None:
        # Mini-batch SGD is noisy; we require end << start, not monotonicity.
        assert learning_curve_decreased([2.0, 2.1, 1.3, 1.6, 0.9]) is True

    def test_single_point_is_not_learning(self) -> None:
        assert learning_curve_decreased([1.0]) is False


class TestCheckpointIO:
    def test_save_load_roundtrip_json_model(self, tmp_path) -> None:
        model = {"w": np.array([1.0, 2.0, 3.0]), "b": 0.5, "name": "demand"}
        path = tmp_path / "ckpt.bin"
        sha = save_checkpoint(model, path)
        assert path.is_file()
        assert len(sha) == 16
        loaded = load_checkpoint(path)
        assert loaded["b"] == 0.5
        assert loaded["name"] == "demand"
        assert loaded["w"]["__ndarray__"] == [1.0, 2.0, 3.0]

    def test_sha_is_deterministic_across_saves(self, tmp_path) -> None:
        model = {"w": np.array([0.1, 0.2]), "layers": 3}
        sha1 = save_checkpoint(model, tmp_path / "a.bin")
        sha2 = save_checkpoint(model, tmp_path / "b.bin")
        assert sha1 == sha2  # determinism (E-S9-03 discipline extended to weights)

    def test_assert_checkpoint_passes_when_sha_matches(self, tmp_path) -> None:
        path = tmp_path / "ckpt.bin"
        sha = save_checkpoint({"w": [1, 2, 3]}, path)
        r = _gradient_result(checkpoint_path=path, checkpoint_sha=sha)
        r.assert_checkpoint()  # does not raise

    def test_assert_checkpoint_fails_on_missing_file(self, tmp_path) -> None:
        r = _gradient_result(checkpoint_path=tmp_path / "nope.bin", checkpoint_sha="deadbeef")
        with pytest.raises(TrainingContractViolation, match="does not exist"):
            r.assert_checkpoint()

    def test_assert_checkpoint_fails_on_sha_mismatch(self, tmp_path) -> None:
        path = tmp_path / "ckpt.bin"
        save_checkpoint({"w": [1, 2, 3]}, path)
        r = _gradient_result(checkpoint_path=path, checkpoint_sha="0000000000000000")
        with pytest.raises(TrainingContractViolation, match="sha mismatch"):
            r.assert_checkpoint()

    def test_assert_checkpoint_fails_when_no_checkpoint_recorded(self) -> None:
        with pytest.raises(TrainingContractViolation, match="no checkpoint"):
            _gradient_result().assert_checkpoint()


class TestToDict:
    def test_to_dict_is_json_safe_and_rounded(self) -> None:
        d = _gradient_result(metrics={"crps": 0.123456789}).to_dict()
        assert d["agent"] == "demand_prophet"
        assert d["learned"] is True
        assert d["metrics"]["crps"] == 0.123457
