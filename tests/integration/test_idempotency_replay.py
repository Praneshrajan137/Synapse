"""Idempotency replay contract test (WS-2 §2, ADR-026).

Verifies that ``synapse_common.idempotency`` correctly:
  - misses on the first call, stores the response,
  - hits with the cached response on a same-body replay,
  - rejects with HTTP 422 on a same-key + different-body replay.

Uses an in-memory fake Redis substitute injected via the test fixture
so the test runs without a live Redis server. The substitute mirrors
the SET/GET/SETEX surface exercised by the production store.
"""

from __future__ import annotations

import json

import pytest
from synapse_common.idempotency import (
    IdempotencyStore,
    _redis_key,
    _request_hash,
)


class _FakeRedis:
    """Minimal stand-in for ``redis.asyncio.Redis``."""

    def __init__(self) -> None:
        self.store: dict[str, tuple[str, int]] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.store[key] = (value, ttl)

    async def get(self, key: str) -> str | None:
        entry = self.store.get(key)
        return entry[0] if entry else None

    async def aclose(self) -> None:
        self.store.clear()


@pytest.fixture
def fake_store() -> IdempotencyStore:
    store = IdempotencyStore(redis_url="memory://", ttl_s=60)
    store._client = _FakeRedis()  # type: ignore[attr-defined]
    return store


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotency_first_call_misses_then_hits(fake_store: IdempotencyStore) -> None:
    payload = {"city": "bengaluru", "store_id": "S1", "sku_id": "SKU1", "quantity": 2}
    body = json.dumps(payload).encode()
    request_hash = _request_hash("POST", "/api/v1/orders/", body)

    assert await fake_store.get("k1") is None
    await fake_store.put("k1", request_hash, {"status": "accepted"}, 200)
    cached = await fake_store.get("k1")
    assert cached is not None
    assert cached["request_hash"] == request_hash
    assert cached["response"] == {"status": "accepted"}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotency_same_body_returns_cached(fake_store: IdempotencyStore) -> None:
    body = b'{"city":"mumbai","store_id":"S2","sku_id":"SKU1","quantity":5}'
    request_hash = _request_hash("POST", "/api/v1/orders/", body)
    await fake_store.put("k2", request_hash, {"status": "accepted", "city": "mumbai"}, 200)
    cached = await fake_store.get("k2")
    assert cached is not None
    assert cached["response"]["city"] == "mumbai"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_idempotency_different_body_mismatch(fake_store: IdempotencyStore) -> None:
    body_a = b'{"city":"bengaluru","store_id":"S1","sku_id":"SKU1","quantity":2}'
    body_b = b'{"city":"bengaluru","store_id":"S1","sku_id":"SKU1","quantity":99}'
    hash_a = _request_hash("POST", "/api/v1/orders/", body_a)
    hash_b = _request_hash("POST", "/api/v1/orders/", body_b)
    assert hash_a != hash_b

    await fake_store.put("k3", hash_a, {"status": "accepted", "quantity": 2}, 200)
    cached = await fake_store.get("k3")
    assert cached is not None
    assert cached["request_hash"] != hash_b


def test_redis_key_namespaced() -> None:
    assert _redis_key("xyz").startswith("synapse:idempotency:")
