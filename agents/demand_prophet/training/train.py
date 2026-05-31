"""
SYNAPSE Demand Prophet -- Training Loop (real gradient steps, ADR-042).

Colab/Kaggle-compatible. MLflow lineage on every checkpoint (I-8). Uses the
INDEPENDENT reward function from rewards.py (I-2). Returns a
:class:`~synapse_common.training_contract.TrainResult` proving the loop took real
gradient steps and the loss fell — the C37/C38 runtime gates consume it.

This replaces the historical no-op that built an optimizer, discarded it, and
returned ``{"status": "pipeline_validated"}`` without a single ``loss.backward()``.

Two tiers (ADR-042):
  * ``train(smoke=True)`` — tiny seeded slice of the real demand history, a few
    epochs on CPU, <=5 min. The CI training-smoke job runs this and gates on the
    returned TrainResult.
  * ``train()`` (full) — the operator/Colab run on the full 1.1M-row series that
    produces the registered production checkpoint.

Usage:
  python -m agents.demand_prophet.training.train [--epochs 50] [--smoke]
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import structlog
import torch
import yaml
from synapse_common.training_contract import TrainResult, save_checkpoint

from agents.demand_prophet.config import DemandProphetConfig
from agents.demand_prophet.models.hybrid import DemandProphetHybrid
from agents.demand_prophet.training.conformal import ConformalCalibrator
from agents.demand_prophet.training.dataset import (
    HORIZONS,
    WindowedData,
    build_graph,
    build_supervised,
    to_torch_batch,
)
from agents.demand_prophet.training.rewards import crps_loss

logger = structlog.get_logger(__name__)

ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"

try:
    import mlflow
    import mlflow.pytorch  # noqa: F401

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    logger.warning("mlflow_not_available", fallback="local checkpointing only")


def _smoke_config() -> DemandProphetConfig:
    """A small, CPU-friendly config for the gated smoke train."""
    return DemandProphetConfig(
        hgt_hidden_dim=32,
        hgt_num_heads=2,
        hgt_num_layers=1,
        tft_hidden_size=32,
        tft_attention_heads=2,
        tft_num_static=8,
        tft_num_time_known=6,
        tft_num_time_observed=3,
        batch_size=8,
        max_epochs=3,
        learning_rate=1e-2,
    )


def _build_model(config: DemandProphetConfig) -> DemandProphetHybrid:
    return DemandProphetHybrid(
        hgt_hidden_dim=config.hgt_hidden_dim,
        hgt_num_heads=config.hgt_num_heads,
        hgt_num_layers=config.hgt_num_layers,
        tft_hidden_size=config.tft_hidden_size,
        tft_num_heads=config.tft_attention_heads,
        tft_num_static=config.tft_num_static,
        tft_num_time_known=config.tft_num_time_known,
        tft_num_time_observed=config.tft_num_time_observed,
    )


def _batch_loss(
    model: DemandProphetHybrid,
    window: WindowedData,
    idx: np.ndarray,
    quantile_levels: list[float],
    device: torch.device,
) -> torch.Tensor:
    """CRPS loss summed over horizons for one batch (real forward + grad path)."""
    batch = to_torch_batch(window, idx)
    n = batch["num_skus"]
    graph = build_graph(n)
    static = [t.to(device) for t in batch["static_inputs"]]
    temporal = [t.to(device) for t in batch["temporal_inputs"]]
    targets = batch["targets"].to(device)  # (B, H)

    outputs = model(graph, static, temporal)  # dict[h -> (B, 3)]
    losses: list[torch.Tensor] = []
    for h_idx, h in enumerate(HORIZONS):
        preds = outputs[h]  # (B, 3) = quantiles
        actual = targets[:, h_idx]
        losses.append(crps_loss(preds, actual, quantile_levels))
    return torch.stack(losses).mean()


def _evaluate_coverage(
    model: DemandProphetHybrid,
    window: WindowedData,
    quantile_levels: list[float],
    device: torch.device,
) -> float:
    """Fit the conformal calibrator on a holdout slice; return aggregate coverage."""
    model.eval()
    idx = np.arange(len(window))
    with torch.no_grad():
        batch = to_torch_batch(window, idx)
        graph = build_graph(batch["num_skus"])
        static = [t.to(device) for t in batch["static_inputs"]]
        temporal = [t.to(device) for t in batch["temporal_inputs"]]
        outputs = model(graph, static, temporal)
    predictions = {h: outputs[h].cpu().numpy() for h in HORIZONS}
    actuals = {h: window.targets[idx, h_idx] for h_idx, h in enumerate(HORIZONS)}
    calib = ConformalCalibrator(alpha=0.1, coverage_target=0.85)
    calib.fit(predictions, actuals)
    return float(calib.last_coverage_p90 or 0.0)


def train(config: DemandProphetConfig | None = None, *, smoke: bool = False) -> TrainResult:
    """Main training loop for the Demand Prophet HGT-TFT hybrid (ADR-042)."""
    if config is None:
        config = _smoke_config() if smoke else DemandProphetConfig()

    hparams_path = Path(__file__).parent / "hparams.yaml"
    if hparams_path.exists():
        with open(hparams_path) as f:
            yaml.safe_load(f)  # validated; full-run hyperparameters live here

    seed = 42
    torch.manual_seed(seed)
    np.random.seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("training_start", device=str(device), smoke=smoke)

    window = build_supervised(city="bengaluru", smoke=smoke)
    n = len(window)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_cal = max(8, n // 5)
    train_idx, cal_idx = perm[:-n_cal], perm[-n_cal:]
    cal_window = WindowedData(
        temporal=window.temporal[cal_idx],
        static=window.static[cal_idx],
        targets=window.targets[cal_idx],
        event=window.event[cal_idx],
        sku_ids=[window.sku_ids[i] for i in cal_idx],
        horizons=window.horizons,
    )
    logger.info("data_built", samples=n, train=len(train_idx), calib=len(cal_idx))

    model = _build_model(config).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=config.learning_rate, weight_decay=config.weight_decay
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.max_epochs, eta_min=1e-5
    )
    quantile_levels = list(config.quantile_levels)

    if HAS_MLFLOW and not smoke:
        try:
            mlflow.set_tracking_uri(config.mlflow_tracking_uri)
            mlflow.set_experiment("demand_prophet")
            mlflow.start_run()
        except Exception as exc:  # noqa: BLE001 — tracking is best-effort (I-7)
            logger.warning("mlflow_run_failed", error=str(exc))

    batch_size = config.batch_size
    epoch_losses: list[float] = []
    gradient_steps = 0
    start_loss = float("nan")
    t0 = time.monotonic()

    model.train()
    for epoch in range(config.max_epochs):
        ep_perm = rng.permutation(len(train_idx))
        batch_losses: list[float] = []
        for b in range(0, len(train_idx), batch_size):
            sel = train_idx[ep_perm[b : b + batch_size]]
            if len(sel) < 2:
                continue
            optimizer.zero_grad()
            loss = _batch_loss(model, window, sel, quantile_levels, device)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip_norm)
            optimizer.step()
            gradient_steps += 1
            batch_losses.append(float(loss.detach().cpu()))
        scheduler.step()
        ep_loss = float(np.mean(batch_losses)) if batch_losses else float("nan")
        epoch_losses.append(ep_loss)
        if epoch == 0:
            start_loss = ep_loss
        logger.info("epoch_complete", epoch=epoch, loss=f"{ep_loss:.5f}", steps=gradient_steps)
        if HAS_MLFLOW and not smoke and mlflow.active_run():
            mlflow.log_metric("crps_loss", ep_loss, step=epoch)

    end_loss = epoch_losses[-1] if epoch_losses else float("nan")
    coverage_p90 = _evaluate_coverage(model, cal_window, quantile_levels, device)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    ckpt_path = CHECKPOINT_DIR / ("demand_prophet_smoke.pt" if smoke else "demand_prophet.pt")
    sha = save_checkpoint(model, ckpt_path)

    if HAS_MLFLOW and not smoke and mlflow.active_run():
        try:
            mlflow.pytorch.log_model(model, "demand_prophet_hgt_tft")
            mlflow.register_model(
                f"runs:/{mlflow.active_run().info.run_id}/demand_prophet_hgt_tft",
                "demand_prophet_hgt_tft",
            )
            mlflow.log_metric("coverage_p90", coverage_p90)
            mlflow.end_run()
        except Exception as exc:  # noqa: BLE001 — registry is best-effort (I-7)
            logger.warning("mlflow_register_failed", error=str(exc))

    result = TrainResult(
        agent="demand_prophet",
        gradient_steps=gradient_steps,
        start_loss=start_loss,
        end_loss=end_loss,
        epochs=config.max_epochs,
        seed=seed,
        smoke=smoke,
        checkpoint_path=ckpt_path,
        checkpoint_sha=sha,
        metrics={"coverage_p90": coverage_p90, "wall_s": time.monotonic() - t0},
    )
    logger.info("training_complete", **result.to_dict())
    # Fail loudly if the loop did not actually learn (the gate's runtime half).
    result.assert_learned()
    return result


def main() -> None:
    """CLI entrypoint for training."""
    parser = argparse.ArgumentParser(description="Train Demand Prophet HGT-TFT Hybrid")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--smoke", action="store_true", help="tiny gated smoke train")
    args = parser.parse_args()

    if args.smoke:
        train(smoke=True)
        return
    config = DemandProphetConfig(
        max_epochs=args.epochs, batch_size=args.batch_size, learning_rate=args.lr
    )
    train(config)


if __name__ == "__main__":
    main()
