"""SLO burn endpoint tests (Sprint 19, ADR-047).

``GET /api/v1/system/slo`` is the Standing Watch burn gauge's data source:
JWT-gated, computes multi-window burn from Prometheus, and reports ``source:
"unknown"`` + null windows when Prometheus is unreachable — it must NEVER
fabricate a healthy (green) burn (FE-INV-042).
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


def _prom_ok(value: float) -> dict[str, Any]:
    return {"status": "success", "data": {"result": [{"metric": {}, "value": [0, str(value)]}]}}


def test_slo_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/system/slo").status_code == 401


def test_slo_prometheus_unreachable_is_honest_unknown(client: TestClient) -> None:
    """Default PROM_URL is unresolvable in tests → every window null, source
    'unknown'. NOT a fabricated healthy burn."""
    resp = client.get("/api/v1/system/slo", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "unknown"
    t1 = body["tiers"]["tier_1"]
    assert t1["windows"]["fast"]["burn_rate"] is None
    assert t1["severity"] == "unknown"


def test_slo_computes_burn_and_severity(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """tier_1 with a 10% error over the latency target (budget 0.5%) burns at
    20x → critical; a clean tier reads ok. Burn = error / (1 - objective)."""

    class _FakeResponse:
        status_code = 200

        def __init__(self, value: float) -> None:
            self._value = value

        def raise_for_status(self) -> None: ...

        def json(self) -> dict[str, Any]:
            return _prom_ok(self._value)

    class _FakeClient:
        def __init__(self, **_: Any) -> None: ...

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None: ...

        async def get(self, url: str, params: dict[str, str] | None = None) -> _FakeResponse:
            query = (params or {}).get("query", "")
            # tier_1 fast window burns hot; everything else clean.
            if 'tier="tier_1"' in query and "[1h]" in query:
                return _FakeResponse(0.1)
            return _FakeResponse(0.0)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    resp = client.get("/api/v1/system/slo", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "prometheus"

    t1 = body["tiers"]["tier_1"]
    assert t1["windows"]["fast"]["error_rate"] == pytest.approx(0.1)
    assert t1["windows"]["fast"]["burn_rate"] == pytest.approx(0.1 / 0.005)  # 20x
    assert t1["severity"] == "critical"

    t2 = body["tiers"]["tier_2"]
    assert t2["windows"]["fast"]["burn_rate"] == pytest.approx(0.0)
    assert t2["severity"] == "ok"


def test_slo_viewer_role_suffices(client: TestClient) -> None:
    resp = client.get("/api/v1/system/slo", headers=_bearer(Role.VIEWER))
    assert resp.status_code != 403


def test_slo_objectives_match_burn_rule_budgets() -> None:
    """The endpoint's per-tier objective is the lockstep partner of the burn
    thresholds in orchestrator_burn.yml: fast_threshold = 14.4 * (1-objective)."""
    expected = {"tier_1": 0.072, "tier_2": 0.144, "tier_3": 0.432, "tier_4": 0.72}
    for tier, cfg in system._TIER_SLO.items():
        budget = 1.0 - cfg["objective"]
        assert pytest.approx(expected[tier], rel=1e-6) == 14.4 * budget
