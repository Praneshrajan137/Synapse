"""Parametric golden-trace generator (Sprint 9 §M3).

Reads the 20 Sprint-8 base traces at ``tests/eval/golden_traces/*.json``,
emits 200 deterministically-parametrised variants under
``tests/eval/golden_traces/`` (overwriting the originals). Variation
axes: city × SKU id × store id × disruption seed × confidence jitter.

Production-mirrored ratio target (I-10): ~80% Tier-1, ~12% Tier-2, ~5%
Tier-3, ~3% Tier-4 across both cities. Per-city Bengaluru:Mumbai mix
≈ 60:40 so Mumbai's smaller volume still surfaces in the gate.

Deterministic: uses ``random.Random(0xCAFEBABE)`` seeded once at module
load. Same content every run → ``--check`` mode in CI catches drift.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
TRACES_DIR = REPO_ROOT / "tests" / "eval" / "golden_traces"

SEED = 0xCAFEBABE

# Production-mirrored tier distribution (I-10).
TIER_MIX: dict[str, int] = {
    "tier_1": 160,
    "tier_2": 24,
    "tier_3": 10,
    "tier_4": 6,
}
assert sum(TIER_MIX.values()) == 200

# Per-city allocation (~60/40 Bengaluru/Mumbai).
CITY_MIX: dict[str, float] = {"bengaluru": 0.60, "mumbai": 0.40}

AGENTS_BY_TIER: dict[str, list[list[str]]] = {
    "tier_1": [
        ["demand_prophet"],
        ["pricing_oracle"],
        ["inventory_sentinel"],
        ["routing_navigator"],
        ["freshness_guardian"],
        ["supplier_trust"],
    ],
    "tier_2": [
        ["demand_prophet", "pricing_oracle"],
        ["inventory_sentinel", "routing_navigator"],
        ["freshness_guardian", "demand_prophet"],
    ],
    "tier_3": [
        ["demand_prophet", "pricing_oracle", "inventory_sentinel", "freshness_guardian"],
        ["demand_prophet", "routing_navigator", "freshness_guardian", "supplier_trust"],
        [
            "demand_prophet",
            "pricing_oracle",
            "supplier_trust",
            "sustainability_agent",
        ],
    ],
    "tier_4": [
        [
            "disruption_shield",
            "routing_navigator",
            "inventory_sentinel",
            "supplier_trust",
        ],
        [
            "disruption_shield",
            "demand_prophet",
            "routing_navigator",
            "freshness_guardian",
            "supplier_trust",
        ],
    ],
}

# Tier-routing thresholds in tier_router.py:79-90 drive these confidence ranges.
CONFIDENCE_RANGES: dict[str, tuple[float, float]] = {
    "tier_1": (0.90, 0.99),
    "tier_2": (0.55, 0.89),  # >0.9 collapses to T1, single agent path bumps T1
    "tier_3": (0.30, 0.65),  # 4+ agents OR <0.4 confidence
    "tier_4": (0.30, 0.65),  # disruption_active flips here
}

INV_BY_AGENT: dict[str, list[str]] = {
    "demand_prophet": ["INV-DP-002", "INV-DP-006"],
    "pricing_oracle": ["INV-PO-001"],
    "inventory_sentinel": ["INV-IS-002"],
    "routing_navigator": [],
    "freshness_guardian": [],
    "supplier_trust": [],
    "disruption_shield": [],
    "sustainability_agent": [],
}


def _confidence_for_tier(rng: random.Random, tier: str, n_agents: int) -> float:
    """Pick a confidence that round-trips through tier_router.classify cleanly."""
    lo, hi = CONFIDENCE_RANGES[tier]
    # Tier-2 needs avg_confidence ≥0.4 AND (n_agents > 1 OR confidence < 0.9).
    if tier == "tier_2" and n_agents == 1:
        # Force confidence < 0.9 so the single agent stays at T2.
        hi = min(hi, 0.88)
    return round(rng.uniform(lo, hi), 3)


def _store_for(rng: random.Random, city: str) -> str:
    return f"{city[:3].upper()}-STR-{rng.randint(1, 50):03d}"


def _sku_for(rng: random.Random) -> str:
    return f"SKU-{rng.randint(1, 200):04d}"


def _expected_invariants(agents: list[str]) -> list[str]:
    seen: list[str] = []
    for agent in agents:
        for inv in INV_BY_AGENT.get(agent, []):
            if inv not in seen:
                seen.append(inv)
    return seen


def _make_trace(rng: random.Random, idx: int, tier: str, city: str) -> dict[str, Any]:
    agents = rng.choice(AGENTS_BY_TIER[tier])
    confidence = _confidence_for_tier(rng, tier, len(agents))
    disruption_active = tier == "tier_4"
    requires_twin = tier == "tier_4" and rng.random() > 0.5
    store_id = _store_for(rng, city)
    sku_id = _sku_for(rng)
    payload: dict[str, Any] = {
        "trace_id": f"{tier.replace('_', '')}-{city[:3]}-{idx:04d}-{store_id}-{sku_id}",
        "city": city,
        "description": (
            f"{tier} {city} {','.join(agents)} confidence={confidence}"
            + (" disruption" if disruption_active else "")
        ),
        "agents_involved": agents,
        "avg_confidence": confidence,
        "disruption_active": disruption_active,
        "requires_twin_simulation": requires_twin,
        "expected_tier": tier,
        "expected_invariants": _expected_invariants(agents),
        "expected_essential": tier == "tier_4",
        "payload": {"store_id": store_id, "sku_id": sku_id},
    }
    return payload


def generate() -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    traces: list[dict[str, Any]] = []
    idx = 0
    for tier, count in TIER_MIX.items():
        for _ in range(count):
            # City allocation deterministic on a stratified split.
            city = "mumbai" if rng.random() < CITY_MIX["mumbai"] else "bengaluru"
            traces.append(_make_trace(rng, idx, tier, city))
            idx += 1
    traces.sort(key=lambda t: t["trace_id"])
    return traces


def write_traces(traces: list[dict[str, Any]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Clear stale traces first so the directory is fully owned by the generator.
    for old in out_dir.glob("*.json"):
        old.unlink()
    for trace in traces:
        path = out_dir / f"{trace['trace_id']}.json"
        path.write_text(json.dumps(trace, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def check_traces(traces: list[dict[str, Any]], out_dir: Path) -> bool:
    existing = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in out_dir.glob("*.json")}
    if len(existing) != len(traces):
        print(
            f"trace count drift: on disk={len(existing)} expected={len(traces)}",
            file=sys.stderr,
        )
        return False
    for trace in traces:
        on_disk = existing.get(trace["trace_id"])
        if on_disk is None:
            print(f"missing trace: {trace['trace_id']}", file=sys.stderr)
            return False
        if json.dumps(on_disk, sort_keys=True) != json.dumps(trace, sort_keys=True):
            print(f"trace content drift: {trace['trace_id']}", file=sys.stderr)
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate-golden-traces")
    parser.add_argument("--out", type=Path, default=TRACES_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if on-disk traces drift from the generator output.",
    )
    args = parser.parse_args(argv)
    traces = generate()
    if args.check:
        return 0 if check_traces(traces, args.out) else 1
    write_traces(traces, args.out)
    counts: dict[str, int] = {}
    cities: dict[str, int] = {}
    for trace in traces:
        counts[trace["expected_tier"]] = counts.get(trace["expected_tier"], 0) + 1
        cities[trace["city"]] = cities.get(trace["city"], 0) + 1
    print(f"wrote {len(traces)} traces to {args.out}")
    print(f"  by tier: {counts}")
    print(f"  by city: {cities}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
