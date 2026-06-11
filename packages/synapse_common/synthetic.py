"""Synthetic-traffic detection — the single source of truth (ADR-044).

The always-alive traffic generator (Sprint 14, ``scripts/traffic/decision_loop.py``)
tags every order it emits with ``order_id = "synthetic-<unix_ts>-<seq>"``. Until
ADR-044 that prefix was an implicit convention: the FE would have had to
regex-match order IDs to tell demo pulses from real commerce. This module owns
the rule so every consumer — the audit outbox payload, the decisions API, the
frontend's SyntheticBadge — derives ``is_synthetic`` the same way.

The ``order_id`` reaches a decision only through the append-only context: the
orchestrator records the inbound request as the ``decision_request`` context
message (I-14), so detection scans ``context_messages`` for it. The winning
proposal's payload (``selected_action``) does NOT carry the order id.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

SYNTHETIC_ORDER_PREFIX = "synthetic-"


def is_synthetic_order_id(order_id: object) -> bool:
    """True iff ``order_id`` carries the traffic-generator tag."""
    return isinstance(order_id, str) and order_id.startswith(SYNTHETIC_ORDER_PREFIX)


def _message_content(message: object) -> Mapping[str, Any] | None:
    """Extract the ``content`` mapping from a ContextMessage or its JSONB dump."""
    if isinstance(message, Mapping):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    return content if isinstance(content, Mapping) else None


def is_synthetic_decision(context_messages: Iterable[object]) -> bool:
    """True iff the decision originated from a synthetic (traffic-generator) order.

    Accepts both live ``ContextMessage`` objects and their JSONB-round-tripped
    dict form (the decisions API reads the latter from ``audit_consensus``).
    Scans for the ``decision_request`` context entry and applies the prefix
    rule to its ``request.order_id``. Absent or malformed entries are treated
    as real traffic — a missing tag must never hide a real decision.
    """
    for message in context_messages:
        content = _message_content(message)
        if content is None or content.get("type") != "decision_request":
            continue
        request = content.get("request")
        if isinstance(request, Mapping) and is_synthetic_order_id(request.get("order_id")):
            return True
    return False


__all__ = [
    "SYNTHETIC_ORDER_PREFIX",
    "is_synthetic_decision",
    "is_synthetic_order_id",
]
