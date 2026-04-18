# ADR-003: RL Training Paradigm — Independent Rewards + CTDE via RLlib

## Status
Accepted

## Context
A multi-agent system can train under three paradigms: shared reward (collapses to single-agent control), fully decentralized (no coordination), or Centralized Training with Decentralized Execution (CTDE). Shared rewards mask agent-specific failure modes — a single global reward cannot punish a Routing Navigator's late delivery without also punishing a Demand Prophet's accurate forecast. Fully decentralized training prevents the agents from learning coordination signals at all. SYNAPSE needs both independent agent accountability and emergent coordination.

## Decision
Each of the 8 agents has an independent reward function defined in `agents/<name>/training/rewards.py`. No two agents share a reward signal — Invariant I-2. Coordination is learned via CTDE: during training, agents observe the joint state and other agents' actions through Ray RLlib's MultiAgentEnv interface; at inference, each agent acts on its local observation only. RLlib (Apache 2.0) provides the multi-agent training infrastructure with PPO/MADDPG/DQN per agent type.

## Consequences
- Reward function isolation is enforceable by static analysis (pre-commit `reward-isolation` hook scans for cross-agent imports in `rewards.py`).
- Each agent's policy can be retrained independently without retraining the entire fleet.
- Mutation testing on `rewards.py` (Layer 7) is meaningful because reward changes don't cascade.
- CTDE requires a centralized training environment that simulates all 8 agents simultaneously — provided by Digital Twin Gymnasium wrapper (`digital_twin/training/rl_sandbox.py`).
- Slightly higher coordination loss than shared-reward systems; mitigated by Orchestrator-level Pareto arbitration.

## Alternatives Rejected
- **Shared reward (cooperative MARL)**: rejected — collapses 8 agents to 1, breaks I-2, defeats the entire CTDE rationale.
- **Fully decentralized (independent learners)**: rejected — agents cannot learn coordination; Orchestrator becomes purely reactive.
- **Custom multi-agent framework**: rejected — RLlib already supports CTDE, MADDPG, and federated extensions.
