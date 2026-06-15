"""Decision outcome scoring job (Sprint 19, ADR-047).

The delayed scorer that finally closes the outcome loop. For every decision
older than the settle horizon that has no outcome yet, it derives an honest
outcome from the realized signals that exist today (execution confirmations;
twin divergence where wired) and INSERTs an append-only ``decision_outcomes``
row. Where no realized signal exists the outcome is ``unknown`` — never a
fabricated ``confirmed`` (the derivation lives in the gated pure contract
``synapse_common.outcomes``).

Registered as the ``outcome_score`` APScheduler job
(``data_fabric/scheduler/scheduler.py``); runnable ad-hoc via
``python -m data_fabric.scheduler.scheduler trigger outcome_score``.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import structlog

from synapse_common.outcomes import score_decision

logger = structlog.get_logger(__name__)

# A decision settles before it can be scored — long enough for the Phase-4
# EXECUTING confirmations to land, short enough that the Standing Watch surface
# is not perpetually empty. Tunable via env for dev (shorten to see outcomes).
DEFAULT_HORIZON_MINUTES = int(os.environ.get("SYNAPSE_OUTCOME_HORIZON_MIN", "10"))
DEFAULT_BATCH_LIMIT = int(os.environ.get("SYNAPSE_OUTCOME_BATCH", "500"))


def _dsn() -> str | None:
    return os.environ.get("POSTGRES_DSN")


def score_outcomes(
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
    limit: int = DEFAULT_BATCH_LIMIT,
    dsn: str | None = None,
) -> int:
    """Score every unscored, settled decision. Returns the number scored.

    Degrades honestly: a missing DSN / unreachable DB / absent table logs a
    warning and returns 0 rather than crashing the scheduler.
    """
    dsn = dsn or _dsn()
    if not dsn:
        logger.warning("outcome_score_no_dsn")
        return 0

    horizon_s = horizon_minutes * 60
    now = datetime.now(UTC)
    now_iso = now.isoformat()

    try:
        import psycopg2
    except ImportError:
        logger.warning("outcome_score_psycopg2_missing")
        return 0

    scored = 0
    try:
        conn = psycopg2.connect(dsn)
    except Exception as exc:  # noqa: BLE001
        logger.warning("outcome_score_connect_failed", error=str(exc))
        return 0

    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.decision_id, c.confidence, c.execution_confirmations
                FROM audit_consensus c
                WHERE c.created_at < now() - make_interval(mins => %s)
                  AND NOT EXISTS (
                      SELECT 1 FROM decision_outcomes o
                      WHERE o.decision_id = c.decision_id
                  )
                ORDER BY c.created_at ASC
                LIMIT %s
                """,
                (horizon_minutes, limit),
            )
            rows = cur.fetchall()

            for decision_id, confidence, execution_confirmations in rows:
                outcome = score_decision(
                    confidence=float(confidence),
                    execution_confirmations=execution_confirmations,
                    # Per-decision twin divergence is not yet joinable in the
                    # DB (it is a Prometheus/firehose signal). Wiring it is the
                    # named next ratchet (ADR-047 D4); until then this source is
                    # absent and the scorer falls back to `unknown` honestly.
                    twin_divergence=None,
                    horizon_s=horizon_s,
                    scored_at=now_iso,
                )
                cur.execute(
                    """
                    INSERT INTO decision_outcomes
                        (decision_id, status, source, realized, error, horizon_s, scored_at)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        str(decision_id),
                        outcome["status"],
                        outcome["source"],
                        json.dumps(outcome["realized"], sort_keys=True, separators=(",", ":")),
                        outcome["error"],
                        outcome["horizon_s"],
                        now,
                    ),
                )
                scored += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("outcome_score_failed", error=str(exc))
        return scored
    finally:
        conn.close()

    logger.info("outcome_score_complete", scored=scored, horizon_minutes=horizon_minutes)
    return scored


def run_outcome_scoring() -> int:
    """Scheduler entry point (``() -> int``)."""
    return score_outcomes()
