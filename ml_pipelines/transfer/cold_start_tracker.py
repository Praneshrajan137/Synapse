"""
ml_pipelines/transfer/cold_start_tracker.py

Tracks the cold-start progression for Mumbai deployment.
Each phase transition is logged in MLflow as a distinct experiment.

Transfer learning accelerates the timeline:
  - Phase 1 (Heuristic) skipped: transfer model available immediately
  - Phase 2 (XGBoost) skipped: transfer model outperforms from day 0
  - Phase 3 (GNN) available immediately via transfer (vs 21 days cold-start)
  - Phase 4 (RL) achieved after ~14 days fine-tuning (vs 45 days cold-start)

INVARIANT I-8: All phase transitions tracked in MLflow with exact timestamps.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import mlflow
import structlog

log = structlog.get_logger()


@dataclass
class ColdStartPhase:
    name: str
    description: str
    trigger: str
    expected_metric_range: dict[str, tuple[float, float]]
    actual_metric: float | None = None
    activated_at: datetime | None = None
    status: Literal["pending", "active", "skipped", "completed"] = "pending"


COLD_START_PHASES: dict[str, ColdStartPhase] = {
    "heuristic": ColdStartPhase(
        name="heuristic",
        description="Rule-based fallbacks",
        trigger="deployment_start",
        expected_metric_range={"demand_mape": (0.25, 0.40)},
    ),
    "xgboost": ColdStartPhase(
        name="xgboost",
        description="Lightweight ML on accumulated data",
        trigger="data_volume > 7_days",
        expected_metric_range={"demand_mape": (0.15, 0.25)},
    ),
    "gnn": ColdStartPhase(
        name="gnn",
        description="Graph-based models with relational data",
        trigger="data_volume > 21_days OR transfer_learning",
        expected_metric_range={"demand_mape": (0.08, 0.15)},
    ),
    "rl": ColdStartPhase(
        name="rl",
        description="Full RL policies",
        trigger="data_volume > 45_days OR transfer_finetune > 14_days",
        expected_metric_range={"demand_mape": (0.05, 0.10)},
    ),
}


class ColdStartTracker:
    """Track cold-start phase transitions for a city deployment."""

    def __init__(self, city: str, use_transfer_learning: bool = True) -> None:
        self.city = city
        self.use_transfer = use_transfer_learning
        self.phases = {k: copy.deepcopy(v) for k, v in COLD_START_PHASES.items()}

        if use_transfer_learning:
            self.phases["heuristic"].status = "skipped"
            self.phases["xgboost"].status = "skipped"
            self.phases["gnn"].status = "active"
            self.phases["gnn"].activated_at = datetime.now(UTC)

    def log_phase_transition(self, from_phase: str, to_phase: str, metric: float) -> None:
        """Log phase transition to MLflow."""
        mlflow.set_experiment(f"{self.city}_cold_start_progression")
        with mlflow.start_run(run_name=f"transition_{from_phase}_to_{to_phase}"):
            mlflow.log_params(
                {
                    "city": self.city,
                    "from_phase": from_phase,
                    "to_phase": to_phase,
                    "transfer_learning": self.use_transfer,
                }
            )
            mlflow.log_metric("transition_metric", metric)
            mlflow.log_metric("timestamp", datetime.now(UTC).timestamp())

        self.phases[from_phase].status = "completed"
        self.phases[to_phase].status = "active"
        self.phases[to_phase].activated_at = datetime.now(UTC)
        self.phases[to_phase].actual_metric = metric

        log.info(
            "cold_start_transition",
            city=self.city,
            from_phase=from_phase,
            to_phase=to_phase,
            metric=f"{metric:.4f}",
        )
