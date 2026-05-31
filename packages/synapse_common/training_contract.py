"""SYNAPSE training-truth contract (ADR-042).

The honesty contract (ADR-040/041) made *inference* honest: a served output
records whether it came from a real model or a degraded fallback. This module
is its mirror for *training* - the published language for the single claim that
Sprints 11-13 never checked and the Substance Mandate only began to close:

    "a training run actually happened - the loop took real gradient steps and
     the model measurably learned."

Before this contract, ``demand_prophet/training/train.py`` constructed an
optimizer + scheduler, discarded both, took **zero** gradient steps, and
returned ``{"status": "pipeline_validated"}``. That string was the lie. A
:class:`TrainResult` makes the truth a typed, testable value object that the
``training_truth.py`` / ``checkpoint_truth.py`` gates and the per-agent
``test_train_smoke.py`` tests both consume.

Design notes:

  * **torch-optional.** Non-torch agents (supplier_trust's Bayesian SVI,
    freshness_guardian's Weibull AFT) save numpy/pickle state via the same
    :func:`save_checkpoint` / :func:`load_checkpoint` pair, so the contract is
    one ramp for all eight agents.
  * **deterministic.** The checkpoint sha is a sha256 over the *canonical*
    serialized bytes; two seeded smoke-trains of the same code must produce the
    same sha (E-S9-03 determinism discipline, extended to weights).
  * **frozen value object** (DDD), additive - it never reaches the KV-cached
    prompt body (I-13) nor an agent's domain output schema (I-3).
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# A smoke-train must improve the loss by at least this fraction to count as
# "learned". 5% over a 2-epoch CPU window on a tiny seeded subset is a low but
# non-trivial bar: a no-op loop (the old ``pipeline_validated`` shape) yields
# exactly 0% and fails; a loop that takes real gradient steps clears it.
MIN_IMPROVEMENT = 0.05

# Sentinel for "this agent's model is analytical / exact and has no gradient
# loop" (newsvendor, CVRPTW). Such agents satisfy the contract via calibration
# or optimality-gap truth, NOT via gradient_steps - forcing a fake loop onto a
# closed-form-optimal model would itself be the anti-pattern this contract
# exists to prevent (see ADR-042 §"agents without a gradient loop").
ANALYTICAL = "analytical"


class TrainingContractViolation(AssertionError):
    """Raised when a TrainResult fails to prove that learning occurred."""


@dataclass(frozen=True)
class TrainResult:
    """Immutable record that a training run took real gradient steps (ADR-042).

    ``kind`` is ``"gradient"`` for agents with a real optimizer loop and
    :data:`ANALYTICAL` for closed-form / exact-solver agents (which prove
    substance through :mod:`calibration_truth` instead). The gates branch on it.
    """

    agent: str
    gradient_steps: int
    start_loss: float
    end_loss: float
    epochs: int
    seed: int
    smoke: bool
    kind: str = "gradient"
    checkpoint_path: Path | None = None
    checkpoint_sha: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def improvement(self) -> float:
        """Relative loss reduction in ``[−inf, 1]``; higher is better learning."""
        if self.start_loss == 0.0:
            return 0.0
        return (self.start_loss - self.end_loss) / abs(self.start_loss)

    @property
    def learned(self) -> bool:
        if self.kind == ANALYTICAL:
            return True
        return self.gradient_steps > 0 and self.improvement >= MIN_IMPROVEMENT

    def assert_learned(self, min_improvement: float = MIN_IMPROVEMENT) -> None:
        """Raise unless the loop took >=1 gradient step and the loss fell.

        This is the runtime half of the C37 training-truth gate. The smoke job
        calls it; a regression to a no-op loop raises here and fails CI.
        """
        if self.kind == ANALYTICAL:
            return
        if self.gradient_steps <= 0:
            raise TrainingContractViolation(
                f"{self.agent}: 0 gradient steps - the optimizer was never .step()-ed "
                f"(the 'pipeline_validated' anti-pattern, ADR-042)"
            )
        if self.improvement < min_improvement:
            raise TrainingContractViolation(
                f"{self.agent}: loss improved only {self.improvement:.3%} "
                f"(< {min_improvement:.0%}) over {self.epochs} epoch(s) - the loop runs "
                f"but the model does not learn (vacuous training)"
            )

    def assert_checkpoint(self) -> None:
        """Raise unless the checkpoint exists on disk and its sha matches.

        Runtime half of the C38 checkpoint-truth gate.
        """
        if self.checkpoint_path is None or self.checkpoint_sha is None:
            raise TrainingContractViolation(
                f"{self.agent}: no checkpoint recorded - training produced no loadable artifact"
            )
        path = Path(self.checkpoint_path)
        if not path.is_file():
            raise TrainingContractViolation(
                f"{self.agent}: checkpoint {path} does not exist on disk"
            )
        actual = _sha_of_file(path)
        if actual != self.checkpoint_sha:
            raise TrainingContractViolation(
                f"{self.agent}: checkpoint sha mismatch - recorded {self.checkpoint_sha}, "
                f"on-disk {actual} (non-deterministic serialization or corruption)"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "kind": self.kind,
            "gradient_steps": self.gradient_steps,
            "start_loss": round(self.start_loss, 6),
            "end_loss": round(self.end_loss, 6),
            "improvement": round(self.improvement, 6),
            "epochs": self.epochs,
            "seed": self.seed,
            "smoke": self.smoke,
            "learned": self.learned,
            "checkpoint_path": str(self.checkpoint_path) if self.checkpoint_path else None,
            "checkpoint_sha": self.checkpoint_sha,
            "metrics": {k: round(float(v), 6) for k, v in self.metrics.items()},
        }

    @classmethod
    def analytical(
        cls, agent: str, *, metrics: dict[str, float] | None = None, seed: int = 0
    ) -> TrainResult:
        """Construct a result for a closed-form / exact-solver agent.

        Such an agent has no gradient loop; its substance is proven by
        :mod:`calibration_truth`. ``learned`` is True by construction so the
        training-truth gate does not demand a fake loss curve from it.
        """
        return cls(
            agent=agent,
            gradient_steps=0,
            start_loss=0.0,
            end_loss=0.0,
            epochs=0,
            seed=seed,
            smoke=True,
            kind=ANALYTICAL,
            metrics=metrics or {},
        )


def learning_curve_decreased(
    losses: list[float], *, min_improvement: float = MIN_IMPROVEMENT
) -> bool:
    """True if a per-step/epoch loss sequence shows genuine learning.

    Tolerant of the noise inherent in mini-batch SGD: we do not require strict
    monotonicity (which real training rarely shows), only that the *end* of the
    curve is meaningfully below the *start*.
    """
    if len(losses) < 2 or losses[0] == 0.0:
        return False
    return (losses[0] - losses[-1]) / abs(losses[0]) >= min_improvement


# ---------------------------------------------------------------------------
# Checkpoint I/O - torch-optional, deterministic sha
# ---------------------------------------------------------------------------
def _sha_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def _sha_of_file(path: Path) -> str:
    return _sha_of_bytes(Path(path).read_bytes())


def save_checkpoint(model: Any, path: Path | str) -> str:
    """Serialize ``model`` to ``path`` deterministically; return its sha256[:16].

    Torch ``nn.Module`` -> ``torch.save(state_dict)`` (sorted keys for a stable
    byte layout). Anything else (a dataclass of numpy arrays, a fitted lifelines
    model, a dict) -> canonical JSON when JSON-able, else ``pickle``. The sha is
    computed over the *written file*, so :meth:`TrainResult.assert_checkpoint`
    verifies exactly what serving will load.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    state = getattr(model, "state_dict", None)
    if callable(state):  # torch nn.Module (duck-typed; no hard torch import)
        try:
            import torch  # noqa: PLC0415 - optional dependency, imported lazily

            sd = model.state_dict()
            ordered = {k: sd[k] for k in sorted(sd)}
            buf = io.BytesIO()
            torch.save(ordered, buf)
            path.write_bytes(buf.getvalue())
            sha = _sha_of_file(path)
            logger.info("checkpoint_saved", kind="torch", path=str(path), sha=sha)
            return sha
        except ImportError:  # pragma: no cover - torch absent on dev box
            logger.warning("torch_absent_on_save", fallback="json/pickle")

    payload = _to_jsonable(model)
    if payload is not None:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        path.write_bytes(data)
        sha = _sha_of_file(path)
        logger.info("checkpoint_saved", kind="json", path=str(path), sha=sha)
        return sha

    import pickle  # noqa: PLC0415

    path.write_bytes(pickle.dumps(model, protocol=5))
    sha = _sha_of_file(path)
    logger.info("checkpoint_saved", kind="pickle", path=str(path), sha=sha)
    return sha


