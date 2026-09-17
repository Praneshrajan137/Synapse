"""Unit tests for the external demand feed (audit R4.1/R4.5/R4.9, task 10.11).

Scope note: these are the *example* tests for the four states an external feed can be in
(unconfigured, unreachable, reachable-and-quiet, reachable-with-records) plus the inventory
obligation. The universal properties over arbitrary record streams are Property 28 (task
10.12) and Property 29 (task 10.13); nothing here duplicates them.

The fakes below implement the ``FeedConsumer`` protocol, which is the whole point of that
seam: the honest-degradation paths must be provable without a broker (I-0 keeps Kafka out of
the local loop; the real-stack proof is an integration workload).
"""

from __future__ import annotations

from typing import Any

from synapse_common.world import (
    NOT_CONFIGURED,
    RECORDS_REJECTED,
    UNREACHABLE,
    ExternalFeedSource,
    SourceProvenance,
    WorldEventKind,
    WorldSource,
)
from synapse_common.world.source import DEMAND_TOPIC, INVENTORY_TOPIC, FeedUnreachableError


class _Reachable:
    """A broker that advertises both topics and hands over a fixed record batch once."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = list(records)
        self.closed = False

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        return (DEMAND_TOPIC, INVENTORY_TOPIC)

    def drain(self, *, max_records: int = 1000, timeout: float = 1.0) -> list[dict[str, Any]]:
        batch, self._records = self._records[:max_records], []
        return batch

    def close(self) -> None:
        self.closed = True


class _Unreachable:
    """A configured broker nobody answers for."""

    def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
        raise FeedUnreachableError("no broker answered")

    def drain(self, *, max_records: int = 1000, timeout: float = 1.0) -> list[dict[str, Any]]:
        raise AssertionError("drain must not be attempted on an unreachable cluster")

    def close(self) -> None:
        return None


def _order(sku: str, quantity: float, *, order_id: str, city: str = "bengaluru") -> dict[str, Any]:
    return {
        "order_id": order_id,
        "city": city,
        "store_id": "store_001",
        "sku_id": sku,
        "quantity": quantity,
        "timestamp": "2026-01-01T00:00:00Z",
    }


def _source(consumer: Any, **kwargs: Any) -> ExternalFeedSource:
    # A retry budget of milliseconds: the retry policy itself is ADR-016's, proven in
    # packages/tests/test_retry.py. These tests must not pay for real backoff.
    return ExternalFeedSource(
        city="bengaluru",
        consumer_factory=lambda _topic: consumer,
        poll_timeout_s=0.01,
        retry_base_delay_s=0.001,
        **kwargs,
    )


def test_source_declares_external_and_satisfies_the_protocol() -> None:
    src = _source(_Reachable([]))
    assert src.provenance() is SourceProvenance.EXTERNAL
    assert isinstance(src, WorldSource)


def test_unconfigured_feed_reports_not_configured_and_polls_nothing() -> None:
    src = ExternalFeedSource(city="bengaluru", bootstrap_servers="")
    assert src.degradation() == NOT_CONFIGURED
    assert src.poll_arrivals(0.0, 60.0) == []
    assert src.initial_inventory() is None
    assert src.degradation() == NOT_CONFIGURED


def test_unreachable_feed_degrades_with_zero_arrivals_and_no_seeded_fallback() -> None:
    """R4.5: degraded + zero arrivals, and demand never advances from a generator."""
    src = _source(_Unreachable())
    assert src.poll_arrivals(0.0, 60.0) == []
    assert src.degradation() == UNREACHABLE
    # Repeated polls keep returning nothing: there is no generator behind this source to
    # quietly take over, so an unreachable feed can never manufacture demand.
    assert src.poll_arrivals(60.0, 60.0) == []
    assert src.degradation() == UNREACHABLE


def test_reachable_but_quiet_feed_is_not_degraded() -> None:
    """Zero real orders is a fact about the world, not a fault (I-7 cuts both ways)."""
    src = _source(_Reachable([]))
    assert src.poll_arrivals(0.0, 60.0) == []
    assert src.degradation() is None


def test_absent_topic_is_treated_as_unreachable() -> None:
    class _NoTopic(_Reachable):
        def reachable_topics(self, timeout: float = 5.0) -> tuple[str, ...]:
            return ("synapse.something.else",)

    src = _source(_NoTopic([_order("sku_1", 3.0, order_id="o1")]))
    assert src.poll_arrivals(0.0, 60.0) == []
    assert src.degradation() == UNREACHABLE


def test_real_records_become_arrivals_with_the_published_quantity() -> None:
    """R4.1: the incorporated quantity equals the published quantity."""
    records = [_order("sku_1", 3.0, order_id="o1"), _order("sku_2", 7.0, order_id="o2")]
    src = _source(_Reachable(records))
    events = src.poll_arrivals(120.0, 60.0)

    assert [e.quantity for e in events] == [3.0, 7.0]
    assert [e.sku_id for e in events] == ["sku_1", "sku_2"]
    assert {e.kind for e in events} == {WorldEventKind.DEMAND_ARRIVAL}
    assert [e.sim_time_min for e in events] == [120.0, 120.0]
    # Deterministic, record-derived identity (R4.6): a replay produces the same ids.
    assert [e.event_id for e in events] == ["ext:o1", "ext:o2"]
    assert src.degradation() is None
    assert src.feed_revision() == "ext:o2"


def test_records_for_another_city_are_not_incorporated() -> None:
    src = _source(_Reachable([_order("sku_1", 3.0, order_id="o1", city="mumbai")]))
    assert src.poll_arrivals(0.0, 60.0) == []
    assert src.degradation() is None  # a foreign record is not a fault, just not ours


def test_unusable_records_are_rejected_not_repaired() -> None:
    records = [
        _order("sku_1", 0.0, order_id="bad-zero"),
        {"order_id": "bad-no-sku", "city": "bengaluru", "quantity": 4.0},
        _order("sku_3", 5.0, order_id="good"),
    ]
    src = _source(_Reachable(records))
    events = src.poll_arrivals(0.0, 60.0)

    assert [e.event_id for e in events] == ["ext:good"]
    assert [e.quantity for e in events] == [5.0]
    assert src.degradation() == RECORDS_REJECTED


def test_boolean_quantity_is_rejected_rather_than_read_as_one_unit() -> None:
    record = _order("sku_1", 1.0, order_id="b1")
    record["quantity"] = True
    src = _source(_Reachable([record]))
    assert src.poll_arrivals(0.0, 60.0) == []
    assert src.degradation() == RECORDS_REJECTED


def test_empty_horizon_polls_nothing() -> None:
    src = _source(_Reachable([_order("sku_1", 3.0, order_id="o1")]))
    assert src.poll_arrivals(0.0, 0.0) == []


def test_initial_inventory_is_read_from_the_feed() -> None:
    """R4.9 (supplied case): opening stock comes from the source, not a literal."""
    snapshots = [
        {"city": "bengaluru", "sku_id": "sku_1", "level": 42.0},
        {"city": "bengaluru", "sku_id": "sku_1", "level": 40.0},  # later snapshot wins
        {"city": "bengaluru", "sku_id": "sku_2", "on_hand": 7},
        {"city": "mumbai", "sku_id": "sku_9", "level": 999.0},
    ]
    src = _source(_Reachable(snapshots))
    assert src.initial_inventory() == {"sku_1": 40.0, "sku_2": 7.0}


def test_absent_inventory_returns_none_rather_than_a_default() -> None:
    """R4.9 (absent case): no substituted literal, so the runtime can degrade honestly."""
    src = _source(_Reachable([]))
    assert src.initial_inventory() is None


def test_unreachable_inventory_returns_none_and_degrades() -> None:
    src = _source(_Unreachable())
    assert src.initial_inventory() is None
    assert src.degradation() == UNREACHABLE


def test_consumer_is_closed_after_every_poll() -> None:
    consumer = _Reachable([_order("sku_1", 1.0, order_id="o1")])
    src = _source(consumer)
    src.poll_arrivals(0.0, 60.0)
    assert consumer.closed is True
