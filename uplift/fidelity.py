"""
SYNAPSE Decision-Integrity Uplift Proof — twin-fidelity disclosure (R5).

Every uplift number reported by the harness MUST be co-located with the twin's
KL-divergence value so a reader can judge how far to trust the claim given the
twin's fidelity to reality (R5.1). This module owns that disclosure primitive.

``FidelityReport`` reads the current ``synapse_digital_twin_kl_divergence`` gauge
(``synapse_common.metrics.DIGITAL_TWIN_KL_DIVERGENCE``, C34) and compares it to the
C34 re-sync threshold (``digital_twin.config.TwinConfig.kl_divergence_threshold``,
default ``0.1``). The gauge is labelled per ``agent_name``; fidelity is bounded by
the *least* faithful agent, so the report takes the worst-case (maximum) KL value
across all reporting agents. When no agent has emitted a value yet, the divergence
is unavailable and the confidence annotation is ``unknown`` — the uplift number is
NOT presented as fidelity-validated (R5.3).

Confidence mapping (Property 20 / R5.3–R5.5):
    - value unavailable  -> ``unknown``                  (not fidelity-validated)
    - value >  threshold -> ``low_confidence_divergent`` (twin has drifted)
    - value <= threshold -> ``within_fidelity_bound``    (trustworthy within bound)
"""
from __future__ import annotations

import dataclasses
import math
from typing import Final

from digital_twin.config import TwinConfig
from synapse_common.metrics import DIGITAL_TWIN_KL_DIVERGENCE

# Confidence annotations (the only three values ``FidelityReport.confidence`` returns).
CONFIDENCE_UNKNOWN: Final = "unknown"
CONFIDENCE_LOW_DIVERGENT: Final = "low_confidence_divergent"
CONFIDENCE_WITHIN_BOUND: Final = "within_fidelity_bound"

# The fixed statement co-located with every uplift number (R5.2). Kept here so the
# result-assembly layer (task 10.1) and this module share a single source of truth.
FIDELITY_BOUND_STATEMENT: Final = (
    "The validity of this uplift number is bounded by twin fidelity."
)


def _read_current_kl_divergence(gauge=DIGITAL_TWIN_KL_DIVERGENCE) -> float | None:
    """Return the worst-case (maximum) current KL value across all reporting agents.

    The C34 gauge is labelled by ``agent_name``; before any agent has reported, the
    gauge has no child samples and the value is unavailable. Fidelity is bounded by
    the least faithful agent, so we surface the maximum observed divergence. Returns
    ``None`` when no finite value is available (R5.3 "unknown").
    """
    values: list[float] = []
    for metric in gauge.collect():
        for sample in metric.samples:
            value = sample.value
            if value is None:
                continue
            value = float(value)
            if math.isnan(value):
                continue
            values.append(value)
    if not values:
        return None
    return max(values)


@dataclasses.dataclass(frozen=True)
class FidelityReport:
    """Twin-fidelity disclosure accompanying an uplift number (R5).

    ``kl_divergence`` is the current C34 KL value (``None`` when unavailable, R5.3);
    ``threshold`` is the C34 re-sync threshold it is compared against.
    """

    kl_divergence: float | None
    threshold: float

    @property
    def confidence(self) -> str:
        """The three-way confidence annotation (R5.3–R5.5, Property 20).

        ``unknown`` when the KL value is unavailable (not fidelity-validated, R5.3);
        ``low_confidence_divergent`` when strictly above the threshold (R5.4);
        ``within_fidelity_bound`` when at or below the threshold (R5.5).
        """
        if self.kl_divergence is None:
            return CONFIDENCE_UNKNOWN
        if self.kl_divergence > self.threshold:
            return CONFIDENCE_LOW_DIVERGENT
        return CONFIDENCE_WITHIN_BOUND

    @property
    def is_fidelity_validated(self) -> bool:
        """True only when a KL value is available (R5.3: no value ⇒ not validated)."""
        return self.kl_divergence is not None

    @property
    def fidelity_bound_statement(self) -> str:
        """The fixed statement co-located with the uplift number (R5.2)."""
        return FIDELITY_BOUND_STATEMENT

    @classmethod
    def from_metric(
        cls,
        *,
        config: TwinConfig | None = None,
        gauge=DIGITAL_TWIN_KL_DIVERGENCE,
    ) -> "FidelityReport":
        """Build a report from the live C34 gauge and the twin's configured threshold.

        Reads the current ``synapse_digital_twin_kl_divergence`` value (R5.1) and
        compares it to ``TwinConfig.kl_divergence_threshold`` (default ``0.1``).
        """
        cfg = config or TwinConfig()
        return cls(
            kl_divergence=_read_current_kl_divergence(gauge),
            threshold=cfg.kl_divergence_threshold,
        )
