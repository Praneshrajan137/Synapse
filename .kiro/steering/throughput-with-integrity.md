---
inclusion: always
---

# Throughput With Integrity — go fast without buying a false pass

Subordinate to `local-compute-budget.md` (I-0) and `execution-routing.md`.

Written after eight sessions averaging **5.25 leaf tasks each**, when the remaining work was
diagnosed as bounded by *process*, not by difficulty. The diagnosis, measured: one session
wrote ~1,400 lines of prose for ~350 lines of code, stating a single finding **five times**;
spent ~90 minutes blocked on serial CI waits; and dispatched **zero** parallel authoring agents
while I-0 permitted unlimited.

## Values, in precedence order

1. **An honest null outranks a fast pass.** A measurement that refuses to conclude is a result.
   The most valuable output of session 7 was *declining* to author eleven leaves.
2. **A refusal is a deliverable.** A guard that makes a defect loud is progress, and removing
   one to make a gate green is forbidden.
3. **Speed is only real if it is discharged.** See the metric below.
4. **State the domain a claim holds over.** An algebraic identity is not a floating-point
   identity. Correcting a *precondition* is not weakening an *assertion* (R2.10) — the test is
   whether the standard became **stricter**.
5. **A citation is not a mechanism.** Walk to the constructor; read the code path the assertion
   names, not the docstring of the object that holds it.
6. **Capability is not use.** `contributions()` could decompose a cost for eight sessions and no
   run called it, which is the only reason a finding stayed a hypothesis. Ask what the tree can
   already do before building anything.

## THE METRIC

> **Throughput is leaf tasks DISCHARGED. A `[~]` counts ZERO.**

This is the whole safety design, not an accounting preference. Authoring on an invalid premise
scores **nothing**, so speed can never purchase a false confirmation. Every session reports four
numbers: leaves discharged, core-seconds consumed, CI wall-clock on the critical path, and
parallel agents dispatched.

**The live example of why.** Tasks 12.3 and 13.3 flip the last two insensitive KPIs. With both
flipped, the negative regret of finding 54 maps to `sub-margin` — the **one** verdict that
*confirms* Finding 4. Under a leaves-authored metric, authoring E2c scores 11. Under this
metric it scores 0 until the comparator is repaired. **The metric is what makes the fast path
and the honest path the same path.**

## Guardrails — each names the failure it prevents

### G1 — Parallel authoring is MANDATORY. Exactly ONE agent may execute code.

I-0 already said authoring agents were unlimited; sessions used zero. Dispatch one agent per
independent unit of work, and say in the opening how many and why.

**The executor cap stays at one, and this is not a compromise.** Relaxing it to three produced
the 2026-08-01 throttle — *"a batch of five was dispatched with `pnpm build`, Playwright, and
per-agent `pytest` all permitted. Medium throttle within minutes. No process leaked — the load
was entirely authorised."* Wide authoring parallelism is safe **because** exactly one agent
holds the process budget. **They are one design, not two rules in tension.** What widens is the
executor's permitted *kind*, governed by `execution-routing.md`, never the count.

### G2 — Partition by coupling closure, never by file count.

An agent owns an **entire** same-commit coupling or none of it. Splitting a schema change from
the fixtures that carry it, or a rename from its declaration, manufactures exactly the
half-applied state the overrun clause exists to prevent — and now with two agents unable to see
each other's work.

### G3 — Every dispatched agent carries a written contract.

Four clauses, every time:
- **files it may touch**, and **files it must not**;
- **the one canonical location** for its findings;
- **"authoring only — do not execute"**, unless it is the designated executor;
- **the couplings it owns**, named.

Without this, six agents produce six copies of one finding — the duplication this repo's own
lesson condemns: *"Consensus across documents is not evidence — it is usually one unchecked
claim copied forward."*

### G4 — A session may not close with an unharvested `[~]`.

Every `[~]` must be tested against the newest run naming its discharge job. Task 26.1 sat
**dischargeable for two sessions** because sweeps were scoped to what a wave *changed*. A mark
whose discharge has silently arrived is indistinguishable, from the ledger alone, from one still
waiting. **Make it mechanical, not remembered.**

### G5 — CI parallelism must be a proven partition.

Splitting a suite across jobs can mask a test that only passed because another ran first, and
can silently drop a path. Any split asserts that the partition is **exhaustive and disjoint**,
and that total collected equals the pre-split count — predicted, then measured. **Partition,
never filter; assert non-emptiness.**

### G6 — This reset is itself falsifiable.

**Target: ≥ 11 leaves discharged** in the first full session under these rules, inside the
recorded core-second reading. If missed, the progress ledger says **the reset failed** and names
which lever underperformed. A process change that cannot fail is not a process change — the same
standard this spec applies to every number it publishes.

## One document per fact

One canonical home per finding: **the ADR** for design facts, **the task body** for ledger
facts. `HANDOFF.md` and `NEXT_SESSION_PROMPT.md` are **derived** — current state, pointers, and
the honesty ledger. Never a third copy of a finding.

**Prose is not free.** It is the largest single line-item in a session's output and it competes
directly with the work. Write the finding once, well, where a reader will look for it.

## What is never traded for speed

The forbidden repairs, unchanged and non-negotiable: no argument defaults, no widening to
`Any`, no `# type: ignore`, no narrowing a checker's scope, no lowering a floor, no
`continue-on-error` — **and no removing a refusal path to make a gate green.**

If an error is genuinely a tooling artefact, repair **the declaration that misleads the
checker**, never the call sites that report it.
