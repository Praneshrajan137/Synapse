"""
ml_pipelines/transfer/cold_start_baseline.py

Trains cold-start baseline models for each agent on Mumbai data from scratch
(random initialization, no transfer learning). These serve as the CONTROL
variant in A/B testing against transfer-learned models.

Usage:
    python ml_pipelines/transfer/cold_start_baseline.py --agent demand_prophet --data-dir data/mumbai

Registered as: mumbai_coldstart_{model_name} in MLflow Staging.

INVARIANT I-8: All model lineage tracked in MLflow.
"""

from __future__ import annotations

import argparse
from typing import Any

import mlflow
import numpy as np
import structlog
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingWarmRestarts
from torch.utils.data import DataLoader

from ml_pipelines.transfer.transfer import TRANSFER_CONFIGS, create_mumbai_loaders

log = structlog.get_logger()


def _build_simple_model(input_dim: int, output_dim: int) -> nn.Module:
    """Build a simple feedforward model for cold-start baseline."""
    return nn.Sequential(
        nn.Linear(input_dim, 128),
        nn.ReLU(),
        nn.Linear(128, 64),
        nn.ReLU(),
        nn.Linear(64, output_dim),
    )


def train_cold_start(
    agent_name: str,
    data_dir: str,
) -> dict[str, float]:
    """Train a model from scratch on Mumbai data (no transfer learning)."""
    config = TRANSFER_CONFIGS[agent_name]
    metric_name = config["metric"]
    direction = config["metric_direction"]

    train_loader, val_loader, _ = create_mumbai_loaders(data_dir, agent_name)

    sample_batch = next(iter(train_loader))
    input_dim = sample_batch[0].shape[1]
    output_dim = sample_batch[1].shape[1]

    model = _build_simple_model(input_dim, output_dim)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)

    optimizer = AdamW(model.parameters(), lr=config["lr_unfrozen"], weight_decay=config["weight_decay"])
    scheduler = CosineAnnealingWarmRestarts(optimizer, T_0=5, T_mult=2)

    best_metric = float("inf") if direction == "minimize" else float("-inf")
    patience_counter = 0
    max_epochs = config["max_epochs"]
    patience = config["early_stop_patience"]

    for epoch in range(max_epochs):
        model.train()
        train_loss = 0.0
        n_batches = 0
        for batch in train_loader:
            features, targets = batch[0].to(device), batch[1].to(device)
            optimizer.zero_grad()
            preds = model(features)
            loss = nn.functional.mse_loss(preds, targets)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_loss += loss.item()
            n_batches += 1
        scheduler.step()

        model.eval()
        val_loss = 0.0
        val_n = 0
        with torch.no_grad():
            for batch in val_loader:
                features, targets = batch[0].to(device), batch[1].to(device)
                preds = model(features)
                val_loss += nn.functional.mse_loss(preds, targets).item()
                val_n += 1
        val_metric = val_loss / max(val_n, 1)

        mlflow.log_metrics(
            {"train_loss": train_loss / max(n_batches, 1), f"val_{metric_name}": val_metric},
            step=epoch,
        )

        improved = val_metric < best_metric if direction == "minimize" else val_metric > best_metric
        if improved:
            best_metric = val_metric
            patience_counter = 0
            torch.save(model.state_dict(), f"/tmp/coldstart_{agent_name}.pt")
        else:
            patience_counter += 1

        if patience_counter >= patience:
            log.info("cold_start_early_stop", agent=agent_name, epoch=epoch)
            break

    import pathlib
    ckpt = pathlib.Path(f"/tmp/coldstart_{agent_name}.pt")
    if ckpt.exists():
        model.load_state_dict(torch.load(ckpt, weights_only=True))

    return {
        f"final_{metric_name}": best_metric,
        "total_epochs_trained": float(epoch + 1),
        "training_type": "cold_start",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SYNAPSE Cold-Start Baseline Training")
    parser.add_argument("--agent", required=True, choices=list(TRANSFER_CONFIGS.keys()))
    parser.add_argument("--data-dir", default="data/mumbai")
    args = parser.parse_args()

    config = TRANSFER_CONFIGS[args.agent]
    model_name = f"mumbai_coldstart_{config['model_name']}"

    mlflow.set_experiment(f"mumbai_coldstart_{args.agent}")
    with mlflow.start_run(run_name=f"coldstart_{args.agent}"):
        mlflow.log_params({
            "agent_name": args.agent,
            "training_type": "cold_start",
            "city": "mumbai",
        })
        metrics = train_cold_start(args.agent, args.data_dir)
        mlflow.log_metrics(metrics)

        train_loader, _, _ = create_mumbai_loaders(args.data_dir, args.agent)
        sample = next(iter(train_loader))
        model = _build_simple_model(sample[0].shape[1], sample[1].shape[1])
        import pathlib
        ckpt = pathlib.Path(f"/tmp/coldstart_{args.agent}.pt")
        if ckpt.exists():
            model.load_state_dict(torch.load(ckpt, weights_only=True))

        mlflow.pytorch.log_model(model, args.agent)
        mlflow.register_model(
            f"runs:/{mlflow.active_run().info.run_id}/{args.agent}",
            model_name,
        )
        log.info("cold_start_registered", model_name=model_name)


if __name__ == "__main__":
    main()
