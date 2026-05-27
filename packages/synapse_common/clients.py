"""
SYNAPSE Bulkheaded HTTP Clients (WS-1).

One ``httpx.AsyncClient`` per upstream dependency, with explicit connection
limits. Prevents head-of-line blocking: a slow Pinecone call cannot starve
the Ollama pool, and vice-versa. Each client is created lazily, kept open
for the process lifetime, and closed by ``synapse_common.lifespan.graceful_shutdown``.

The pool sizes here are conservative defaults tuned for the docker-compose
stack. Override per-deployment via env (``SYNAPSE_HTTPX_<NAME>_MAX``).

Usage
-----
    client = await get_client("ollama")
    resp = await client.post("/api/chat", json=payload)
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import httpx
import structlog

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = structlog.get_logger(__name__)


class BulkheadConfig:
    """Per-dependency bulkhead pool sizing."""

    __slots__ = ("name", "max_connections", "max_keepalive", "timeout_seconds")

    def __init__(
        self,
        name: str,
        max_connections: int,
        max_keepalive: int,
        timeout_seconds: float,
    ) -> None:
        self.name = name
        self.max_connections = max_connections
        self.max_keepalive = max_keepalive
        self.timeout_seconds = timeout_seconds


_DEFAULT_CONFIGS: dict[str, BulkheadConfig] = {
    # Ollama on shared GPU; concurrent requests serialize on the GPU anyway.
    "ollama": BulkheadConfig("ollama", max_connections=8, max_keepalive=4, timeout_seconds=120.0),
    # Pinecone — semantic cache; high QPS, small payloads.
    "pinecone": BulkheadConfig(
        "pinecone", max_connections=32, max_keepalive=16, timeout_seconds=10.0
    ),
    # A2A — agent-to-agent; tier-4 decisions can take 120s.
    "a2a": BulkheadConfig("a2a", max_connections=64, max_keepalive=32, timeout_seconds=120.0),
    # Orchestrator — API gateway -> orchestrator hop.
    "orchestrator": BulkheadConfig(
        "orchestrator", max_connections=32, max_keepalive=16, timeout_seconds=120.0
    ),
    # Generic / unspecified.
    "default": BulkheadConfig("default", max_connections=16, max_keepalive=8, timeout_seconds=30.0),
}


def _config_for(name: str) -> BulkheadConfig:
    base = _DEFAULT_CONFIGS.get(name) or _DEFAULT_CONFIGS["default"]
    env_max = os.environ.get(f"SYNAPSE_HTTPX_{name.upper()}_MAX")
    if env_max is not None:
        try:
            override = int(env_max)
            return BulkheadConfig(
                name=base.name,
                max_connections=override,
                max_keepalive=min(override, base.max_keepalive),
                timeout_seconds=base.timeout_seconds,
            )
        except ValueError:
            logger.warning("bulkhead_env_invalid", name=name, value=env_max)
    return base


_REGISTRY: dict[str, httpx.AsyncClient] = {}
_REGISTRY_LOCK = asyncio.Lock()


def _build_client(config: BulkheadConfig) -> httpx.AsyncClient:
    limits = httpx.Limits(
        max_connections=config.max_connections,
        max_keepalive_connections=config.max_keepalive,
    )
    return httpx.AsyncClient(timeout=config.timeout_seconds, limits=limits)


async def get_client(name: str) -> httpx.AsyncClient:
    """Return the bulkheaded client for a named dependency.

    First call creates and registers the client; subsequent calls reuse it.
    Safe to call concurrently.
    """
    existing = _REGISTRY.get(name)
    if existing is not None:
        return existing
    async with _REGISTRY_LOCK:
        existing = _REGISTRY.get(name)
        if existing is not None:
            return existing
        config = _config_for(name)
        client = _build_client(config)
        _REGISTRY[name] = client
        logger.info(
            "bulkhead_client_created",
            name=name,
            max_connections=config.max_connections,
            max_keepalive=config.max_keepalive,
            timeout_seconds=config.timeout_seconds,
        )
        return client


def registered_names() -> Iterable[str]:
    return tuple(_REGISTRY.keys())


async def close_all() -> None:
    """Close every registered client. Called by graceful_shutdown."""
    async with _REGISTRY_LOCK:
        clients = list(_REGISTRY.items())
        _REGISTRY.clear()
    for name, client in clients:
        try:
            await client.aclose()
        except Exception as exc:  # noqa: BLE001
            logger.warning("bulkhead_close_failed", name=name, error=str(exc))


async def reset_registry() -> None:
    """Test helper: close + clear all clients."""
    await close_all()


# Sprint 11 WS-2: api/main.py lifespan imports `close_clients` from this
# module. The canonical name in this file has always been `close_all`;
# the alias keeps both names valid without breaking either call site.
close_clients = close_all
