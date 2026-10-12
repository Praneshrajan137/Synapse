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
import json
import time
from pathlib import Path
from typing import Any, Final

import numpy as np
import structlog
import torch
import yaml
from pydantic import BaseModel, ConfigDict
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
# The serving-resolved model name (matches the ModelRegistry base_name + the
# MLflow registered model). The checkpoint + sidecar are written under it so the
# $0 serving source resolves them (ADR-043).
SERVING_NAME = "demand_prophet_hgt_tft"

try:
    import mlflow
    import mlflow.pytorch  # noqa: F401

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False
    logger.warning("mlflow_not_available", fallback="local checkpointing only")

# ---------------------------------------------------------------------------
# The published held-out block (decision-quality-proof R9.13, task 18.1, AD-19)
# ---------------------------------------------------------------------------
# Until this block existed the sidecar carried exactly `version`, `smoke`, `arch`
# and `calibrator`, so BOTH recomputes in
# scripts/audit/published_checkpoint_truth.py -- `recompute_final_crps` (R3.9) and
# `recompute_coverage_p90` (R8.9) -- had no input and reported UNAVAILABLE for every
# artifact this file produced. C46 read that UNAVAILABLE as `ok`, which is the hole
# R9.14 closes; publishing the block is what stops R9.13 being unavailable by
# construction.

#: The minimum number of published held-out rows a recompute needs to be evidence.
#: MIRRORS the committed declaration
#: `infrastructure/quality/checkpoint-truth.yaml::tolerances.final_crps.min_samples`.
#: It is mirrored rather than read because training must not acquire a runtime
#: dependency on an audit policy file, and a read that degraded to a default on an
#: unreadable policy would be guard-then-ignore (the C33 `substance_truth` defect).
#: The equality of the two declarations is pinned mechanically -- by AST, without
#: importing torch -- in `tests/verify/test_recompute_or_unavailable_property.py`.
HELDOUT_MIN_ROWS: Final[int] = 32

#: Cap on published rows PER HORIZON. A full train holds out ~225k windows across 5
#: horizons; publishing all of them would make a ~50 MB sidecar out of a file the
#: serving path and the gate each fetch on every start. The cap is a publication
#: shape, not a threshold any gate compares against, so it is declared here rather
#: than in `checkpoint-truth.yaml` -- whose committed draft-07 schema is
#: `additionalProperties: false` at every level and so admits no new key.
HELDOUT_MAX_ROWS_PER_HORIZON: Final[int] = 512


class HeldoutHorizon(BaseModel):
    """One horizon's published held-out evidence: the raw quantiles AND the bounds.

    The distinction between the two is the subtle part and the reason both are
    published. ``predictions`` carries the model's raw quantile forecasts at the
    declared ``quantile_levels`` -- with ``[0.1, 0.5, 0.9]`` the span from the first
    to the last is a nominal **80%** raw-quantile band. ``lower_90`` / ``upper_90``
    carry the **conformal-adjusted** band produced by
    ``ConformalCalibrator.predict_intervals``: a single symmetric CQR radius widens
    both ends, giving the nominal **90%** interval INV-DP-002 is about
    (``empirical_coverage(output.lower_90, output.upper_90, actuals) >= 0.85``,
    severity critical, ``agents/demand_prophet/spec.yaml``).

    A reader cannot infer the second from the first, so the coverage recompute reads
    ``lower_90`` / ``upper_90`` and never the quantile columns: comparing actuals
    against the 80% raw band would measure a different interval from the one
    INV-DP-002 declares, and would under-report coverage against a 0.85 floor.
    """

    model_config = ConfigDict(frozen=True)

    #: One row per held-out window, one value per declared quantile level.
    predictions: tuple[tuple[float, ...], ...]
    #: The realised value for each row. Same length as ``predictions``.
    actuals: tuple[float, ...]
    #: Conformal-adjusted lower bound per row (``max(q_lo - Q, 0)``).
    lower_90: tuple[float, ...]
    #: Conformal-adjusted upper bound per row (``q_hi + Q``).
    upper_90: tuple[float, ...]


