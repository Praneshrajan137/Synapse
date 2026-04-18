# ADR-010: Causal Inference for Pricing — Double ML via EconML

## Status
Accepted

## Context
Pricing Oracle must learn the *causal* effect of a price change on demand, not the correlation. Naive correlation conflates seasonality, promotions, and confounders with the true price elasticity — leading to systematically wrong pricing decisions. Pure A/B testing is too slow (weeks per experiment) and risks revenue loss during exploration. We need a causal estimator that works on observational data with high-dimensional confounders.

## Decision
Use **Double Machine Learning** via Microsoft EconML (MIT) for pre-training elasticity estimates per category and per SKU. The Pricing Oracle's `models/causal.py` runs DoubleMLLinearRegressor with XGBoost first-stage models on historical pricing/demand data. Estimated elasticities feed the MADDPG actor as a prior — the actor learns deviations from the causal baseline, dramatically reducing exploration variance vs. cold-start RL. After deployment, the orchestrator runs structured A/B tests via `ml_pipelines/ab_test/framework.py` to validate that DML elasticity estimates remain accurate (drift detection).

## Consequences
- Pricing decisions have a causal foundation, not a correlational one.
- MADDPG converges 3-5× faster because elasticity priors anchor the policy.
- Adds a pre-training step before MADDPG training; documented in Sprint 3 deliverables.
- EconML requires scikit-learn-compatible nuisance models — natural fit with XGBoost/LightGBM.
- Cross-elasticity for top-5 substitutes computed offline and cached in Feast (`elasticity_features.py`).

## Alternatives Rejected
- **Naive correlation**: rejected — biased; would violate Competition Act compliance.
- **A/B testing only**: rejected — too slow; no signal during exploration.
- **Bayesian causal models (DoWhy)**: rejected — heavier dependency tree, slower inference, no significant accuracy gain at our data volume.
