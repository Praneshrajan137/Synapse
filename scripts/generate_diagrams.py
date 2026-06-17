"""Auto-generate Mermaid C4 diagrams from agent + topic metadata (Sprint 9 §M-dx-2).

Reads each ``agents/<name>/agent_card.json`` + ``infrastructure/kafka/topics.json``
and emits three Mermaid docs:

  - docs/diagrams/c4_context.md  — system-wide context (Bengaluru + Mumbai).
  - docs/diagrams/c4_container.md — per-service containers + Kafka topics.
  - docs/diagrams/c4_dataflow.md  — producer/consumer arrows per topic.

Deterministic output (sorted iteration) so ``--check`` mode is a
meaningful CI gate, identical in spirit to Sprint 7's
``scripts/generate_burn_alerts.py --check`` precedent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = REPO_ROOT / "agents"
TOPICS_JSON = REPO_ROOT / "infrastructure" / "kafka" / "topics.json"
OUT_DIR = REPO_ROOT / "docs" / "diagrams"


def _agent_name(card: dict[str, Any]) -> str:
    return str(card.get("agent_name") or card.get("name", "unknown"))


def _load_agents() -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for card_path in sorted(AGENTS_DIR.glob("*/agent_card.json")):
        cards.append(json.loads(card_path.read_text(encoding="utf-8")))
    return cards


def _load_topics() -> list[dict[str, Any]]:
    data = json.loads(TOPICS_JSON.read_text(encoding="utf-8"))
    return sorted(data["topics"], key=lambda t: t["name"])


def render_context(agents: list[dict[str, Any]]) -> str:
    lines = [
        "# SYNAPSE C4 — System Context (Sprint 9 §M-dx-2, auto-generated)",
        "",
        "```mermaid",
        "C4Context",
        "    title SYNAPSE multi-agent quick-commerce platform",
        '    Person(operator, "Operator", "Triggers decisions / inspects audit")',
        '    System_Boundary(synapse, "SYNAPSE Platform") {',
        '        System(orchestrator, "Orchestrator", "4-tier consensus engine")',
    ]
    for card in sorted(agents, key=_agent_name):
        name = _agent_name(card)
        desc = card.get("description", "")
        lines.append(f'        System({name}, "{name}", "{desc}")')
    lines += [
        "    }",
        '    System_Ext(kafka, "Kafka", "18 topics, frozen post-Sprint 7")',
        '    System_Ext(postgres, "Postgres", "Append-only audit + chained hash")',
        '    System_Ext(neo4j, "Neo4j", "Supply network graph (per-city)")',
        '    Rel(operator, orchestrator, "Triggers decisions")',
    ]
    for card in sorted(agents, key=_agent_name):
        lines.append(f'    Rel(orchestrator, {_agent_name(card)}, "A2A JSON-RPC")')
    lines += ["```", ""]
    return "\n".join(lines)


def render_container(agents: list[dict[str, Any]], topics: list[dict[str, Any]]) -> str:
    lines = [
        "# SYNAPSE C4 — Container View (Sprint 9 §M-dx-2, auto-generated)",
        "",
        "```mermaid",
        "C4Container",
        "    title SYNAPSE service containers (per-city overlay merged)",
    ]
    for card in sorted(agents, key=_agent_name):
        name = _agent_name(card)
        cities = ",".join(card.get("cities", []))
        lines.append(f'    Container({name}, "{name}", "Python 3.11", "cities: {cities}")')
    lines.append('    ContainerDb(audit_db, "audit_consensus", "Postgres")')
    for topic in topics:
        slug = topic["name"].replace(".", "_")
        lines.append(
            f'    ContainerQueue({slug}, "{topic["name"]}", "Kafka",'
            f' "partitions: {topic["partitions"]}")'
        )
    lines += ["```", ""]
    return "\n".join(lines)


def render_dataflow(topics: list[dict[str, Any]]) -> str:
    lines = [
        "# SYNAPSE C4 — Data Flow (Sprint 9 §M-dx-2, auto-generated)",
        "",
        "```mermaid",
        "flowchart LR",
    ]
    for topic in topics:
        producer = topic.get("producer", "?")
        consumers = topic.get("key_consumers", [])
        for consumer in consumers:
            lines.append(f"    {producer}-->|{topic['name']}|{consumer}")
    lines += ["```", ""]
    return "\n".join(lines)


def generate() -> dict[str, str]:
    agents = _load_agents()
    topics = _load_topics()
    return {
        "c4_context.md": render_context(agents),
        "c4_container.md": render_container(agents, topics),
        "c4_dataflow.md": render_dataflow(topics),
    }


def write(payload: dict[str, str]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, content in payload.items():
        (OUT_DIR / name).write_text(content, encoding="utf-8")


def check(payload: dict[str, str]) -> bool:
    drift: list[str] = []
    for name, content in payload.items():
        on_disk = OUT_DIR / name
        if not on_disk.exists():
            drift.append(f"missing {on_disk.relative_to(REPO_ROOT)}")
            continue
        if on_disk.read_text(encoding="utf-8") != content:
            drift.append(f"out of sync: {on_disk.relative_to(REPO_ROOT)}")
    if drift:
        print("\n".join(drift), file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    payload = generate()
    if args.check:
        return 0 if check(payload) else 1
    write(payload)
    print(f"wrote {len(payload)} diagrams to {OUT_DIR.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
