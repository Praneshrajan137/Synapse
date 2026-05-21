"""
SYNAPSE Idempotency-Key middleware (WS-2 §2, ADR-026).

POST/PUT/PATCH endpoints that mutate state read an ``Idempotency-Key``
header (UUID). The (key, request-hash) pair is stored in Redis with a
24 h TTL. Replay semantics:

  - same key + same body  → return cached response (cheap fast path)
  - same key + diff body  → HTTP 422 (caller bug)
  - missing key           → HTTP 400 (caller bug)

The implementation is deliberately Redis-backed: an in-process LRU
cache would not survive an orchestrator restart, breaking the outbox-
after-crash invariant (WS-2 §3 acceptance test).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import structlog
from fastapi import HTTPException, Request, status

from synapse_common.metrics import IDEMPOTENT_HIT_TOTAL

logger = structlog.get_logger(__name__)


IDEMPOTENCY_TTL_S: int = int(os.environ.get("SYNAPSE_IDEMPOTENCY_TTL_S", str(24 * 3600)))
REDIS_URL: str = os.environ.get("SYNAPSE_REDIS_URL", "redis://redis:6379/0")


class IdempotencyError(HTTPException):
    """Raised when an Idempotency-Key contract is violated."""


def _canonical_body(body: bytes) -> str:
    """Return a canonical JSON form of ``body`` for hashing.

    Falls back to the raw bytes hash if the body is not valid JSON.
    """
    if not body:
        return ""
    try:
        decoded = json.loads(body.decode("utf-8"))
        return json.dumps(decoded, sort_keys=True, separators=(",", ":"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return hashlib.sha256(body).hexdigest()


def _request_hash(method: str, path: str, body: bytes) -> str:
    """Deterministic SHA-256 over method+path+canonical-body."""
    canon = _canonical_body(body)
    h = hashlib.sha256()
    h.update(method.upper().encode("utf-8"))
    h.update(b"\x1f")
    h.update(path.encode("utf-8"))
    h.update(b"\x1f")
    h.update(canon.encode("utf-8"))
    return h.hexdigest()


def _redis_key(idempotency_key: str) -> str:
    return f"synapse:idempotency:{idempotency_key}"


class IdempotencyStore:
    """Redis-backed (key, request_hash) → response cache."""

    def __init__(self, redis_url: str = REDIS_URL, ttl_s: int = IDEMPOTENCY_TTL_S) -> None:
        self._redis_url = redis_url
        self._ttl_s = ttl_s
        self._client: Any = None

    async def _ensure_client(self) -> Any:  # noqa: ANN401
        if self._client is not None:
            return self._client
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("redis>=5.0 (asyncio) required for idempotency") from exc
        self._client = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._client

    async def get(self, idempotency_key: str) -> dict[str, Any] | None:
        client = await self._ensure_client()
        raw = await client.get(_redis_key(idempotency_key))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[no-any-return]

    async def put(
        self,
        idempotency_key: str,
        request_hash: str,
        response_body: dict[str, Any],
        status_code: int,
    ) -> None:
        client = await self._ensure_client()
        entry = {
            "request_hash": request_hash,
            "status_code": status_code,
            "response": response_body,
        }
        await client.setex(
            _redis_key(idempotency_key),
            self._ttl_s,
            json.dumps(entry, sort_keys=True, separators=(",", ":")),
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


_DEFAULT_STORE: IdempotencyStore | None = None


def get_store() -> IdempotencyStore:
    """Return the process-wide store singleton."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = IdempotencyStore()
    return _DEFAULT_STORE


async def enforce_idempotency(request: Request) -> tuple[str, str] | None:
    """FastAPI dependency. Returns ``(idempotency_key, request_hash)`` on miss.

    On a cache hit, returns ``None`` after setting ``request.state.idempotent_response``.
    The route handler should consult ``request.state`` and short-circuit when set.

    The store is keyed per ``Idempotency-Key`` header value. Routes that
    require idempotency should ``Depends(enforce_idempotency)`` and call
    ``record_idempotent_response`` after they've produced a response body.
    """
    key = request.headers.get("Idempotency-Key")
    if not key:
        IDEMPOTENT_HIT_TOTAL.labels(outcome="missing_key").inc()
        raise IdempotencyError(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required",
        )

    body = await request.body()
    request._body = body  # type: ignore[attr-defined,misc,unused-ignore]
    request_hash = _request_hash(request.method, request.url.path, body)

    cached = await get_store().get(key)
    if cached is None:
        IDEMPOTENT_HIT_TOTAL.labels(outcome="miss").inc()
        request.state.idempotency_key = key
        request.state.idempotency_request_hash = request_hash
        return key, request_hash

    if cached["request_hash"] != request_hash:
        IDEMPOTENT_HIT_TOTAL.labels(outcome="mismatch").inc()
        raise IdempotencyError(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Idempotency-Key reused with a different request body",
        )

    IDEMPOTENT_HIT_TOTAL.labels(outcome="hit").inc()
    request.state.idempotent_response = cached
    return None


async def record_idempotent_response(
    idempotency_key: str,
    request_hash: str,
    response_body: dict[str, Any],
    status_code: int = 200,
) -> None:
    """Persist a route's response under its ``Idempotency-Key``."""
    await get_store().put(idempotency_key, request_hash, response_body, status_code)
