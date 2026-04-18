"""Shared helpers for demo segments 01–05.

Implements E-S6-06 Kafka consumer-group lag polling (Python confluent-kafka,
cross-platform) and a tiny structlog bootstrap so each segment can run
standalone *or* be chained from run_demo.sh. No paid APIs (I-1).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import structlog
from confluent_kafka import Consumer
from confluent_kafka.admin import AdminClient, ConsumerGroupTopicPartitions

logger = structlog.get_logger(__name__)

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
ORCHESTRATOR_URL = os.environ.get("ORCHESTRATOR_URL", "http://localhost:8085")
POSTGRES_DSN = os.environ.get(
    "POSTGRES_DSN",
    "postgresql://synapse:synapse_audit_2026@localhost:5432/synapse_audit",
)
MAX_LAG_WAIT_SECONDS = int(os.environ.get("MAX_LAG_WAIT_SECONDS", "120"))
LAG_POLL_INTERVAL = int(os.environ.get("LAG_POLL_INTERVAL", "2"))


def load_city_data(city: str) -> dict[str, list[dict[str, Any]]]:
    """Load stores.json and skus.json for a city."""
    base = Path("data") / city
    if not base.exists():
        raise FileNotFoundError(
            f"{base} not found — run 'make generate-{city}' first"
        )
    return {
        "stores": json.loads((base / "stores.json").read_text(encoding="utf-8")),
        "skus": json.loads((base / "skus.json").read_text(encoding="utf-8")),
    }


def wait_for_zero_lag(group: str, bootstrap: str = KAFKA_BOOTSTRAP) -> int:
    """Block until consumer-group lag reaches 0 (E-S6-06).

    Returns final lag (0 on success, >0 on timeout).
    """
    logger.info("lag_poll_start", group=group, bootstrap=bootstrap)
    admin = AdminClient({"bootstrap.servers": bootstrap})
    elapsed = 0
    final_lag = 0

    while elapsed < MAX_LAG_WAIT_SECONDS:
        try:
            groups_result = admin.list_consumer_groups().result()
            group_ids = [g.group_id for g in groups_result.valid]
            if group not in group_ids:
                logger.info("lag_poll_group_absent", group=group)
                return 0

            offsets_future = admin.list_consumer_group_offsets(
                [ConsumerGroupTopicPartitions(group)]
            )
            total_lag = 0
            for group_tp in offsets_future.values():
                result = group_tp.result()
                if not result.topic_partitions:
                    continue
                probe = Consumer(
                    {
                        "bootstrap.servers": bootstrap,
                        "group.id": "_synapse_demo_lag_probe",
                        "auto.offset.reset": "latest",
                    }
                )
                try:
                    for tp in result.topic_partitions:
                        if tp.offset >= 0:
                            _lo, hi = probe.get_watermark_offsets(tp, timeout=5)
                            if hi > tp.offset:
                                total_lag += hi - tp.offset
                finally:
                    probe.close()
            final_lag = total_lag
        except Exception as exc:  # noqa: BLE001 — best-effort probe
            logger.warning("lag_poll_error", error=str(exc))
            return 0

        if final_lag == 0:
            logger.info("lag_poll_done", group=group, elapsed=elapsed)
            return 0

        logger.info("lag_poll_waiting", group=group, lag=final_lag, elapsed=elapsed)
        time.sleep(LAG_POLL_INTERVAL)
        elapsed += LAG_POLL_INTERVAL

    logger.warning("lag_poll_timeout", group=group, lag=final_lag)
    return final_lag


def sleep_scaled(base_seconds: float, speed_factor: float) -> None:
    """Scaled delay for segment pacing (speed=1.0 → real-time)."""
    if speed_factor <= 0:
        speed_factor = 1.0
    time.sleep(max(0.0, base_seconds / speed_factor))


def emit_banner(title: str, city: str, speed: float) -> None:
    """Standardized segment banner."""
    bar = "═" * 60
    print(bar)
    print(f"  {title}")
    print(f"  city={city}  speed={speed}x  time={time.strftime('%H:%M:%S')}")
    print(bar)
