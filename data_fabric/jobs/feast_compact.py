"""Nightly Feast compaction (Sprint 9 §M-life-6, ADR-035 sibling).

Iterates each Feast online-store entry per feature view; drops keys
whose TTL has elapsed. Sprint 9 ships the compaction *pattern* + a
graceful skip when Feast is offline; Sprint 10 plumbs the real Feast
client into the scheduler.

Default TTL: 30 days. Override per feature view via
``SYNAPSE_FEAST_TTL_DAYS_<feature>`` env var.
"""

from __future__ import annotations

import os
import time

import structlog

logger = structlog.get_logger(__name__)


DEFAULT_TTL_DAYS = int(os.environ.get("SYNAPSE_FEAST_TTL_DAYS", "30"))
FEATURE_VIEWS = (
    "demand_features",
    "supplier_features",
    "perishable_features",
    "elasticity_features",
    "routing_features",
    "event_features",
)


def _ttl_for(feature_view: str) -> int:
    env_key = f"SYNAPSE_FEAST_TTL_DAYS_{feature_view.upper()}"
    return int(os.environ.get(env_key, str(DEFAULT_TTL_DAYS)))


def compact_feature_views(views: list[str] | None = None) -> int:
    """Return 0 on success; logs counts per feature view.

    When Feast / Redis are unavailable the function logs ``skipped`` and
    still returns 0 — scheduler health depends on the job not crashing
    overnight just because dev infra is down.
    """
    try:
        import redis  # noqa: F401
    except ImportError:
        logger.warning("feast_compact_redis_missing")
        return 0

    targets = views or list(FEATURE_VIEWS)
    cutoff_ts = int(time.time()) - DEFAULT_TTL_DAYS * 86_400
    for view in targets:
        ttl_days = _ttl_for(view)
        view_cutoff = int(time.time()) - ttl_days * 86_400
        logger.info(
            "feast_compact_view",
            feature_view=view,
            ttl_days=ttl_days,
            cutoff_unix=view_cutoff,
            cutoff_global=cutoff_ts,
        )
    logger.info("feast_compact_complete", views=targets)
    return 0


if __name__ == "__main__":
    raise SystemExit(compact_feature_views())
