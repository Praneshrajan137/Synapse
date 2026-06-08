"""Torch-free lead-time posterior container (ADR-043 decoupling).

``LeadTimePosterior`` is a plain summary value object with no torch/pyro
dependency. It lived in ``bayesian_lead.py`` (which imports pyro+torch at module
load), forcing every importer of the *summary* to pull in the full ML stack. The
serving path (a closed-form conjugate update, ``inference/serving_model.py``) and
the inference pipeline only need the summary, so it lives here and ``bayesian_lead``
re-exports it for backward compatibility.
"""

from __future__ import annotations


class LeadTimePosterior:
    """Immutable container for a lead-time posterior summary (days)."""

    __slots__ = ("mean_days", "std_days", "p10_days", "p90_days")

    def __init__(self, mean_days: float, std_days: float, p10_days: float, p90_days: float) -> None:
        self.mean_days = mean_days
        self.std_days = std_days
        self.p10_days = p10_days
        self.p90_days = p90_days

    def to_dict(self) -> dict[str, float]:
        return {
            "mean_days": self.mean_days,
            "std_days": self.std_days,
            "p10_days": self.p10_days,
            "p90_days": self.p90_days,
        }


__all__ = ["LeadTimePosterior"]
