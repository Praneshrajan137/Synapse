"""SYNAPSE idempotency middleware — Redis-backed `Idempotency-Key` header.

Replaying a write request with the same key inside the TTL window returns the
cached response and stamps `X-Idempotent-Replay: true`. A second request that
shares the key but carries a different body fails 422 — duplicate-key races
must surface, never silently overwrite.

ADR-029. Honours I-7 (graceful degradation): if Redis is unreachable the
middleware degrades open and writes a structured warning to the audit log;
critical decisions never block on the cache.

Usage::

    from synapse_common.idempotency import IdempotencyMiddleware
    app.add_middleware(IdempotencyMiddleware, redis_url=...)

The middleware only touches mutating verbs (POST/PUT/PATCH/DELETE) and only
when the client supplies an `Idempotency-Key` header — read-only traffic and
unkeyed traffic are passed through unchanged.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger(__name__)

DEFAULT_TTL_SECONDS = 24 * 60 * 60  # 24 h
MUTATING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HEADER = "Idempotency-Key"
REPLAY_HEADER = "X-Idempotent-Replay"


def _hash_body(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _key(tenant: str, idem_key: str) -> str:
    return f"idem:{tenant}:{idem_key}"


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware enforcing `Idempotency-Key` on mutating endpoints."""

    def __init__(
        self,
        app: Any,
        redis_url: str = "redis://localhost:6379/0",
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        tenant_header: str = "X-Tenant-Id",
        default_tenant: str = "default",
    ) -> None:
        super().__init__(app)
        self._redis_url = redis_url
        self._ttl = ttl_seconds
        self._tenant_header = tenant_header
        self._default_tenant = default_tenant
        self._client: Any = None  # lazy

    def _get_redis(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import redis  # type: ignore[import-untyped]

            self._client = redis.from_url(self._redis_url, decode_responses=True)
            return self._client
        except Exception as exc:  # noqa: BLE001 — degrade open per I-7
            logger.warning("idempotency_redis_unavailable", error=str(exc))
            return None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)
        idem_key = request.headers.get(HEADER)
        if not idem_key:
            return await call_next(request)

        # Buffer the body so we can hash it AND let downstream handlers consume it.
        body = await request.body()
        body_hash = _hash_body(body)
        tenant = request.headers.get(self._tenant_header, self._default_tenant)
        cache_key = _key(tenant, idem_key)

        client = self._get_redis()
        if client is None:
            logger.warning("idempotency_degrade_open", key=cache_key)
            return await self._call_with_buffered_body(request, call_next, body)

        try:
            cached = client.get(cache_key)
        except Exception as exc:  # noqa: BLE001 — degrade open
            logger.warning("idempotency_redis_get_failed", error=str(exc), key=cache_key)
            return await self._call_with_buffered_body(request, call_next, body)

        if cached:
            try:
                record: dict[str, Any] = json.loads(cached)
            except json.JSONDecodeError:
                record = {}
            if record.get("body_hash") != body_hash:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": "idempotency_key_conflict",
                        "detail": (
                            "Idempotency-Key reused with a different request body. "
                            "Either change the key or send the original body."
                        ),
                    },
                )
            return JSONResponse(
                status_code=int(record.get("status", 200)),
                content=record.get("payload"),
                headers={REPLAY_HEADER: "true"},
            )

        response = await self._call_with_buffered_body(request, call_next, body)
        await self._cache_response(client, cache_key, response, body_hash)
        return response

    async def _call_with_buffered_body(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
        body: bytes,
    ) -> Response:
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}

        request._receive = receive  # type: ignore[attr-defined]
        return await call_next(request)

    async def _cache_response(
        self,
        client: Any,
        cache_key: str,
        response: Response,
        body_hash: str,
    ) -> None:
        if response.status_code >= 500:
            return  # never cache failures
        try:
            chunks: list[bytes] = []
            async for chunk in response.body_iterator:  # type: ignore[attr-defined]
                if isinstance(chunk, bytes):
                    chunks.append(chunk)
                else:
                    chunks.append(str(chunk).encode("utf-8"))
            full_body = b"".join(chunks)

            try:
                payload: Any = json.loads(full_body) if full_body else None
            except json.JSONDecodeError:
                payload = full_body.decode("utf-8", errors="replace")

            record = {
                "body_hash": body_hash,
                "status": response.status_code,
                "payload": payload,
            }
            client.setex(cache_key, self._ttl, json.dumps(record, separators=(",", ":")))

            # Rebuild the response stream so the client still receives a body.
            async def regen() -> Any:
                yield full_body

            response.body_iterator = regen()  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            logger.warning("idempotency_cache_write_failed", error=str(exc), key=cache_key)


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "HEADER",
    "REPLAY_HEADER",
    "IdempotencyMiddleware",
]
