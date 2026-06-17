# ADR-052: Closing the Agentic Loop — making SYNAPSE genuinely autonomous

## Status
Accepted — **Phase 0 (this PR): contract + seams.** Phases 1–6 land incrementally
behind the gates this ADR defines (`scripts/audit/agency_truth.py`). The recommended
first increment is the autonomous *vertical slice* (inventory reorder loop, Bengaluru).

## Context
A primary-source audit (the five-phase consensus core plus three parallel code
sweeps, 2026-06-17) established a load-bearing truth the sprint-status prose did not:
**SYNAPSE is a governed decision-*pipeline* demonstrator, not an autonomous agent
system.** The enforcement *apparatus* (Sprints 11–19: mechanical gates, ADRs,
provenance, honest degradation, deploy-truth) is genuine and excellent. The agentic
*core* is hollow in five verified ways:

1. **No autonomy / initiative.** The only trigger for any decision is an external HTTP
   POST. In the live system that is a synthetic ticker (`scripts/traffic/decision_loop.py`)
   posting random `synthetic-` orders every ~4 min. The orchestrator consumes **no**
   Kafka topic and reacts to nothing (`orchestrator/inference/serve.py:231` is the sole
   entry; `topics.json` lists `orchestrator` only under `consumers_planned`).
2. **No perception loop.** Agents answer one request with mostly-fallback features, then
   idle. Nothing watches for a stockout, demand spike, or disruption.
3. **No actuation.** Every `agents/*/a2a/handler.py::execute()` returns
   `{"status":"executed","kafka_published":true}` and changes **nothing** — no Kafka
   write, no DB write, no world-state change. The `kafka_published` claim is literally
   false. `MCP_TOOLS` are defined in all 8 agents and **never called**.
4. **Deliberation is theater.** `debate_respond()` returns `{"status":"maintained"}`; the
   LLM's analysis is logged then discarded; `_check_convergence` is measured on utility
   scores that never move; the winner is `argmax(utility_score)` (`protocol.py:626`) while
   the NSGA-II Pareto arbitration is computed, stored, and ignored.
5. **Open loop.** Meta-RL is fed the *predicted* `utility_score` (`protocol.py:583`), not a
   realized outcome; the Sprint-19 scorer structurally always writes `"unknown"` (twin
   divergence not wired, `outcome_score.py:97`); agent confidence has a constant 0.5 floor
   so I-5 escalation effectively never fires; no calibrator updates from experience.

**The reframe.** *Agency is architectural, not model-quality.* A trivial-policy
thermostat is more agentic than a brilliant model that only answers when prompted.
SYNAPSE becomes genuinely autonomous by **closing the loop** with the policies that
already exist — perceive → decide on its own initiative → act on the world → observe
realized outcomes → adapt. Trained models then become a *quality* upgrade to an
already-agentic system. This is why setting model training aside (operator's explicit
carve-out) is correct sequencing, not a compromise.

**The decisive reuse finding.** The stateful world *already exists but is dormant.*
`digital_twin/simulation/engine.py::SupplyChainSimulation` is a persistent SimPy
supply-chain model with real `_inventory`/`_freshness`/`_metrics`, `start()/advance()`
stepping, and `set_policy(dispatch_speed, restock_threshold, order_qty_mult)` levers that
genuinely change the dynamics. `digital_twin/training/rl_sandbox.py::SupplyChainGymEnv`
already wraps it as a full perceive→act→reward loop. Both are used **only offline for RL
training**; live serving uses the *stateless* `WhatIfEngine`. So this is **promote + wire
+ add a sensor**, not build-from-scratch.

## Decision
Build the standing agentic loop in six phases, each gated so it cannot silently regress.

```
WorldSource (pluggable: SimWorldSource now | ExternalFeedSource later)
   → WorldRuntime (standing, ticking digital-twin world; perceive + actuate)
   → SensorLoop (autonomous initiative: detect condition → run_consensus on its own)
   → ConsensusProtocol (debate revises proposals; Pareto knee BINDS the selection)
   → execute() mutates the world + event-sources to Kafka
   → outcome scored against REALIZED world KPIs → meta-RL + calibrators adapt
   → back to perceive (continuous)
```

### Phase 0 — Contract & seams (this PR)
- This ADR.
- `packages/synapse_common/world/` — the typed substrate: `WorldEvent`, `WorldAction`,
  `WorldState` Pydantic models (I-3) and the **`WorldSource`** seam: `SimWorldSource`
  (deterministic Poisson demand from the simulation, **now**) and `ExternalFeedSource`
  (reads `synapse.orders.demand`, **later** — an honest stub, never pretends to be wired).
- `proto/domain/world_event.schema.json`, `world_action.schema.json` (I-3 boundary).
- No behavior change yet; no topic added.

