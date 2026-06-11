"""System posture endpoint tests (ADR-044 D4).

``GET /api/v1/system/posture`` is the DegradedBanner's data source: JWT-gated,
proxies the orchestrator, and fails HONESTLY (503 with a reason) when the
orchestrator is unreachable — it must never fabricate a green posture.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from synapse_common.auth import Role

from api.middleware.jwt import manager
from api.routers import system


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(system.router, prefix="/api/v1/system")
    return TestClient(app)


def _bearer(role: Role) -> dict[str, str]:
    token, _exp = manager().sign_access(subject="tester", role=role)
    return {"Authorization": f"Bearer {token}"}


def test_posture_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/system/posture").status_code == 401


def test_posture_orchestrator_down_is_honest_503(client: TestClient) -> None:
    """Default ORCHESTRATOR_URL is unresolvable in tests → httpx error →
    503 with the reason, NOT a fabricated healthy posture."""
    resp = client.get("/api/v1/system/posture", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 503
    assert "orchestrator unreachable" in resp.json()["detail"]


def test_posture_proxies_orchestrator_payload(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Success path: the gateway returns the orchestrator's posture verbatim
    (no reshaping — the orchestrator owns the schema)."""
    payload = {
        "brownout": {"bengaluru": "SHED_T4", "mumbai": "NONE"},
        "breakers": {"ollama": "open", "postgres": "closed"},
        "degraded": True,
    }

    class _FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict[str, Any]:
            return payload

    class _FakeClient:
        def __init__(self, **_: Any) -> None: ...

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None: ...

        async def get(self, url: str) -> _FakeResponse:
            assert url.endswith("/api/v1/status/posture")
            return _FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    resp = client.get("/api/v1/system/posture", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    assert resp.json() == payload


def test_posture_viewer_role_suffices(client: TestClient) -> None:
    """Posture is read-only — VIEWER must NOT need OPS. (403 here would mean
    the banner is invisible to exactly the operators who watch the wall.)"""
    resp = client.get("/api/v1/system/posture", headers=_bearer(Role.VIEWER))
    assert resp.status_code != 403
