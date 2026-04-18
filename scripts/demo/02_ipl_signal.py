"""Segment 02 — IPL Signal.

Simulates a cricket / IPL-induced demand surge: essential snack + beverage
SKUs spike 3–5x in specific zones 45 minutes before match start. Orders are
serialized deterministically (I-13) and emitted via Kafka producer if a
broker is reachable; otherwise streamed to stdout for dry-run demos.

v4.0 plan §8.2 — second narrative beat.

Usage:
    python scripts/demo/02_ipl_signal.py <city> [speed_factor]
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

IPL_SURGE_MULTIPLIER = 4
IPL_CATEGORIES = {"snacks", "beverages", "dairy"}
IPL_CONSUMER_GROUP_TMPL = "synapse-orchestrator-{city}"


def build_surge_orders(
    stores: list[dict[str, Any]],
    skus: list[dict[str, Any]],
    city: str,
    n_stores: int = 8,
    n_skus: int = 12,
) -> list[dict[str, Any]]:
    rng = random.Random(42)
    matching_skus = [s for s in skus if s.get("category") in IPL_CATEGORIES]
    if not matching_skus:
        matching_skus = skus[:n_skus]

    target_stores = rng.sample(stores, min(n_stores, len(stores)))
    target_skus = rng.sample(matching_skus, min(n_skus, len(matching_skus)))

    orders: list[dict[str, Any]] = []
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for store in target_stores:
        for sku in target_skus:
            qty = rng.randint(5, 20) * IPL_SURGE_MULTIPLIER
            orders.append(
                {
                    "city": city,
                    "store_id": store["id"],
                    "sku_id": sku["sku_id"],
                    "quantity": qty,
                    "signal": "ipl_match_surge",
                    "timestamp": ts,
                }
            )
    return orders


def try_publish(orders: list[dict[str, Any]]) -> bool:
    """Attempt Kafka publish; return True if broker reachable."""
    try:
        from confluent_kafka import Producer

        producer = Producer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP,
                "message.timeout.ms": 3000,
            }
        )
        for order in orders:
            payload = json.dumps(order, sort_keys=True, separators=(",", ":"))
            producer.produce("synapse.orders.demand", payload.encode("utf-8"))
        producer.flush(timeout=5)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[02] Kafka publish unavailable ({exc}) — dry-run mode")
        return False


def main(city: str, speed: float) -> int:
    emit_banner("SEGMENT 02 — IPL Demand Signal", city, speed)
    data = load_city_data(city)

    orders = build_surge_orders(data["stores"], data["skus"], city)
    print(f"Synthesized {len(orders)} surge orders ({IPL_SURGE_MULTIPLIER}x baseline)")
    print(f"  categories targeted: {sorted(IPL_CATEGORIES)}")
    print(f"  stores affected:     {len({o['store_id'] for o in orders})}")
    print(f"  SKUs affected:       {len({o['sku_id'] for o in orders})}")

    published = try_publish(orders)

    snapshot_dir = Path("data") / city / "demo"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "ipl_signal_orders.json").write_text(
        json.dumps(orders, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    if published:
        wait_for_zero_lag(IPL_CONSUMER_GROUP_TMPL.format(city=city))
    else:
        sleep_scaled(2.0, speed)

    print("Segment 02 complete — surge signal dispatched.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/demo/02_ipl_signal.py <city> [speed_factor]")
        sys.exit(1)
    raise SystemExit(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.0))
