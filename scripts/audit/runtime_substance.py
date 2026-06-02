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

This gate is the RUNTIME counterpart: it boots each *wired* agent's checkpoint
through its **production** serving path (``ModelRegistry`` → ``load_serving_model``
→ ``<Agent>Pipeline``) against real per-entity features and asserts the output is
genuinely real — ``degraded=False``, the agent's declared ``confidence_basis``, and
confidence NOT collapsed to the fallback floor. A regression to either defect
turns the affected agent's probe RED.

**Per-agent probe registry (ADR-043 ratchet).** Each agent contributes one probe
via :func:`register_probe`. :func:`evaluate` runs all registered probes and
aggregates (any FAIL → FAIL; else any OK → OK; else SKIP). New agents append a
probe in their reality PR; the methodology scales without touching this scaffold.

Like ``checkpoint_truth`` / ``calibration_truth`` each probe **SKIPs** (never
fabricates a pass) when torch is absent or no serving checkpoint exists — the
runtime proof lives in the CI ``training-smoke`` job, which produces the artifact
first.

Run::

    python -m scripts.audit.runtime_substance                 # human lines (all probes)
    python -m scripts.audit.runtime_substance --json          # machine JSON (aggregate)
    python -m scripts.audit.runtime_substance --check         # exit 1 on any real failure
    python -m scripts.audit.runtime_substance --agent pricing_oracle   # one probe
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DIR = ROOT / "artifacts" / "checkpoints"


@dataclass
class RuntimeProbe:
    status: str  # ok | fail | skip
    detail: str


# --------------------------------------------------------------------------- #
# Per-agent probe registry. Each probe boots one agent's real serving path and
# returns a RuntimeProbe. evaluate() aggregates across all registered probes.
# --------------------------------------------------------------------------- #
ProbeFn = Callable[[], RuntimeProbe]
PROBES: dict[str, ProbeFn] = {}


def register_probe(agent: str) -> Callable[[ProbeFn], ProbeFn]:
    """Register ``fn`` as the runtime-substance probe for ``agent``."""

    def _decorator(fn: ProbeFn) -> ProbeFn:
        PROBES[agent] = fn
        return fn

    return _decorator


class StubFeatureStore:
    """Generic in-process Feast stand-in returning DISTINCT per-entity features.

    Parameterised by a ``feature_template`` (``{feature_ref: fn(i) -> value}``) so
    each agent's probe exercises its own ``FEATURE_REFS``. The gate's job is to
    drive the real serving code path end-to-end, not to prove a Feast deployment is
    up (that is the integration assertion). Distinct features make
    ``feature_source=FEAST`` and feed the model varying input.
    """

    def __init__(
        self,
        feature_template: dict[str, Callable[[int], float]],
        *,
        entity_key: str = "sku_id",
    ) -> None:
        self._template = feature_template
        self._entity_key = entity_key

    class _Online:
        def __init__(
            self,
            entities: list[str],
            template: dict[str, Callable[[int], float]],
            entity_key: str,
        ) -> None:
            self._entities = entities
            self._template = template
            self._entity_key = entity_key

        def to_dict(self) -> dict[str, list[Any]]:
            n = len(self._entities)
            out: dict[str, list[Any]] = {self._entity_key: list(self._entities)}
            for ref, fn in self._template.items():
                out[ref] = [fn(i) for i in range(n)]
            return out

    def get_online_features(self, features: object, entity_rows: list[dict[str, Any]]) -> Any:
        entities = [r[self._entity_key] for r in entity_rows]
        return self._Online(entities, self._template, self._entity_key)


