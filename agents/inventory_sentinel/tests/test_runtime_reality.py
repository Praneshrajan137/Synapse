"""INV-IS-009 — runtime reality for the conformal-calibrated newsvendor (ADR-043).

Torch/lifelines-free: builds an InventoryServingModel from hand-set conformal
residuals, wires it into the pipeline, and proves the decision is genuinely real —
non-degraded, RESIDUAL_VARIANCE basis, and confidence that varies with forecast
volatility (a low-variance SKU is more confident than a high-variance one). Also
proves the honesty fix: with no calibration the decision is degraded.
"""

from __future__ import annotations

import numpy as np
from synapse_common.provenance import ConfidenceBasis

from agents.inventory_sentinel.inference.pipeline import InventorySentinelPipeline
from agents.inventory_sentinel.inference.serving_model import (
    InventoryServingModel,
    build_inventory_model,
)


def _model() -> InventoryServingModel:
    rng = np.random.default_rng(0)
    residuals = rng.normal(0.0, 5.0, size=400).tolist()
    return build_inventory_model(
        {"residuals": residuals, "half_width": 8.2}, {"version": "full_test"}
    )


def test_builder_produces_a_real_calibration() -> None:
    m = _model()
    assert m.is_real
    assert m.version == "full_test"
    assert m.residuals.size >= 10


def test_inv_is_009_runtime_reality_non_degraded_residual_variance() -> None:
    """INV-IS-009 — calibrated newsvendor serves real, volatility-varying confidence."""
    pipe = InventorySentinelPipeline(serving_model=_model())
    actions = pipe.decide(
        ["low_vol", "high_vol"],
        "store_x",
        demand_forecast={
            "low_vol": {"mean": 50.0, "std": 2.0, "on_hand": 5.0},
            "high_vol": {"mean": 50.0, "std": 40.0, "on_hand": 5.0},
        },
    )
    prov = pipe.last_provenance
    conf = {a.sku_id: a.confidence for a in actions}
    # INV-IS-009: real provenance + RESIDUAL_VARIANCE basis + volatility-varying confidence.
    assert not prov.degraded
    assert prov.confidence_basis == ConfidenceBasis.RESIDUAL_VARIANCE
    assert conf["low_vol"] > conf["high_vol"]


def test_unfitted_is_honestly_degraded() -> None:
    pipe = InventorySentinelPipeline()  # no serving_model → empty calibration
    pipe.decide(["x"], "store_x", demand_forecast={"x": {"mean": 10.0, "std": 3.0}})
    assert pipe.last_provenance.degraded
