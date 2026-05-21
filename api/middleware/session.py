"""Session resolution + auth gate middleware (Atlas Console BFF).

Companion to ``api/routers/auth.py``. Where ``auth.py`` owns the lifecycle
of a session, this middleware does three things on every request:

1. **Resolve** the opaque session cookie (if present) and stash the parsed
   payload at ``request.state.session``. Downstream routers read it
   without re-implementing Redis access.

2. **Inject** the server-side JWT into the upstream ``Authorization`` header
   when the gateway proxies a call to the orchestrator (``/api/v1/decisions``,
   ``/a2a``). The browser never sees the token.

3. **Gate** protected paths. Configurable via ``PROTECTED_PREFIXES`` —
   paths under those prefixes return 401 without a valid session. Public
   paths (``/health``, ``/ready``, ``/metrics``, ``/auth/*``, ``/openapi.json``)
   bypass.

Why a middleware (not a global Depends())?
-----------------------------------------
- SSE responses (``api/routers/sse.py``) detach early; a Depends() would
  consume the session lookup but the streaming generator wouldn't see it.
  Middleware runs before the response object is finalised, so it works
  for both regular and streaming responses.
- A single resolution point keeps DPDPA auth-event logging coherent.

Performance
-----------
Redis lookup is a single ``GET`` on a hot key. We do **not** cache the
parsed payload in a request-scoped attribute beyond the request lifetime
— a stale session must be discovered on the next call after a logout.
"""

from __future__ import annotations

import json
import os
from collections.abc import Awaitable, Callable
from typing import Any, Final

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)

SESSION_COOKIE_NAME: Final = "synapse_session"
SESSION_REDIS_DB: Final = int(os.environ.get("SYNAPSE_SESSION_REDIS_DB", "2"))

# Paths that require a valid session. Order matters — first match wins.
# Anything under /api/v1/ is gated except the explicit allow-list.
PROTECTED_PREFIXES: Final[tuple[str, ...]] = (
    "/api/v1/decisions",
    "/api/v1/orders",
    "/api/v1/agents",
    "/api/v1/stream",
    "/api/v1/audit",
)

PUBLIC_EXACT: Final[frozenset[str]] = frozenset(
    {"/health", "/ready", "/metrics", "/openapi.json", "/docs", "/redoc"}
)

PUBLIC_PREFIXES: Final[tuple[str, ...]] = (
    "/auth/",
    "/static/",
    # RUM ingest (B4) + CSP report-to (B7). See api/routers/rum.py — must
    # be reachable BEFORE login so the very first paint of the login page
    # can beacon LCP, and a CSP violation on a logged-out page can report.
    "/api/v1/rum",
)


def _redis_client() -> Any:
    import redis  # type: ignore[import-not-found]

    return redis.Redis.from_url(
        os.environ.get("SYNAPSE_REDIS_URL", "redis://redis:6379"),
        db=SESSION_REDIS_DB,
        decode_responses=True,
    )


def _is_public(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


def _is_protected(path: str) -> bool:
    return any(path.startswith(p) for p in PROTECTED_PREFIXES)


class SessionMiddleware(BaseHTTPMiddleware):
    """Resolve session, gate protected paths, inject JWT for upstream proxies."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path

        # Public path: never even peek at the cookie.
        if _is_public(path):
            return await call_next(request)

        sid = request.cookies.get(SESSION_COOKIE_NAME)
        session_payload: dict[str, Any] | None = None
        if sid:
            try:
                raw = _redis_client().get(f"atlas:session:{sid}")
                if raw is not None:
                    session_payload = json.loads(raw)
            except Exception as exc:  # noqa: BLE001
                # Fail open on session-store outage so the rest of the gateway
                # remains diagnosable; the audit gate (DPDPA) handles its own
                # finer-grained checks. Surface in logs.
                logger.warning("session_read_failed", path=path, error=str(exc))

        if session_payload is not None:
            request.state.session = session_payload
            # Forward the server-side JWT to upstream proxies. Routers like
            # decisions.trigger_decision use ``requests.post`` to talk to the
            # orchestrator; they read this header off the request and pass it
            # along (next session: extend decisions.py to honour it).
            jwt = session_payload.get("jwt")
            if jwt:
                # Starlette's request.headers is immutable; stash the JWT on
                # request.state for downstream routers to consume.
                request.state.upstream_authorization = f"Bearer {jwt}"

        if _is_protected(path) and session_payload is None:
            return JSONResponse(
                {"detail": "not authenticated"},
                status_code=401,
                headers={"WWW-Authenticate": "Cookie"},
            )

        return await call_next(request)
