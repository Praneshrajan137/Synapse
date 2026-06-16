"""
SYNAPSE A2A SDK — Agent-to-Agent communication via JSON-RPC 2.0 (I-9).
A2A Protocol (Google, Linux Foundation) for inter-agent communication.
MCP (Anthropic) for agent-to-tool communication. NEVER conflate.

Sprint-7 hardening (WS-1 §4, WS-2 §1, ADR-025/026):
  - Tier-aware timeouts (T1=2s, T2=10s, T3=30s, T4=120s).
  - W3C traceparent injection via ``synapse_common.tracing``.
  - Full Jitter retry on transient transport errors only (never 4xx).
  - Per-target circuit breaker from ``synapse_common.breakers``.
  - Shared ``httpx.AsyncClient`` bulkhead from ``synapse_common.clients``.
"""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

import httpx
import structlog

from synapse_common.breakers import get_breaker
from synapse_common.clients import get_client
from synapse_common.metrics import A2A_REQUEST_LATENCY, A2A_REQUESTS_TOTAL
from synapse_common.models import DecisionTier, SynapseBaseModel
from synapse_common.retry import retry_with_jitter
from synapse_common.tracing import inject_a2a_headers

logger = structlog.get_logger(__name__)

JSON_KWARGS: dict[str, Any] = {"sort_keys": True, "separators": (",", ":")}


# Tier-aware timeout budgets. Aligns with I-10 decision-tier SLAs.
TIER_TIMEOUTS: dict[DecisionTier, float] = {
    DecisionTier.TIER_1: 2.0,
    DecisionTier.TIER_2: 10.0,
    DecisionTier.TIER_3: 30.0,
    DecisionTier.TIER_4: 120.0,
}


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


def _timeout_for(tier: DecisionTier | None, override: float | None) -> float:
    if override is not None:
        return override
    if tier is not None:
        return TIER_TIMEOUTS[tier]
    return TIER_TIMEOUTS[DecisionTier.TIER_2]


async def send_a2a_request(
    target_url: str,
    method: str,
    params: dict[str, Any],
    timeout: float | None = None,
    tier: DecisionTier | None = None,
    max_retries: int = 2,
) -> A2AResponse:
    """Send an A2A JSON-RPC request with tier-aware timeout, traceparent, retry, breaker.

    Args:
        target_url: base URL of the target agent (the SDK appends ``/a2a``).
        method: JSON-RPC method name (``proposal``, ``debate_respond``, ``execute``).
        params: JSON-RPC params object.
        timeout: explicit timeout override in seconds; if absent, ``tier`` drives it.
        tier: decision tier — drives default timeout per I-10.
        max_retries: Full-Jitter retry budget (transient transport errors only).
    """
    effective_timeout = _timeout_for(tier, timeout)
    breaker_name = _breaker_name(target_url)
    breaker = get_breaker(
        name=breaker_name,
        fail_max=5,
        reset_timeout=30.0,
        expected_exceptions=(httpx.TransportError, httpx.HTTPStatusError),
    )

    @retry_with_jitter(
        max_retries=max_retries,
        base_delay=0.5,
        cap=10.0,
        retryable_exceptions=(httpx.TransportError,),
    )
    async def _send() -> A2AResponse:
        result: A2AResponse = await breaker.call(
            _do_send, target_url, method, params, effective_timeout, tier
        )
        return result

    response: A2AResponse = await _send()
    return response


async def _do_send(
    target_url: str,
    method: str,
    params: dict[str, Any],
    timeout: float,
    tier: DecisionTier | None,
) -> A2AResponse:
    request = A2ARequest(method=method, params=params)
    headers: dict[str, str] = {"Content-Type": "application/json"}
    inject_a2a_headers(headers)
    if tier is not None:
        headers["X-Synapse-Tier"] = tier.value
    headers["X-Synapse-Request-Id"] = request.id

    client = await get_client("a2a")
    body = json.dumps(request.model_dump(mode="json"), **JSON_KWARGS)
    # PR-3 observability: per-target call latency + outcome. Before this the
    # consensus fan-out had no per-agent metric, so a slow/failing single agent
    # was invisible (you could only see the aggregate consensus duration).
    target = _target_label(target_url)
    start = time.monotonic()
    outcome = "ok"
    try:
        response = await client.post(
            f"{target_url}/a2a",
            content=body,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        outcome = "client_error" if 400 <= exc.response.status_code < 500 else "server_error"
        if 400 <= exc.response.status_code < 500:
            logger.error(
                "a2a_client_error_no_retry",
                target=target_url,
                method=method,
                status=exc.response.status_code,
                request_id=request.id,
            )
        raise
    except httpx.TransportError:
        outcome = "transport_error"
        raise
    finally:
        A2A_REQUEST_LATENCY.labels(target=target, method=method).observe(time.monotonic() - start)
        A2A_REQUESTS_TOTAL.labels(target=target, method=method, outcome=outcome).inc()
    return A2AResponse.model_validate(response.json())


def _breaker_name(target_url: str) -> str:
    """Derive a stable breaker name from a target URL (host[:port])."""
    netloc = target_url.split("://", 1)[-1]
    netloc = netloc.split("/", 1)[0]
    return f"a2a:{netloc}"


def _target_label(target_url: str) -> str:
    """Low-cardinality metric label: the target host (no scheme/port/path)."""
    netloc = target_url.split("://", 1)[-1].split("/", 1)[0]
    return netloc.split(":")[0]
