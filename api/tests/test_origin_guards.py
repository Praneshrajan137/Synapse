"""F2 (ADR-050): CORS allow-list + trusted-host filter on the API gateway.

Builds a minimal app and installs the real ``_install_origin_guards`` with
controlled env (the same isolation pattern as test_ratelimit_middleware), so the
behaviour is verified without standing up the full gateway.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.main import _install_origin_guards


def _build(
    monkeypatch: object,
    *,
    origins: str | None = None,
    hosts: str | None = None,
) -> FastAPI:
    mp = monkeypatch
    if origins is not None:
        mp.setenv("SYNAPSE_ALLOWED_ORIGINS", origins)  # type: ignore[attr-defined]
    else:
        mp.delenv("SYNAPSE_ALLOWED_ORIGINS", raising=False)  # type: ignore[attr-defined]
    if hosts is not None:
        mp.setenv("SYNAPSE_ALLOWED_HOSTS", hosts)  # type: ignore[attr-defined]
    else:
        mp.delenv("SYNAPSE_ALLOWED_HOSTS", raising=False)  # type: ignore[attr-defined]
    app = FastAPI()
    _install_origin_guards(app)

    @app.get("/ping")
    def ping() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_cors_allows_listed_origin(monkeypatch: object) -> None:
    client = TestClient(_build(monkeypatch, origins="http://localhost:5173"))
    r = client.get("/ping", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_does_not_echo_unlisted_origin(monkeypatch: object) -> None:
    client = TestClient(_build(monkeypatch, origins="http://localhost:5173"))
    r = client.get("/ping", headers={"Origin": "http://evil.example"})
    # The request itself still completes (CORS is browser-enforced) but the
    # gateway must never echo the hostile origin into Access-Control-Allow-Origin.
    assert r.headers.get("access-control-allow-origin") != "http://evil.example"


def test_trustedhost_rejects_bad_host(monkeypatch: object) -> None:
    client = TestClient(
        _build(monkeypatch, hosts="trusted.example"), base_url="http://evil.example"
    )
    assert client.get("/ping").status_code == 400


def test_trustedhost_allows_good_host(monkeypatch: object) -> None:
    client = TestClient(
        _build(monkeypatch, hosts="trusted.example"), base_url="http://trusted.example"
    )
    assert client.get("/ping").status_code == 200


def test_default_hosts_wildcard_allows_any(monkeypatch: object) -> None:
    # Tier-D default is "*" (no-op); a deploy host is never accidentally blocked.
    client = TestClient(_build(monkeypatch), base_url="http://anything.example")
    assert client.get("/ping").status_code == 200
