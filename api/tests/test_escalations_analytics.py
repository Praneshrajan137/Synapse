"""Escalation analytics endpoint tests (Sprint 19, ADR-047).

``GET /api/v1/escalations/analytics`` is the Standing Watch escalation-pressure
panel's data source: JWT-gated, a pure SQL aggregate over audit_escalations.
DB-free here — psycopg2.connect is faked so the aggregation/shape contract is
pinned without a live Postgres.
"""

from __future__ import annotations

from typing import Any

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from synapse_common.auth import Role

from api.middleware.jwt import manager
from api.routers import escalations


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://x:y@localhost/z")
    app = FastAPI()
    app.include_router(escalations.router, prefix="/api/v1/escalations")
    return TestClient(app)


def _bearer(role: Role) -> dict[str, str]:
    token, _exp = manager().sign_access(subject="tester", role=role)
    return {"Authorization": f"Bearer {token}"}


class _FakeCursor:
    def __init__(self, agg: tuple[Any, ...], reasons: list[tuple[Any, ...]]) -> None:
        self._agg = agg
        self._reasons = reasons
        self._last = ""

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        self._last = "reasons" if "escalation_reason, count" in sql else "agg"

    def fetchone(self) -> tuple[Any, ...]:
        return self._agg

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._reasons


class _FakeConn:
    def __init__(self, agg: tuple[Any, ...], reasons: list[tuple[Any, ...]]) -> None:
        self._cur = _FakeCursor(agg, reasons)

    def cursor(self) -> _FakeCursor:
        return self._cur

    def close(self) -> None: ...


def _install_db(
    monkeypatch: pytest.MonkeyPatch,
    agg: tuple[Any, ...],
    reasons: list[tuple[Any, ...]],
) -> None:
    monkeypatch.setattr(psycopg2, "connect", lambda *_a, **_k: _FakeConn(agg, reasons))


def test_analytics_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/escalations/analytics").status_code == 401


def test_analytics_rejects_bad_window(client: TestClient) -> None:
    assert (
        client.get(
            "/api/v1/escalations/analytics?window_hours=0", headers=_bearer(Role.VIEWER)
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/escalations/analytics?window_hours=9999", headers=_bearer(Role.VIEWER)
        ).status_code
        == 422
    )


def test_analytics_rejects_bad_city(client: TestClient) -> None:
    resp = client.get(
        "/api/v1/escalations/analytics?city=gotham", headers=_bearer(Role.VIEWER)
    )
    assert resp.status_code == 422


def test_analytics_shapes_aggregate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # (total, overridden, approved, rejected, modified, p50, p90, max)
    agg = (10, 6, 3, 2, 1, 1200.0, 5000.0, 9000)
    reasons = [("confidence_below_threshold", 5), ("guardrail_service_level", 3)]
    _install_db(monkeypatch, agg, reasons)

    resp = client.get("/api/v1/escalations/analytics", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 10
    assert body["overridden"] == 6
    assert body["pending"] == 4
    assert body["override_actions"] == {
        "approved": 3,
        "rejected": 2,
        "modified": 1,
        "none": 4,
    }
    assert body["resolution_time_ms"]["p50"] == pytest.approx(1200.0)
    assert body["resolution_time_ms"]["max"] == 9000
    assert body["top_reasons"][0] == {"reason": "confidence_below_threshold", "count": 5}
    assert body["window_hours"] == 24


def test_analytics_empty_window_is_zeroed_not_null(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A quiet window reads zeros (honest 'no escalations'), and resolution
    percentiles are null (no data) — never a fabricated number."""
    agg = (0, 0, 0, 0, 0, None, None, None)
    _install_db(monkeypatch, agg, [])
    resp = client.get(
        "/api/v1/escalations/analytics?city=bengaluru", headers=_bearer(Role.VIEWER)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["pending"] == 0
    assert body["resolution_time_ms"]["p50"] is None
    assert body["top_reasons"] == []
    assert body["city"] == "bengaluru"
