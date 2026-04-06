"""
SYNAPSE -- Synthetic Traffic Generator for Shadow Mode Testing.
Generates realistic request patterns for all 3 Sprint 2 agents.
Uses reproducible RNG (np.random.Generator) for deterministic test runs.

Usage:
  python scripts/synthetic_traffic.py [--target demand_prophet|routing_navigator|inventory_sentinel|all] [--requests 100]
"""
from __future__ import annotations

import argparse
import json
import time
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

STORE_IDS: list[str] = [
    "STORE_BLR_001", "STORE_BLR_002", "STORE_MUM_001",
    "STORE_MUM_002", "STORE_DEL_001",
]

SKU_CATEGORIES: dict[str, list[str]] = {
    "dairy": [f"SKU_DAIRY_{i:03d}" for i in range(1, 21)],
    "bakery": [f"SKU_BAKERY_{i:03d}" for i in range(1, 16)],
    "beverages": [f"SKU_BEV_{i:03d}" for i in range(1, 26)],
    "snacks": [f"SKU_SNACK_{i:03d}" for i in range(1, 31)],
    "produce": [f"SKU_PROD_{i:03d}" for i in range(1, 16)],
}

ALL_SKUS: list[str] = [sku for skus in SKU_CATEGORIES.values() for sku in skus]


def generate_demand_request(rng: np.random.Generator) -> dict[str, Any]:
    """Generate a realistic demand forecast request."""
    store_id = rng.choice(STORE_IDS)
    num_skus = int(rng.integers(1, 50))
    sku_ids = list(rng.choice(ALL_SKUS, size=min(num_skus, len(ALL_SKUS)), replace=False))

    return {
        "sku_ids": sku_ids,
        "store_id": store_id,
        "horizons": ["15min", "1h", "6h", "24h", "7d"],
        "include_uncertainty": True,
    }


def generate_route_request(rng: np.random.Generator) -> dict[str, Any]:
    """Generate a realistic routing request."""
    num_orders = int(rng.integers(1, 50))
    num_riders = int(rng.integers(1, max(2, num_orders // 5)))

    orders = [
        {
            "order_id": f"ORD-{i:04d}",
            "lat": float(12.97 + rng.normal(0, 0.02)),
            "lon": float(77.59 + rng.normal(0, 0.02)),
            "weight": float(rng.uniform(0.5, 5.0)),
            "priority": int(rng.choice([1, 2, 3])),
        }
        for i in range(num_orders)
    ]

    riders = [
        {"rider_id": f"RIDER-{i:03d}", "vehicle_type": str(rng.choice(["bike", "ev_scooter"]))}
        for i in range(num_riders)
    ]

    return {
        "orders": orders,
        "riders": riders,
        "store_id": str(rng.choice(STORE_IDS)),
        "use_student": bool(rng.choice([True, False])),
    }


def generate_inventory_request(rng: np.random.Generator) -> dict[str, Any]:
    """Generate a realistic inventory decision request."""
    store_id = rng.choice(STORE_IDS)
    num_skus = int(rng.integers(1, 100))
    sku_ids = list(rng.choice(ALL_SKUS, size=min(num_skus, len(ALL_SKUS)), replace=False))

    return {"sku_ids": sku_ids, "store_id": store_id}


def run_shadow_mode(
    target: str = "all",
    num_requests: int = 100,
    seed: int = 42,
) -> dict[str, Any]:
    """Run shadow mode traffic generation."""
    rng = np.random.default_rng(seed)
    results: dict[str, list[dict[str, Any]]] = {
        "demand_prophet": [],
        "routing_navigator": [],
        "inventory_sentinel": [],
    }

    generators = {
        "demand_prophet": generate_demand_request,
        "routing_navigator": generate_route_request,
        "inventory_sentinel": generate_inventory_request,
    }

    targets = list(generators.keys()) if target == "all" else [target]

    for i in range(num_requests):
        agent = str(rng.choice(targets))
        request = generators[agent](rng)

        record = {
            "request_id": i,
            "agent": agent,
            "request": request,
            "timestamp": time.time(),
        }
        results[agent].append(record)

        if (i + 1) % 25 == 0:
            logger.info("shadow_progress", completed=i + 1, total=num_requests)

    summary = {
        agent: len(requests)
        for agent, requests in results.items()
    }
    logger.info("shadow_complete", summary=summary)
    return {"results": results, "summary": summary}


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="SYNAPSE Shadow Mode Traffic Generator")
    parser.add_argument(
        "--target",
        choices=["demand_prophet", "routing_navigator", "inventory_sentinel", "all"],
        default="all",
    )
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    result = run_shadow_mode(args.target, args.requests, args.seed)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(result["summary"], f, indent=2)
        logger.info("results_saved", path=args.output)


if __name__ == "__main__":
    main()