class HeldoutBlock(BaseModel):
    """The ``heldout`` block of the published serving sidecar (R9.13).

    Its shape is the one
    ``infrastructure/quality/checkpoint-truth.yaml::tolerances.final_crps`` declares
    and ``published_checkpoint_truth._horizon_blocks`` normalises: a
    ``quantile_levels`` list plus a ``horizons`` mapping. The two band widths are
    stated as numbers rather than left to a reader's arithmetic, because conflating
    them is the specific error this block exists to prevent.

    Held out from *training*, in-sample for the *conformal radius*: these rows are
    the calibration slice, excluded from every gradient step, and they are also the
    rows the CQR radius was fitted on. That is exactly what
    ``calibrator.last_coverage_p90`` already reports and what INV-DP-002 is measured
    on today; the recompute makes that number checkable rather than asserted. It does
    not turn it into an out-of-sample estimate, and this docstring is the only place
    that says so, so do not read the block as one.
    """

    model_config = ConfigDict(frozen=True)

    #: The levels ``predictions`` columns are ordered by (config.quantile_levels).
    quantile_levels: tuple[float, ...]
    #: ``levels[-1] - levels[0]`` -- the nominal width of the RAW quantile band.
    raw_quantile_band: float
    #: ``1 - alpha`` -- the nominal width of the CONFORMAL-ADJUSTED band.
    conformal_adjusted_band: float
    #: Total published rows across every horizon, the count the recomputes compare
    #: against :data:`HELDOUT_MIN_ROWS`. Stated so a reader sees the count without
    #: recounting; both recomputes count the lists themselves and never trust this.
    rows: int
    #: The minimum this artifact was published against, so a sidecar published under
    #: an older minimum is legible after the committed value moves.
    min_rows: int
    horizons: dict[str, HeldoutHorizon]


def _heldout_block(
    calibrator: ConformalCalibrator,
    predictions: dict[str, np.ndarray],
    actuals: dict[str, np.ndarray],
    quantile_levels: list[float],
) -> HeldoutBlock:
    """Build the published held-out block from the fitted calibrator's own output.

    The adjusted bounds come from :meth:`ConformalCalibrator.predict_intervals` -- the
    same call the serving path makes -- rather than from a re-derivation here, so the
    published bounds cannot drift from the ones served. A recompute against
    independently re-derived bounds would prove nothing about the artifact in use.

    Rows are capped at :data:`HELDOUT_MAX_ROWS_PER_HORIZON` by taking a prefix. The
    calibration indices were drawn by ``rng.permutation``, so a prefix is already a
    seeded random sample of the slice, and taking it is deterministic and replayable
    from the recorded seed.
    """
    intervals = calibrator.predict_intervals(predictions)
    horizons: dict[str, HeldoutHorizon] = {}
    total = 0
    for horizon in sorted(predictions):
        lower, upper = intervals[horizon]
        keep = min(len(actuals[horizon]), HELDOUT_MAX_ROWS_PER_HORIZON)
        horizons[horizon] = HeldoutHorizon(
            predictions=tuple(
                tuple(float(value) for value in row) for row in predictions[horizon][:keep]
            ),
            actuals=tuple(float(value) for value in actuals[horizon][:keep]),
            lower_90=tuple(float(value) for value in lower[:keep]),
            upper_90=tuple(float(value) for value in upper[:keep]),
        )
        total += keep
    levels = tuple(float(level) for level in quantile_levels)
    return HeldoutBlock(
        quantile_levels=levels,
        raw_quantile_band=float(levels[-1] - levels[0]) if levels else 0.0,
        conformal_adjusted_band=float(1.0 - calibrator.alpha),
        rows=total,
        min_rows=HELDOUT_MIN_ROWS,
        horizons=horizons,
    )


def _published_rows_coverage(block: HeldoutBlock) -> float | None:
    """Empirical coverage of the adjusted bounds over the rows actually published.

    Logged, never recorded as a claim: the operator's publish gate (runbook step 4)
    needs to know whether the block it is about to upload will clear the 0.85 floor,
    and ``calibrator.last_coverage_p90`` answers that for the *whole* slice rather
    than for the capped prefix. ``published_checkpoint_truth.recompute_coverage_p90``
    recomputes this independently from the published file and is the verdict; this is
    a courtesy to the operator, ``None`` when nothing was published.
    """
    per_horizon: list[float] = []
    for horizon in block.horizons.values():
        if not horizon.actuals:
            continue
        covered = sum(
            1
            for actual, low, high in zip(
                horizon.actuals, horizon.lower_90, horizon.upper_90, strict=True
            )
            if low <= actual <= high
        )
        per_horizon.append(covered / len(horizon.actuals))
    return float(np.mean(per_horizon)) if per_horizon else None


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
    graph = build_graph(n).to(device)
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


