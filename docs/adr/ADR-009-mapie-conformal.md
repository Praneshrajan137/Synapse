# ADR-009: Uncertainty Quantification — MAPIE Conformal + Pyro Bayesian

## Status
Accepted

## Context
Inventory Sentinel sets safety stock from Demand Prophet's forecasts. A point forecast forces Sentinel to either over-stock (waste, fulfilling I-2 negatively) or under-stock (stockouts). Uncertainty estimates from Monte Carlo Dropout are uncalibrated — a 90% MCD interval might empirically cover only 60% of true outcomes. Bayesian deep learning via variational inference is computationally prohibitive on Colab's free T4. We need calibrated uncertainty intervals with finite-sample coverage guarantees.

## Decision
Use **MAPIE** (BSD-3, scikit-learn-compatible) for **demand forecasts** — provides distribution-free conformal prediction intervals with empirical coverage guarantees ≥ (1 − α). The Demand Prophet exports `lower_90`, `upper_90`, `lower_95`, `upper_95` per horizon via `agents/demand_prophet/training/conformal.py`. After Mumbai transfer learning, intervals MUST be recalibrated on Mumbai holdout (E-S6-04) — Bengaluru intervals are invalid for Mumbai distribution.

Use **Pyro** (Apache 2.0) for **supplier lead-time posteriors** in `agents/supplier_trust/models/bayesian_lead.py`. Lead-time distributions are heavy-tailed and require a full posterior, not just an interval. Pyro's NUTS sampler runs on CPU in <2 minutes per supplier.

## Consequences
- Inventory Sentinel can size safety stock as a function of conformal width — explicit metamorphic test MR-IS-001 enforces this.
- 90% conformal intervals achieve ≥85% empirical coverage in Twin Oracle tests (I-12).
- MAPIE adds ~80 ms per inference call (negligible vs Tier 2 < 500 ms SLA).
- Pyro NUTS samplers are slow on large supplier graphs; mitigated by per-supplier per-week caching in Feast.
- Conformal recalibration after every transfer learning run becomes a mandatory pipeline step.

## Alternatives Rejected
- **MC Dropout**: rejected — uncalibrated; produces overconfident intervals.
- **Ensemble variance**: rejected — requires N model copies (4× memory); still uncalibrated.
- **No uncertainty (point estimates only)**: rejected — defeats Inventory Sentinel's safety-stock optimization.
- **Variational Bayesian DL**: rejected — too compute-intensive for Colab free tier.
