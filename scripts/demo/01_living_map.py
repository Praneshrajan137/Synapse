"""Segment 01 — Living Map.

Shows initial city state: dark stores, SKU catalog slice, and rider fleet.
This is the establishing shot of the demo: the viewer sees the *scale* of
the quick-commerce network before any perturbation.

v4.0 plan §8.2 — demo narrative opener.

Usage:
    python scripts/demo/01_living_map.py <city> [speed_factor]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts.demo._common import emit_banner, load_city_data, sleep_scaled


def summarize_stores(stores: list[dict[str, Any]]) -> dict[str, Any]:
    zones: dict[str, int] = {}
    for s in stores:
        zones[s.get("zone", "unknown")] = zones.get(s.get("zone", "unknown"), 0) + 1
    return {
        "count": len(stores),
        "zones": zones,
        "bounding_box": {
            "lat_min": min(s["lat"] for s in stores),
            "lat_max": max(s["lat"] for s in stores),
            "lon_min": min(s["lon"] for s in stores),
            "lon_max": max(s["lon"] for s in stores),
        },
    }


def summarize_skus(skus: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, int] = {}
    essential_count = 0
    for sku in skus:
        cat = sku.get("category", "unknown")
        categories[cat] = categories.get(cat, 0) + 1
        if sku.get("essential"):
            essential_count += 1
    return {
        "count": len(skus),
        "categories": categories,
        "essential_count": essential_count,
    }


def main(city: str, speed: float) -> int:
    emit_banner("SEGMENT 01 — Living Map", city, speed)

    data = load_city_data(city)
    stores_summary = summarize_stores(data["stores"])
    skus_summary = summarize_skus(data["skus"])

    print(f"Dark stores: {stores_summary['count']}")
    print(f"  zones: {stores_summary['zones']}")
    bb = stores_summary["bounding_box"]
    print(
        f"  bounds: lat [{bb['lat_min']:.4f}, {bb['lat_max']:.4f}] "
        f"lon [{bb['lon_min']:.4f}, {bb['lon_max']:.4f}]"
    )
    print(f"SKU catalog: {skus_summary['count']} SKUs")
    top_cats = sorted(
        skus_summary["categories"].items(), key=lambda kv: -kv[1]
    )[:5]
    for cat, n in top_cats:
        print(f"  {cat}: {n}")
    print(f"Essential SKUs (price-capped per I-6): {skus_summary['essential_count']}")

    # Persist a snapshot for downstream segments.
    snapshot_dir = Path("data") / city / "demo"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    (snapshot_dir / "living_map_snapshot.json").write_text(
        json.dumps(
            {"stores": stores_summary, "skus": skus_summary},
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    print(f"Snapshot written: {snapshot_dir / 'living_map_snapshot.json'}")

    sleep_scaled(3.0, speed)
    print("Segment 01 complete — map established.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/demo/01_living_map.py <city> [speed_factor]")
        sys.exit(1)
    raise SystemExit(main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1.0))
