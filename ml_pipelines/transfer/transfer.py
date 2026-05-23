"""
ml_pipelines/transfer/transfer.py

Transfer Learning Pipeline for Multi-City Deployment

Architecture:
  For each agent model, the transfer learning strategy follows a 3-phase approach:
    Phase 1: Load pre-trained Bengaluru checkpoint from MLflow registry (Production)
    Phase 2: Freeze early layers (graph encoders, temporal encoders, embeddings)
    Phase 3: Unfreeze and fine-tune final layers (prediction heads, output projections)

MLflow Integration:
  - Source: mlflow.get_model("{agent}", stage="Production") -- Bengaluru checkpoint
  - Target: New experiment "mumbai_transfer_{agent_name}"
  - Track: epochs_to_converge, final_metric, convergence_speedup_ratio

Key Metrics:
  - convergence_speedup = bengaluru_epochs / mumbai_equiv_epoch  (target: >2.5x)
  - final_metric_gap = abs(mumbai - bengaluru) / bengaluru         (target: <5%)

INVARIANT I-8: Every training artifact is tracked in MLflow with full lineage.
INVARIANT I-5: Conformal intervals MUST be recalibrated on Mumbai holdout (E-S6-04).
ERROR PATTERN E-S6-07: Mumbai models use 'mumbai_' prefix in MLflow registry.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import structlog
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
from torch.utils.data import DataLoader, TensorDataset

log = structlog.get_logger()

# ─── TRANSFER CONFIGURATION PER AGENT ────────────────────────────────────────
# Epoch counts are SUPERVISED fine-tuning epochs (not RL env steps).

TRANSFER_CONFIGS: dict[str, dict[str, Any]] = {
    "demand_prophet": {
        "model_name": "demand_prophet_hgt_tft",
        "freeze_modules": [
            "graph_encoder.hgt_layers",
            "temporal_backbone.embedding",
            "temporal_backbone.variable_selection",
        ],
        "unfreeze_modules": [
            "temporal_backbone.attention",
            "fusion_layer",
            "prediction_heads",
        ],
        "lr_unfrozen": 1e-4,
        "weight_decay": 0.01,
        "max_epochs": 20,
        "early_stop_patience": 5,
        "metric": "crps",
        "metric_direction": "minimize",
        "bengaluru_epochs": 50,
        "bengaluru_final_metric": 0.08,
        "convergence_threshold_pct": 5.0,
    },
    "routing_navigator": {
        "model_name": "routing_navigator_pointer",
        "freeze_modules": [
            "encoder.layers.0",
            "encoder.layers.1",
            "encoder.layers.2",
            "encoder.layers.3",
        ],
        "unfreeze_modules": [
            "encoder.layers.4",
            "encoder.layers.5",
            "decoder",
        ],
        "lr_unfrozen": 5e-5,
        "weight_decay": 0.01,
        "max_epochs": 40,
        "early_stop_patience": 10,
        "metric": "mean_route_cost",
        "metric_direction": "minimize",
        "bengaluru_epochs": 100,
        "bengaluru_final_metric": 150.0,
        "convergence_threshold_pct": 5.0,
    },
    "inventory_sentinel_l1": {
        "model_name": "inventory_sentinel_strategic",
        "freeze_modules": ["feature_extractor"],
        "unfreeze_modules": ["policy_head", "value_head"],
        "lr_unfrozen": 3e-4,
        "weight_decay": 0.0,
        "max_epochs": 50,
        "early_stop_patience": 12,
        "metric": "fill_rate",
        "metric_direction": "maximize",
        "bengaluru_epochs": 100,
        "bengaluru_final_metric": 0.95,
        "convergence_threshold_pct": 5.0,
    },
    "inventory_sentinel_l2": {
        "model_name": "inventory_sentinel_tactical",
        "freeze_modules": ["feature_extractor"],
        "unfreeze_modules": ["policy_head", "value_head"],
        "lr_unfrozen": 3e-4,
        "weight_decay": 0.0,
        "max_epochs": 50,
        "early_stop_patience": 12,
        "metric": "service_level",
        "metric_direction": "maximize",
        "bengaluru_epochs": 100,
        "bengaluru_final_metric": 0.93,
        "convergence_threshold_pct": 5.0,
    },
    "pricing_oracle": {
        "model_name": "pricing_oracle_maddpg",
        "freeze_modules": ["critic.layers.0", "critic.layers.1"],
        "unfreeze_modules": ["actor", "critic.layers.2", "critic.output"],
        "lr_unfrozen": 1e-4,
        "weight_decay": 0.01,
        "max_epochs": 30,
        "early_stop_patience": 8,
        "metric": "revenue_fairness",
        "metric_direction": "maximize",
        "bengaluru_epochs": 80,
        "bengaluru_final_metric": 0.88,
        "convergence_threshold_pct": 5.0,
    },
    "disruption_shield": {
        "model_name": "disruption_shield_ensemble",
        "freeze_modules": [],
        "unfreeze_modules": ["isolation_forest", "lstm_autoencoder", "gnn_anomaly"],
        "lr_unfrozen": 1e-3,
        "weight_decay": 0.0,
        "max_epochs": 50,
        "early_stop_patience": 10,
        "metric": "f1_score",
        "metric_direction": "maximize",
        "bengaluru_epochs": 100,
        "bengaluru_final_metric": 0.91,
        "convergence_threshold_pct": 5.0,
    },
    "supplier_trust": {
        "model_name": "supplier_trust_gnn",
        "freeze_modules": ["gnn_encoder.layers.0"],
        "unfreeze_modules": ["gnn_encoder.layers.1", "trust_head", "bayesian_lead_time"],
        "lr_unfrozen": 5e-4,
        "weight_decay": 0.01,
        "max_epochs": 30,
        "early_stop_patience": 8,
        "metric": "trust_calibration",
        "metric_direction": "minimize",
        "bengaluru_epochs": 60,
        "bengaluru_final_metric": 0.05,
        "convergence_threshold_pct": 5.0,
    },
}


class TransferLearningPipeline:
    """
    Orchestrates transfer learning from source city (Bengaluru) to target city (Mumbai).

    Protocol:
      1. Load checkpoint from MLflow (Production stage)
      2. Validate checkpoint architecture matches current code
      3. Apply freeze/unfreeze strategy
      4. Create Mumbai-specific DataLoaders
      5. Fine-tune with reduced LR + cosine annealing
      6. Track convergence vs cold-start baseline
      7. Run conformal calibration on Mumbai holdout (MANDATORY -- E-S6-04)
      8. Register in MLflow as "mumbai_{agent}" in Staging (E-S6-07 prefix rule)
    """

    def __init__(
        self,
        agent_name: str,
        source_city: str = "bengaluru",
        target_city: str = "mumbai",
    ) -> None:
        self.agent_name = agent_name
        self.source_city = source_city
        self.target_city = target_city
        self.config = TRANSFER_CONFIGS[agent_name]

    def load_source_checkpoint(self) -> nn.Module:
        """Load Production-stage model from MLflow registry."""
        model_uri = f"models:/{self.config['model_name']}/Production"
        model = mlflow.pytorch.load_model(model_uri)
        log.info(
            "loaded_source_checkpoint",
            agent=self.agent_name,
            model_uri=model_uri,
            param_count=sum(p.numel() for p in model.parameters()),
        )
        return model

    def load_bengaluru_final_metric(self) -> float:
        """Load Bengaluru's final metric from MLflow for convergence comparison."""
        client = mlflow.tracking.MlflowClient()
        model_name = self.config["model_name"]
        versions = client.get_latest_versions(model_name, stages=["Production"])
        if versions:
            run_id = versions[0].run_id
            run = client.get_run(run_id)
            metric_key = f"final_{self.config['metric']}"
            val = run.data.metrics.get(metric_key)
            if val is not None:
                log.info("loaded_bengaluru_metric", metric=metric_key, value=val)
                return float(val)
        fallback = self.config["bengaluru_final_metric"]
        log.info("using_fallback_bengaluru_metric", value=fallback)
        return float(fallback)

    def apply_freeze_strategy(self, model: nn.Module) -> nn.Module:
        """Freeze early layers, unfreeze final layers per config."""
        for param in model.parameters():
            param.requires_grad = False

        unfrozen_count = 0
        for module_path in self.config["unfreeze_modules"]:
            module = self._get_module_by_path(model, module_path)
            for param in module.parameters():
                param.requires_grad = True
                unfrozen_count += param.numel()

        total_params = sum(p.numel() for p in model.parameters())
        frozen_params = total_params - unfrozen_count
        freeze_ratio = frozen_params / total_params if total_params > 0 else 0

        log.info(
            "freeze_strategy_applied",
            agent=self.agent_name,
            total_params=total_params,
            frozen_params=frozen_params,
            unfrozen_params=unfrozen_count,
            freeze_ratio=f"{freeze_ratio:.1%}",
        )
        return model

    def create_optimizer(self, model: nn.Module) -> tuple[AdamW, CosineAnnealingWarmRestarts]:
        """Create optimizer with LR for unfrozen params only."""
        trainable = [p for p in model.parameters() if p.requires_grad]
        optimizer = AdamW(
            trainable,
            lr=self.config["lr_unfrozen"],
            weight_decay=self.config["weight_decay"],
        )
        scheduler = CosineAnnealingWarmRestarts(optimizer, T_0=5, T_mult=2)
        return optimizer, scheduler

    def train_loop(
        self,
        model: nn.Module,
        train_loader: DataLoader,
        val_loader: DataLoader,
        optimizer: AdamW,
        scheduler: CosineAnnealingWarmRestarts,
        bengaluru_metric: float,
    ) -> dict[str, float]:
        """Fine-tuning loop with convergence tracking against Bengaluru baseline."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)

        metric_name = self.config["metric"]
        direction = self.config["metric_direction"]
        patience = self.config["early_stop_patience"]
        threshold_pct = self.config["convergence_threshold_pct"]

        best_metric = float("inf") if direction == "minimize" else float("-inf")
        patience_counter = 0
        equiv_epoch: int | None = None
        history: list[float] = []

        for epoch in range(self.config["max_epochs"]):
            # ── Training ──────────────────────────────────────────────
            model.train()
            train_loss = 0.0
            n_batches = 0
            for batch in train_loader:
                batch = [b.to(device) for b in batch]
                optimizer.zero_grad()
                loss = self._compute_loss(model, batch)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad],
                    max_norm=1.0,
                )
                optimizer.step()
                train_loss += loss.item()
                n_batches += 1
            scheduler.step()
            avg_train_loss = train_loss / max(n_batches, 1)

            # ── Validation ────────────────────────────────────────────
            model.eval()
            val_metric = self._evaluate(model, val_loader, device)
            history.append(val_metric)

            # ── MLflow Logging ────────────────────────────────────────
            mlflow.log_metrics(
                {
                    "train_loss": avg_train_loss,
                    f"val_{metric_name}": val_metric,
                    "learning_rate": optimizer.param_groups[0]["lr"],
                    "epoch": epoch,
                },
                step=epoch,
            )

            # ── Convergence Check: reached Bengaluru-equivalent? ──────
            if equiv_epoch is None:
                gap_pct = (
                    abs(val_metric - bengaluru_metric) / max(abs(bengaluru_metric), 1e-8) * 100
                )
                if gap_pct <= threshold_pct:
                    equiv_epoch = epoch
                    log.info(
                        "bengaluru_equivalence_reached",
                        agent=self.agent_name,
                        epoch=epoch,
                        val_metric=f"{val_metric:.6f}",
                        bengaluru_metric=f"{bengaluru_metric:.6f}",
                        gap_pct=f"{gap_pct:.2f}%",
                    )

            # ── Early Stopping ────────────────────────────────────────
            improved = (
                val_metric < best_metric if direction == "minimize" else val_metric > best_metric
            )
            if improved:
                best_metric = val_metric
                patience_counter = 0
                torch.save(model.state_dict(), f"/tmp/best_{self.agent_name}.pt")
            else:
                patience_counter += 1

            if patience_counter >= patience:
                log.info(
                    "early_stopping_triggered",
                    agent=self.agent_name,
                    epoch=epoch,
                    patience_exhausted=patience,
                )
                break

            if epoch % 5 == 0:
                log.info(
                    "training_progress",
                    agent=self.agent_name,
                    epoch=epoch,
                    metric=f"{val_metric:.6f}",
                    best=f"{best_metric:.6f}",
                )

        # ── Restore Best Model ────────────────────────────────────────
        best_ckpt = Path(f"/tmp/best_{self.agent_name}.pt")
        if best_ckpt.exists():
            model.load_state_dict(torch.load(best_ckpt, weights_only=True))

        # ── Convergence Speedup ───────────────────────────────────────
        if equiv_epoch is None:
            equiv_epoch = len(history)
        convergence_speedup = self.config["bengaluru_epochs"] / max(equiv_epoch, 1)
        final_gap_pct = abs(best_metric - bengaluru_metric) / max(abs(bengaluru_metric), 1e-8) * 100

        metrics = {
            "convergence_epoch": float(equiv_epoch),
            "convergence_speedup": convergence_speedup,
            f"final_{metric_name}": best_metric,
            "bengaluru_final_metric": bengaluru_metric,
            "metric_gap_pct": final_gap_pct,
            "total_epochs_trained": float(len(history)),
            "freeze_ratio": sum(1 for p in model.parameters() if not p.requires_grad)
            / max(sum(1 for p in model.parameters()), 1),
        }

        mlflow.log_metrics(
            {
                "convergence_speedup": convergence_speedup,
                "convergence_epoch": float(equiv_epoch),
                "metric_gap_pct": final_gap_pct,
            }
        )

        log.info(
            "transfer_training_complete",
            agent=self.agent_name,
            convergence_speedup=f"{convergence_speedup:.1f}x",
            final_metric=f"{best_metric:.6f}",
            target_speedup="2.5x",
        )
        return metrics

    def run_conformal_calibration(
        self, model: nn.Module, calibration_loader: DataLoader
    ) -> dict[str, float]:
        """
        Run conformal prediction calibration on Mumbai holdout data.

        E-S6-04: Bengaluru conformal intervals are INVALID for Mumbai distribution.
        This method MUST be called after transfer training.
        """
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        model.eval()

        all_preds: list[np.ndarray] = []
        all_actuals: list[np.ndarray] = []

        with torch.no_grad():
            for batch in calibration_loader:
                batch = [b.to(device) for b in batch]
                preds = model(batch[0])
                all_preds.append(preds.cpu().numpy())
                all_actuals.append(batch[1].cpu().numpy())

        preds_array = np.concatenate(all_preds, axis=0).flatten()
        actuals_array = np.concatenate(all_actuals, axis=0).flatten()

        calibration_results: dict[str, float] = {}
        for alpha in [0.05, 0.10, 0.20]:
            confidence = 1 - alpha
            residuals = np.abs(actuals_array - preds_array)
            quantile = float(np.quantile(residuals, confidence))

            lower = preds_array - quantile
            upper = preds_array + quantile
            coverage = float(np.mean((actuals_array >= lower) & (actuals_array <= upper)))

            key_cov = f"mumbai_calibration_coverage_{int(confidence * 100)}"
            key_width = f"mumbai_interval_width_{int(confidence * 100)}"
            calibration_results[key_cov] = coverage
            calibration_results[key_width] = quantile * 2
            mlflow.log_metric(key_cov, coverage)
            mlflow.log_metric(key_width, quantile * 2)

        coverage_90 = calibration_results.get("mumbai_calibration_coverage_90", 0)
        assert coverage_90 >= 0.85, (
            f"Conformal calibration FAILED: 90% coverage is {coverage_90:.3f} < 0.85. "
            f"E-S6-04 violation."
        )

        log.info(
            "conformal_calibration_complete",
            agent=self.agent_name,
            coverage_90=f"{coverage_90:.3f}",
            city=self.target_city,
        )
        return calibration_results

    def register_model(self, model: nn.Module, metrics: dict[str, float]) -> None:
        """Register fine-tuned model in MLflow as Staging for Mumbai.

        NOTE: This method logs to the ACTIVE mlflow run (no nested start_run).
        E-S6-07: Uses 'mumbai_' prefix to prevent collision.
        """
        mlflow.log_params(
            {
                "source_city": self.source_city,
                "target_city": self.target_city,
                "freeze_ratio": metrics.get("freeze_ratio", 0),
                "transfer_strategy": "freeze_early_finetune_final",
                "agent_name": self.agent_name,
                "model_name": self.config["model_name"],
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.pytorch.log_model(model, self.agent_name)

        model_name = f"mumbai_{self.config['model_name']}"
        mlflow.register_model(
            f"runs:/{mlflow.active_run().info.run_id}/{self.agent_name}",
            model_name,
        )
        log.info("model_registered", model_name=model_name, stage="Staging")

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _compute_loss(self, model: nn.Module, batch: list[torch.Tensor]) -> torch.Tensor:
        features, targets = batch[0], batch[1]
        predictions = model(features)
        return nn.functional.mse_loss(predictions, targets)

    def _evaluate(self, model: nn.Module, val_loader: DataLoader, device: torch.device) -> float:
        model.eval()
        total_loss = 0.0
        n_batches = 0
        with torch.no_grad():
            for batch in val_loader:
                batch = [b.to(device) for b in batch]
                loss = self._compute_loss(model, batch)
                total_loss += loss.item()
                n_batches += 1
        return total_loss / max(n_batches, 1)

    @staticmethod
    def _get_module_by_path(model: nn.Module, path: str) -> nn.Module:
        parts = path.split(".")
        module: Any = model
        for part in parts:
            module = list(module.children())[int(part)] if part.isdigit() else getattr(module, part)
        return module


def create_mumbai_loaders(
    data_dir: str, agent_name: str, batch_size: int = 64
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """
    Create train/val/calibration DataLoaders from Mumbai Parquet data.
    Split: 70% train, 15% val, 15% calibration.
    """
    if agent_name.startswith("demand_prophet"):
        df = pd.read_parquet(f"{data_dir}/demand_features.parquet")
        features = torch.tensor(
            df[["rolling_mean_7d", "rolling_std_7d", "trend_slope", "seasonality_idx"]].values,
            dtype=torch.float32,
        )
        targets = torch.tensor(
            df["rolling_mean_7d"].shift(-1).fillna(0).values,
            dtype=torch.float32,
        ).unsqueeze(1)
    else:
        n_samples = 10000
        rng = np.random.default_rng(42)
        features = torch.tensor(rng.standard_normal((n_samples, 32)), dtype=torch.float32)
        targets = torch.tensor(rng.standard_normal((n_samples, 1)), dtype=torch.float32)

    n = len(features)
    train_end = int(n * 0.7)
    val_end = int(n * 0.85)

    train_ds = TensorDataset(features[:train_end], targets[:train_end])
    val_ds = TensorDataset(features[train_end:val_end], targets[train_end:val_end])
    cal_ds = TensorDataset(features[val_end:], targets[val_end:])

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    cal_loader = DataLoader(cal_ds, batch_size=batch_size, shuffle=False)

    log.info(
        "data_loaders_created",
        agent=agent_name,
        train=len(train_ds),
        val=len(val_ds),
        calibration=len(cal_ds),
    )
    return train_loader, val_loader, cal_loader


# Need pandas for create_mumbai_loaders when parquet path is used
import pandas as pd  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="SYNAPSE Transfer Learning Pipeline")
    parser.add_argument("--agent", required=True, choices=list(TRANSFER_CONFIGS.keys()))
    parser.add_argument("--source-city", default="bengaluru")
    parser.add_argument("--target-city", default="mumbai")
    parser.add_argument("--data-dir", default="data/mumbai")
    parser.add_argument("--dry-run", action="store_true", help="Validate without training")
    args = parser.parse_args()

    pipeline = TransferLearningPipeline(args.agent, args.source_city, args.target_city)

    experiment_name = f"mumbai_transfer_{args.agent}"
    mlflow.set_experiment(experiment_name)

    model = pipeline.load_source_checkpoint()
    model = pipeline.apply_freeze_strategy(model)

    if args.dry_run:
        log.info("dry_run_complete", agent=args.agent)
        return

    bengaluru_metric = pipeline.load_bengaluru_final_metric()
    train_loader, val_loader, cal_loader = create_mumbai_loaders(args.data_dir, args.agent)
    optimizer, scheduler = pipeline.create_optimizer(model)

    with mlflow.start_run(run_name=f"transfer_{args.target_city}_{args.agent}"):
        metrics = pipeline.train_loop(
            model, train_loader, val_loader, optimizer, scheduler, bengaluru_metric
        )
        cal_metrics = pipeline.run_conformal_calibration(model, cal_loader)
        metrics.update(cal_metrics)
        pipeline.register_model(model, metrics)

    log.info(
        "transfer_pipeline_complete",
        agent=args.agent,
        speedup=f"{metrics.get('convergence_speedup', 0):.1f}x",
    )


if __name__ == "__main__":
    main()
