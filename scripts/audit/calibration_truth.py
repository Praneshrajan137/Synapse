"""Make the SYNAPSE *calibration gap* mechanically visible (ADR-042, C40).

A trained, loadable model (C37+C38) can still be *wrong about its own
uncertainty*. This is the deepest substance check: it proves the prediction
intervals are **real**, not decorative. For a nominal 90% interval the empirical
held-out coverage must be close to 0.90; the frontier guarantee (Adaptive
Conformal Inference / Conformalized Quantile Regression) is that split-conformal
calibration achieves this distribution-free.

This gate consumes the held-out metrics each smoke/full-train writes to
:data:`ARTIFACTS_DIR` (``metrics.coverage_p90`` for conformal agents,
``metrics.pi_coverage`` for analytical interval agents, ``metrics.d_cal`` for
survival agents) and asserts coverage >= the agent's documented target. With no
artifacts it **SKIPs** - never a fabricated pass.

The targets match the agents' own configs (e.g. demand_prophet's
``conformal_coverage_target = 0.85`` floor for a 0.90-nominal interval; the
slack absorbs finite-sample error).

Run::

    python -m scripts.audit.calibration_truth [--json|--check]
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT / "artifacts" / "training"

# Per-agent (metric_key, floor). The metric the agent's calibration writes, and
# the minimum acceptable empirical coverage. Agents absent here are not yet
# calibration-gated (added in their ratchet PR).
CALIBRATION_TARGETS: dict[str, tuple[str, float]] = {
    "demand_prophet": ("coverage_p90", 0.85),     # 90%-nominal conformal PI, 0.85 floor
    "supplier_trust": ("posterior_coverage", 0.80),
    "freshness_guardian": ("d_cal", 0.80),
    "inventory_sentinel": ("pi_coverage", 0.85),
    "routing_navigator": ("og_coverage", 0.80),   # 80%-nominal optimality-gap PI
    "disruption_shield": ("detection_auc", 0.75),  # anomaly separability (ROC-AUC)
}

# Agents that MUST have produced a calibration metric when a smoke run was
# expected (CI sets SYNAPSE_SMOKE_RUN=1 after smoke_train). Grows one per PR.
SMOKE_REQUIRED: frozenset[str] = frozenset(
    {
        "demand_prophet",
        "inventory_sentinel",
        "routing_navigator",
        "supplier_trust",
        "disruption_shield",
        "freshness_guardian",
    }
)
_SMOKE_EXPECTED = bool(os.environ.get("SYNAPSE_SMOKE_RUN"))


@dataclass
class Result:
    agent: str
    status: str  # ok | below_floor | no_metric | no_artifact
    detail: str


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)


def collect() -> tuple[Report, bool]:
    report = Report()
    any_artifact = ARTIFACTS_DIR.is_dir() and any(ARTIFACTS_DIR.glob("*.json"))
    if not any_artifact:
        return report, False
    artifacts = {}
    for art in sorted(ARTIFACTS_DIR.glob("*.json")):
        try:
            data = json.loads(art.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        artifacts[data.get("agent", art.stem)] = data

    for agent, (metric_key, floor) in sorted(CALIBRATION_TARGETS.items()):
        data = artifacts.get(agent)
        if data is None:
            if _SMOKE_EXPECTED and agent in SMOKE_REQUIRED:
                report.results.append(
                    Result(agent, "no_metric", "smoke run expected a calibration artifact, none found")
                )
            continue  # no artifact for this agent yet -> skip silently
        metrics = data.get("metrics", {})
        if metric_key not in metrics:
            report.results.append(
                Result(agent, "no_metric", f"artifact has no metrics.{metric_key}")
            )
            continue
        cov = float(metrics[metric_key])
        if cov + 1e-9 < floor:
            report.results.append(
                Result(agent, "below_floor", f"{metric_key}={cov:.4f} < floor {floor}")
            )
        else:
            report.results.append(
                Result(agent, "ok", f"{metric_key}={cov:.4f} >= floor {floor}")
            )
    return report, True


def run(*, as_json: bool = False, check: bool = False) -> int:
    report, any_artifact = collect()
    failures = [r for r in report.results if r.status in {"below_floor", "no_metric"}]

    if as_json:
        print(json.dumps({
            "summary": {"artifacts_found": any_artifact, "checked": len(report.results),
                        "failures": len(failures)},
            "results": [r.__dict__ for r in report.results],
        }, indent=2, sort_keys=True))
    else:
        if not any_artifact:
            print("[--] calibration-truth: no training artifacts present (SKIP - run the smoke job)")
        for r in report.results:
            sym = "[OK]" if r.status == "ok" else "[XX]"
            print(f"{sym} {r.agent:<22} {r.status:<12} {r.detail}")
        if report.results:
            print()
        print(f"Calibration-truth: {len(failures)} failure(s) across {len(report.results)} calibrated agent(s).")

    if check:
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
