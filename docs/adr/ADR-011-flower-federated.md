# ADR-011: Federated Learning Framework — Flower with FedAvg

## Status
Accepted

## Context
DPDPA 2023 requires data localization for personal/customer data within store boundaries. Centralized training of Inventory Sentinel models across 25-50 dark stores would aggregate per-store demand data — a DPDPA violation. We need cross-store learning without raw data leaving any store. Privacy-preserving federated learning frameworks vary widely in maturity and language support.

## Decision
Use **Flower** (Apache 2.0) for cross-store federated training of Inventory Sentinel L2 (Tactical, per-store). Each store runs a Flower client; a single Flower server performs FedAvg aggregation. Configuration: train on 50% of stores per round, evaluate on 25%, minimum 3 stores to participate, minimum 5 stores online. Only gradient updates leave the store boundary — raw demand data never does. Audit log (I-4) records every aggregation round.

## Consequences
- DPDPA-compliant by construction — `tests/compliance/test_dpdpa.py` asserts no raw demand data crosses the federated boundary.
- Flower works with PyTorch and RLlib natively — no custom serialization required.
- Aggregation rounds add ~10 minutes vs centralized training; acceptable for daily/weekly retraining cadences.
- Failed/dropped clients handled by FedAvg's partial-aggregation semantics.
- Adds a Flower server container to the production deployment.

## Alternatives Rejected
- **PySyft**: rejected — heavier complexity; weaker RL ecosystem.
- **TensorFlow Federated**: rejected — TensorFlow only; we are PyTorch-first.
- **Centralized training**: rejected — DPDPA violation.
