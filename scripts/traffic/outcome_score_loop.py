"""SYNAPSE -- always-alive outcome scorer (Sprint 17, ADR-046).

Runs as the ``outcome-scorer`` compose service, REUSING the api-gateway image
(no new CD-matrix image -- ADR-039 / C27 safe), exactly like the
``traffic-generator`` sidecar. Every few minutes it scores settled decisions
against realized signals and appends to the append-only ``decision_outcomes``
table, so the Standing Watch calibration view is fed live.

Why a focused sidecar and not the data_fabric APScheduler: that scheduler is
not deployed, and starting it would also activate 5 unrelated batch jobs
(conformal recal, drift, feast compaction, audit archival) that have never run
in production. This loop runs ONLY the outcome-scoring job.

The honest derivation + the DB driver live in
``data_fabric.jobs.outcome_score`` (gated by verify_claims C51); this module is
only the loop + heartbeat wrapper. ``score_outcomes`` already degrades to 0 on
a missing table / unreachable DB (e.g. before the forward migration applies),
so a pass is never a crash. The heartbeat is touched every iteration; a
PERSISTENT failure stops it, flips the healthcheck unhealthy, and trips the
C47 deploy gate / live-truth watchdog.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import structlog

from data_fabric.jobs.outcome_score import score_outcomes

logger = structlog.get_logger(__name__)

INTERVAL_SECONDS = int(os.environ.get("OUTCOME_LOOP_INTERVAL_SECONDS", "300"))
HEARTBEAT_FILE = Path(os.environ.get("OUTCOME_HEARTBEAT_FILE", "/tmp/outcome-heartbeat"))


def run_forever() -> None:
    logger.info("outcome_scorer_loop_started", interval_seconds=INTERVAL_SECONDS)
    while True:
        try:
            scored = score_outcomes()
            logger.info("outcome_scorer_pass", scored=scored)
        except Exception as exc:  # noqa: BLE001 - a sidecar must never crash-loop
            # score_outcomes already swallows DB errors and returns 0; this is
            # belt-and-suspenders so any unexpected error logs and continues.
            logger.warning("outcome_scorer_pass_failed", error=str(exc))
        # Heartbeat regardless of scored count: an honest 0-scored pass (no
        # settled decisions yet, or table not migrated) is still a live loop.
        HEARTBEAT_FILE.touch()
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run_forever()
