"""Segment 03 — Disruption Injection.

Injects a targeted disruption event (warehouse offline OR monsoon flooding
OR supplier default) onto the Kafka disruption topic. Demonstrates the
Disruption Shield agent's anomaly ensemble + Pinecone playbook retrieval
reaching the orchestrator for Tier 3 consensus.

v4.0 plan §8.2 — third narrative beat (crisis).

Usage:
    python scripts/demo/03_disruption.py <city> [speed_factor] [kind]
      kind: warehouse_offline (default) | monsoon_flood | supplier_default
"""

from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path
from typing import Any

from scripts.demo._common import (
    KAFKA_BOOTSTRAP,
    emit_banner,
    load_city_data,
    sleep_scaled,
    wait_for_zero_lag,
)

CONSUMER_GROUP_TMPL = "synapse-orchestrator-{city}"


def build_disruption(
    city: str, kind: str, stores: list[dict[str, Any]]
) -> dict[str, Any]:
    rng = random.Random(0xD15)
    affected = rng.sample(stores, min(3, len(stores)))
    base = {
        "city": city,
        "kind": kind,
        "severity": 0.85,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "affected_store_ids": [s["id"] for s in affected],
    }
    if kind == "warehouse_offline":
        base["details"] = {"duration_minutes_est": 180, "root_cause": "power_outage"}
    elif kind == "monsoon_flood":
        base["details"] = {
            "monsoon_intensity": 0.92,
            "affected_zones": sorted({s.get("zone", "unknown") for s in affected}),
        }
    elif kind == "supplier_default":
        base["details"] = {
            "supplier_id": "SUP-0042",
            "missing_skus_pct": 0.34,
            "lead_time_delta_days": 5,
        }
    else:
        raise ValueError(f"Unknown disruption kind: {kind}")
    return base


def try_publish(event: dict[str, Any]) -> bool:
    try:
        from confluent_kafka import Producer

        producer = Producer(
            {"bootstrap.servers": KAFKA_BOOTSTRAP, "message.timeout.ms": 3000}
        )
        payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
        # Publish to the REGISTERED disruption topic (topics.json) — the firehose
        # `disruption` channel + audit sink consume it. The prior ad-hoc
        # "synapse.signals.disruption" was unregistered and failed the
        # topic-registry contract test (no such namespace exists).
        producer.produce("synapse.disruption.alert", payload.encode("utf-8"))
        producer.flush(timeout=5)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[03] Kafka publish unavailable ({exc}) — dry-run mode")
        return False


def main(city: str, speed: float, kind: str) -> int:
    emit_banner(f"SEGMENT 03 — Disruption ({kind})", city, speed)
    data = load_city_data(city)
    event = build_disruption(city, kind, data["stores"])

    print(f"Disruption kind:     {event['kind']}")
    print(f"Severity:            {event['severity']}")
    print(f"Affected stores:     {event['affected_store_ids']}")
    print(f"Details:             {json.dumps(event['details'], sort_keys=True)}")

    published = try_publish(event)

    snapshot_dir = Path("data") / city / "demo"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "disruption_event.json").write_text(
        json.dumps(event, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    if published:
        wait_for_zero_lag(CONSUMER_GROUP_TMPL.format(city=city))
    else:
        sleep_scaled(2.0, speed)

    print("Segment 03 complete — disruption signal dispatched.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/demo/03_disruption.py <city> [speed_factor] [kind]"
        )
        sys.exit(1)
    speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    kind = sys.argv[3] if len(sys.argv) > 3 else "warehouse_offline"
    raise SystemExit(main(sys.argv[1], speed, kind))
