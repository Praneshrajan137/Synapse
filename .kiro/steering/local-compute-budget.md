---
inclusion: always
---

# RULE — Local Compute Budget (I-0)

Treat this as invariant **I-0**, ranking alongside the 14 in `.cursorrules`.

Hardware, **measured 2026-09-11 with `Get-CimInstance` rather than asserted**: Lenovo 83GS,
**15.71 GB** RAM physical and OS-visible (**6.86 GB free** at measurement), i5-12450HX with
**8 physical / 12 logical** cores, RTX 3050 6 GB Laptop plus Intel UHD. Thermally throttling.
**This corrects two figures that were both wrong**: this file said 16 GB and a session said
14 GB. Only ~44% of RAM was free, so the binding limit is often *available* memory rather than
total — and **no workload in this repository needs the GPU**, so reserve no budget for it.

The machine handles ordinary development work fine. What throttles it is **process type and
process count**, not "running things" in general. This rule names both precisely, because
two earlier versions of it got the line in the wrong place — one banned almost all
execution (costing unverified work), the other permitted five concurrent agents
each cleared to run builds and browsers (which throttled the machine within
minutes).

**Where a workload runs is decided by `execution-routing.md`, which is an allow-list.** This
file governs *how much*; that table governs *where*, and it is authority on kind. Unlisted or
unmeasured means CI. The category taxonomy below remains as a set of fast heuristics, not as
the definition — the primary cost metric is **cores × wall-seconds**, because throttling tracks
sustained load and a kind-based list cannot distinguish a 3-second `ruff` from a 20-minute
`pytest` at the same core count.

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

- **Parallel sub-agents for reading, writing, and analysis: REQUIRED, not merely permitted.**
  Authoring does not heat the machine. Dispatch one per independent unit of work and state in
  the session opening how many and why. **This clause read "unlimited" for eight sessions and
  sessions used zero**, which is why it now reads as an obligation. `throughput-with-integrity.md`
  G1–G3 carry the dispatch contract, and **G7 makes parallel the DEFAULT: any wave with two or
  more independent units dispatches two or more agents, and working serially requires a stated
  reason.** G7 also covers the wider tool surface — code intelligence, symbol and reference
  lookup, research powers — which sessions have left unused in favour of shell and text search.
- **Sub-agents that execute code: exactly ONE at a time.** Not three, not two.
  When a batch needs a test run, exactly one agent in that batch gets the process
  budget and the rest are explicitly authoring-only.
- One test process at a time within that agent, too. Serial, not concurrent.

**The two clauses above are ONE design, not two rules in tension.** Wide authoring parallelism
is affordable *because* exactly one agent holds the process budget; the cap is what makes the
obligation safe. What may widen is the single executor's permitted **kind**, governed by
`execution-routing.md`. **The count never widens** — see the 2026-08-01 precedent below, where
relaxing it to three throttled the machine on load that was entirely authorised.

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
  file you specifically need coverage on. **ALWAYS SET IT EXPLICITLY, IN THE SAME COMMAND.**
  `conftest.py` loads `default` when the variable is unset, and `default` is **500** — a **50×**
  load, measured 2026-09-11 by importing `conftest` itself (unset → 500, `dev` → 10,
  `heavy` → 100, `ci` → 500). An unexported variable is the largest single accidental load
  available on this machine. **The one exception is deliberate:** a scoped *pure-arithmetic*
  file at `ci` costs seconds and catches what `dev` cannot — two consecutive findings were paid
  for by CI that a local `ci` run would have caught first.
- **Be honest about what ran.** "Authored and diagnostics-clean, not executed" is
  a legitimate result. "Should pass" reported as "passes" is not (I-7).
- **Report core-seconds, not just invocation counts.** `cores × wall-seconds` is the cost;
  the count is a proxy that cannot distinguish a 1-second gate from a 20-minute suite.

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
