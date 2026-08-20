---
inclusion: always
---

# RULE — Local Compute Budget (I-0)

Treat this as invariant **I-0**, ranking alongside the 14 in `.cursorrules`.

Hardware: 16 GB laptop, RTX 3050, thermally throttling. The machine handles
ordinary development work fine. What throttles it is **process type and process
count**, not "running things" in general. This rule names both precisely, because
two earlier versions of it got the line in the wrong place — one banned almost all
execution (costing unverified work), the other permitted five concurrent agents
each cleared to run builds and browsers (which throttled the machine within
minutes).

## What actually throttles this laptop — the taxonomy

Ordered worst first. **Category 1 is the one that caused the 2026-08-01 incident.**

### 1. Service-type processes — NEVER run locally
Indefinite lifetime; they hold CPU and RAM until something kills them, and an
agent that starts one usually does not.
- Dev servers: `pnpm dev`, `npm start`, `vite`, `uvicorn`, `fastapi dev`
- Watchers: any `--watch`, `nodemon`, `tsc -w`, **`vitest` without `--run`**,
  `jest --watch`, `webpack --watch`
- Browsers: Playwright / Chromium sessions, the e2e matrix
- Containers and stateful services: `docker compose up`, the 21-container stack,
  Kafka, Postgres, Redis
- Anything that binds a port

### 2. Bundler and full-project compiler passes — one at a time, only when needed
Bounded, but they saturate every core while they run.
- `pnpm build`, `vite build`, Rollup, `pnpm install`, full-project `tsc`

### 3. Fan-out test execution — NEVER run locally
The cost is the fan-out, not the individual test.
- `-n auto`, `-j$(nproc)`, repo-wide bare `pytest`, `mutmut`, the full Playwright
  matrix, repo-wide `--cov`, the `nightly` Hypothesis profile (5000 examples)

### 4. Simulation and training workloads — NEVER run locally
- `uplift.cli --full` and anything at `MIN_SCENARIOS` scale (1000 replicates ×
  5 arms × 4 scenarios ≈ 20,000 closed loops over the real SimPy twin)
- Model training, GPU fine-tunes, `ProcessPoolExecutor` sweeps
- Chaos/load tests, Schemathesis fuzz

### 5. Cheap and safe — encouraged
- `get_diagnostics`, file reads, `grep`
- `ruff`, `mypy` on changed files
- `tsc --noEmit` on changed files
- **One** scoped test run: a single file, or one narrow directory
- One cheap gate script: `python -m scripts.audit.<gate> --json`

## The concurrency rule — this is the load-bearing half

**Process count multiplies everything above.** Three category-5 runs at once is a
category-2 load. Five is a throttle.

- **Parallel sub-agents for reading, writing, and analysis: unlimited.** Authoring
  does not heat the machine. Use as many as the work justifies.
- **Sub-agents that execute code: exactly ONE at a time.** Not three, not two.
  When a batch needs a test run, exactly one agent in that batch gets the process
  budget and the rest are explicitly authoring-only.
- One test process at a time within that agent, too. Serial, not concurrent.

## Required local behaviour

- **Never start a background process for verification.** If one is started for a
  reason the user asked for, stop it in the same turn.
- **Sweep before finishing.** List background processes; confirm none of yours
  survived. After a cancelled run, check for orphaned `python` / `node` /
  `chrome` processes explicitly — a cancelled agent does not clean up after
  itself.
- `-m "not slow"` unless you mean it. `slow` marks tests that drive the SimPy
  twin, the real `ConsensusProtocol`, a subprocess harness, or a browser. Run
  those deliberately, one at a time, never as a side effect of a wide run.
- Prefer `-x -q --tb=line -p no:randomly` for a fast, readable signal.
- `HYPOTHESIS_PROFILE=dev` (10) locally; `heavy` (100) only for a single scoped
  file you specifically need coverage on.
- **Be honest about what ran.** "Authored and diagnostics-clean, not executed" is
  a legitimate result. "Should pass" reported as "passes" is not (I-7).

## Escalation path for heavy work

1. `.github/workflows/ci.yml` — and `mutation.yml`, `integration.yml`,
   `uplift.yml`, `frontend.yml`, `sprint6-e2e-oracle.yml`. These exist; add a
   step rather than running locally.
2. GCP runner / VM (see `cd-gcp.yml`, ADR-036 window).
3. Only if neither works: ask, state expected duration and CPU cost, wait for an
   explicit yes.

## Authoring rule for property/fuzz tests

**Unchanged, and still binding.** Never hardcode `max_examples` in `@settings`.
Inherit from the root `conftest.py` profiles (`dev`=10, `heavy`=100,
`ci`/`default`=500, `nightly`=5000), so a local run is light and a CI run
satisfies the >=100-iteration obligation. A hardcoded `max_examples` overrides the
profile in *both* directions — that is what amplified the original incident, and
three pre-existing violations still sit in `tests/uplift/` and `tests/verify/`.

Mark any test that drives the SimPy twin, the real `ConsensusProtocol`, a
subprocess harness, or a browser with `@pytest.mark.slow`. A `slow` marker only
works if the workflow that owns the test actually selects on it — check the job,
not just the marker.

## Precedent

- **E-S13-05**: `mutmut` validated on CI Linux runners, not the Windows dev box.
- **2026 uplift incident**: five concurrent sub-agent `pytest` processes plus a
  leaked background suite throttled the laptop mid-feature. Root cause:
  unbounded concurrency plus a leak, amplified by hardcoded `max_examples`.
- **2026-08-01 incident**: the rule was relaxed to allow 3 concurrent
  code-executing agents, and a batch of five was dispatched with `pnpm build`,
  Playwright, and per-agent `pytest` all permitted. Medium throttle within
  minutes. No process leaked — the load was entirely *authorised*. Root cause:
  granting service-type permissions (category 1 and 2) to multiple agents at
  once. Repair: the category taxonomy above, and a hard cap of **one**
  code-executing agent.
