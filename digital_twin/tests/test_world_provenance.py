"""World provenance is derived, and absent inventory degrades (audit R4.2/R4.9, task 10.11).

Before this increment ``WorldState.is_synthetic`` was pinned ``True`` in the model, so the
flag could not distinguish the two cases it existed to distinguish. Design AD-11 derives it
from the active source's declared class; these tests read it back through ``perceive()`` -
the same discipline ``orchestrator/tests/test_real_actuation_e2e.py`` uses, where the world
is the oracle rather than the component's self-report.

Property 28 (task 10.12) generalises this over arbitrary sources. What is pinned here are the
four concrete states a shipped world can be in.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from synapse_common.world.models import SourceProvenance
from synapse_common.world.source import (
    DEMAND_TOPIC,
    INVENTORY_ABSENT,
    INVENTORY_TOPIC,
    STUB_SOURCE,
    ExternalFeedSource,
)

from digital_twin.world.runtime import WorldRuntime

if TYPE_CHECKING:  # pragma: no cover - typing only
    from synapse_common.world.models import WorldEvent

_OPENING = {"sku_1": 12.0, "sku_2": 34.0}


class _Broker:
    """A reachable broker with a per-topic record batch, drained once."""

    def __init__(self, batches: dict[str, list[dict[str, Any]]], topic: str) -> None:
        self._batches = batches
        self._topic = topic

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        return (DEMAND_TOPIC, INVENTORY_TOPIC)

    def drain(self, *, max_records: int = 1000, timeout: float = 1.0) -> list[dict[str, Any]]:
        return self._batches.pop(self._topic, [])

    def close(self) -> None:
        return None


def _feed(batches: dict[str, list[dict[str, Any]]]) -> ExternalFeedSource:
    return ExternalFeedSource(
        city="bengaluru",
        consumer_factory=lambda topic: _Broker(batches, topic),
        poll_timeout_s=0.01,
        retry_base_delay_s=0.001,
    )


class _StubSource:
    """A source that can never produce an arrival - the R4.8 shape."""

    name = "stub:bengaluru"

    def poll_arrivals(self, now_sim_min: float, horizon_min: float) -> list[WorldEvent]:
        return []

    def provenance(self) -> SourceProvenance:
        return SourceProvenance.STUB

    def initial_inventory(self) -> dict[str, float] | None:
        return dict(_OPENING)

    def degradation(self) -> str | None:
        return None


def test_a_seeded_world_reports_synthetic_and_undegraded() -> None:
    rt = WorldRuntime(city="bengaluru", seed=42).start(run_clock=False)
    try:
        state = rt.perceive()
        assert state.source_class is SourceProvenance.SEEDED
        assert state.is_synthetic is True
        assert state.degraded is False
        assert state.degraded_reason is None
    finally:
        rt.stop()


def test_a_feed_driven_world_reports_non_synthetic_and_reads_its_opening_stock() -> None:
    """R4.2 + R4.9: the flag derives from the source, and the stock comes from the feed."""
    inventory_records = [
        {"city": "bengaluru", "sku_id": sku, "level": level} for sku, level in _OPENING.items()
    ]
    rt = WorldRuntime(
        city="bengaluru", source=_feed({INVENTORY_TOPIC: inventory_records})
    ).start(run_clock=False)
    try:
        state = rt.perceive()
        assert state.source_class is SourceProvenance.EXTERNAL
        assert state.is_synthetic is False
        assert state.inventory == _OPENING
        assert state.degraded is False
    finally:
        rt.stop()


def test_absent_inventory_degrades_instead_of_substituting_the_literal_default() -> None:
    """R4.9: no ``{sku_i: 100.0}`` stand-in for stock a real source never reported."""
    rt = WorldRuntime(city="bengaluru", source=_feed({})).start(run_clock=False)
    try:
        state = rt.perceive()
        assert state.inventory == {}
        assert state.degraded is True
        assert state.degraded_reason == INVENTORY_ABSENT
        assert state.is_synthetic is False
    finally:
        rt.stop()


def test_a_stub_driven_world_is_always_degraded() -> None:
    """An empty world must not read as a healthy one, whatever the stub reports."""
    rt = WorldRuntime(city="bengaluru", source=_StubSource()).start(run_clock=False)
    try:
        state = rt.perceive()
        assert state.source_class is SourceProvenance.STUB
        assert state.is_synthetic is False
        assert state.degraded is True
        assert state.degraded_reason == STUB_SOURCE
    finally:
        rt.stop()