def load_checkpoint(path: Path | str) -> Any:
    """Load a checkpoint written by :func:`save_checkpoint`.

    Tries torch, then JSON, then pickle - the inverse of the save dispatch.
    Never raises on a missing file beyond the standard ``FileNotFoundError``;
    callers that want graceful degradation should guard with ``Path.is_file()``.
    """
    path = Path(path)
    data = path.read_bytes()
    try:
        import torch  # noqa: PLC0415

        return torch.load(io.BytesIO(data), map_location="cpu", weights_only=True)
    except (ImportError, Exception):  # noqa: BLE001 - fall through to json/pickle
        pass
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        import pickle  # noqa: PLC0415

        return pickle.loads(data)  # noqa: S301 - our own artifact, not untrusted input


def _to_jsonable(obj: Any) -> Any | None:
    """Best-effort conversion of a simple model to a JSON-able structure."""
    import numpy as np  # noqa: PLC0415 - numpy is a core dep, present everywhere

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            jv = _to_jsonable(v)
            if jv is None and v is not None:
                return None
            out[str(k)] = jv
        return out
    if isinstance(obj, np.ndarray):
        return {"__ndarray__": obj.tolist(), "dtype": str(obj.dtype)}
    if isinstance(obj, (list, tuple)):
        converted = [_to_jsonable(v) for v in obj]
        return converted if all(c is not None for c in converted) else None
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return None


__all__ = [
    "ANALYTICAL",
    "MIN_IMPROVEMENT",
    "TrainResult",
    "TrainingContractViolation",
    "learning_curve_decreased",
    "load_checkpoint",
    "save_checkpoint",
]
