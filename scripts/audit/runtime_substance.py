"""Make the SYNAPSE *runtime* substance gap mechanically visible (ADR-043, C42).

``substance_truth.py`` (C33) is a STATIC gate: it AST-walks the pipelines and
flags dishonest *shapes* — a ``confidence=0.85`` literal, a guard-then-ignore
fallback, RNG feeding a model. By construction it cannot see whether a real model
actually executes at runtime. That blind spot hid two real defects in the
flagship slice:

  1. serving constructed an *unfit* calibrator → the first real-path request raised
     ``RuntimeError`` → unhandled 500 (invisible because every test ran model=None);
  2. the registry was MLflow-only, so a trained checkpoint was never loadable at $0
     → every request silently took the honest-but-hollow fallback.

This gate is the RUNTIME counterpart: it boots the demand_prophet checkpoint
through the *production* serving path (``ModelRegistry`` → ``load_serving_model``
→ ``DemandProphetPipeline``) against real per-SKU features and asserts the output
is genuinely real — ``degraded=False``, ``confidence_basis=CONFORMAL_INTERVAL``,
and confidence NOT collapsed to the fallback floor. A regression to either defect
turns this RED.

Like ``checkpoint_truth`` / ``calibration_truth`` it **SKIPs** (never fabricates a
pass) when torch is absent or no serving checkpoint exists — the runtime proof
lives in the CI ``training-smoke`` job, which produces the artifact first.

Run::

    python -m scripts.audit.runtime_substance            # human line
    python -m scripts.audit.runtime_substance --json      # machine JSON
    python -m scripts.audit.runtime_substance --check      # exit 1 on a real failure
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SERVING_CKPT = ROOT / "artifacts" / "checkpoints" / "demand_prophet_hgt_tft.pt"


@dataclass
class RuntimeProbe:
    status: str  # ok | fail | skip
    detail: str


class _StubFeast:
    """In-process Feast stand-in returning DISTINCT per-SKU features.

    The gate's job is to exercise the real serving code path end-to-end, not to
    prove a Feast deployment is up (that is WS-C's integration assertion). Distinct
    features make ``feature_source=FEAST`` and feed the model varying input.
    """

    class _Online:
        def __init__(self, skus: list[str]) -> None:
            self._skus = skus

        def to_dict(self) -> dict[str, list]:
            n = len(self._skus)
            # Vary each feature per-SKU so the real path is genuinely exercised.
            return {
                "sku_id": self._skus,
                "sku_demand_signals:rolling_mean_7d": [8.0 + 3.0 * i for i in range(n)],
                "sku_demand_signals:rolling_std_7d": [1.0 + 0.5 * i for i in range(n)],
                "sku_demand_signals:trend_slope": [0.05 * (i + 1) for i in range(n)],
                "sku_demand_signals:seasonality_idx": [0.2 + 0.1 * i for i in range(n)],
            }

    def get_online_features(self, features: object, entity_rows: list[dict]) -> Any:
        return self._Online([r["sku_id"] for r in entity_rows])


def evaluate() -> RuntimeProbe:
    """Probe the real serving path; SKIP when its prerequisites are absent."""
    try:
        import torch  # noqa: F401, PLC0415 — runtime ML stack required for a real load
    except ImportError:
        return RuntimeProbe("skip", "torch absent - runtime proof runs in the CI smoke job")
    if not SERVING_CKPT.is_file():
        return RuntimeProbe("skip", f"no serving checkpoint at {SERVING_CKPT.name} (run smoke job)")

    from synapse_common.model_registry import ModelRegistry  # noqa: PLC0415
    from synapse_common.provenance import ConfidenceBasis, FeatureSource  # noqa: PLC0415

    from agents.demand_prophet.inference.pipeline import (  # noqa: PLC0415
        FALLBACK_CONFIDENCE,
        DemandProphetPipeline,
    )
    from agents.demand_prophet.inference.serving_model import (  # noqa: PLC0415
        build_demand_prophet_model,
        load_serving_model,
    )

    registry = ModelRegistry(
        None, checkpoint_dir=SERVING_CKPT.parent, model_builder=build_demand_prophet_model
    )
    model = load_serving_model(registry)
    if model is None:
        return RuntimeProbe("fail", "checkpoint present but registry resolved a degraded model")
    calibrator = getattr(model, "calibrator", None)
    if calibrator is None or not getattr(calibrator, "is_calibrated", False):
        return RuntimeProbe("fail", "model loaded but the fitted calibrator was not restored")

    pipe = DemandProphetPipeline(
        model=model, conformal_calibrator=calibrator, feast_client=_StubFeast()
    )
    forecasts = pipe.predict(["sku_a", "sku_b", "sku_c"], "store_x", horizons={"1h", "24h"})
    prov = pipe.last_provenance

    if prov.degraded:
        return RuntimeProbe("fail", f"real checkpoint served degraded (src={prov.feature_source})")
    if prov.feature_source != FeatureSource.FEAST:
        return RuntimeProbe("fail", f"expected FEAST features, got {prov.feature_source}")
    if prov.confidence_basis != ConfidenceBasis.CONFORMAL_INTERVAL:
        return RuntimeProbe("fail", f"basis {prov.confidence_basis} is not CONFORMAL_INTERVAL")
    confs = [round(f.confidence, 4) for f in forecasts]
    if all(c == FALLBACK_CONFIDENCE for c in confs):
        return RuntimeProbe("fail", "confidence collapsed to the fallback floor (disguised)")

    cov = getattr(calibrator, "last_coverage_p90", None)
    return RuntimeProbe(
        "ok",
        f"real checkpoint served: degraded=False, basis=CONFORMAL_INTERVAL, "
        f"coverage_p90={cov}, confidences={confs}",
    )


def run(*, as_json: bool = False, check: bool = False) -> int:
    probe = evaluate()
    if as_json:
        print(json.dumps({"status": probe.status, "detail": probe.detail}, sort_keys=True))
    else:
        sym = {"ok": "[OK]", "fail": "[XX]", "skip": "[--]"}[probe.status]
        print(f"{sym} runtime-substance  {probe.detail}")
    if check:
        return 1 if probe.status == "fail" else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
