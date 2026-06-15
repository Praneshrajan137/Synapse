"""Shared readiness/health helper (Sprint 20, PR-2).

Before this, every agent's ``/health`` returned ``{"status": "healthy"}`` with HTTP
200 unconditionally — so the Dockerfile ``HEALTHCHECK`` (and the compose probe that
the C47/C50 deploy gates lean on) proved only that the HTTP port answers, NOT that
the service is actually ready. A crash-looped-but-port-up or pipeline-failed service
reported healthy. This helper makes readiness honest: HTTP 503 when not ready, 200
when ready, with a ``degraded`` middle state for "serving but a non-critical
dependency is down" (e.g. Kafka down → the orchestrator still answers tier-1/2
decisions, so it is degraded, not unready).
"""

from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse


def readiness_response(
    component: str,
    *,
    ready: bool,
    degraded: bool = False,
    **checks: Any,
) -> JSONResponse:
    """Build a standard readiness response.

    Args:
        component: the service/agent name (e.g. ``"orchestrator"``).
        ready: False → HTTP 503 (the probe fails, marking the container unhealthy).
            True → HTTP 200.
        degraded: only meaningful when ``ready`` is True; sets ``status="degraded"``
            so operators can see "serving, but a non-critical dependency is down".
        **checks: per-dependency booleans/strings surfaced in the body for operators
            (e.g. ``database=True, kafka="degraded"``).
    """
    if not ready:
        status = "unready"
    elif degraded:
        status = "degraded"
    else:
        status = "healthy"
    payload: dict[str, Any] = {"status": status, "component": component, "ready": ready}
    payload.update(checks)
    return JSONResponse(status_code=200 if ready else 503, content=payload)


__all__ = ["readiness_response"]
