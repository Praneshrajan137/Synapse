"""
SYNAPSE HTTP-client bulkheads (WS-1 §3, ADR-025).

A single shared ``httpx.AsyncClient`` per external dependency, each
with explicit ``Limits`` so Pinecone slowness can never starve Ollama
or Neo4j of connections. Combined with a per-dep circuit breaker
(``synapse_common.breakers``), this is the inner ring of the
resilience mesh.

Callers should never instantiate ``httpx.AsyncClient()`` directly —
use ``get_client(name)``. A grep test in CI guards this convention.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ClientProfile:
    """Connection-pool tuning per named dependency."""

    name: str
    base_url: str | None
    max_connections: int
    max_keepalive_connections: int
    default_timeout_s: float


# Named bulkhead profiles. Tunings reflect Sprint-7 plan §M4.
# Tier-aware A2A timeouts (M6) override default_timeout_s at call time.
PROFILES: dict[str, ClientProfile] = {
    "ollama": ClientProfile(
        name="ollama",
        base_url=None,
        max_connections=20,
        max_keepalive_connections=10,
        default_timeout_s=60.0,
    ),
    "neo4j_http": ClientProfile(
        name="neo4j_http",
        base_url=None,
        max_connections=10,
        max_keepalive_connections=5,
        default_timeout_s=10.0,
    ),
    "feast_http": ClientProfile(
        name="feast_http",
        base_url=None,
        max_connections=20,
        max_keepalive_connections=10,
        default_timeout_s=5.0,
    ),
    "pinecone": ClientProfile(
        name="pinecone",
        base_url=None,
        max_connections=10,
        max_keepalive_connections=5,
        default_timeout_s=10.0,
    ),
    "orchestrator": ClientProfile(
        name="orchestrator",
        base_url=None,
        max_connections=50,
        max_keepalive_connections=25,
        default_timeout_s=30.0,
    ),
    "a2a": ClientProfile(
        name="a2a",
        base_url=None,
        max_connections=100,
        max_keepalive_connections=50,
        default_timeout_s=120.0,
    ),
}


_CLIENTS: dict[str, httpx.AsyncClient] = {}
_LOCK = asyncio.Lock()


async def get_client(name: str) -> httpx.AsyncClient:
    """Return the shared ``AsyncClient`` for the named dependency.

    Raises ``KeyError`` if ``name`` is not a registered profile —
    callers must add the profile to ``PROFILES`` rather than spin up
    an anonymous client.
    """
    existing = _CLIENTS.get(name)
    if existing is not None and not existing.is_closed:
        return existing
    async with _LOCK:
        existing = _CLIENTS.get(name)
        if existing is not None and not existing.is_closed:
            return existing
        if name not in PROFILES:
            raise KeyError(
                f"no httpx bulkhead profile for '{name}' — "
                f"add a ClientProfile to synapse_common.clients.PROFILES first"
            )
        profile = PROFILES[name]
        client = httpx.AsyncClient(
            base_url=profile.base_url or "",
            timeout=httpx.Timeout(profile.default_timeout_s),
            limits=httpx.Limits(
                max_connections=profile.max_connections,
                max_keepalive_connections=profile.max_keepalive_connections,
            ),
        )
        _CLIENTS[name] = client
        logger.info(
            "httpx_bulkhead_opened",
            name=name,
            max_connections=profile.max_connections,
            max_keepalive=profile.max_keepalive_connections,
        )
        return client


async def close_clients() -> None:
    """Close all bulkhead clients. Register this with ``Lifespan.on_shutdown``."""
    async with _LOCK:
        for name, client in list(_CLIENTS.items()):
            try:
                await client.aclose()
            except Exception as exc:  # noqa: BLE001
                logger.warning("httpx_bulkhead_close_failed", name=name, error=str(exc))
        _CLIENTS.clear()


def register_profile(profile: ClientProfile) -> None:
    """Add or replace a client profile at runtime. Test/admin helper."""
    PROFILES[profile.name] = profile
