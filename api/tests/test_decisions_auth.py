"""API gateway auth + secret-handling tests (Plan v2, Phase 5).

The decisions router previously left read endpoints unauthenticated and carried a
hardcoded DB password as a DSN default. These tests pin the hardened contract:

  * every non-health endpoint requires a valid bearer token (401 without);
  * ``trigger`` requires the OPS role (403 for a VIEWER);
  * the DSN is fail-fast — an unset ``POSTGRES_DSN`` yields 503, never a silent
    fallback to an embedded credential.

The app under test mounts only the decisions router (no lifespan), so no Kafka /
Postgres connection is attempted at startup — auth is evaluated as a dependency
before any handler body runs.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.middleware.jwt import manager
from api.routers import decisions
from synapse_common.auth import Role


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Ensure no DSN leaks in from the environment so the fail-fast path is exercised.
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    app = FastAPI()
    app.include_router(decisions.router, prefix="/api/v1/decisions")
    return TestClient(app)


def _bearer(role: Role) -> dict[str, str]:
    token, _exp = manager().sign_access(subject="tester", role=role)
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------- #
# 401 — no token
# --------------------------------------------------------------------------- #
def test_recent_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/decisions/recent").status_code == 401


def test_get_decision_requires_auth(client: TestClient) -> None:
    assert client.get(f"/api/v1/decisions/{uuid4()}").status_code == 401


def test_trigger_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/decisions/", json={}).status_code == 401


def test_invalid_token_rejected(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/decisions/recent", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# 403 — insufficient role
# --------------------------------------------------------------------------- #
def test_trigger_forbidden_for_viewer(client: TestClient) -> None:
    resp = client.post("/api/v1/decisions/", json={}, headers=_bearer(Role.VIEWER))
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Auth passes — then fail-fast DSN (no embedded secret)
# --------------------------------------------------------------------------- #
def test_recent_authorized_then_dsn_fail_fast(client: TestClient) -> None:
    resp = client.get("/api/v1/decisions/recent", headers=_bearer(Role.VIEWER))
    # Auth passed (not 401/403); DB unconfigured => 503, never a silent default.
    assert resp.status_code == 503
    assert "POSTGRES_DSN" in resp.json()["detail"]


def test_viewer_can_read_but_not_trigger(client: TestClient) -> None:
    # VIEWER reaches the read handler (503 due to no DSN) but is blocked on trigger.
    assert client.get(
        "/api/v1/decisions/recent", headers=_bearer(Role.VIEWER)
    ).status_code == 503
    assert client.post(
        "/api/v1/decisions/", json={}, headers=_bearer(Role.VIEWER)
    ).status_code == 403
