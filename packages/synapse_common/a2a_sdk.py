"""
SYNAPSE A2A SDK — Agent-to-Agent communication via JSON-RPC 2.0 (I-9).

A2A Protocol (Google, Linux Foundation) for inter-agent communication.
MCP (Anthropic) for agent-to-tool communication. NEVER conflate.

Every envelope carries an additive `correlation_id` (stable per originating
flow) and `causation_id` (id of the immediate upstream call). Together they
form a causal DAG persisted in the audit ledger (ADR-027).

Envelopes are validated against `proto/a2a/jsonrpc.schema.json` at the
boundary (ADR-025). Pydantic guards intra-process construction; the schema
guards the wire.
"""

from __future__ import annotations

import contextvars
import json
from typing import Any
from uuid import uuid4

import httpx
import structlog

from synapse_common.models import SynapseBaseModel
from synapse_common.schema_registry import get_registry

logger = structlog.get_logger(__name__)

JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}

# ContextVars carry the active causal frame across async boundaries. Server-side
# handlers should call `bind_causal_context(...)` on inbound envelopes; outbound
# `send_a2a_request(...)` reads them and stamps the next envelope.
_CORRELATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "synapse_correlation_id", default=None
)
_CAUSATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "synapse_causation_id", default=None
)


def bind_causal_context(correlation_id: str | None, causation_id: str | None) -> None:
    """Bind the inbound envelope's ids so outbound calls inherit them."""
    if correlation_id is not None:
        _CORRELATION_ID.set(correlation_id)
    if causation_id is not None:
        _CAUSATION_ID.set(causation_id)


def current_correlation_id() -> str | None:
    return _CORRELATION_ID.get()


def current_causation_id() -> str | None:
    return _CAUSATION_ID.get()


class A2ARequest(SynapseBaseModel):
    """JSON-RPC 2.0 request for A2A protocol with causal envelope (ADR-027)."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] = {}
    id: str = ""
    correlation_id: str | None = None
    causation_id: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            object.__setattr__(self, "id", str(uuid4()))


class A2AResponse(SynapseBaseModel):
    """JSON-RPC 2.0 response for A2A protocol."""

    jsonrpc: str = "2.0"
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    id: str


class AgentCard(SynapseBaseModel):
    """A2A Agent Card — capability declaration per agent."""

    name: str
    description: str
    version: str
    url: str
    capabilities: list[str]
    supported_methods: list[str]


def _build_request(method: str, params: dict[str, Any]) -> A2ARequest:
    """Construct an envelope, inheriting causal ids from the active context."""
    correlation = _CORRELATION_ID.get() or str(uuid4())
    causation = _CAUSATION_ID.get()  # may be None for the root call
    return A2ARequest(
        method=method,
        params=params,
        correlation_id=correlation,
        causation_id=causation,
    )


async def send_a2a_request(
    target_url: str,
    method: str,
    params: dict[str, Any],
    timeout: float = 5.0,
) -> A2AResponse:
    """Send a JSON-RPC envelope to another agent.

    Validates the envelope against `proto/a2a/jsonrpc.schema.json` before
    transmit (ADR-025). Stamps `correlation_id` (inherited or freshly minted)
    and `causation_id` (the request's own id, so the next hop can chain).
    """
    request = _build_request(method, params)
    payload = request.model_dump(mode="json", exclude_none=True)
    get_registry().validate(payload, "a2a.jsonrpc")

    # The next hop's causation_id is *this* envelope's id. We don't mutate the
    # caller's ContextVar — that would leak across awaits — but the receiving
    # server is expected to bind_causal_context(correlation_id=request.correlation_id,
    # causation_id=request.id) on entry.
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            f"{target_url}/a2a",
            content=json.dumps(payload, **JSON_KWARGS),
            headers={
                "Content-Type": "application/json",
                "X-Correlation-Id": request.correlation_id or "",
            },
        )
        response.raise_for_status()
        return A2AResponse.model_validate(response.json())
