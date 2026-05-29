"""SYNAPSE output provenance & honest-degradation contract (ADR-040).

Every served agent output carries a :class:`Provenance` value object recording
*how* it was produced:

  * ``model_version`` — the registry version/sha of the model that produced it
    (``"degraded"`` when no real model was loaded). Reaches the audit trail (I-4).
  * ``feature_source`` — ``feast`` when features came from the online store,
    ``fallback`` when they were synthesised because Feast was unreachable.
  * ``degraded`` — ``True`` iff *any* dependency fell back. Downstream consensus
    MUST down-weight a degraded proposal; a silent fallback corrupts the Pareto
    arbitration. This is the field that makes I-7 graceful degradation *honest*.
  * ``confidence_basis`` — how the accompanying ``confidence`` was derived
    (conformal interval width, ensemble variance, posterior spread, …) — NEVER
    ``constant``. A constant confidence above the HITL threshold makes I-5
    (confidence-gated escalation) impossible to fire; recording the basis makes
    that failure mode auditable.

Provenance is a frozen value object (DDD). It is additive and optional on the
domain output models, so it does not break I-3 (existing consumers ignore it)
and stays out of the KV-cached prompt body (I-13).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from synapse_common.models import SynapseBaseModel

DEGRADED_VERSION = "degraded"


class FeatureSource(StrEnum):
    """Where the features feeding a prediction came from."""

    FEAST = "feast"
    FALLBACK = "fallback"
    DIRECT = "direct"  # supplied in-request (agent does not read the online store)


class ConfidenceBasis(StrEnum):
    """How a served ``confidence`` value was derived. ``CONSTANT`` is a smell —
    it means confidence is not tied to model uncertainty and I-5 cannot fire."""

    CONFORMAL_INTERVAL = "conformal_interval"
    ENSEMBLE_VARIANCE = "ensemble_variance"
    POSTERIOR_SPREAD = "posterior_spread"
    DECODER_ENTROPY = "decoder_entropy"
    CRITIC_VALUE_SPREAD = "critic_value_spread"
    RESIDUAL_VARIANCE = "residual_variance"
    SURVIVAL_CI_WIDTH = "survival_ci_width"
    FALLBACK_FLOOR = "fallback_floor"  # degraded path: confidence is the I-7 floor
    CONSTANT = "constant"  # NEVER acceptable on a real path — flagged by substance_truth


class Provenance(SynapseBaseModel):
    """Immutable record of how an agent output was produced (ADR-040)."""

    model_version: str = Field(
        default=DEGRADED_VERSION,
        description="Registry version/sha, or 'degraded' when no real model was loaded.",
    )
    feature_source: FeatureSource = FeatureSource.FALLBACK
    degraded: bool = True
    confidence_basis: ConfidenceBasis = ConfidenceBasis.FALLBACK_FLOOR

    @classmethod
    def real(
        cls,
        *,
        model_version: str,
        confidence_basis: ConfidenceBasis,
        feature_source: FeatureSource = FeatureSource.FEAST,
    ) -> Provenance:
        """Construct provenance for a genuine, non-degraded prediction."""
        if model_version == DEGRADED_VERSION:
            raise ValueError("real() requires a concrete model_version, not 'degraded'")
        if confidence_basis in (ConfidenceBasis.CONSTANT, ConfidenceBasis.FALLBACK_FLOOR):
            raise ValueError(
                "real() requires an uncertainty-derived confidence_basis "
                "(not CONSTANT/FALLBACK_FLOOR)"
            )
        return cls(
            model_version=model_version,
            feature_source=feature_source,
            degraded=False,
            confidence_basis=confidence_basis,
        )

    @classmethod
    def degraded_fallback(
        cls,
        *,
        feature_source: FeatureSource = FeatureSource.FALLBACK,
        model_version: str = DEGRADED_VERSION,
    ) -> Provenance:
        """Construct provenance for a degraded (I-7 fallback) prediction."""
        return cls(
            model_version=model_version,
            feature_source=feature_source,
            degraded=True,
            confidence_basis=ConfidenceBasis.FALLBACK_FLOOR,
        )

    def trace_line(self) -> str:
        """Human-readable provenance line for ``justification_trace`` (no schema churn)."""
        return (
            f"provenance: model_version={self.model_version} "
            f"feature_source={self.feature_source.value} "
            f"degraded={str(self.degraded).lower()} "
            f"confidence_basis={self.confidence_basis.value}"
        )


__all__ = [
    "DEGRADED_VERSION",
    "ConfidenceBasis",
    "FeatureSource",
    "Provenance",
]
