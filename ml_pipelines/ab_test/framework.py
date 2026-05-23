"""
ml_pipelines/ab_test/framework.py

A/B Testing Framework for Transfer Learning Validation

Design:
  - Treatment: Transfer-learned Mumbai model (fine-tuned from Bengaluru)
  - Control: Cold-start Mumbai model (trained from scratch on Mumbai data)
  - Metrics: agent-specific (see METRICS dict)
  - Test: Two-sided Welch's t-test with Bonferroni correction
  - Significance: p-value < 0.05 after correction
  - Effect size: Cohen's d reported for practical significance
  - Sample size: Minimum 1000 predictions per variant (E-S6-08)

INVARIANT I-8: Every comparison traceable to exact model checkpoints via MLflow lineage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

import mlflow
import numpy as np
import structlog
from scipy import stats

log = structlog.get_logger()

_Conclusion = Literal["treatment_wins", "control_wins", "no_significant_difference"]


@dataclass
class ABTestResult:
    agent_name: str
    metric_name: str
    control_mean: float
    control_std: float
    treatment_mean: float
    treatment_std: float
    n_control: int
    n_treatment: int
    t_statistic: float
    p_value: float
    p_value_corrected: float
    cohens_d: float
    conclusion: _Conclusion
    practical_significance: Literal["large", "medium", "small", "negligible"]


class ABTestFramework:
    """Statistically rigorous A/B comparison between cold-start and transfer-learned models."""

    METRICS: dict[str, list[str]] = {
        "demand_prophet": ["crps", "mape", "calibration_coverage", "inference_latency_ms"],
        "routing_navigator": [
            "mean_route_cost",
            "mean_delivery_time",
            "rider_gini",
            "inference_latency_ms",
        ],
        "inventory_sentinel": ["fill_rate", "holding_cost", "stockout_rate", "waste_rate"],
        "pricing_oracle": ["revenue_delta", "elasticity_alignment", "essential_cap_violations"],
        "disruption_shield": ["f1_score", "false_positive_rate", "detection_latency_ms"],
        "supplier_trust": ["trust_calibration", "lead_time_mae"],
    }

    METRIC_LOWER_IS_BETTER: dict[str, bool] = {
        "crps": True,
        "mape": True,
        "inference_latency_ms": True,
        "mean_route_cost": True,
        "mean_delivery_time": True,
        "rider_gini": True,
        "holding_cost": True,
        "stockout_rate": True,
        "waste_rate": True,
        "essential_cap_violations": True,
        "false_positive_rate": True,
        "detection_latency_ms": True,
        "trust_calibration": True,
        "lead_time_mae": True,
        "fill_rate": False,
        "calibration_coverage": False,
        "revenue_delta": False,
        "elasticity_alignment": False,
        "f1_score": False,
    }

    MIN_SAMPLE_SIZE = 1000

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name
        base_name = agent_name.split("_l")[0] if "_l" in agent_name else agent_name
        self.metrics = self.METRICS.get(base_name, self.METRICS.get(agent_name, []))

    def run_test(
        self,
        control_predictions: dict[str, np.ndarray],
        treatment_predictions: dict[str, np.ndarray],
    ) -> list[ABTestResult]:
        """Run A/B test across all metrics for this agent."""
        results: list[ABTestResult] = []
        n_metrics = len(self.metrics)

        for metric_name in self.metrics:
            control = control_predictions[metric_name]
            treatment = treatment_predictions[metric_name]

            assert len(control) >= self.MIN_SAMPLE_SIZE, (
                f"Control sample size {len(control)} < {self.MIN_SAMPLE_SIZE} minimum — E-S6-08"
            )
            assert len(treatment) >= self.MIN_SAMPLE_SIZE, (
                f"Treatment sample size {len(treatment)} < {self.MIN_SAMPLE_SIZE} minimum — E-S6-08"
            )

            t_stat, p_value = stats.ttest_ind(control, treatment, equal_var=False)
            p_corrected = min(p_value * n_metrics, 1.0)

            pooled_std = np.sqrt((np.std(control) ** 2 + np.std(treatment) ** 2) / 2)
            cohens_d = (
                abs(float(np.mean(treatment)) - float(np.mean(control))) / pooled_std
                if pooled_std > 0
                else 0.0
            )

            lower_is_better = self.METRIC_LOWER_IS_BETTER.get(metric_name, True)
            if p_corrected < 0.05:
                if lower_is_better:
                    conclusion: _Conclusion = (
                        "treatment_wins"
                        if np.mean(treatment) < np.mean(control)
                        else "control_wins"
                    )
                else:
                    conclusion = (
                        "treatment_wins"
                        if np.mean(treatment) > np.mean(control)
                        else "control_wins"
                    )
            else:
                conclusion = "no_significant_difference"

            if cohens_d >= 0.8:
                practical: Literal["large", "medium", "small", "negligible"] = "large"
            elif cohens_d >= 0.5:
                practical = "medium"
            elif cohens_d >= 0.2:
                practical = "small"
            else:
                practical = "negligible"

            result = ABTestResult(
                agent_name=self.agent_name,
                metric_name=metric_name,
                control_mean=float(np.mean(control)),
                control_std=float(np.std(control)),
                treatment_mean=float(np.mean(treatment)),
                treatment_std=float(np.std(treatment)),
                n_control=len(control),
                n_treatment=len(treatment),
                t_statistic=float(t_stat),
                p_value=float(p_value),
                p_value_corrected=float(p_corrected),
                cohens_d=float(cohens_d),
                conclusion=conclusion,
                practical_significance=practical,
            )
            results.append(result)

            log.info(
                "ab_test_result",
                agent=self.agent_name,
                metric=metric_name,
                conclusion=conclusion,
                p_corrected=f"{p_corrected:.4f}",
                cohens_d=f"{cohens_d:.3f}",
                practical=practical,
            )

        return results

    def log_to_mlflow(self, results: list[ABTestResult]) -> None:
        """Log all A/B test results to MLflow experiment."""
        experiment_name = f"mumbai_ab_test_{self.agent_name}"
        mlflow.set_experiment(experiment_name)

        with mlflow.start_run(run_name=f"ab_test_{self.agent_name}"):
            for r in results:
                prefix = f"ab_{r.metric_name}"
                mlflow.log_metrics(
                    {
                        f"{prefix}_control_mean": r.control_mean,
                        f"{prefix}_treatment_mean": r.treatment_mean,
                        f"{prefix}_p_value": r.p_value_corrected,
                        f"{prefix}_cohens_d": r.cohens_d,
                        f"{prefix}_n_control": float(r.n_control),
                        f"{prefix}_n_treatment": float(r.n_treatment),
                    }
                )
            mlflow.log_param(
                "conclusion_summary",
                json.dumps({r.metric_name: r.conclusion for r in results}),
            )
            mlflow.log_param("agent_name", self.agent_name)
            mlflow.log_param("min_sample_size", self.MIN_SAMPLE_SIZE)
