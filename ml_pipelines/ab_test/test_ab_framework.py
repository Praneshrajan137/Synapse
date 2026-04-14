"""
ml_pipelines/ab_test/test_ab_framework.py

Unit tests for the A/B Testing Framework.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml_pipelines.ab_test.framework import ABTestFramework


class TestABFramework:
    def test_significant_improvement_detected(self) -> None:
        """Transfer model clearly better -> treatment_wins."""
        fw = ABTestFramework("demand_prophet")
        rng = np.random.default_rng(42)
        control = {
            "crps": rng.normal(0.15, 0.03, 1000),
            "mape": rng.normal(0.12, 0.02, 1000),
            "calibration_coverage": rng.normal(0.88, 0.03, 1000),
            "inference_latency_ms": rng.normal(45, 5, 1000),
        }
        treatment = {
            "crps": rng.normal(0.10, 0.03, 1000),
            "mape": rng.normal(0.08, 0.02, 1000),
            "calibration_coverage": rng.normal(0.91, 0.03, 1000),
            "inference_latency_ms": rng.normal(44, 5, 1000),
        }
        results = fw.run_test(control, treatment)
        crps_result = [r for r in results if r.metric_name == "crps"][0]
        assert crps_result.p_value_corrected < 0.05
        assert crps_result.cohens_d > 0.5

    def test_no_difference_detected(self) -> None:
        """Same distributions -> no_significant_difference."""
        fw = ABTestFramework("demand_prophet")
        rng = np.random.default_rng(42)
        data = {
            "crps": rng.normal(0.10, 0.03, 1000),
            "mape": rng.normal(0.08, 0.02, 1000),
            "calibration_coverage": rng.normal(0.90, 0.03, 1000),
            "inference_latency_ms": rng.normal(45, 5, 1000),
        }
        results = fw.run_test(data, data)
        for r in results:
            assert r.conclusion == "no_significant_difference"

    def test_bonferroni_correction_applied(self) -> None:
        """p-value corrected must be >= raw p-value."""
        fw = ABTestFramework("demand_prophet")
        rng = np.random.default_rng(42)
        control = {
            "crps": rng.normal(0.15, 0.03, 1000),
            "mape": rng.normal(0.12, 0.02, 1000),
            "calibration_coverage": rng.normal(0.88, 0.03, 1000),
            "inference_latency_ms": rng.normal(45, 5, 1000),
        }
        treatment = {
            "crps": rng.normal(0.14, 0.03, 1000),
            "mape": rng.normal(0.11, 0.02, 1000),
            "calibration_coverage": rng.normal(0.89, 0.03, 1000),
            "inference_latency_ms": rng.normal(44, 5, 1000),
        }
        results = fw.run_test(control, treatment)
        for r in results:
            assert r.p_value_corrected >= r.p_value

    def test_effect_size_classification(self) -> None:
        """Cohen's d correctly classified as large."""
        fw = ABTestFramework("demand_prophet")
        rng = np.random.default_rng(42)
        control = {
            "crps": rng.normal(0.20, 0.03, 1000),
            "mape": rng.normal(0.20, 0.02, 1000),
            "calibration_coverage": rng.normal(0.80, 0.03, 1000),
            "inference_latency_ms": rng.normal(60, 5, 1000),
        }
        treatment = {
            "crps": rng.normal(0.10, 0.03, 1000),
            "mape": rng.normal(0.08, 0.02, 1000),
            "calibration_coverage": rng.normal(0.95, 0.03, 1000),
            "inference_latency_ms": rng.normal(40, 5, 1000),
        }
        results = fw.run_test(control, treatment)
        for r in results:
            assert r.practical_significance == "large"

    def test_minimum_sample_size_enforced(self) -> None:
        """Sample size below 1000 raises assertion — E-S6-08."""
        fw = ABTestFramework("demand_prophet")
        rng = np.random.default_rng(42)
        small_data = {
            "crps": rng.normal(0.10, 0.03, 50),
            "mape": rng.normal(0.08, 0.02, 50),
            "calibration_coverage": rng.normal(0.90, 0.03, 50),
            "inference_latency_ms": rng.normal(45, 5, 50),
        }
        with pytest.raises(AssertionError, match="E-S6-08"):
            fw.run_test(small_data, small_data)

    def test_direction_aware_conclusion(self) -> None:
        """Lower CRPS = better, so higher treatment CRPS => control_wins."""
        fw = ABTestFramework("demand_prophet")
        rng = np.random.default_rng(42)
        control = {
            "crps": rng.normal(0.10, 0.02, 1000),
            "mape": rng.normal(0.08, 0.02, 1000),
            "calibration_coverage": rng.normal(0.90, 0.02, 1000),
            "inference_latency_ms": rng.normal(45, 5, 1000),
        }
        treatment = {
            "crps": rng.normal(0.20, 0.02, 1000),
            "mape": rng.normal(0.15, 0.02, 1000),
            "calibration_coverage": rng.normal(0.85, 0.02, 1000),
            "inference_latency_ms": rng.normal(50, 5, 1000),
        }
        results = fw.run_test(control, treatment)
        crps_result = [r for r in results if r.metric_name == "crps"][0]
        assert crps_result.conclusion == "control_wins"
