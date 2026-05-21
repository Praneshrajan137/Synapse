"""
SYNAPSE Idempotency-Key Middleware (WS-2).

Implements the ``Idempotency-Key`` HTTP header pattern (Stripe / IETF
draft-ietf-httpapi-idempotency-key). On retried requests with the same key
+ same body hash, returns the cached response. On same key + different
body, returns 422 Unprocessable Entity (replay-attack guard).

Storage backends
----------------
* ``InMemoryStore`` -- per-process dict, used for tests and single-replica
  dev. TTL enforced lazily on read.
* ``RedisStore`` -- production. Keys are SHA-256(idempotency_key); values
  hold the request body hash + the cached response payload + expiry.

Usage
-----
    from synapse_common.idempotency import idempotent, configure_store

    configure_store(RedisStore(redis_client))

    @router.post("/orders")
    @idempotent(scope="orders")
    async def create_order(req: OrderRequest, request: Request) -> dict:
        ...

The decorator looks up the ``Idempotency-Key`` header from the FastAPI
``Request`` parameter, hashes the body, and short-circuits on a match.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeVar

import structlog
from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = structlog.get_logger(__name__)

T = TypeVar("T")

DEFAULT_TTL_SECONDS = 24 * 3600
HEADER = "Idempotency-Key"


@dataclass(frozen=True)
class CachedResponse:
    body_hash: str
    response_json: str
    expires_at: float


class IdempotencyStore(Protocol):
    async def get(self, key: str) -> CachedResponse | None: ...
    async def set(self, key: str, value: CachedResponse) -> None: ...


class InMemoryStore:
    """Process-local store. Not safe across replicas."""

    def __init__(self) -> None:
        self._data: dict[str, CachedResponse] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> CachedResponse | None:
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.expires_at < time.time():
                self._data.pop(key, None)
                return None
            return entry

    async def set(self, key: str, value: CachedResponse) -> None:
        async with self._lock:
            self._data[key] = value


class RedisStore:
    """Redis-backed store. Pass an ``aioredis``/``redis.asyncio`` client."""

    def __init__(self, redis_client: Any, prefix: str = "synapse:idem:") -> None:
        self._redis = redis_client
        self._prefix = prefix

    def _full_key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> CachedResponse | None:
        raw = await self._redis.get(self._full_key(key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        return CachedResponse(
            body_hash=data["body_hash"],
            response_json=data["response_json"],
            expires_at=data["expires_at"],
        )

    async def set(self, key: str, value: CachedResponse) -> None:
        payload = json.dumps(
            {
                "body_hash": value.body_hash,
                "response_json": value.response_json,
                "expires_at": value.expires_at,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        ttl = max(int(value.expires_at - time.time()), 1)
        await self._redis.set(self._full_key(key), payload, ex=ttl)


_STORE: IdempotencyStore = InMemoryStore()


def configure_store(store: IdempotencyStore) -> None:
    """Swap the global idempotency store. Call once on app startup."""
    global _STORE  # noqa: PLW0603
    _STORE = store


def _hash_body(scope: str, method: str, path: str, body: bytes) -> str:
    h = hashlib.sha256()
    h.update(scope.encode("utf-8"))
    h.update(b"\n")
    h.update(method.encode("utf-8"))
    h.update(b"\n")
    h.update(path.encode("utf-8"))
    h.update(b"\n")
    h.update(body)
    return h.hexdigest()


def idempotent(
    *,
    scope: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Decorator that enforces Idempotency-Key on a FastAPI handler.

    The decorated handler MUST accept a ``request: Request`` parameter so we
    can read headers + body. Handlers without an ``Idempotency-Key`` header
    pass through untouched (idempotency is opt-in by the client).
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            request: Request | None = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
            if request is None:
                # No Request available; cannot enforce. Fail loudly so the
                # decorator isn't silently a no-op in production.
                raise RuntimeError(
                    "@idempotent requires the FastAPI handler to accept a "
                    "'request: Request' parameter"
                )
            key = request.headers.get(HEADER)
            if not key:
                return await func(*args, **kwargs)

            body = await request.body()
            body_hash = _hash_body(scope, request.method, request.url.path, body)

            cached = await _STORE.get(key)
            if cached is not None:
                if cached.body_hash != body_hash:
                    logger.warning(
                        "idempotency_key_reuse_with_different_body",
                        key=key,
                        scope=scope,
                    )
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Idempotency-Key reused with a different request body."
                        ),
                    )
                logger.info("idempotency_replay_served", scope=scope)
                return json.loads(cached.response_json)  # type: ignore[no-any-return]

            response = await func(*args, **kwargs)

            try:
                response_json = json.dumps(
                    response,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                await _STORE.set(
                    key,
                    CachedResponse(
                        body_hash=body_hash,
                        response_json=response_json,
                        expires_at=time.time() + ttl_seconds,
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                # Caching failure must not break the handler. Log and move on;
                # the worst case is a duplicate execution on retry.
                logger.warning(
                    "idempotency_cache_failed", scope=scope, error=str(exc)
                )
            return response

        return wrapper

    return decorator
