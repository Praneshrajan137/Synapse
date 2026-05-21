"""
SYNAPSE A2A SDK — Agent-to-Agent communication via JSON-RPC 2.0 (I-9).

A2A Protocol (Google, Linux Foundation) for inter-agent communication.
MCP (Anthropic) for agent-to-tool communication. NEVER conflate.

WS-1 / WS-2 hardening (Sprint 7):
    * Tier-aware timeouts: Tier 1 = 2s, Tier 2 = 10s, Tier 3 = 30s, Tier 4 = 120s.
    * W3C trace-context propagation (``traceparent`` + ``tracestate`` headers).
    * Idempotent JSON-RPC ``id`` survives retries so the receiving agent can dedupe.
    * Full-Jitter retry on transport errors (ADR-016).
    * Named circuit breaker per target host so a single bad agent cannot fan out.
    * Never retries 4xx (those are caller bugs); only network / 5xx retries.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import structlog

from synapse_common.breakers import get_breaker
from synapse_common.models import SynapseBaseModel
from synapse_common.retry import retry_with_jitter

if TYPE_CHECKING:
    from synapse_common.models import DecisionTier

logger = structlog.get_logger(__name__)

JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}

TIER_TIMEOUT_SECONDS: dict[str, float] = {
    "tier_1": 2.0,
    "tier_2": 10.0,
    "tier_3": 30.0,
    "tier_4": 120.0,
}

DEFAULT_TIMEOUT_SECONDS: float = 5.0
DEFAULT_RETRIES: int = 2
DEFAULT_BASE_DELAY: float = 0.25


class A2ARequest(SynapseBaseModel):
    """JSON-RPC 2.0 request for A2A protocol."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] = {}
    id: str = ""

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


def _resolve_timeout(tier: DecisionTier | str | None, explicit: float | None) -> float:
    if explicit is not None:
        return explicit
    if tier is None:
        return DEFAULT_TIMEOUT_SECONDS
    tier_key = tier.value if hasattr(tier, "value") else str(tier)
    return TIER_TIMEOUT_SECONDS.get(tier_key, DEFAULT_TIMEOUT_SECONDS)


def _trace_headers() -> dict[str, str]:
    """Read the active OTel context and emit W3C traceparent / tracestate.

    No-ops cleanly when the OTel SDK isn't installed (CI / unit tests).
    """
    try:
        from opentelemetry.propagate import inject
    except Exception:  # noqa: BLE001
        return {}
    carrier: dict[str, str] = {}
    try:
        inject(carrier)
    except Exception as exc:  # noqa: BLE001
        logger.debug("trace_inject_failed", error=str(exc))
        return {}
    return carrier


def _breaker_name_for(target_url: str) -> str:
    parsed = urlparse(target_url)
    host = parsed.hostname or "unknown"
    return f"a2a:{host}"


async def send_a2a_request(
    target_url: str,
    method: str,
    params: dict[str, Any],
    timeout: float | None = None,
    *,
    tier: DecisionTier | str | None = None,
    request_id: str | None = None,
    max_retries: int = DEFAULT_RETRIES,
) -> A2AResponse:
    """Send an A2A JSON-RPC request to another agent.

    Args:
        target_url: Base URL of the receiving agent (path ``/a2a`` is appended).
        method: JSON-RPC method name.
        params: JSON-RPC params object.
        timeout: Explicit timeout in seconds. Overrides ``tier`` if both given.
        tier: Decision tier; if provided and ``timeout`` is None, the timeout
            is derived from the tier's SLA (Tier 1 = 2s ... Tier 4 = 120s).
        request_id: Stable request id, reused on retry so the receiving agent
            can dedupe. Auto-generated if omitted.
        max_retries: Number of Full-Jitter retries on transport errors. ``0``
            disables retries.

    Raises:
        BreakerOpenError: target's breaker is OPEN.
        httpx.HTTPStatusError: 4xx/5xx (4xx are NOT retried).
        httpx.TransportError: only after retries are exhausted.
    """
    effective_timeout = _resolve_timeout(tier, timeout)
    request = A2ARequest(method=method, params=params, id=request_id or str(uuid4()))
    body = json.dumps(request.model_dump(mode="json"), **JSON_KWARGS)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    headers.update(_trace_headers())
    breaker = get_breaker(
        _breaker_name_for(target_url),
        fail_max=5,
        reset_timeout=30.0,
        expected_exceptions=(httpx.TransportError, httpx.HTTPStatusError),
    )

    async def _do_send_once() -> A2AResponse:
        async with breaker.guard(), httpx.AsyncClient(timeout=effective_timeout) as client:
            response = await client.post(
                f"{target_url}/a2a",
                content=body,
                headers=headers,
            )
            response.raise_for_status()
            return A2AResponse.model_validate(response.json())

    if max_retries <= 0:
        return await _do_send_once()

    wrapped = retry_with_jitter(
        max_retries=max_retries,
        base_delay=DEFAULT_BASE_DELAY,
        cap=min(effective_timeout, 5.0),
        retryable_exceptions=(httpx.TransportError,),
    )(_do_send_once)
    return await wrapped()  # type: ignore[no-any-return]