# --------------------------------------------------------------------------- #
# demand_prophet (forecasting paradigm) — the reference probe.
# --------------------------------------------------------------------------- #
@register_probe("demand_prophet")
def _probe_demand_prophet() -> RuntimeProbe:
    """Probe the real demand_prophet serving path; SKIP when prerequisites absent."""
    try:
        import torch  # noqa: F401, PLC0415 — runtime ML stack required for a real load
    except ImportError:
        return RuntimeProbe("skip", "torch absent - runtime proof runs in the CI smoke job")
    ckpt = CHECKPOINT_DIR / "demand_prophet_hgt_tft.pt"
    if not ckpt.is_file():
        return RuntimeProbe("skip", f"no serving checkpoint at {ckpt.name} (run smoke job)")

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

    # Distinct per-SKU features so the real path is genuinely exercised.
    stub_feast = StubFeatureStore(
        {
            "sku_demand_signals:rolling_mean_7d": lambda i: 8.0 + 3.0 * i,
            "sku_demand_signals:rolling_std_7d": lambda i: 1.0 + 0.5 * i,
            "sku_demand_signals:trend_slope": lambda i: 0.05 * (i + 1),
            "sku_demand_signals:seasonality_idx": lambda i: 0.2 + 0.1 * i,
        }
    )

    registry = ModelRegistry(
        None, checkpoint_dir=ckpt.parent, model_builder=build_demand_prophet_model
    )
    model = load_serving_model(registry)
    if model is None:
        return RuntimeProbe("fail", "checkpoint present but registry resolved a degraded model")
    calibrator = getattr(model, "calibrator", None)
    if calibrator is None or not getattr(calibrator, "is_calibrated", False):
        return RuntimeProbe("fail", "model loaded but the fitted calibrator was not restored")

    pipe = DemandProphetPipeline(
        model=model, conformal_calibrator=calibrator, feast_client=stub_feast
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
        f"demand_prophet served real: degraded=False, basis=CONFORMAL_INTERVAL, "
        f"coverage_p90={cov}, confidences={confs}",
    )


# --------------------------------------------------------------------------- #
# routing_navigator (analytical / solver paradigm) — torch-free probe.
# --------------------------------------------------------------------------- #
@register_probe("routing_navigator")
def _probe_routing_navigator() -> RuntimeProbe:
    """Boot the calibrated CVRPTW solver through serving; SKIP if no checkpoint.

    Analytical + torch-free: this probe runs (and PASSES) anywhere the calibration
    checkpoint exists, so the solver paradigm's runtime substance is provable
    without the ML stack.
    """
    ckpt = CHECKPOINT_DIR / "routing_cvrptw.pt"
    if not ckpt.is_file():
        return RuntimeProbe("skip", "no routing_cvrptw.pt calibration (run the smoke job)")

    from synapse_common.model_registry import ModelRegistry  # noqa: PLC0415
    from synapse_common.provenance import ConfidenceBasis, FeatureSource  # noqa: PLC0415

    from agents.routing_navigator.inference.pipeline import (  # noqa: PLC0415
        RoutingNavigatorPipeline,
    )
    from agents.routing_navigator.inference.serving_model import (  # noqa: PLC0415
        build_routing_model,
        load_serving_model,
    )

    registry = ModelRegistry(None, checkpoint_dir=ckpt.parent, model_builder=build_routing_model)
    model = load_serving_model(registry)
    if model is None or not getattr(model, "is_real", False):
        return RuntimeProbe("fail", "calibration present but registry resolved a degraded model")

    pipe = RoutingNavigatorPipeline(solver_model=model)
    # Two structurally different instances (a tight near-collinear cluster vs. a
    # larger scattered set) → different optimality gaps → different calibrated
    # confidence, proving the signal is non-constant on real inputs.
    instances = [
        [
            {"order_id": f"o{i}", "lat": 12.97 + 0.004 * i, "lon": 77.59 + 0.004 * i,
             "weight_kg": 2.0, "due_min": 300.0}
            for i in range(1, 4)
        ],
        [
            {"order_id": f"o{i}", "lat": 12.97 + 0.05 * ((i % 3) - 1),
             "lon": 77.59 + 0.05 * ((i % 2) - 0.5), "weight_kg": 2.0, "due_min": 300.0}
            for i in range(1, 8)
        ],
    ]
    confs: list[float] = []
    for orders in instances:
        riders = [{"rider_id": "r1", "capacity_kg": 30.0}]
        plans = pipe.route(orders, riders, "store_x", use_student=False)
        if not plans:
            return RuntimeProbe("fail", "Tier-2 solver returned no plans on a valid instance")
        confs.append(round(plans[0].confidence, 4))
        prov = pipe.last_provenance
        if prov.degraded:
            return RuntimeProbe("fail", "calibrated solver served degraded provenance")
        if prov.confidence_basis != ConfidenceBasis.OPTIMALITY_GAP:
            return RuntimeProbe("fail", f"basis {prov.confidence_basis} is not OPTIMALITY_GAP")
        if prov.feature_source != FeatureSource.DIRECT:
            return RuntimeProbe("fail", f"expected DIRECT source, got {prov.feature_source}")

    if all(c == 0.5 for c in confs):
        return RuntimeProbe("fail", "confidence collapsed to the greedy floor (not calibrated)")
    return RuntimeProbe(
        "ok",
        f"routing_navigator served real: degraded=False, basis=OPTIMALITY_GAP, "
        f"calibrated_confidences={confs}",
    )


