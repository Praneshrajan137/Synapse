"""ADR-057: in open mode a ``view`` preview grant changes nothing, and an ``act`` grant does what
OPS may; ``POST /api/v1/orders/`` no longer accepts an anonymous call (finding 89).

The app mounts the auth, orders, decisions and steering routers without the gateway lifespan
and without Postgres, so an ACCEPTED call runs its handler and stops at the missing
infrastructure with an honest 503. That status is the proof the dependency let it through; a
refusal is 401 or 403 before any handler body runs.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.access import ACCESS_MODE_ENV, OPEN_AUTHORITY_ENV
from api.routers import auth, decisions, orders, steering
from orchestrator.inference.serve import EDGE_FORWARDING_HEADERS

ORDER = {
    "city": "bengaluru",
    "store_id": "STORE_BLR_001",
    "sku_id": "SKU_DAIRY_001",
    "quantity": 2,
}
OVERRIDE = {"action": "approved", "reason": "preview authority probe"}
#: Every operator mutation the gateway serves: (name, path, body).
MUTATIONS = [
    ("order", "/api/v1/orders/", ORDER),
    ("steering", "/api/v1/steering/", {"action": "reset"}),
    ("trigger", "/api/v1/decisions/", {"order_id": "preview-authority-probe"}),
    ("override", f"/api/v1/decisions/{uuid4()}/override", OVERRIDE),
]
#: The mutations whose handler stops at missing Postgres (the trigger is proven separately).
STOPS_AT_POSTGRES = [mutation for mutation in MUTATIONS if mutation[0] != "trigger"]


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    for name in ("POSTGRES_DSN", ACCESS_MODE_ENV, OPEN_AUTHORITY_ENV):
        monkeypatch.delenv(name, raising=False)
    app = FastAPI()
    app.include_router(auth.router, prefix="/api/v1/auth")
    app.include_router(orders.router, prefix="/api/v1/orders")
    app.include_router(decisions.router, prefix="/api/v1/decisions")
    app.include_router(steering.router, prefix="/api/v1/steering")
    return TestClient(app)


def _preview(client: TestClient, monkeypatch: pytest.MonkeyPatch, authority: str) -> dict[str, str]:
    monkeypatch.setenv(ACCESS_MODE_ENV, "open")
    monkeypatch.setenv(OPEN_AUTHORITY_ENV, authority)
    resp = client.post("/api/v1/auth/preview")
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.parametrize(("name", "path", "body"), MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_a_view_preview_grant_is_refused_by_every_mutation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    path: str,
    body: dict[str, Any],
) -> None:
    headers = _preview(client, monkeypatch, "view")
    resp = client.post(path, json=body, headers=headers)
    assert resp.status_code == 403, name
    assert resp.json()["detail"] == "role 'viewer' insufficient; need 'ops'"


@pytest.mark.parametrize(
    ("name", "path", "body"), STOPS_AT_POSTGRES, ids=[m[0] for m in STOPS_AT_POSTGRES]
)
def test_an_act_preview_grant_is_accepted_where_ops_is(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    path: str,
    body: dict[str, Any],
) -> None:
    headers = _preview(client, monkeypatch, "act")
    resp = client.post(path, json=body, headers=headers)
    assert resp.status_code == 503, (name, resp.text)


class _OrchestratorResponse:
    status_code = 200

    @staticmethod
    def json() -> dict[str, str]:
        return {"decision_id": "d-preview", "tier": "tier_1"}


class _RecordingOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    async def post(self, url: str, **kwargs: Any) -> _OrchestratorResponse:
        self.calls.append((url, dict(kwargs.get("headers") or {})))
        return _OrchestratorResponse()


def test_an_act_preview_grant_triggers_a_decision_over_the_internal_hop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    orchestrator = _RecordingOrchestrator()

    async def _client(_name: str) -> _RecordingOrchestrator:
        return orchestrator

    monkeypatch.setattr(decisions, "get_client", _client)
    headers = _preview(client, monkeypatch, "act")
    resp = client.post("/api/v1/decisions/", json={"order_id": "probe"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["decision_id"] == "d-preview"
    assert len(orchestrator.calls) == 1
    url, sent = orchestrator.calls[0]
    assert url.endswith("/api/v1/decisions")
    # The gateway's hop carries none of the headers the orchestrator's internal-only guard
    # reads as proof of an edge call (the one list it declares), so the guard admits it.
    edge_headers = {name.lower() for name in EDGE_FORWARDING_HEADERS}
    assert edge_headers, "the orchestrator's guard names no edge-forwarding header"
    assert edge_headers.isdisjoint(name.lower() for name in sent)


def test_an_anonymous_order_is_refused(client: TestClient) -> None:
    resp = client.post("/api/v1/orders/", json=ORDER)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "missing bearer token"
