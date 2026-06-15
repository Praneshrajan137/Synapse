"""Calibration endpoint tests (Sprint 17, ADR-046).

``GET /api/v1/system/calibration`` scores confidence against the realized
outcomes. It must: exclude synthetic by default (FE-INV-044), disclose n
(FE-INV-043), return null Brier on no evidence, and degrade to "no outcomes
yet" (not 503) before the decision_outcomes table is migrated.
"""

from __future__ import annotations

from typing import Any

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from synapse_common.auth import Role

from api.middleware.jwt import manager
from api.routers import system


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://x:y@localhost/z")
    app = FastAPI()
    app.include_router(system.router, prefix="/api/v1/system")
    return TestClient(app)


def _bearer(role: Role) -> dict[str, str]:
    token, _exp = manager().sign_access(subject="tester", role=role)
    return {"Authorization": f"Bearer {token}"}


class _FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]] | Exception) -> None:
        self._rows = rows

    def __enter__(self) -> _FakeCursor:
        return self

    def __exit__(self, *_: Any) -> bool:
        return False

    def execute(self, sql: str, params: tuple[Any, ...] | None = None) -> None:
        if isinstance(self._rows, Exception):
            raise self._rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        assert not isinstance(self._rows, Exception)
        return self._rows


class _FakeConn:
    def __init__(self, rows: list[tuple[Any, ...]] | Exception) -> None:
        self._cur = _FakeCursor(rows)

    def cursor(self) -> _FakeCursor:
        return self._cur

    def rollback(self) -> None: ...

    def close(self) -> None: ...


def _install_db(monkeypatch: pytest.MonkeyPatch, rows: list[tuple[Any, ...]] | Exception) -> None:
    monkeypatch.setattr(psycopg2, "connect", lambda *_a, **_k: _FakeConn(rows))


def test_calibration_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/system/calibration").status_code == 401


def test_calibration_excludes_synthetic_by_default(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        (0.95, "confirmed", False),
        (0.92, "diverged", False),
        (0.50, "unknown", False),
        (0.99, "confirmed", True),  # synthetic — excluded by default
    ]
    _install_db(monkeypatch, rows)
    resp = client.get("/api/v1/system/calibration", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    body = resp.json()
    assert body["include_synthetic"] is False
    assert body["n_total"] == 3  # synthetic dropped
    assert body["n_scored"] == 2  # unknown excluded from scored
    assert body["n_unknown"] == 1
    assert body["brier_score"] is not None
    assert len(body["bins"]) == 10


def test_calibration_includes_synthetic_when_asked(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [(0.95, "confirmed", False), (0.99, "confirmed", True)]
    _install_db(monkeypatch, rows)
    resp = client.get(
        "/api/v1/system/calibration?include_synthetic=true", headers=_bearer(Role.VIEWER)
    )
    assert resp.json()["n_total"] == 2


def test_calibration_empty_is_null_brier_not_zero(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_db(monkeypatch, [])
    body = client.get("/api/v1/system/calibration", headers=_bearer(Role.VIEWER)).json()
    assert body["n_total"] == 0
    assert body["brier_score"] is None  # honest: no evidence != perfect calibration


def test_calibration_missing_table_degrades_to_empty(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pre-migration: a missing decision_outcomes table reads 'no outcomes
    yet', NOT a 503 that would break the Standing Watch surface."""
    _install_db(monkeypatch, psycopg2.errors.UndefinedTable("relation does not exist"))
    resp = client.get("/api/v1/system/calibration", headers=_bearer(Role.VIEWER))
    assert resp.status_code == 200
    assert resp.json()["n_total"] == 0


def test_calibration_rejects_bad_window(client: TestClient) -> None:
    assert (
        client.get(
            "/api/v1/system/calibration?window_hours=0", headers=_bearer(Role.VIEWER)
        ).status_code
        == 422
    )
