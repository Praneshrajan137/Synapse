"""Streaming materialization for the Feast online store (ADR-030).

Consumes the frozen ingress topic ``synapse.orders.demand`` (I-6 - no new
topics) and maintains 1-minute and 5-minute rolling demand features, pushing
them to the Feast online store via the push API. The offline Parquet feature
views are untouched; this is purely additive.

purpose-achievement-audit R4.7 / task 10.14 makes this module the *deployed*
consumer of the orders ingress topic. It runs as the ``stream-materialization``
service in ``docker/docker-compose.gcp.yml`` with a heartbeat healthcheck (C50),
so a topic recorded with real ``consumers`` resolves to a service that actually
consumes it rather than to design intent. Before that wiring, real operator
orders reached Kafka (``api/routers/orders.py``) and nothing turned them into
features - the audit's R4 finding.

Honest degradation (I-7). Three failure modes are reported, never papered over:

  * **Broker unreachable.** ``SynapseConsumer.poll`` returns ``None`` for a
    quiet topic and for a broken broker alike, so this module proves
    reachability with ``reachable_topics()`` (the one call that raises
    ``KafkaUnreachableError``) at connect time and on every pass that read zero
    records. An unreachable feed is reported ``degraded``; it is never counted
    as a quiet one, and no arrival is ever invented.
  * **Feast SDK absent.** No image in the CD matrix installs ``feast`` today,
    so ``_open_store`` returns ``None`` and every pass is reported ``degraded``
    with ``reason="feast_sdk_unavailable"``. Rows are still consumed, gated and
    aggregated; the module does not claim a materialization it did not perform.
  * **Late or malformed rows** are quarantined by
    ``data_fabric.etl.quality_gates`` (written to disk, not dropped) and never
    enter a rolling window.

Every pass writes its outcome, as canonical JSON, to the heartbeat file the
compose healthcheck reads. That healthcheck asserts the loop is ALIVE - the
file is fresh - and deliberately does not assert ``degraded is False``: a
degraded-but-running consumer must stay visibly running so C47 reports honest
container truth instead of a crash loop. The degraded reason travels in the
heartbeat payload and in the structured log, so "healthy" is never readable as
"materializing".

Connection retries use ``synapse_common.retry.full_jitter`` (ADR-016) - never a
fixed-delay loop - so a broker that is slow to come up does not crash-loop the
container.

No automated test asserts online/offline parity yet. That obligation is real and
unmet: it needs a broker and a Redis online store, which I-0 keeps off the dev
laptop, so it belongs to an integration workflow rather than to a claim in this
docstring.
"""

from __future__ import annotations

import json
import os
import signal
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import FrameType
from typing import Any, Final

import structlog
from pydantic import BaseModel, ConfigDict

from data_fabric.etl.quality_gates import (
    GateRegistry,
    evaluate,
    gate_freshness,
    gate_no_nulls,
)
from synapse_common.kafka_client import (
    KafkaConfig,
    KafkaUnreachableError,
    SynapseConsumer,
)
from synapse_common.retry import retry_with_jitter

logger = structlog.get_logger(__name__)

#: The ingress topic this consumer exists for (ADR-029, frozen set - I-6).
ORDERS_TOPIC: Final[str] = "synapse.orders.demand"

#: Feature view fed through the Feast push API
#: (``data_fabric/feast/feature_views_streaming.py``).
STREAMING_FEATURE_VIEW: Final[str] = "sku_demand_signals_streaming"

DEFAULT_WINDOWS: tuple[timedelta, ...] = (
    timedelta(minutes=1),
    timedelta(minutes=5),
)

#: Default heartbeat path. The compose healthcheck reads this file and the
#: freshness bound it applies lives beside it in the compose service, matching
#: the ``traffic-generator`` / ``outcome-scorer`` sidecars.
DEFAULT_HEARTBEAT_FILE: Final[str] = "/tmp/stream-materialization-heartbeat"


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _utcnow().isoformat().replace("+00:00", "Z")


