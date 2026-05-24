"""Streaming materialization for Feast online store (ADR-030).

Reads the existing 16 frozen Kafka topics (I-6 — no new topics) and writes
1-minute and 5-minute rolling features into Redis via the Feast push API.
The offline Parquet feature views remain unchanged; this is additive.

Online/offline parity is the central invariant (I-4): for any timestamp T,
the online feature value at T must equal the offline feature view computed
at T within ε. Verified by `tests/integration/test_streaming_materialization.py`.

Implementation notes:
  * Uses `synapse_common.kafka_client.SynapseConsumer` so deserialization
    is the same deterministic JSON path as everything else.
  * Push to Feast happens via `feature_store.push("name", df, to=PushMode.ONLINE)`.
  * Watermark handling: late events past 5 min are routed to quarantine via
    `data_fabric.etl.quality_gates.gate_freshness`; they neither overwrite
    the online cache nor poison the rolling window.
"""

from __future__ import annotations

import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Deque

import structlog

from data_fabric.etl.quality_gates import (
    GateRegistry,
    evaluate,
    gate_freshness,
    gate_no_nulls,
)
from synapse_common.kafka_client import KafkaConfig, SynapseConsumer

logger = structlog.get_logger(__name__)

DEFAULT_WINDOWS: tuple[timedelta, ...] = (
    timedelta(minutes=1),
    timedelta(minutes=5),
)


@dataclass
class RollingWindow:
    """Per-key rolling counter aggregated over a time window."""

    span: timedelta
    events: dict[str, Deque[tuple[datetime, float]]] = field(default_factory=lambda: defaultdict(deque))

    def add(self, key: str, ts: datetime, value: float) -> None:
        q = self.events[key]
        q.append((ts, value))
        cutoff = ts - self.span
        while q and q[0][0] < cutoff:
            q.popleft()

    def count(self, key: str) -> int:
        return len(self.events.get(key, ()))

    def sum(self, key: str) -> float:
        return float(sum(v for _, v in self.events.get(key, ())))


@dataclass
class StreamMaterializer:
    """Glue between Kafka consumption and Feast online store."""

    feature_store_repo: str = "data_fabric/feast"
    bootstrap_servers: str = "kafka:9092"
    group_id: str = "synapse-stream-materializer"
    topics: tuple[str, ...] = ("synapse.orders.demand",)
    windows: tuple[timedelta, ...] = DEFAULT_WINDOWS
    timestamp_field: str = "timestamp"
    key_fields: tuple[str, ...] = ("store_id", "sku_id")

    def _key(self, row: dict[str, Any]) -> str:
        return "|".join(str(row.get(f, "")) for f in self.key_fields)

    def _gates(self) -> GateRegistry:
        reg = GateRegistry()
        reg.register("not_null", gate_no_nulls(list(self.key_fields) + [self.timestamp_field]))
        # 5-minute lateness budget; older events route to quarantine.
        reg.register("freshness", gate_freshness(self.timestamp_field, max_age_seconds=300.0))
        return reg

    def run(self, max_events: int | None = None) -> None:
        """Block-consume and materialize. `max_events` caps for tests."""
        consumer = SynapseConsumer(
            KafkaConfig(bootstrap_servers=self.bootstrap_servers, group_id=self.group_id),
            list(self.topics),
        )
        gates = self._gates()
        windows = {span: RollingWindow(span=span) for span in self.windows}
        store = _open_store(self.feature_store_repo)

        consumed = 0
        try:
            while max_events is None or consumed < max_events:
                row = consumer.poll(timeout=1.0)
                if row is None:
                    continue
                consumed += 1
                topic_label = row.get("topic", self.topics[0])
                if not evaluate(row, gates, topic=topic_label):
                    continue
                ts = _parse_ts(row[self.timestamp_field])
                key = self._key(row)
                value = float(row.get("quantity", 1))
                for w in windows.values():
                    w.add(key, ts, value)

                _push_features(store, key=key, ts=ts, windows=windows, row=row)
        finally:
            consumer.close()


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    s = str(raw).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _open_store(repo_path: str) -> Any:
    """Open a Feast feature store handle. Returns None when feast is absent."""
    try:
        from feast import FeatureStore  # type: ignore[import-untyped]

        return FeatureStore(repo_path=os.fspath(repo_path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("feast_open_failed", error=str(exc))
        return None


def _push_features(
    store: Any,
    *,
    key: str,
    ts: datetime,
    windows: dict[timedelta, RollingWindow],
    row: dict[str, Any],
) -> None:
    if store is None:
        return
    try:
        import pandas as pd
        from feast.data_source import PushMode  # type: ignore[import-untyped]

        store_id, sku_id = (key.split("|") + ["", ""])[:2]
        df = pd.DataFrame(
            [
                {
                    "store_id": store_id,
                    "sku_id": sku_id,
                    "event_timestamp": ts,
                    "orders_last_1m": windows[timedelta(minutes=1)].count(key),
                    "orders_last_5m": windows[timedelta(minutes=5)].count(key),
                    "qty_last_5m": windows[timedelta(minutes=5)].sum(key),
                }
            ]
        )
        store.push("sku_demand_signals_streaming", df, to=PushMode.ONLINE)
    except Exception as exc:  # noqa: BLE001
        logger.warning("feast_push_failed", error=str(exc), key=key)


__all__ = [
    "DEFAULT_WINDOWS",
    "RollingWindow",
    "StreamMaterializer",
]
