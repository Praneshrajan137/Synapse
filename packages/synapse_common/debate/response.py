"""Shared ``debate_respond`` orchestration for all eight agents (ADR-052, R3).

Every agent's A2A ``debate_respond`` must apply the *identical* bounded-concession
decision so the eight handlers cannot drift apart (a correctness + maintenance risk).
The pure arithmetic lives in :mod:`synapse_common.debate.concession`; this module wraps
it with the honest, schema-validated request/response glue that each handler delegates to.

The contract, per the requirements:

* The consensus position is the arithmetic mean of the current round's proposal
  ``utility_score`` values (R3.2).
* When the agent already lies within the convergence band of the consensus it returns a
  maintained position rather than a revision (R3.9).
* Otherwise it concedes toward the consensus by a bounded amount (R3.3) and returns a
  revised proposal whose ``utility_score`` and ``payload`` reflect the *actual* revised
  position — never a fabricated value (R3.7).
* The revised payload is validated against the agent's ``proto/domain/`` schema before it
  is returned (I-3, R3.6); on validation failure the agent returns its maintained prior
  position with ``rationale="revision_failed_schema"`` and never returns the invalid
  revision (R3.10).

The function is pure with respect to the agent: it reads only ``params`` and the shared
schema registry, performs no I/O, and returns a plain JSON-RPC ``result`` dict.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from synapse_common.debate.concession import (
    concede_toward,
    consensus_position,
    within_convergence_band,
)
from synapse_common.schemas import SchemaValidationError, validate_agent_payload

if TYPE_CHECKING:
    from collections.abc import Mapping


def _maintained(
    agent_name: str,
    round_number: int,
    consensus: float | None,
    rationale: str,
) -> dict[str, Any]:
    """Build a maintained-position response (no revision applied)."""
    response: dict[str, Any] = {
        "status": "maintained",
        "round": round_number,
        "agent": agent_name,
        "rationale": rationale,
    }
    if consensus is not None:
        response["consensus_position"] = consensus
    return response


def _current_payload(params: Mapping[str, Any]) -> dict[str, Any] | None:
    """Extract the agent's current proposal payload from the request params.

    The orchestrator passes the agent's prior proposal so the agent can return an honest
    revision of it. We accept a few equivalent shapes (a direct ``current_payload`` /
    ``payload`` key, or a nested ``current_proposal``/``proposal`` envelope) and return
    ``None`` when no payload is available — in which case the agent cannot honestly revise
    and maintains its prior position instead.
    """
    for key in ("current_payload", "payload"):
        candidate = params.get(key)
        if isinstance(candidate, dict):
            return candidate
    for key in ("current_proposal", "proposal"):
        envelope = params.get(key)
        if isinstance(envelope, dict):
            nested = envelope.get("payload")
            if isinstance(nested, dict):
                return nested
    return None


def build_debate_response(agent_name: str, params: Mapping[str, Any]) -> dict[str, Any]:
    """Compute an agent's honest ``debate_respond`` reply via rule-based concession.

    Args:
        agent_name: The canonical agent short-name (e.g. ``"demand_prophet"``) used to
            select the ``proto/domain/`` schema for validation.
        params: The JSON-RPC ``debate_respond`` params. Recognised keys:
            ``round_number`` (int), ``round_utilities`` (the current round's proposal
            ``utility_score`` values), ``current_utility_score`` (this agent's score), and
            the agent's current payload under ``current_payload``/``payload`` (or nested
            under ``current_proposal``/``proposal``).

    Returns:
        A maintained-position dict (``status="maintained"``) or a revised-proposal dict
        (``status="revised"``) carrying the bounded, honest ``utility_score`` and the
        schema-valid revised ``payload``.
    """
    round_number = int(params.get("round_number", 1))
    raw_scores = params.get("round_utilities") or []
    scores = [float(s) for s in raw_scores]

    # No peer context this round → there is no consensus to concede toward; maintain (I-7).
    if not scores:
        return _maintained(agent_name, round_number, None, "no_round_context")

    consensus = consensus_position(scores)
    current = float(params.get("current_utility_score", consensus))

    # R3.9: already converged enough → maintain rather than concede.
    if within_convergence_band(current, consensus):
        return _maintained(agent_name, round_number, consensus, "within_band")

    # R3.3: bounded, monotone concession toward consensus (never overshooting).
    revised_score = concede_toward(current, consensus)

    # R3.7: the revision must reflect the agent's actual proposed payload, not a
    # fabricated one. Without the prior payload we cannot honestly revise → maintain.
    revised_payload = _current_payload(params)
    if revised_payload is None:
        return _maintained(agent_name, round_number, consensus, "revision_failed_schema")

    # I-3 / R3.6 / R3.10: only return the revision if its payload passes schema validation.
    try:
        validate_agent_payload(agent_name, revised_payload)
    except SchemaValidationError:
        return _maintained(agent_name, round_number, consensus, "revision_failed_schema")

    return {
        "status": "revised",
        "round": round_number,
        "agent": agent_name,
        "utility_score": revised_score,
        "payload": revised_payload,
        "consensus_position": consensus,
    }