def _env_str(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        # I-7: a malformed knob is reported, not silently reinterpreted.
        logger.warning("stream_materialization_env_unparseable", var=name, raw=raw, using=default)
        return default


def _env_int(name: str, default: int) -> int:
    return int(_env_float(name, float(default)))


def _new_event_map() -> dict[str, deque[tuple[datetime, float]]]:
    return defaultdict(deque)


class MaterializationPass(BaseModel):
    """One consume-gate-materialize pass, recorded exactly as it happened.

    ``degraded`` is a first-class outcome (I-7): a pass that consumed rows but
    could not materialize them is neither a success nor a crash, and the reason
    is carried rather than inferred.
    """

    model_config = ConfigDict(frozen=True)

    at: str
    consumed: int = 0
    quarantined: int = 0
    materialized: int = 0
    degraded: bool = False
    reason: str | None = None

    def as_canonical_json(self) -> str:
        """Canonical serialization (sorted keys, no whitespace) for the heartbeat."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


@dataclass
class RollingWindow:
    """Per-key rolling counter aggregated over a time window."""

    span: timedelta
    events: dict[str, deque[tuple[datetime, float]]] = field(default_factory=_new_event_map)

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

    def prune(self, now: datetime) -> int:
        """Expire events older than the span and drop keys that went empty.

        Called once per pass so a long-running container's memory tracks the
        active key set rather than every key ever seen.
        """
        cutoff = now - self.span
        emptied: list[str] = []
        for key, q in self.events.items():
            while q and q[0][0] < cutoff:
                q.popleft()
            if not q:
                emptied.append(key)
        for key in emptied:
            del self.events[key]
        return len(emptied)


@dataclass
class StreamMaterializer:
    """Glue between Kafka consumption and the Feast online store."""

    feature_store_repo: str = "data_fabric/feast"
    bootstrap_servers: str = "kafka:9092"
    group_id: str = "synapse-stream-materializer"
    topics: tuple[str, ...] = (ORDERS_TOPIC,)
    windows: tuple[timedelta, ...] = DEFAULT_WINDOWS
    timestamp_field: str = "timestamp"
    key_fields: tuple[str, ...] = ("store_id", "sku_id")
    quantity_field: str = "quantity"
    lateness_budget_seconds: float = 300.0
    pass_interval_seconds: float = 5.0
    poll_timeout_seconds: float = 1.0
    max_records_per_pass: int = 500
    connect_retries: int = 5
    connect_base_delay: float = 1.0
    heartbeat_file: Path = Path(DEFAULT_HEARTBEAT_FILE)
    _stop: bool = field(default=False, init=False, repr=False)
    _absent_topics: tuple[str, ...] = field(default=(), init=False, repr=False)

    # -- construction ------------------------------------------------------
    @classmethod
    def from_env(cls) -> StreamMaterializer:
        """Build from the environment the compose service supplies.

        Every knob has a documented default so the module is runnable with no
        environment at all; the deployed values live in
        ``docker/docker-compose.gcp.yml`` next to the healthcheck that reads the
        heartbeat, which keeps the operational contract in one place.
        """
        topics = tuple(
            t.strip()
            for t in _env_str("STREAM_MATERIALIZATION_TOPICS", ORDERS_TOPIC).split(",")
            if t.strip()
        ) or (ORDERS_TOPIC,)
        return cls(
            feature_store_repo=_env_str("FEAST_REPO_PATH", "data_fabric/feast"),
            bootstrap_servers=_env_str("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            group_id=_env_str("STREAM_MATERIALIZATION_GROUP_ID", "synapse-stream-materializer"),
            topics=topics,
            lateness_budget_seconds=_env_float(
                "STREAM_MATERIALIZATION_LATENESS_BUDGET_SECONDS", 300.0
            ),
            pass_interval_seconds=_env_float("STREAM_MATERIALIZATION_PASS_INTERVAL_SECONDS", 5.0),
            poll_timeout_seconds=_env_float("STREAM_MATERIALIZATION_POLL_TIMEOUT_SECONDS", 1.0),
            max_records_per_pass=_env_int("STREAM_MATERIALIZATION_MAX_RECORDS_PER_PASS", 500),
            heartbeat_file=Path(
                _env_str("STREAM_MATERIALIZATION_HEARTBEAT_FILE", DEFAULT_HEARTBEAT_FILE)
            ),
        )

    # -- lifecycle ---------------------------------------------------------
    def request_stop(self) -> None:
        """Ask the loop to finish its pass and close the consumer cleanly."""
        self._stop = True

    # -- internals ---------------------------------------------------------
    def _key(self, row: dict[str, Any]) -> str:
        return "|".join(str(row.get(f, "")) for f in self.key_fields)

    def _gates(self) -> GateRegistry:
        reg = GateRegistry()
        reg.register("not_null", gate_no_nulls([*self.key_fields, self.timestamp_field]))
        # Lateness budget: older events route to quarantine rather than
        # poisoning a rolling window or overwriting the online cache.
        reg.register(
            "freshness",
            gate_freshness(self.timestamp_field, max_age_seconds=self.lateness_budget_seconds),
        )
        return reg

    def _quantity(self, row: dict[str, Any]) -> float:
        try:
            return float(row.get(self.quantity_field, 1))
        except (TypeError, ValueError):
            return 1.0

    def _try_connect(self) -> tuple[SynapseConsumer | None, str | None]:
        """Subscribe and prove a broker answered. Returns ``(None, reason)`` on failure.

        Retries are jittered per ADR-016 (``synapse_common.retry``). Constructing a
        ``Consumer`` never contacts a broker, so the subscription alone proves
        nothing; ``reachable_topics()`` is the probe that fails loudly.
        """

        @retry_with_jitter(
            max_retries=self.connect_retries,
            base_delay=self.connect_base_delay,
            retryable_exceptions=(KafkaUnreachableError,),
        )
        def _attempt() -> SynapseConsumer:
            consumer = SynapseConsumer(
                KafkaConfig(bootstrap_servers=self.bootstrap_servers, group_id=self.group_id),
                list(self.topics),
            )
            try:
                advertised = consumer.reachable_topics()
            except KafkaUnreachableError:
                consumer.close()
                raise
            self._absent_topics = tuple(t for t in self.topics if t not in advertised)
            return consumer

        try:
            consumer: SynapseConsumer = _attempt()
        except KafkaUnreachableError as exc:
            return None, f"broker_unreachable: {exc}"
        if self._absent_topics:
            logger.warning(
                "stream_materialization_topics_absent", topics=list(self._absent_topics)
            )
        return consumer, None

    # -- one pass ----------------------------------------------------------
    def run_pass(
        self,
        consumer: SynapseConsumer,
        store: Any,
        windows: dict[timedelta, RollingWindow],
    ) -> MaterializationPass:
        """Drain what is available, gate it, aggregate it, materialize it.

        A pass that reads nothing re-probes reachability, because ``poll()``
        collapses "empty" and "broken" into ``None`` and only one of those two is
        an honest zero.
        """
        gates = self._gates()
        records = consumer.drain(
            max_records=self.max_records_per_pass, timeout=self.poll_timeout_seconds
        )
        if not records:
            try:
                consumer.reachable_topics()
            except KafkaUnreachableError as exc:
                return MaterializationPass(
                    at=_now_iso(), degraded=True, reason=f"broker_unreachable: {exc}"
                )

        consumed = 0
        quarantined = 0
        materialized = 0
        for row in records:
            consumed += 1
            topic_label = str(row.get("topic") or self.topics[0])
            if not evaluate(row, gates, topic=topic_label):
                quarantined += 1
                continue
            try:
                ts = _parse_ts(row[self.timestamp_field])
            except (KeyError, TypeError, ValueError) as exc:
                quarantined += 1
                logger.warning("stream_materialization_timestamp_unparseable", error=str(exc))
                continue
            key = self._key(row)
            value = self._quantity(row)
            for window in windows.values():
                window.add(key, ts, value)
            if _push_features(store, key=key, ts=ts, windows=windows):
                materialized += 1

        now = _utcnow()
        for window in windows.values():
            window.prune(now)

        reasons: list[str] = []
        if store is None:
            reasons.append("feast_sdk_unavailable")
        if self._absent_topics:
            reasons.append("topics_absent:" + ",".join(self._absent_topics))
        if consumed and materialized < consumed - quarantined:
            reasons.append("push_incomplete")
        return MaterializationPass(
            at=_now_iso(),
            consumed=consumed,
            quarantined=quarantined,
            materialized=materialized,
            degraded=bool(reasons),
            reason="; ".join(reasons) if reasons else None,
        )

    # -- the loop ----------------------------------------------------------
    def run_forever(self, max_passes: int | None = None) -> MaterializationPass:
        """Consume until stopped. ``max_passes`` bounds the loop for tests.

        Returns the last completed pass so a caller (or a bounded test) reads the
        outcome instead of inferring it. A pass that could not connect still
        writes a degraded heartbeat, so an unreachable broker is visible in the
        container rather than only in the logs.
        """
        windows = {span: RollingWindow(span=span) for span in self.windows}
        store = _open_store(self.feature_store_repo)
        consumer: SynapseConsumer | None = None
        last = MaterializationPass(at=_now_iso(), degraded=True, reason="no_pass_completed")
        passes = 0
        logger.info(
            "stream_materialization_started",
            topics=list(self.topics),
            group_id=self.group_id,
            bootstrap_servers=self.bootstrap_servers,
            windows=[int(w.total_seconds()) for w in self.windows],
            feast_available=store is not None,
        )
        try:
            while not self._stop and (max_passes is None or passes < max_passes):
                passes += 1
                if consumer is None:
                    consumer, reason = self._try_connect()
                    if consumer is None:
                        last = MaterializationPass(at=_now_iso(), degraded=True, reason=reason)
                        logger.warning("stream_materialization_degraded", reason=reason)
                        _write_heartbeat(self.heartbeat_file, last)
                        self._sleep(self.pass_interval_seconds)
                        continue
                last = self.run_pass(consumer, store, windows)
                payload = last.model_dump(mode="json")
                if last.degraded:
                    logger.warning("stream_materialization_pass_degraded", **payload)
                else:
                    logger.info("stream_materialization_pass", **payload)
                # Heartbeat on every pass, degraded or not: an honest zero-record
                # pass is still a live loop, and the reason rides along.
                _write_heartbeat(self.heartbeat_file, last)
                if last.reason is not None and last.reason.startswith("broker_unreachable"):
                    consumer.close()
                    consumer = None
                self._sleep(self.pass_interval_seconds)
        finally:
            if consumer is not None:
                consumer.close()
            logger.info("stream_materialization_stopped", passes=passes)
        return last

    def _sleep(self, seconds: float) -> None:
        if seconds > 0 and not self._stop:
            time.sleep(seconds)


def _parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    s = str(raw).replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _write_heartbeat(path: Path, record: MaterializationPass) -> None:
    """Write the pass outcome the compose healthcheck reads.

    A heartbeat that cannot be written is logged and does not stop the loop; the
    healthcheck will observe the staleness on its own, which is the honest
    signal.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(record.as_canonical_json(), encoding="utf-8")
    except OSError as exc:
        logger.warning(
            "stream_materialization_heartbeat_failed", error=str(exc), path=str(path)
        )


def _open_store(repo_path: str) -> Any:
    """Open a Feast feature store handle. Returns ``None`` when feast is absent.

    ``None`` is not a silent fallback: ``run_pass`` turns it into a degraded pass
    carrying ``feast_sdk_unavailable``, so a container that consumes but cannot
    materialize reports exactly that.
    """
    try:
        from feast import FeatureStore  # type: ignore[import-untyped]

        return FeatureStore(repo_path=os.fspath(repo_path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("feast_open_failed", error=str(exc), repo_path=repo_path)
        return None


def _push_features(
    store: Any,
    *,
    key: str,
    ts: datetime,
    windows: dict[timedelta, RollingWindow],
) -> bool:
    """Push one key's rolling features online. Returns True iff the push happened."""
    if store is None:
        return False
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
        store.push(STREAMING_FEATURE_VIEW, df, to=PushMode.ONLINE)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("feast_push_failed", error=str(exc), key=key)
        return False


def main() -> None:
    """Entry point for the ``stream-materialization`` compose service."""
    materializer = StreamMaterializer.from_env()

    def _handle_signal(signum: int, _frame: FrameType | None) -> None:
        logger.info("stream_materialization_signal", signal=signum)
        materializer.request_stop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, _handle_signal)
    materializer.run_forever()


__all__ = [
    "DEFAULT_HEARTBEAT_FILE",
    "DEFAULT_WINDOWS",
    "ORDERS_TOPIC",
    "STREAMING_FEATURE_VIEW",
    "MaterializationPass",
    "RollingWindow",
    "StreamMaterializer",
    "main",
]


if __name__ == "__main__":
    main()
