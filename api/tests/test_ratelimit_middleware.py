"""Integration test for the gateway rate-limit middleware.

Builds a minimal FastAPI app with only RateLimitMiddleware (so it does not need
the gateway's Postgres/Kafka lifespan) and verifies: a burst over the limit
returns 429 + Retry-After, and exempt liveness paths are never throttled.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.ratelimit import RateLimitMiddleware


def _app(rate: float, burst: float) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, rate_per_sec=rate, burst=burst)

    @app.get("/api/v1/thing")
    def thing() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def test_burst_over_limit_returns_429_with_retry_after() -> None:
    client = TestClient(_app(rate=1, burst=2))
    assert client.get("/api/v1/thing").status_code == 200
    assert client.get("/api/v1/thing").status_code == 200
    resp = client.get("/api/v1/thing")  # 3rd within the same instant → blocked
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert int(resp.headers["Retry-After"]) >= 1
    assert resp.json()["detail"] == "rate limit exceeded"


def test_health_path_is_exempt() -> None:
    client = TestClient(_app(rate=1, burst=1))
    # Hammer health well past the limit — never throttled.
    for _ in range(10):
        assert client.get("/health").status_code == 200


def test_disabled_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPSE_RATELIMIT_ENABLED", "0")
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, rate_per_sec=1, burst=1)

    @app.get("/api/v1/thing")
    def thing() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    for _ in range(5):
        assert client.get("/api/v1/thing").status_code == 200
