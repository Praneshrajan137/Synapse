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

ADR-044: the definitions moved to ``synapse_common.models`` because
``AgentProposal`` now carries a typed ``provenance`` field and this module
imports from ``models`` — keeping the value object next to the proposal keeps
the import graph acyclic. This module remains the canonical import path for
agent pipelines and tests; everything re-exports unchanged.
"""

from __future__ import annotations

from synapse_common.models import (
    DEGRADED_VERSION,
    ConfidenceBasis,
    FeatureSource,
    Provenance,
)

__all__ = [
    "DEGRADED_VERSION",
    "ConfidenceBasis",
    "FeatureSource",
    "Provenance",
]