# --------------------------------------------------------------------------- #
# Aggregation across all registered probes.
# --------------------------------------------------------------------------- #
def evaluate(agents: list[str] | None = None) -> RuntimeProbe:
    """Run the registered probes and aggregate into a single RuntimeProbe.

    Aggregation rule: any FAIL → FAIL (the gate must go RED on a real regression);
    else any OK → OK (at least one agent is proven real at runtime); else SKIP (no
    prerequisites available — the CI smoke job is where this turns real).
    """
    names = agents if agents is not None else sorted(PROBES)
    results: dict[str, RuntimeProbe] = {}
    for name in names:
        probe = PROBES.get(name)
        if probe is None:
            results[name] = RuntimeProbe("skip", f"no probe registered for {name}")
            continue
        results[name] = probe()

    fails = [f"{n}: {r.detail}" for n, r in results.items() if r.status == "fail"]
    if fails:
        return RuntimeProbe("fail", "; ".join(fails))

    oks = [n for n, r in results.items() if r.status == "ok"]
    skips = [n for n, r in results.items() if r.status == "skip"]
    if oks:
        detail = f"{len(oks)}/{len(results)} agent(s) served real output: {', '.join(oks)}"
        if skips:
            detail += f" (skipped: {', '.join(skips)})"
        return RuntimeProbe("ok", detail)
    return RuntimeProbe("skip", f"all {len(results)} probe(s) skipped: {', '.join(skips)}")


def evaluate_each(agents: list[str] | None = None) -> dict[str, RuntimeProbe]:
    """Per-agent probe results (for human/JSON reporting and tests)."""
    names = agents if agents is not None else sorted(PROBES)
    return {n: (PROBES[n]() if n in PROBES else RuntimeProbe("skip", "no probe")) for n in names}


def run(*, as_json: bool = False, check: bool = False, agents: list[str] | None = None) -> int:
    per_agent = evaluate_each(agents)
    agg = evaluate(agents)
    if as_json:
        per = {n: {"status": r.status, "detail": r.detail} for n, r in per_agent.items()}
        print(
            json.dumps(
                {"status": agg.status, "detail": agg.detail, "per_agent": per},
                sort_keys=True,
            )
        )
    else:
        sym = {"ok": "[OK]", "fail": "[XX]", "skip": "[--]"}
        for name, r in per_agent.items():
            print(f"{sym[r.status]} runtime-substance  {name:18s} {r.detail}")
        print(f"{sym[agg.status]} runtime-substance  {'AGGREGATE':18s} {agg.detail}")
    if check:
        return 1 if agg.status == "fail" else 0
    return 0


def _parse_agents(argv: list[str]) -> list[str] | None:
    if "--agent" in argv:
        idx = argv.index("--agent")
        if idx + 1 < len(argv):
            return [argv[idx + 1]]
    return None


if __name__ == "__main__":
    sys.exit(
        run(
            as_json="--json" in sys.argv,
            check="--check" in sys.argv,
            agents=_parse_agents(sys.argv),
        )
    )
