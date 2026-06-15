"""Scaffold a starter spec.yaml for a new SYNAPSE agent.

Usage:
    python .claude/skills/synapse-engineer/scripts/spec_gen.py <agent_name>

Produces `agents/<agent_name>/spec.yaml` with the canonical structure:
agent_name, version, description, architecture, invariants,
preconditions, postconditions, state_machine, rewards, contracts,
data_sources, metrics.

No network calls. Pure template expansion. Idempotent (refuses to
overwrite).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent

AGENT_ABBREV = {
    "demand_prophet": "DP",
    "routing_navigator": "RN",
    "inventory_sentinel": "IS",
    "pricing_oracle": "PO",
    "disruption_shield": "DS",
    "supplier_trust": "ST",
    "sustainability_agent": "SA",
    "freshness_guardian": "FG",
}


def render(agent: str) -> str:
    abbrev = AGENT_ABBREV.get(agent, agent[:2].upper())
    pretty = agent.replace("_", " ").title()
    return dedent(
        f"""\
        # SYNAPSE Agent Spec — {pretty}
        # Single source of truth for SDD (see docs/specs/agent_spec_schema.json)
        agent_name: {agent}
        version: "0.1.0"
        description: "TODO: 1-sentence purpose"

        architecture:
          tier: 2  # 1 = <100ms RL-only; 2 = <500ms RL+Feast; 3 = 2-15s LLM; 4 = 15-120s Twin
          inference_endpoint: /predict
          training_module: agents/{agent}/training/train.py

        invariants:
          - id: INV-{abbrev}-001
            description: "TODO: what must always hold"
            assertion: "0 <= result.confidence <= 1"
            severity: critical

        preconditions:
          - id: PRE-{abbrev}-001
            description: "Kafka topics reachable"
            check: "kafka_healthy() == True"
          - id: PRE-{abbrev}-002
            description: "Feast online store reachable"
            check: "feast_online_available() == True"

        postconditions:
          - id: POST-{abbrev}-001
            description: "Output validates against proto schema"
            check: "schema_validate(result, 'proto/domain/{agent}.schema.json')"

        state_machine:
          initial_state: IDLE
          states: [IDLE, PROPOSING, DEBATING, EXECUTING, LEARNING, ERROR]
          transitions:
            - from: IDLE
              to: PROPOSING
              trigger: request_received
              guard: kafka_healthy and feast_available
              timeout_seconds: 2.0
            - from: PROPOSING
              to: DEBATING
              trigger: proposal_submitted
              timeout_seconds: 5.0

        rewards:
          module: agents/{agent}/training/rewards.py
          signature: "reward(state, action, next_state) -> float"
          independent: true  # I-2: never import from agents.*.*

        contracts:
          inbound: agents/{agent}/contracts/inbound.py
          outbound: agents/{agent}/contracts/outbound.py

        data_sources:
          feast_features: []
          kafka_topics: []
          neo4j_patterns: []

        metrics:
          - synapse_{agent}_requests_total
          - synapse_{agent}_latency_seconds
          - synapse_{agent}_errors_total
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("agent", help="snake_case agent name")
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite existing spec.yaml (refused by default)",
    )
    args = parser.parse_args()

    out = Path("agents") / args.agent / "spec.yaml"
    if out.exists() and not args.force:
        print(f"REFUSE: {out} exists (pass --force to overwrite)", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(args.agent), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
