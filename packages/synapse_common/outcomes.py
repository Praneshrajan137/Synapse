"""Honest decision-outcome contract (Sprint 19, ADR-047).

The pure, deterministic core of the outcome loop — no I/O, no clock, no DB.
The scorer (``data_fabric/jobs/outcome_score.py``) uses these to derive an
outcome from realized signals; the calibration endpoint
(``api/routers/system.py::/calibration``) uses ``reliability_bins`` +
``brier_score`` to score confidence against those outcomes.

The honesty rule (I-7 applied to outcomes): an outcome is ``unknown`` until a
realized signal genuinely exists. ``confirmed``/``diverged`` are NEVER produced
without evidence. ``scripts/audit/outcome_truth.py`` is the AST gate that keeps
it that way; this module is its primary target.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

OUTCOME_STATUSES: tuple[str, ...] = ("confirmed", "diverged", "unknown")

# Tokens a realized confirmation may carry. Divergence dominates: a single
# failure means the decision did not play out as planned.
_CONFIRM_TOKENS: frozenset[str] = frozenset(
    {"confirmed", "confirm", "success", "succeeded", "ok", "executed", "completed", "applied"}
)
_DIVERGE_TOKENS: frozenset[str] = frozenset(
    {"diverged", "divergence", "failed", "failure", "rejected", "error", "aborted", "mismatch"}
)


def _token_of(item: Any) -> str | None:
    """Extract a lowercase status token from a confirmation item, or None."""
    if isinstance(item, str):
        return item.strip().lower() or None
    if isinstance(item, Mapping):
        for key in ("status", "result", "state", "outcome"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
    return None


def classify_execution_confirmations(confirmations: Any) -> str | None:
    """Derive a verdict from a decision's execution confirmations.

    Returns ``"diverged"`` (any failure token), ``"confirmed"`` (any success
    token and no failure), or ``None`` when there is no interpretable signal
    (empty, missing, or uninterpretable) — None means "no verdict", which the
    caller renders as ``unknown``.
    """
    if not isinstance(confirmations, Sequence) or isinstance(confirmations, (str, bytes)):
        return None
    if len(confirmations) == 0:
        return None
    saw_confirm = False
    for item in confirmations:
        token = _token_of(item)
        if token is None:
            continue
        if token in _DIVERGE_TOKENS:
            return "diverged"
        if token in _CONFIRM_TOKENS:
            saw_confirm = True
    return "confirmed" if saw_confirm else None


def score_decision(
    *,
    confidence: float,
    execution_confirmations: Any,
    twin_divergence: float | None = None,
    twin_threshold: float = 0.1,
    horizon_s: int,
    scored_at: str,
) -> dict[str, Any]:
    """Score one decision against the realized signals that exist today.

    Source precedence: execution confirmations first (the Phase-4 EXECUTING
    record), then twin divergence (I-12 KL signal as a realized-vs-model
    proxy). When neither yields a verdict the status is ``unknown`` — never a
    fabricated ``confirmed``. ``confidence`` is carried into ``realized`` for
    transparency but does NOT influence the status (that would be circular).
    """
    verdict = classify_execution_confirmations(execution_confirmations)
    source = "execution_confirmations" if verdict is not None else None

    if verdict is None and twin_divergence is not None:
        verdict = "diverged" if twin_divergence > twin_threshold else "confirmed"
        source = "twin_divergence"

    status = verdict if verdict is not None else "unknown"
    source = source or "none"

    error: float | None = None
    if status == "diverged" and twin_divergence is not None:
        error = float(twin_divergence)

    n_confirmations = (
        len(execution_confirmations)
        if isinstance(execution_confirmations, Sequence)
        and not isinstance(execution_confirmations, (str, bytes))
        else 0
    )
    realized = {
        "confidence": float(confidence),
        "n_execution_confirmations": n_confirmations,
        "twin_divergence": twin_divergence,
    }
    return {
        "status": status,
        "source": source,
        "realized": realized,
        "error": error,
        "horizon_s": int(horizon_s),
        "scored_at": scored_at,
    }


def outcome_correct(status: str) -> bool | None:
    """Map an outcome status to a calibration target.

    ``confirmed`` → True (correct), ``diverged`` → False (incorrect),
    anything else (``unknown``) → None (excluded from the scored set — a
    decision we cannot grade must not be counted as right OR wrong).
    """
    if status == "confirmed":
        return True
    if status == "diverged":
        return False
    return None


def reliability_bins(
    samples: Iterable[tuple[float, bool | None]],
    n_bins: int = 10,
) -> list[dict[str, Any]]:
    """Bin (confidence, correct) pairs into a reliability curve.

    ``correct=None`` samples are excluded from the scored aggregates but the
    function never invents data: an empty bin reports ``n=0`` and null means.
    """
    if n_bins < 1:
        raise ValueError("n_bins must be >= 1")
    width = 1.0 / n_bins
    confidences: list[list[float]] = [[] for _ in range(n_bins)]
    corrects: list[list[bool]] = [[] for _ in range(n_bins)]
    for confidence, correct in samples:
        idx = min(n_bins - 1, max(0, int(confidence * n_bins)))
        if correct is None:
            continue
        confidences[idx].append(float(confidence))
        corrects[idx].append(bool(correct))

    bins: list[dict[str, Any]] = []
    for i in range(n_bins):
        scored = corrects[i]
        n = len(scored)
        bins.append(
            {
                "lo": round(i * width, 4),
                "hi": round((i + 1) * width, 4),
                "n": n,
                "mean_confidence": (sum(confidences[i]) / n) if n else None,
                "observed_rate": (sum(1 for c in scored if c) / n) if n else None,
            }
        )
    return bins


def brier_score(samples: Iterable[tuple[float, bool | None]]) -> float | None:
    """Mean squared error of confidence vs. realized correctness.

    Computed over the SCORED set only (``correct`` is not None). Returns None
    when nothing is scored — a null Brier is honest; a 0.0 would imply perfect
    calibration on zero evidence.
    """
    total = 0.0
    n = 0
    for confidence, correct in samples:
        if correct is None:
            continue
        target = 1.0 if correct else 0.0
        total += (float(confidence) - target) ** 2
        n += 1
    return (total / n) if n else None
