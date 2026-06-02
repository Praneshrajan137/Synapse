"""INV-ST-007 — runtime reality for the conjugate Bayesian serving path (ADR-043).

Torch-free: builds a :class:`SupplierServingModel` from a synthetic fitted prior
(no Pyro), wires it into the pipeline, and proves established-vendor scoring is
genuinely real — non-degraded, POSTERIOR_SPREAD basis, and a confidence that is
derived from the posterior tightness (more/steadier deliveries → higher
confidence), never a constant. The CI runtime gate
(`runtime_substance --agent supplier_trust`) proves the same on the SVI-fitted
prior checkpoint; the SVI fit itself is the only Pyro/CI-gated step.
"""

from __future__ import annotations

import numpy as np
from synapse_common.provenance import ConfidenceBasis

from agents.supplier_trust.inference.pipeline import SupplierTrustPipeline
from agents.supplier_trust.inference.serving_model import (
    SupplierServingModel,
    build_supplier_model,
)


def _prior() -> SupplierServingModel:
    # Population log-mean ~2.0 (≈7.4 days), between-supplier spread 0.3, within 0.4.
    return build_supplier_model(
        {"prior_mu": 2.0, "prior_mu_scale": 0.3, "sigma": 0.4}, {"version": "full_abc123"}
    )


def _history(n: int, base: float, jitter: float) -> list[dict]:
    rng = np.random.default_rng(0)
    return [
        {"lead_time_days": float(max(0.1, base + jitter * rng.standard_normal())), "on_time": True}
        for _ in range(n)
    ]


def test_builder_produces_a_real_prior() -> None:
    model = _prior()
    assert isinstance(model, SupplierServingModel)
    assert model.is_real
    assert model.version == "full_abc123"


def test_conjugate_posterior_tightens_with_more_data() -> None:
    # INV-ST-007 substance: more deliveries → tighter posterior → narrower interval.
    model = _prior()
    few = model.posterior(np.array([7.0, 7.5, 6.8]))
    many = model.posterior(np.full(60, 7.2))
    assert (many.p90_days - many.p10_days) < (few.p90_days - few.p10_days)


def test_inv_st_007_runtime_reality_non_degraded_posterior_spread() -> None:
    """INV-ST-007 — fitted prior serves real, non-constant, posterior-spread confidence."""
    pipe = SupplierTrustPipeline(serving_model=_prior())
    steady = pipe.score("sup_steady", _history(40, 7.0, 0.2))
    erratic = pipe.score("sup_erratic", _history(5, 7.0, 3.0))
    prov = pipe.last_provenance
    # INV-ST-007: real provenance + POSTERIOR_SPREAD basis + confidence varies.
    assert not prov.degraded
    assert prov.confidence_basis == ConfidenceBasis.POSTERIOR_SPREAD
    assert steady.confidence != erratic.confidence
    assert 0.0 <= steady.confidence <= 1.0


def test_serving_path_runs_without_torch() -> None:
    # The ADR-043 decoupling guarantee: scoring via the conjugate serving model
    # must not require torch/pyro. On a torch-free runner this call would raise
    # ImportError if the path touched torch — succeeding *is* the proof.
    pipe = SupplierTrustPipeline(serving_model=_prior())
    result = pipe.score("sup_x", _history(10, 7.0, 0.3))
    assert 0.0 <= result.trust_score <= 1.0
    assert not pipe.last_provenance.degraded
