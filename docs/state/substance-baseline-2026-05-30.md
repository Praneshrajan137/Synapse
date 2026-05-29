# SYNAPSE — Substance Baseline (Plan v2, Phase 0)

> **Dated:** 2026-05-30
> **HEAD:** `be3edd1` (Sprint 13 — Coverage & Mutation Truth)
> **Method:** `python -m scripts.audit.substance_truth` (AST audit of every
> `agents/*/inference/pipeline.py`). Numbers below are *measured*, not asserted.

This is the honest starting line for the Substance Mandate. Sprints 11-13 built
a fully honest *enforcement* boundary; this baseline measures the one thing that
boundary never checked — whether the outputs it validates are **real**.

## Measured substance gap (today)

| Agent | Violations | Kinds |
| --- | --- | --- |
| demand_prophet | 5 | ignored_dependency ×4, hardcoded_confidence ×1 |
| pricing_oracle | 3 | ignored_dependency ×1, random_model_input ×1, hardcoded_confidence ×1 |
| supplier_trust | 1 | hardcoded_confidence ×1 |
| sustainability_agent | 1 | hardcoded_confidence ×1 |
| disruption_shield | 0 | — clean |
| freshness_guardian | 0 | — clean (confidence is fitted-conditional, not constant) |
| inventory_sentinel | 0 | — clean (`confidence=round(conf, 3)`) |
| routing_navigator | 0 | — clean |
| **Total** | **10** | across 8 pipelines; **4/8 agents clean** |

**The anti-patterns (all confirmed by `file:line`):**
- `ignored_dependency` — `if self._dep is None:` guard then returns the *same*
  fallback when the dependency IS present (`demand_prophet/inference/pipeline.py:118,123,121,131`;
  `pricing_oracle/inference/pipeline.py:175`). The real model / Feast / Neo4j are
  ignored even when injected.
- `hardcoded_confidence` — `confidence=0.85` (and `0.1`) constants. A constant
  confidence above the HITL threshold makes **I-5 (confidence-gated escalation)
  impossible to fire** — the safety mechanism is dead by construction.
- `random_model_input` — `_build_observations()` feeds the model `default_rng()`
  noise rather than real features (`pricing_oracle/inference/pipeline.py:235`).

A separate, deeper finding (not yet machine-checked, tracked for Phase 2): even
`demand_prophet/training/train.py:116-123` — the supposed gold-standard training
loop — builds an optimizer and scheduler, discards them, and returns
`{"status": "pipeline_validated"}` **without a single gradient step**. No agent
has a genuine training loop; there is no trained checkpoint anywhere in the repo.

## Ratchet wired (regression-proof from day one)

- `scripts/audit/substance_truth.py` — `--json` / `--check` (exit 1 on any violation).
- `verify_claims.py` **C33** — ratchet idiom: PASS while violations ≤ baseline (10),
  FAIL on any increase. Phase 2 lowers the baseline one agent per PR toward **0**;
  Phase 4 wires `substance_truth.py --check` as a hard blocking CI gate at zero.
- `make verify-claims` after wiring: **PASS=26 FAIL=0 PARTIAL=1 (C33)** — green and honest.

## Per-package coverage floors — pending first CI measurement

Per Plan principle 2 ("measure before changing"), the 9 placeholder `0.0` floors
in `infrastructure/quality/coverage-floors.yaml` (orchestrator + 8 agents) are
**not** filled with guessed numbers here. They require a single CI run on a Linux
runner with the full dependency stack (`torch`, `lifelines`, `pymoo`,
`torch_geometric`, `ortools`) — see E-S13-01. That measurement lands in Phase 4
(`coverage_ratchet.py --apply` against the CI `coverage.xml`), and floors are then
seeded at `measured − 0.5`. Recording fabricated floors now would itself be the
kind of theatre this plan exists to eliminate.

## Update — Phase 2 closure (same session)

All 8 pipelines were rewired through the ADR-041 anti-corruption layer and the
ADR-040 provenance/derived-confidence contract. `substance_truth.py --check` now
reports **0 violations, 8/8 agents clean** (exit 0); `verify_claims.py` **C33**
ratcheted baseline 10 → 0 and is **PASS**. Confidence is derived per agent
(conformal interval width / waste entropy / posterior spread / elasticity
strength) — the constant `0.85` is gone. demand_prophet's serving path is
verified end-to-end (real + degraded) by `agents/demand_prophet/tests/test_pipeline_contract.py`
(5 tests, torch-free). Genuine multi-epoch model training (torch/ortools stack)
remains the documented operator/Colab step (Plan principle 5), CI-smoke-trained.

