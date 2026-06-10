"""SYNAPSE -- always-alive synthetic decision traffic (Sprint 14).

Runs as the ``traffic-generator`` compose service (reusing the api-gateway
image -- no new image, ADR-039/C26 safe). Every few minutes it drives ONE
real decision through the production path:

    orchestrator POST /api/v1/decisions -> consensus -> audit ->
    outbox -> Kafka -> firehose WebSocket -> UI

so the live cockpit always has fresh data and the full pipeline is
continuously exercised (a silent break surfaces in the C47/watchdog
container checks instead of lying dormant until a demo).

Honesty: every synthetic decision is tagged with an ``order_id`` of the
form ``synthetic-<ts>-<n>`` so it is distinguishable in the audit chain.

The loop touches ``HEARTBEAT_FILE`` after each successful decision; the
compose healthcheck asserts the heartbeat is fresh, so a persistently
failing loop turns the container unhealthy and trips the deploy/watchdog
gates. stdlib + structlog only (both present in the api-gateway image).
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

ORCHESTRATOR_URL = os.environ.get(
    "SYNAPSE_ORCHESTRATOR_URL", "http://orchestrator:8085"
).rstrip("/")
INTERVAL_SECONDS = int(os.environ.get("TRAFFIC_INTERVAL_SECONDS", "240"))
JITTER_SECONDS = int(os.environ.get("TRAFFIC_JITTER_SECONDS", "60"))
HEARTBEAT_FILE = Path(os.environ.get("TRAFFIC_HEARTBEAT_FILE", "/tmp/traffic-heartbeat"))

STORE_IDS = (
    "STORE_BLR_001",
    "STORE_BLR_002",
    "STORE_MUM_001",
    "STORE_MUM_002",
    "STORE_DEL_001",
)
SKU_IDS = (
    *(f"SKU_DAIRY_{i:03d}" for i in range(1, 21)),
    *(f"SKU_BEV_{i:03d}" for i in range(1, 26)),
    *(f"SKU_SNACK_{i:03d}" for i in range(1, 31)),
    *(f"SKU_PROD_{i:03d}" for i in range(1, 16)),
)


def build_payload(rng: random.Random, seq: int) -> dict[str, Any]:
    """One synthetic-but-realistic decision request, honestly tagged."""
    items = [
        {"sku_id": rng.choice(SKU_IDS), "quantity": rng.randint(1, 5)}
        for _ in range(rng.randint(1, 3))
    ]
    return {
        "order_id": f"synthetic-{int(time.time())}-{seq}",
        "store_id": rng.choice(STORE_IDS),
        "items": items,
    }


def post_decision(payload: dict[str, Any], timeout: float = 90.0) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    req = urllib.request.Request(
        f"{ORCHESTRATOR_URL}/api/v1/decisions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed internal URL
        loaded: dict[str, Any] = json.loads(resp.read().decode())
        return loaded


def run_forever() -> None:
    rng = random.Random(os.environ.get("TRAFFIC_SEED") or None)
    seq = 0
    logger.info(
        "traffic_loop_started",
        orchestrator=ORCHESTRATOR_URL,
        interval_seconds=INTERVAL_SECONDS,
    )
    while True:
        seq += 1
        payload = build_payload(rng, seq)
        try:
            decision = post_decision(payload)
            HEARTBEAT_FILE.touch()
            logger.info(
                "synthetic_decision_ok",
                order_id=payload["order_id"],
                decision_id=decision.get("decision_id"),
                tier=decision.get("tier"),
                confidence=decision.get("confidence"),
            )
        except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            # Log-and-continue: a transient orchestrator restart must not
            # crash-loop this container. A PERSISTENT failure stops the
            # heartbeat, the healthcheck flips unhealthy, and the deploy /
            # watchdog gates surface it loudly.
            logger.warning(
                "synthetic_decision_failed", order_id=payload["order_id"], error=str(exc)
            )
        time.sleep(INTERVAL_SECONDS + rng.randint(0, max(JITTER_SECONDS, 1)))


if __name__ == "__main__":
    run_forever()
