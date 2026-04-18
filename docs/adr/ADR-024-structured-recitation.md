# ADR-024: Structured Recitation for Long-Horizon Tasks

## Status
Accepted

## Context
Long agent contexts suffer from the **lost-in-the-middle phenomenon** — instructions buried in the middle of a long context receive less attention than those at the end. After ~10 tool calls, the agent drifts from its original objective. Manus AI's production research demonstrates that *recitation* — periodically rewriting the objective at the end of the context — restores attention to the goal without invalidating the KV-cache (the system prompt prefix is unchanged).

## Decision
Every SYNAPSE agent implements `recite_objective()` in `agents/<name>/state_machine.py`. After every **10 tool calls** (configurable per agent in `spec.yaml`), the agent appends a structured objective summary to its context. The recitation contains:

- Agent name and current FSM state.
- Tool calls completed (count + summary).
- Active objective (1-2 sentences).
- Active constraints from the Orchestrator's weight vector.
- Remaining steps to complete the current goal.

The Orchestrator has an **enhanced** `recite_objective()` that additionally includes:
- Current consensus phase (Proposal/Debate/Arbitration/Execution/Learning).
- Debate round number.
- Proposals received (per agent, with utility scores).
- Conflicts detected.
- Pareto convergence score.
- Weight vector.
- Pending agent responses.
- Error count.

Recitation is **append-only** (compatible with ADR-023, I-14) and **does not modify the system prefix** (compatible with ADR-021, I-13).

## Consequences
- Long-horizon tasks (Tier 3-4 multi-round debates) maintain objective focus.
- Adds ~500 tokens per recitation; bounded by tool-call cadence.
- Makes audit logs richer — recitations capture the agent's understanding of the goal at each checkpoint.
- Auto-generated test verifies recitation cadence (every 10 tool calls ± 1).

## Alternatives Rejected
- **No recitation**: rejected — attention drift in production.
- **Manual checkpointing**: rejected — relies on developer discipline; not enforceable.
- **Context truncation**: rejected — loses error retention (violates ADR-023, I-14).
