"""Segment 04 — Agent Debate.

Triggers a Tier 3 orchestrator decision cycle and prints the consensus
trajectory: proposals received → debate rounds → arbitration → Pareto
convergence score. If the orchestrator is unreachable, prints a scripted
debate summary from the disruption snapshot written by segment 03.

v4.0 plan §8.2 — fourth narrative beat (deliberation).

Usage:
    python scripts/demo/04_debate.py <city> [speed_factor]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

from scripts.demo._common import (
    ORCHESTRATOR_URL,
    emit_banner,
    sleep_scaled,
    wait_for_zero_lag,
)

CONSUMER_GROUP_TMPL = "synapse-orchestrator-{city}"


def trigger_orchestrator(city: str) -> dict[str, Any] | None:
    try:
        import requests

        resp = requests.post(
            f"{ORCHESTRATOR_URL}/api/v1/decisions",
            json={
                "city": city,
                "trigger": "demo_disruption_debate",
                "tier": "tier_3",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"[04] Orchestrator returned {resp.status_code}: {resp.text[:200]}")
    except Exception as exc:  # noqa: BLE001
        print(f"[04] Orchestrator unreachable ({exc}) — scripted summary")
    return None


def scripted_summary(city: str) -> dict[str, Any]:
    disruption_path = Path("data") / city / "demo" / "disruption_event.json"
    kind = "unknown"
    if disruption_path.exists():
        data = json.loads(disruption_path.read_text(encoding="utf-8"))
        kind = data.get("kind", "unknown")
    return {
        "decision_id": "scripted-demo-0001",
        "trigger": kind,
        "consensus_action": "shift_inventory_and_reroute",
        "confidence": 0.81,
        "debate_rounds": 2,
        "proposals": [
            {"agent": "routing_navigator", "utility": 0.78},
            {"agent": "inventory_sentinel", "utility": 0.82},
            {"agent": "disruption_shield", "utility": 0.86},
            {"agent": "pricing_oracle", "utility": 0.74},
        ],
        "pareto_convergence": 0.94,
        "weight_vector": {"cost": 0.35, "time": 0.35, "sustainability": 0.2, "fairness": 0.1},
    }


def render(summary: dict[str, Any]) -> None:
    print(f"Decision ID:       {summary.get('decision_id', 'N/A')}")
    print(f"Tier:              3 (LLM + RL)")
    print(f"Consensus action:  {summary.get('consensus_action', 'N/A')}")
    print(f"Confidence:        {summary.get('confidence', 'N/A')}")
    print(f"Debate rounds:     {summary.get('debate_rounds', 'N/A')}")
    print("Proposals:")
    for p in summary.get("proposals", []):
        print(f"  {p['agent']:<24s} utility={p['utility']:.3f}")
    if "pareto_convergence" in summary:
        print(f"Pareto convergence: {summary['pareto_convergence']:.3f}")
    if "weight_vector" in summary:
        wv = summary["weight_vector"]
        wv_str = " ".join(f"{k}={v:.2f}" for k, v in wv.items())
        print(f"Weight vector:     {wv_str}")


def main(city: str, speed: float) -> int:
    emit_banner("SEGMENT 04 — 5-Phase Consensus Debate", city, speed)

    live = trigger_orchestrator(city)
    summary = live if live else scripted_summary(city)
    render(summary)

    snapshot_dir = Path("data") / city / "demo"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "debate_summary.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    if live is not None:
        wait_for_zero_lag(CONSUMER_GROUP_TMPL.format(city=city))
    else:
        sleep_scaled(3.0, speed)

    print("Segment 04 complete — consensus reached.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/demo/04_debate.py <city> [speed_factor]")
        sys.exit(1)
    raise SystemExit(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.0))
