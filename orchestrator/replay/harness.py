"""Orchestrator replay harness — bundle-level determinism (ADR-032).

A replay *bundle* is the complete set of inputs needed to re-run a single
orchestrator decision off-line and produce a byte-identical output. It pins:

  * `inputs`  — the raw agent proposals + user request
  * `seeds`   — every RNG seed (numpy, torch, python random, NSGA-II)
  * `weights` — the objective weight vector at decision time
  * `feature_snapshot` — Feast online-store values fetched at decision time
  * `model_checkpoints` — content-addressable hashes of every loaded model
  * `software_version` — git commit + Python + key library versions
  * `otel_trace_id` — the parent OTel trace for cross-checking

Bundles serialize as deterministic JSON (`sort_keys=True, separators=(',',':')`)
so two bundles for the same inputs are *bit-for-bit* identical. CI's
`tests/verify/test_replay.py` enforces this on a fixed-seed Tier-4 fixture.

Replay is the universal oracle (Layer 6). Mutating the consensus selector
must be detectable as a diff in the replay output (Layer 7 mutation kill).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

DEFAULT_SEED = 42
JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":"), "default": str}


@dataclass(frozen=True)
class ReplayBundle:
    """Self-contained, deterministic replay record (ADR-032)."""

    decision_id: str
    captured_at: str
    inputs: dict[str, Any]
    weights: dict[str, float]
    seeds: dict[str, int]
    feature_snapshot: dict[str, Any]
    model_checkpoints: dict[str, str]
    software_version: dict[str, str]
    otel_trace_id: str | None = None
    notes: str = ""
    bundle_hash: str = ""  # filled at save time

    def to_json(self) -> str:
        payload = bundle_to_dict(self)
        # Hash is computed *over* the bundle minus the hash field so it's stable.
        return json.dumps(payload, **JSON_KWARGS)


def bundle_to_dict(bundle: ReplayBundle) -> dict[str, Any]:
    d = asdict(bundle)
    return d


def _content_hash(payload: dict[str, Any]) -> str:
    without_hash = {k: v for k, v in payload.items() if k != "bundle_hash"}
    blob = json.dumps(without_hash, **JSON_KWARGS).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _software_version() -> dict[str, str]:
    info = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    try:
        import git  # type: ignore[import-untyped]

        repo = git.Repo(search_parent_directories=True)
        info["git_commit"] = repo.head.commit.hexsha
    except Exception:  # noqa: BLE001
        info["git_commit"] = os.environ.get("GIT_COMMIT", "unknown")
    return info


def _seeds(seed: int = DEFAULT_SEED) -> dict[str, int]:
    return {
        "python_random": seed,
        "numpy": seed,
        "torch": seed,
        "nsga2": seed,
    }


def capture_bundle(
    *,
    decision_id: str,
    inputs: dict[str, Any],
    weights: dict[str, float],
    feature_snapshot: dict[str, Any] | None = None,
    model_checkpoints: dict[str, str] | None = None,
    seed: int = DEFAULT_SEED,
    otel_trace_id: str | None = None,
    notes: str = "",
) -> ReplayBundle:
    """Construct a `ReplayBundle` from a live decision context.

    Pins every source of nondeterminism. Callers should invoke this *after*
    the decision is made but *before* any side-effects fire so the bundle
    captures the exact inputs that produced the recorded output.
    """
    bundle = ReplayBundle(
        decision_id=decision_id,
        captured_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        inputs=inputs,
        weights=dict(weights),
        seeds=_seeds(seed),
        feature_snapshot=feature_snapshot or {},
        model_checkpoints=model_checkpoints or {},
        software_version=_software_version(),
        otel_trace_id=otel_trace_id,
        notes=notes,
    )
    payload = bundle_to_dict(bundle)
    payload["bundle_hash"] = _content_hash(payload)
    return ReplayBundle(**payload)


def save_bundle(bundle: ReplayBundle, path: Path | str) -> Path:
    """Write the bundle as deterministic JSON to disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bundle_to_dict(bundle)
    blob = json.dumps(payload, **JSON_KWARGS)
    path.write_text(blob, encoding="utf-8")
    logger.info("replay_bundle_saved", path=str(path), hash=bundle.bundle_hash)
    return path


def load_bundle(path: Path | str) -> ReplayBundle:
    """Load a bundle from disk and verify its content hash."""
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = payload.get("bundle_hash", "")
    actual = _content_hash(payload)
    if expected and expected != actual:
        raise ValueError(
            f"replay bundle hash mismatch at {path}: expected={expected} actual={actual}"
        )
    # Defensive: drop unknown keys so dataclass(**) doesn't choke.
    fields = {f for f in ReplayBundle.__dataclass_fields__}
    filtered = {k: v for k, v in payload.items() if k in fields}
    return ReplayBundle(**filtered)


def _seed_runtime(seeds: dict[str, int]) -> None:
    """Pin every RNG used by the orchestrator before re-running a decision."""
    import random as _random

    _random.seed(seeds.get("python_random", DEFAULT_SEED))
    try:
        import numpy as np

        np.random.seed(seeds.get("numpy", DEFAULT_SEED))
    except ImportError:
        pass
    try:
        import torch  # type: ignore[import-untyped]

        torch.manual_seed(seeds.get("torch", DEFAULT_SEED))
        torch.use_deterministic_algorithms(True, warn_only=True)  # type: ignore[attr-defined]
    except ImportError:
        pass


def replay(bundle: ReplayBundle) -> dict[str, Any]:
    """Re-run the orchestrator decision against the bundle inputs.

    Returns the freshly-produced output as a dict. Callers compare against the
    recorded output (e.g. via `assert canonical(a) == canonical(b)`).
    """
    _seed_runtime(bundle.seeds)

    # Late import: orchestrator.consensus.pareto pulls in pymoo.
    from orchestrator.consensus.pareto import run_pareto_arbitration
    from synapse_common.models import AgentProposal

    proposals = [AgentProposal.model_validate(p) for p in bundle.inputs.get("proposals", [])]
    result = run_pareto_arbitration(proposals, bundle.weights)
    return result


def canonical(payload: Any) -> str:
    """Canonical-JSON helper: byte-equality compare of two replay outputs."""
    return json.dumps(payload, **JSON_KWARGS)


__all__ = [
    "DEFAULT_SEED",
    "ReplayBundle",
    "bundle_to_dict",
    "canonical",
    "capture_bundle",
    "load_bundle",
    "replay",
    "save_bundle",
]
