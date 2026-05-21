# ADR-032: Replay harness — bundle-level determinism for orchestrator decisions

## Status
Accepted (Sprint 7)

## Context
"Why did the orchestrator pick X instead of Y?" used to require log
spelunking and best-guess reconstruction. The system pinned deterministic
JSON (I-13) but not the *full* set of inputs needed to bit-exactly
reproduce a decision: RNG seeds, model checkpoints, Feast online snapshot,
software versions, and OTel trace ids were scattered or implicit.

Mutation testing (Layer 7) needs an oracle that detects when a mutated
operator changes the decision; replay byte-equality is that oracle.

## Decision
Introduce **`orchestrator/replay/harness.py`**:

- `ReplayBundle` — frozen dataclass capturing `inputs`, `seeds`,
  `weights`, `feature_snapshot`, `model_checkpoints`, `software_version`,
  `otel_trace_id`. Serialized as deterministic JSON; bundle hash is a
  SHA-256 over everything except itself.
- `capture_bundle(...)` — called immediately after a decision is produced
  but before side-effects fire.
- `save_bundle` / `load_bundle` — disk persistence with hash verification.
- `replay(bundle)` — pins every RNG (`python_random`, `numpy`, `torch`),
  enables `torch.use_deterministic_algorithms(True, warn_only=True)`,
  and re-runs `run_pareto_arbitration` against the bundle inputs.

`tests/verify/test_replay.py` asserts two replays of the same bundle
produce byte-identical canonical JSON. CI fails on any drift.

## Consequences
- Replay is the universal Layer-6 oracle for the orchestrator.
- Mutation kill-rate measurable as "did the replay output diff?".
- Bundles are inspectable artifacts for HITL operators.
- One-time cost: `torch.use_deterministic_algorithms(True)` slows some
  ops; we accept the slowdown for orchestrator-tier reproducibility.

## Alternatives Rejected
- **Deterministic-by-construction (no RNG)** — NSGA-II is stochastic; we
  pin the seed.
- **Logging + reconstruction** — logs are sampled; bundles are complete.
- **Container-image pinning only** — captures `software_version` but not
  RNG state or feature snapshots.
