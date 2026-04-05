# SYNAPSE Agent Conventions Reference

## Canonical Agent Structure
Every agent lives in agents/<agent_name>/ with this exact layout:
- models/ — Trained model artifacts, loaded at inference time
- training/ — RL training scripts, rewards.py (AGENT-SCOPED per I-2)
- inference/ — FastAPI inference server, pipeline.py
- a2a/ — A2A JSON-RPC handler: proposal(), debate_respond(), execute()
- contracts/ — Consumer-driven contract test definitions
- tests/ — Unit tests, spec tests (auto-generated from spec.yaml)
- spec.yaml — Single source of truth for agent behavior (SDD)
- state_machine.py — Agent lifecycle FSM with recite_objective()

## Spec-First Development Workflow
1. Write spec.yaml (invariants, pre/postconditions, state machine, metamorphic)
2. Run: make generate-spec-tests -> auto-generates test_spec.py (RED)
3. Implement agent code -> tests go GREEN
4. Run: make check-spec-coverage -> 100% invariant coverage required
5. Commit with: git commit -m "feat(<agent>): implement <invariant_id>"

## Reward Function Isolation (I-2)
- rewards.py MUST import ONLY from synapse_common or its own agent directory
- Cross-agent imports in rewards.py = automatic PR rejection
- CI hook: reward-isolation pre-commit check enforces this

## A2A Protocol Methods (I-9)
Every agent MUST implement these three JSON-RPC methods:
- proposal(decision_context) -> AgentProposal
- debate_respond(proposals, round) -> revised AgentProposal
- execute(consensus_action) -> ExecutionResult

## State Machine Convention
All agents use the same 6-state FSM: IDLE -> PROPOSING -> DEBATING -> EXECUTING -> LEARNING -> IDLE
With ERROR state accessible from PROPOSING and EXECUTING.
recite_objective() fires every 10 tool calls to prevent attention drift (ADR-024).
