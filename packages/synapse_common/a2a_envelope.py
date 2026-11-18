"""The A2A ``proposal`` envelope, read strictly (I-7, I-9; CLAUDE.md E-DQP-02).

The consensus protocol sends each agent its request one level down, as
``params={"decision_context": request}`` (``ConsensusProtocol._request_proposal`` in
``orchestrator/consensus/protocol.py``). Every agent handler used to pass ``params`` straight to
its ``proposal``, which read keys at the top level, so no agent read its request
(decision-quality-proof finding 112). :func:`decision_context` is the one reader of the envelope,
and each handler's ``proposal`` dispatch calls it. ``debate_respond`` and ``execute`` are sent
flat and are not read through it.

**Why strict.** Params that carry no ``decision_context`` object are refused with
:class:`MissingDecisionContextError`. They are never read at the top level instead: a tolerant
``params.get("decision_context", params)`` accepts both shapes, so a caller that dropped the
envelope would get proposals built from defaults again, and nothing would say so. A handler's
JSON-RPC boundary turns the refusal into an error response whose message names the key.

**Why ``None`` reads as absent.** The orchestrator's HTTP route builds the request with
``DecisionRequest.model_dump()`` (``orchestrator/inference/serve.py``), so a field the caller
left unset arrives as ``None``, not as a missing key. ``ctx.get("store_id", default)`` then
returns ``None`` instead of the default, and the proposal fails validation. Dropping ``None``
values makes an unset field and an absent key read the same way. Only ``None`` is dropped:
``0``, ``""``, ``False`` and empty containers are values.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final

#: The ``params`` key under which the consensus protocol sends a proposal's request.
PROPOSAL_ENVELOPE_KEY: Final[str] = "decision_context"

#: Where the envelope is built. Every refusal names it, so a reader can find the sender.
_SENDER: Final[str] = "ConsensusProtocol._request_proposal (orchestrator/consensus/protocol.py)"


class MissingDecisionContextError(ValueError):
    """A ``proposal`` call's params carry no ``decision_context`` object to read."""


#: The name the handler contract was written against, and the one the Inventory Sentinel's
#: handler imports. Ruff's N818 requires an exception class to end in ``Error``, so the class is
#: named that way and this is the same class under the contracted name.
MissingDecisionContext = MissingDecisionContextError


def _refusal(found: str) -> MissingDecisionContextError:
    return MissingDecisionContextError(
        f"proposal params carry no {PROPOSAL_ENVELOPE_KEY!r} object ({found}). {_SENDER} "
        f"sends the request as params={{{PROPOSAL_ENVELOPE_KEY!r}: request}}; a flat request "
        "is refused, never read at the top level"
    )


def decision_context(params: Mapping[str, Any]) -> dict[str, Any]:
    """Return the request a ``proposal`` call carries in its envelope, ``None`` values dropped.

    The result is a new dict of the envelope's items whose value is not ``None``. Neither
    ``params`` nor the envelope is modified, and nested values are not copied.

    Raises:
        MissingDecisionContextError: ``params`` is not an object, has no ``decision_context``
            key, or holds something other than an object under it.
    """
    # Params arrive from JSON, where a positional array or a null is possible whatever the
    # annotation says. This check refuses them by name rather than as a bare TypeError.
    if not isinstance(params, Mapping):
        raise _refusal(f"params is a {type(params).__name__}")
    if PROPOSAL_ENVELOPE_KEY not in params:
        raise _refusal(f"params has keys {sorted(map(str, params))}")
    envelope = params[PROPOSAL_ENVELOPE_KEY]
    if not isinstance(envelope, Mapping):
        raise _refusal(f"{PROPOSAL_ENVELOPE_KEY!r} holds a {type(envelope).__name__}")
    return {key: value for key, value in envelope.items() if value is not None}


__all__ = [
    "PROPOSAL_ENVELOPE_KEY",
    "MissingDecisionContext",
    "MissingDecisionContextError",
    "decision_context",
]