def _fit_calibrator(
    model: DemandProphetHybrid,
    window: WindowedData,
    quantile_levels: list[float],
    device: torch.device,
) -> tuple[ConformalCalibrator, dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Fit the conformal calibrator on a holdout slice; return it WITH its evidence.

    Returning the calibrator (not just its coverage number) is the ADR-043 fix:
    the fitted CQR adjustments are persisted in the serving sidecar so the serving
    path restores a calibrated model instead of rebuilding an unfit one.

    Returning the ``(predictions, actuals)`` it was fitted on alongside it is the
    R9.13 fix: those arrays are the only possible input to the published held-out
    block, and re-running the forward pass to recover them would both double the
    compute and risk publishing evidence the calibrator was never fitted against.
    """
    model.eval()
    idx = np.arange(len(window))
    with torch.no_grad():
        batch = to_torch_batch(window, idx)
        graph = build_graph(batch["num_skus"]).to(device)
        static = [t.to(device) for t in batch["static_inputs"]]
        temporal = [t.to(device) for t in batch["temporal_inputs"]]
        outputs = model(graph, static, temporal)
    predictions = {h: outputs[h].cpu().numpy() for h in HORIZONS}
    actuals = {h: window.targets[idx, h_idx] for h_idx, h in enumerate(HORIZONS)}
    calib = ConformalCalibrator(alpha=0.1, coverage_target=0.85)
    calib.fit(predictions, actuals)
    return calib, predictions, actuals


def _serving_arch(config: DemandProphetConfig) -> dict[str, int]:
    """The exact ``DemandProphetHybrid`` kwargs the checkpoint was trained with.

    Persisted in the sidecar so the serving builder reconstructs the identical
    architecture (smoke arch ≠ full arch) before ``load_state_dict``.
    """
    return {
        "hgt_hidden_dim": config.hgt_hidden_dim,
        "hgt_num_heads": config.hgt_num_heads,
        "hgt_num_layers": config.hgt_num_layers,
        "tft_hidden_size": config.tft_hidden_size,
        "tft_num_heads": config.tft_attention_heads,
        "tft_num_static": config.tft_num_static,
        "tft_num_time_known": config.tft_num_time_known,
        "tft_num_time_observed": config.tft_num_time_observed,
    }


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

    window = build_supervised(
        city="bengaluru",
        smoke=smoke,
        num_static=config.tft_num_static,
        num_channels=config.tft_num_time_known + config.tft_num_time_observed,
    )
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
    calibrator, cal_predictions, cal_actuals = _fit_calibrator(
        model, cal_window, quantile_levels, device
    )
    coverage_p90 = float(calibrator.last_coverage_p90 or 0.0)
    heldout = _heldout_block(calibrator, cal_predictions, cal_actuals, quantile_levels)

    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    # ADR-043: write the checkpoint under the *serving-resolved* name so the
    # ModelRegistry $0 checkpoint source finds it by `resolve_name(...)`. A full
    # train overwrites the smoke artifact for production serving; both are content
    # -addressed by the sha recorded in the TrainResult (C38 hashes the path, not
    # the filename, so this rename is gate-safe).
    ckpt_path = CHECKPOINT_DIR / f"{SERVING_NAME}.pt"
    sha = save_checkpoint(model, ckpt_path)

    # ADR-043 serving sidecar: the architecture dims + the FITTED calibrator state
    # travel with the weights so serving reconstructs the exact model and a
    # calibrated interval, never an unfit calibrator (the latent-500 fix).
    #
    # R9.13 adds `heldout`. Without it the two recomputes in
    # scripts/audit/published_checkpoint_truth.py have no input, report UNAVAILABLE,
    # and -- through the C46 surface this feature re-points -- that UNAVAILABLE read
    # as `ok`. The block carries the raw quantile predictions AND the
    # conformal-adjusted `lower_90`/`upper_90` bounds separately, because the
    # declared quantile_levels span a nominal 80% band while INV-DP-002 is about the
    # adjusted 90% one, and no reader can derive the second from the first.
    sidecar: dict[str, Any] = {
        "version": f"{'smoke' if smoke else 'full'}_{sha}",
        "smoke": smoke,
        "arch": _serving_arch(config),
        "calibrator": calibrator.to_state(),
        "heldout": heldout.model_dump(mode="json"),
    }
    sidecar_path = CHECKPOINT_DIR / f"{SERVING_NAME}.serving.json"
    sidecar_path.write_text(
        json.dumps(sidecar, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    logger.info("serving_sidecar_written", path=str(sidecar_path), coverage_p90=coverage_p90)
    # The operator's publish gate (docs/runbooks/train-and-publish-checkpoint.md
    # step 4) decides on the 0.85 floor, and the gate that judges the published file
    # recomputes coverage over exactly these rows -- which are a capped prefix of the
    # slice `coverage_p90` above summarises. Report both, and report the shortfall
    # when the block is too short to be evidence at all, so a publication that will
    # land UNAVAILABLE is visible before the upload rather than after it.
    logger.info(
        "heldout_block_written",
        rows=heldout.rows,
        min_rows=heldout.min_rows,
        below_min_rows=heldout.rows < heldout.min_rows,
        horizons=sorted(heldout.horizons),
        raw_quantile_band=heldout.raw_quantile_band,
        conformal_adjusted_band=heldout.conformal_adjusted_band,
        coverage_p90_over_published_rows=_published_rows_coverage(heldout),
    )

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