### Phases 1–6 (summary; each its own increment behind the gates)
- **P1 WorldRuntime** — one persistent `SupplyChainSimulation` per city, advanced by a
  background clock (SimPy is synchronous → thread executor + lock). New twin methods
  `world_state` (perceive) / `apply_action` (actuate: `set_policy` + per-SKU reorder +
  `inject_disruption`). Small engine lever additions only (a `price_mult` demand lever,
  per-SKU reorder).
- **P2 SensorLoop** — a background task in the orchestrator (lifecycle modeled on
  `OutboxDispatcher`) that **polls `world_state`** (and, in a later increment, consumes
  world events), rule-detects decision-worthy conditions (reorder-point breach, demand
  spike, spoilage, disruption), debounces, and calls `run_consensus` itself. Replaces the
  synthetic ticker as the liveness driver; a low-rate heartbeat covers quiet windows.
- **P3 Actuation** — rewrite each `execute()` to translate the consensus action into a
  `WorldRuntime.apply_action` call **and** event-source it to the agent's Kafka topic
  (making `kafka_published` finally true). Decide MCP: wire one real tool server for
  `world_state`/feature reads (makes I-9 real), or delete the dead `mcp_tools.py`.
- **P4 Deliberation** — rule-based concession in `debate_respond()` (a non-pivotal agent
  relaxes utility toward consensus; a pivotal agent holds + justifies); orchestrator
  re-collects revised proposals so convergence is measured on **moving** scores; the
  selected action is the **Pareto knee**, not `argmax`. LLM mediation optional (I-7/I-13).
- **P5 Closed loop** — after horizon H, read realized KPIs from `WorldRuntime`, compute
  predicted-vs-realized divergence, pass it to `outcomes.score_decision(twin_divergence=…)`
  (the arg already exists; `outcome_score.py` passes `None` today) → outcomes flip
  `confirmed`/`diverged`; feed the **realized** outcome to `meta_rl.update`; refit each
  agent calibrator from the realized stream so confidence is live and I-5 can fire.
- **P6 Gates** — `scripts/audit/agency_truth.py` asserts (a) a non-HTTP autonomous trigger
  exists, (b) no `execute()` is status-dict-only, (c) non-`unknown` outcome rate > 0,
  (d) the world clock advanced. Wired into `verify_claims.py` + `ci.yml` + `make verify-agency`.

### Governance
- **Topic freeze.** The vertical slice perceives by **polling `world_state`** over A2A/HTTP
  — **no new Kafka topic, no new consumer** is required to be autonomous. World events
  emitted for observability reuse existing topics (`orders.demand`, `inventory.state`,
  `disruption.alert`). If a later increment makes the SensorLoop a Kafka consumer, that
  registration is governed by `topic_consumer_truth.py`; a genuinely new topic would be a
  fresh freeze exception (the ADR-029/ADR-051 precedent).
- **I-2** meta-RL learns only the 8-D blend weights, never per-agent rewards.
- **I-3** every world payload validates against the new schemas before crossing a boundary.
- **I-4/I-14/E-S9-02** `audit_consensus`'s hashed canonical row is untouched; outcomes stay
  the separate append-only `decision_outcomes` stream.
- **I-7** every new component degrades honestly — a dead WorldRuntime idles the Sensor and
  marks `/health` degraded; it never crashes or stalls a decision.
- **Honesty over theater.** Heuristic/fallback policies remain and stay labeled `degraded`
  via the existing `Provenance`. We make the *loop* real; we never relabel an untrained
  heuristic as "intelligent."

## Consequences
**Easier:** the system perceives and acts on its own; a decision visibly changes the
world; outcomes are scored against reality; I-5 can finally fire; the "agentic /
autonomous" claim becomes mechanically true and un-fakeable.

**Harder / cost:** a standing simulation must run inside the twin process (a background
thread + clock); the synthetic-ticker liveness story is superseded (the ticker becomes a
fallback heartbeat); new gates must be kept green.

## Alternatives Rejected
- **Make the LLM orchestrator the single brain (tools = the 8 agents).** Rejected: abandons
  the project's multi-agent-RL identity and leans on the $0 local LLM as load-bearing
  (I-13 / Ollama availability). The thesis is *multi-agent* autonomy; we make that real.
- **Real-world / real-store actuation now.** Rejected: infeasible at $0 (I-1) and not the
  project's nature. The world is the simulation; `ExternalFeedSource` is the honest seam
  for a real demand feed later.
- **Train models first, then close the loop.** Rejected (and the operator's carve-out):
  agency is architectural; a trained model that only answers when prompted is still not an
  agent. Close the loop with existing policies; training is the later quality upgrade.
- **One big PR.** Rejected: multi-phase scope; phasing behind `agency_truth.py` ships
  honest substance incrementally and de-risks the rest.
