# ADR-007: Orchestration Framework — LangGraph with Custom Consensus Protocol

## Status
Accepted

## Context
The Orchestrator coordinates 8 agents through a 5-phase consensus protocol (Proposal → Debate → Arbitration → Execution → Learning). Building this from scratch on raw async Python conflates state-machine logic with LLM call management. AutoGen and CrewAI provide opinionated agent frameworks that hide the consensus state, making auditability difficult. We need a graph-based orchestration framework that exposes every state transition for the audit log (I-4) while still allowing custom consensus semantics.

## Decision
Use LangGraph (MIT) as the orchestration substrate. The 5-phase consensus is implemented as a LangGraph `StateGraph` with explicit nodes per phase and conditional edges for tier routing. The custom consensus protocol lives in `orchestrator/consensus/protocol.py` and uses LangGraph's checkpoint feature for context immutability (I-14). LangGraph integrates natively with LangSmith for tracing and provides built-in state persistence to Postgres.

## Consequences
- Every state transition is observable via LangSmith and auditable via Postgres checkpoints.
- The 5-phase FSM is a first-class graph object, not buried in if/else chains.
- Extending to a 6th phase (e.g., post-execution validation) requires adding a node, not refactoring control flow.
- Tight coupling to LangGraph's StateGraph API; a future migration would be non-trivial.
- LangGraph's checkpoint store is Postgres-only — acceptable since we already require Postgres for audit (I-4).

## Alternatives Rejected
- **AutoGen**: rejected — group chat abstraction hides individual agent proposals; harder to enforce confidence-gated execution (I-5).
- **CrewAI**: rejected — opinionated role/task model doesn't fit the proposal/debate/arbitration semantics.
- **Custom orchestration on raw asyncio**: rejected — would re-implement 60% of LangGraph's state-machine and checkpointing features.
