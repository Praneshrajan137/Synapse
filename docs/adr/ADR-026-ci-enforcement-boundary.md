# ADR-026: CI Is the Enforcement Boundary

## Status
Accepted

## Context
SYNAPSE declares 14 architectural invariants, a 7-layer testing topology
(ADR-015), an 80% coverage floor, and a merge rule that "a PR breaking any
invariant is auto-rejected". A ground-truth audit (`docs/quality_gates/
baseline.md`) found these were largely *declared, not enforced*:

- `ci.yml` ran unit tests **only** under `packages/` (`cd packages && pytest
  tests/`). The 8 agents (~13.8K LOC), orchestrator (~3.4K LOC), and digital
  twin (~1.7K LOC) had real test files that **never ran on a PR**.
- CI installed only `packages/requirements.txt` — it was not even *provisioned*
  to import agent/orchestrator code (no torch, fastapi, mlflow, …).
- The `--cov-fail-under=80` gate measured one package (`synapse_common`); real
  backend-wide coverage was 58.9%.
- The agent `mypy` step aborted on a module-resolution error and was
  `continue-on-error: true` — it emitted no signal at all.
- 8 tests were failing on `main` and CI never saw them; the orchestrator `mypy`
  gate was itself red on `main`.

A guarantee that is not mechanically checked on every PR is not a guarantee.

## Decision
**The `ci.yml` `quality-gates` job is the single enforcement boundary, and it
exercises the entire backend.**

- CI installs the full backend stack (`packages` + `agents/requirements-
  sprint2/3` + `orchestrator/requirements` + editable `synapse_common`).
- The unit-test step runs the full surface — `packages/ agents/ orchestrator/
  digital_twin/ data_fabric/ ml_pipelines/ api/ tests/` — which exercises the
  SDD, Contract, Metamorphic, DbC, and Oracle layers in one pass.
- Coverage is a **ratchet**: `--cov-fail-under` is seeded from the measured
  baseline (58%) and may only ever rise. It is deliberately *not* set to an
  aspirational 80%, which would block the very change that makes CI honest.
- `ruff check` and `ruff format --check` cover all 7 backend packages.
- `mypy --strict` is blocking for `packages/` and `orchestrator/`; the `agents/`
  type-check is honest-but-informational (`continue-on-error`) with a ratchet
  target of 0 errors, after which it flips to blocking.
- `scripts/check_spec_coverage.py` runs as a blocking step (SDD layer 1).

## Consequences
- The CLAUDE.md merge rule becomes literally true: a PR that breaks an
  invariant test, drops coverage, or fails lint/type-check is rejected.
- CI is slower — it installs torch/ray/mlflow and runs ~885 tests (~10–15 min)
  instead of 88. This is the cost of a real gate; `cache: pip` amortizes it.
- Coverage and the agent-`mypy` count become tracked, ratcheting metrics.
- The Fuzz layer remains in `integration.yml` (needs live services); Mutation
  remains in `mutation.yml`. Promoting Mutation to a per-PR check is future
  work.

## Alternatives Rejected
- **Keep the packages-only gate, trust the other workflows.** Rejected:
  `integration.yml` jobs are soft (contracts treat "no tests" as pass),
  `mutation.yml` is schedule-only, and `security.yml` runs every scanner with
  `|| true`. None of them block on the unit surface.
- **Set the coverage gate at 80% immediately.** Rejected: the backend is at
  58.9%; an 80% gate would make the honest-CI PR un-mergeable. A ratchet
  reaches the same place without a flag day.
- **Per-agent CI jobs.** Rejected for now: simpler to run one provisioned job;
  revisit if wall-clock time becomes a problem.
