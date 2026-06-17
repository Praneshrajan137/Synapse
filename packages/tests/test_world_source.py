"""Tests for the ADR-052 world substrate: models + the pluggable WorldSource seam."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from synapse_common.world import (
    ExternalFeedSource,
    SimWorldSource,
    WorldAction,
    WorldActionKind,
    WorldEvent,
    WorldEventKind,
    WorldSource,
    WorldState,
)

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "proto" / "domain"

CATALOG = {
    "city": "bengaluru",
    "store_ids": ["store_001", "store_002"],
    "sku_ids": [f"sku_{i}" for i in range(10)],
}


def _stable(
    events: list[WorldEvent],
) -> list[tuple[str, str | None, str | None, float, float | None]]:
    return [(e.kind.value, e.store_id, e.sku_id, e.sim_time_min, e.quantity) for e in events]


def test_models_round_trip_and_serialise_deterministically() -> None:
    evt = WorldEvent(
        event_id="e1", kind=WorldEventKind.STOCKOUT_RISK, city="bengaluru",
        sim_time_min=12.5, store_id="store_001", sku_id="sku_3", severity=0.8,
    )
    act = WorldAction(
        action_id="a1", kind=WorldActionKind.REORDER, city="bengaluru",
        store_id="store_001", sku_id="sku_3", params={"quantity": 200.0},
    )
    state = WorldState(
        city="bengaluru", sim_time_min=60.0, inventory={"sku_3": 5.0}, fill_rate=0.91
    )

    assert WorldEvent.model_validate_json(evt.to_deterministic_json()) == evt
    assert WorldAction.model_validate_json(act.to_deterministic_json()) == act
    # is_synthetic is always set so no surface mistakes the sim for a real store (ADR-052).
    assert state.is_synthetic is True
    # Deterministic JSON is byte-stable for the same object (I-13).
    assert evt.to_deterministic_json() == evt.to_deterministic_json()


def test_sim_source_is_deterministic_under_seed() -> None:
    a = SimWorldSource(**CATALOG, arrival_rate_per_min=2.0, seed=42)
    b = SimWorldSource(**CATALOG, arrival_rate_per_min=2.0, seed=42)
    # Two identical windows on two same-seed sources replay identically.
    ea = a.poll_arrivals(0.0, 60.0) + a.poll_arrivals(60.0, 60.0)
    eb = b.poll_arrivals(0.0, 60.0) + b.poll_arrivals(60.0, 60.0)
    assert _stable(ea) == _stable(eb)
    assert len(ea) > 0  # λ=2/min over 120 min — P(0) ≈ e^-240


def test_sim_source_respects_catalog_and_kinds() -> None:
    src = SimWorldSource(**CATALOG, arrival_rate_per_min=3.0, seed=7)
    events = src.poll_arrivals(0.0, 30.0)
    for e in events:
        assert e.kind is WorldEventKind.DEMAND_ARRIVAL
        assert e.store_id in CATALOG["store_ids"]
        assert e.sku_id in CATALOG["sku_ids"]
        assert e.quantity is not None and e.quantity >= 1.0
        assert e.city == "bengaluru"
    # Events are returned in simulation-time order.
    assert [e.sim_time_min for e in events] == sorted(e.sim_time_min for e in events)


def test_sim_source_empty_window_yields_nothing() -> None:
    src = SimWorldSource(**CATALOG, seed=1)
    assert src.poll_arrivals(0.0, 0.0) == []


def test_sim_source_rejects_bad_config() -> None:
    with pytest.raises(ValueError):
        SimWorldSource(city="bengaluru", store_ids=[], sku_ids=["sku_0"])
    with pytest.raises(ValueError):
        SimWorldSource(city="bengaluru", store_ids=["s"], sku_ids=["k"], arrival_rate_per_min=0.0)


def test_external_feed_is_honest_stub() -> None:
    # ExternalFeedSource is the "real later" seam — it must never fabricate arrivals (I-7).
    src = ExternalFeedSource(city="bengaluru")
    assert src.poll_arrivals(0.0, 60.0) == []
    # Both implementations satisfy the structural WorldSource protocol.
    assert isinstance(src, WorldSource)
    assert isinstance(SimWorldSource(**CATALOG), WorldSource)


def test_schema_required_fields_match_models() -> None:
    # The proto schemas (I-3 boundary) must not require a field the model cannot emit.
    for fname, model in (("world_event", WorldEvent), ("world_action", WorldAction)):
        schema = json.loads((SCHEMA_DIR / f"{fname}.schema.json").read_text(encoding="utf-8"))
        required = set(schema["required"])
        assert required.issubset(set(model.model_fields)), fname
