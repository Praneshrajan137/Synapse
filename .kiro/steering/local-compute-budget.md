---
inclusion: always
---

# HARD RULE — Local Compute Budget (I-0)

Treat this as invariant **I-0**, ranking alongside the 14 in `.cursorrules`. The
developer works on a thermally-throttling laptop. Saturating it is a
**task-blocking failure**, not an inconvenience. Heavy work runs on CI/CD
(GitHub Actions) or GCP — never on this machine.

## Absolute prohibitions (no local run without explicit per-instance approval)

1. **One process at a time.** Never run more than ONE test/build/bundle process
   concurrently. Sub-agent concurrency for anything that *executes code* is **1**.
   Parallel sub-agents are allowed only for reading, writing, and analysis.
2. **No full suites.** Never run bare `pytest`, `pytest tests/`, `make test`,
   `npm test`, or any whole-directory run. Scope to the single file you changed.
3. **No background processes for verification.** If one is started for a reason
   the user asked for, stop it in the same turn. A leaked `pytest` kept burning
   1.5 GB and 195s of CPU after its task ended — that is the exact incident this
   rule exists to prevent.
4. **CI/GCP-only workloads — never local:** mutation testing (`mutmut`),
   Schemathesis fuzz, chaos/load tests, repo-wide coverage, model training,
   `docker build`, `docker compose up`, the 21-container stack, full-matrix
   Hypothesis runs, `uplift.cli --full`, and any run touching `MIN_SCENARIOS`
   (1000-scenario Monte-Carlo).
5. **No unbounded parallelism.** Never `-n auto`, never `-j$(nproc)`. Cap low
   and explicitly.

## Required local behaviour

- Default to **no execution**: read files, run `getDiagnostics` on changed files,
  and use `--collect-only -q` to count tests instead of running them.
- If a test must run locally: **one file**, `HYPOTHESIS_PROFILE=dev`,
  `-m "not slow"`, `-x -q --tb=line`, `-p no:randomly`.
- **Sweep before finishing.** List background processes; confirm none of yours
  survived. Check for orphaned `python`/`node` processes if a run was cancelled.
- If verification genuinely needs heavy compute, **stop and say so.** Route it to
  CI and state plainly what was verified locally and what was not. An honest
  "green in CI, not run locally" beats heating the laptop.

## Escalation path for heavy work

1. `.github/workflows/ci.yml` (and `mutation.yml`, `integration.yml`,
   `sprint6-e2e-oracle.yml`) — these already exist; add a step rather than
   running locally.
2. GCP runner / VM (see `cd-gcp.yml`, ADR-036 window).
3. Only if neither works: ask permission, state expected duration and CPU cost,
   wait for an explicit yes.

## Authoring rule for property/fuzz tests

Never hardcode `max_examples` in `@settings`. Inherit it from the profiles in the
root `conftest.py` (`dev`=10, `ci`/`default`=500, `nightly`=5000) so local runs
are light and CI runs satisfy the >=100-iteration obligation. Mark any test that
drives the SimPy twin, the real `ConsensusProtocol`, or the CLI end-to-end with
`@pytest.mark.slow` so `-m "not slow"` genuinely excludes it.

## Precedent

- E-S13-05: `mutmut` validated in CI Linux runners, not the Windows dev box.
- 2026 uplift incident: five concurrent sub-agent `pytest` processes plus a
  leaked background suite run throttled the laptop mid-feature. Root cause was
  concurrency, amplified by hardcoded `max_examples` overriding the `dev`
  Hypothesis profile.
