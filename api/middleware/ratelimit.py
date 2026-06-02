"""Application-layer rate-limit middleware for the API gateway (ADR-042 follow-up).

Keys on the client IP and applies a token-bucket limit (``synapse_common.ratelimit``).
Liveness/observability paths are exempt so health checks and Prometheus scrapes are
never throttled. On limit, returns ``429`` with a ``Retry-After`` header.

Configuration (env):
  * ``SYNAPSE_RATELIMIT_RPS``   sustained requests/sec per IP (default 20)
  * ``SYNAPSE_RATELIMIT_BURST`` burst capacity per IP        (default 40)
  * ``SYNAPSE_RATELIMIT_ENABLED`` set to "0" to disable      (default on)
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from synapse_common.ratelimit import RateLimiter

logger = structlog.get_logger(__name__)

# Paths that must never be throttled (liveness, readiness, scrape, build chip).
_EXEMPT_PREFIXES = ("/health", "/ready", "/metrics", "/version")


def _client_key(request: Request) -> str:
    """Best client identifier: X-Forwarded-For first hop, else peer IP."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token-bucket per-IP rate limiting with a Retry-After 429."""

    def __init__(
        self,
        app: Callable[..., Awaitable[Response]],
        *,
        rate_per_sec: float | None = None,
        burst: float | None = None,
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        rate = rate_per_sec if rate_per_sec is not None else float(
            os.environ.get("SYNAPSE_RATELIMIT_RPS", "20")
        )
        cap = burst if burst is not None else float(
            os.environ.get("SYNAPSE_RATELIMIT_BURST", "40")
        )
        self._enabled = os.environ.get("SYNAPSE_RATELIMIT_ENABLED", "1") != "0"
        self._limiter = RateLimiter(rate_per_sec=rate, burst=cap)
        logger.info("ratelimit_installed", rate_per_sec=rate, burst=cap, enabled=self._enabled)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not self._enabled or request.url.path.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        allowed, retry_after = self._limiter.check(_client_key(request))
        if not allowed:
            retry_s = max(1, int(retry_after + 0.999))  # ceil to whole seconds
            logger.warning("ratelimited", client=_client_key(request), path=request.url.path)
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded", "retry_after": retry_s},
                headers={"Retry-After": str(retry_s)},
            )
        return await call_next(request)


__all__ = ["RateLimitMiddleware"]
