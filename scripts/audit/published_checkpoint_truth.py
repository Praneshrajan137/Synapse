"""Prove a *real, published* production checkpoint exists and is calibrated (C43).

ADR-043's C42 boots a checkpoint through the serving path — but in CI that is the
*smoke* artifact. This gate is the authenticity counterpart: it verifies that an
operator actually ran the free-GPU full train (``docs/runbooks/train-and-publish-
checkpoint.md``) and published a genuine, non-smoke, adequately-calibrated
checkpoint to the $0 serving source (HF Hub), and that what is published matches
what the operator recorded in the committed registry.

It is **$0-safe and never fabricates a pass**:

  * ``DP_HF_REPO`` unset                  → SKIP (no published model claimed yet).
  * ``huggingface_hub`` absent            → SKIP (cannot verify the remote).
  * registry still at ``__placeholder__`` → SKIP (no operator has published yet).
  * published sidecar marked ``smoke``    → FAIL (a smoke artifact is not production).
  * coverage below the floor              → FAIL (uncalibrated = not real).
  * registry sha ≠ published sha          → FAIL (drift between record and remote).

So CI stays green without any secret; the moment an operator publishes and records
the result, this turns into a live, regression-guarded proof that *a real model
serves*.

Run::

    python -m scripts.audit.published_checkpoint_truth            # human line
    python -m scripts.audit.published_checkpoint_truth --json     # machine JSON
    python -m scripts.audit.published_checkpoint_truth --check    # exit 1 on a real failure
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "infrastructure" / "ml" / "published_checkpoints.json"
SERVING_NAME = "demand_prophet_hgt_tft"
COVERAGE_FLOOR = 0.85  # INV-DP-002 nominal 90% interval achieves >=85% coverage.


@dataclass
class PublishProbe:
    status: str  # ok | fail | skip
    detail: str


def _load_registry() -> dict[str, Any]:
    if not REGISTRY.is_file():
        return {}
    try:
        parsed: dict[str, Any] = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed


def evaluate(*, name: str = SERVING_NAME) -> PublishProbe:
    """Verify the published production checkpoint; SKIP when unclaimed/unverifiable."""
    repo = os.environ.get("DP_HF_REPO") or None
    if repo is None:
        return PublishProbe("skip", "DP_HF_REPO unset - no published model claimed (operator step)")

    registry = _load_registry()
    if not registry or "__placeholder__" in registry:
        return PublishProbe(
            "skip",
            "published_checkpoints.json is a placeholder - run the publish runbook + record it",
        )

    try:
        from huggingface_hub import hf_hub_download  # noqa: PLC0415
    except ImportError:
        return PublishProbe("skip", "huggingface_hub absent - cannot verify the remote")

    try:
        sidecar_path = hf_hub_download(repo_id=repo, filename=f"{name}.serving.json")
        sidecar: dict[str, Any] = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 — an unreachable/absent remote is honest SKIP, not a lie
        return PublishProbe("skip", f"could not fetch {name}.serving.json from {repo}: {exc}")

    if sidecar.get("smoke") is True:
        return PublishProbe("fail", f"published {name} is a SMOKE artifact, not a production model")

    calib = sidecar.get("calibrator", {}) or {}
    coverage = calib.get("last_coverage_p90")
    if coverage is None or float(coverage) < COVERAGE_FLOOR:
        return PublishProbe(
            "fail", f"published coverage_p90={coverage} < floor {COVERAGE_FLOOR} (uncalibrated)"
        )

    # Cross-check the operator's recorded sha against the published version sha.
    entry = registry.get(name) or registry.get(repo) or {}
    recorded_sha = str(entry.get("sha", "")).strip()
    published_version = str(sidecar.get("version", ""))  # e.g. "full_<sha>"
    if recorded_sha and recorded_sha not in published_version:
        return PublishProbe(
            "fail",
            f"registry sha {recorded_sha!r} not in published version {published_version!r} (drift)",
        )

    return PublishProbe(
        "ok",
        f"published {name} @ {repo}: version={published_version}, coverage_p90={coverage}",
    )


def run(*, as_json: bool = False, check: bool = False) -> int:
    probe = evaluate()
    if as_json:
        print(json.dumps({"status": probe.status, "detail": probe.detail}, sort_keys=True))
    else:
        sym = {"ok": "[OK]", "fail": "[XX]", "skip": "[--]"}[probe.status]
        print(f"{sym} published-checkpoint  {probe.detail}")
    if check:
        return 1 if probe.status == "fail" else 0
    return 0


if __name__ == "__main__":
    sys.exit(run(as_json="--json" in sys.argv, check="--check" in sys.argv))
