"""System autonomy endpoint tests (ADR-053).

``GET /api/v1/system/autonomy`` is the Autonomy Spine's data source: JWT-gated
(VIEWER), it joins the orchestrator SensorLoop status with the twin's live
per-city world_state. It must degrade HONESTLY — an unreachable part resolves to
null with ``degraded=true``, and only a total blackout is a 503. It must never
fabricate a healthy world, and a stalled sim clock must read degraded.
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


def _install_fake_httpx(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sensor: dict[str, Any] | None,
    worlds: dict[str, dict[str, Any] | None],
) -> None:
    """Route the autonomy endpoint's two AsyncClient reads to canned payloads.

    ``sensor=None`` simulates an unreachable orchestrator; a world value of
    ``None`` simulates an unreachable / missing world for that city.
    """

    class _Resp:
        def __init__(self, status: int, body: Any) -> None:
            self.status_code = status
            self._body = body

        def json(self) -> Any:
            return self._body

    class _FakeClient:
        def __init__(self, **_: Any) -> None: ...

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None: ...

        async def get(self, url: str, params: dict[str, Any] | None = None) -> _Resp:
            if url.endswith("/api/v1/status/autonomy"):
                if sensor is None:
                    raise httpx.ConnectError("orchestrator down")
                return _Resp(200, sensor)
            if url.endswith("/world/state"):
                city = (params or {}).get("city")
                state = worlds.get(str(city))
                if state is None:
                    return _Resp(404, {"detail": "no world"})
                return _Resp(200, state)
            raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)


def _world(city: str, *, clock_advancing: bool = True) -> dict[str, Any]:
    return {
        "city": city,
        "sim_time_min": 120.0,
        "inventory": {"SKU-1": 55.0},
        "pending_orders": 2,
        "fill_rate": 0.98,
        "spoilage_rate": 0.01,
        "avg_delivery_min": 9.0,
        "restocks_triggered": 3,
        "demand_rate": 1.2,
        "clock_advancing": clock_advancing,
        "is_synthetic": True,
        "as_of": "2026-07-20T00:00:00Z",
    }


def test_autonomy_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/system/autonomy").status_code == 401


def test_autonomy_total_blackout_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, sensor=None, worlds={"bengaluru": None, "mumbai": None})
    resp = client.get("/api/v1/system/autonomy?city=bengaluru", headers=_bearer(Role.VIEWER))
    # city=bengaluru narrows to one city; sensor down + world down = blind = 503.
    assert resp.status_code == 503


def test_autonomy_success_joins_sensor_and_world(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    sensor = {"running": True, "cities": ["bengaluru"], "polls": 40, "decisions_triggered": 5}
    _install_fake_httpx(monkeypatch, sensor=sensor, worlds={"bengaluru": _world("bengaluru")})
    resp = client.get("/api/v1/system/autonomy?city=bengaluru", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["sensor"]["decisions_triggered"] == 5
    assert body["worlds"]["bengaluru"]["fill_rate"] == 0.98
    assert body["degraded"] is False
    assert "as_of" in body


def test_autonomy_stalled_clock_is_degraded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A world whose sim clock has stalled is degraded (I-7) — never healthy."""
    sensor = {"running": True, "cities": ["bengaluru"], "polls": 40, "decisions_triggered": 5}
    _install_fake_httpx(
        monkeypatch, sensor=sensor, worlds={"bengaluru": _world("bengaluru", clock_advancing=False)}
    )
    resp = client.get("/api/v1/system/autonomy?city=bengaluru", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    assert resp.json()["degraded"] is True


def test_autonomy_sensor_down_but_world_up_is_partial_not_blind(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_httpx(monkeypatch, sensor=None, worlds={"bengaluru": _world("bengaluru")})
    resp = client.get("/api/v1/system/autonomy?city=bengaluru", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["sensor"] is None
    assert body["degraded"] is True
    assert body["worlds"]["bengaluru"] is not None


def test_autonomy_viewer_role_suffices(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_httpx(monkeypatch, sensor={"running": True}, worlds={"bengaluru": _world("bengaluru")})
    resp = client.get("/api/v1/system/autonomy?city=bengaluru", headers=_bearer(Role.VIEWER))
    assert resp.status_code != 403
