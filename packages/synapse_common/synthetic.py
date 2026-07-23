"""Decision-origin detection — the single source of truth (ADR-044, ADR-053).

Every decision carries an ``order_id`` whose prefix tells us WHO initiated it:

* ``synthetic-<unix_ts>-<seq>`` — the always-alive traffic generator
  (Sprint 14, ``scripts/traffic/decision_loop.py``): a demo pulse, not real
  commerce. ``is_synthetic`` is true.
* ``auto-<city>-<trigger>-<seq>`` — the orchestrator ``SensorLoop``
  (ADR-052, ``orchestrator/sensor/loop.py``) convening consensus on its own
  initiative after perceiving the live world. This is the autonomous product
  story: a real decision with no human and no ticker. ``is_synthetic`` is
  **false** — an autonomous decision must never be mislabeled a demo pulse.
* anything else — an operator-injected order (the Ingress console, WS-2).

Until ADR-044 the ``synthetic-`` prefix was an implicit convention the FE had
to regex-match; ADR-053 extends the same discipline to the ``auto-`` prefix so
``initiator`` is a typed field, never a string-match in the UI. This module
owns both rules so every consumer — the audit outbox payload, the decisions
API, the firehose envelope, the frontend's SyntheticBadge / InitiatorBadge —
derives origin the same way.

The ``order_id`` reaches a decision only through the append-only context: the
orchestrator records the inbound request as the ``decision_request`` context
message (I-14), so detection scans ``context_messages`` for it. The winning
proposal's payload (``selected_action``) does NOT carry the order id.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

SYNTHETIC_ORDER_PREFIX = "synthetic-"
AUTONOMOUS_ORDER_PREFIX = "auto-"

# The three mutually-exclusive, exhaustive origins of a decision. ``operator``
# is the default — a missing/malformed tag must classify as a real,
# human-attributable decision, never hide behind ``synthetic`` or over-claim
# ``autonomous``.
DecisionInitiator = Literal["autonomous", "synthetic", "operator"]


def is_synthetic_order_id(order_id: object) -> bool:
    """True iff ``order_id`` carries the traffic-generator tag."""
    return isinstance(order_id, str) and order_id.startswith(SYNTHETIC_ORDER_PREFIX)


def is_autonomous_order_id(order_id: object) -> bool:
    """True iff ``order_id`` was minted by the autonomous ``SensorLoop``."""
    return isinstance(order_id, str) and order_id.startswith(AUTONOMOUS_ORDER_PREFIX)


def initiator_of_order_id(order_id: object) -> DecisionInitiator:
    """Classify a single ``order_id`` into its (total, disjoint) initiator.

    Prefix precedence is unambiguous because the two prefixes cannot overlap
    (``synthetic-`` vs ``auto-``); everything else is ``operator``.
    """
    if is_autonomous_order_id(order_id):
        return "autonomous"
    if is_synthetic_order_id(order_id):
        return "synthetic"
    return "operator"


def _message_content(message: object) -> Mapping[str, Any] | None:
    """Extract the ``content`` mapping from a ContextMessage or its JSONB dump."""
    if isinstance(message, Mapping):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    return content if isinstance(content, Mapping) else None


def _order_id_from_context(context_messages: Iterable[object]) -> object:
    """Return the ``decision_request`` order_id from the append-only context.

    Returns ``None`` when no well-formed ``decision_request`` entry is present
    — callers treat that as an operator/real decision, never a demo pulse.
    """
    for message in context_messages:
        content = _message_content(message)
        if content is None or content.get("type") != "decision_request":
            continue
        request = content.get("request")
        if isinstance(request, Mapping):
            return request.get("order_id")
    return None


def is_synthetic_decision(context_messages: Iterable[object]) -> bool:
    """True iff the decision originated from a synthetic (traffic-generator) order.

    Accepts both live ``ContextMessage`` objects and their JSONB-round-tripped
    dict form (the decisions API reads the latter from ``audit_consensus``).
    Scans for the ``decision_request`` context entry and applies the prefix
    rule to its ``request.order_id``. Absent or malformed entries are treated
    as real traffic — a missing tag must never hide a real decision.
    """
    return is_synthetic_order_id(_order_id_from_context(context_messages))


def initiator_of_decision(context_messages: Iterable[object]) -> DecisionInitiator:
    """Classify a decision's initiator from its append-only context (ADR-053).

    Same context-scan as :func:`is_synthetic_decision`, but returns the full
    three-way origin. An autonomous decision is never reported as synthetic.
    """
    return initiator_of_order_id(_order_id_from_context(context_messages))


__all__ = [
    "AUTONOMOUS_ORDER_PREFIX",
    "SYNTHETIC_ORDER_PREFIX",
    "DecisionInitiator",
    "initiator_of_decision",
    "initiator_of_order_id",
    "is_autonomous_order_id",
    "is_synthetic_decision",
    "is_synthetic_order_id",
]
