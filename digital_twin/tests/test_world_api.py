"""Smoke tests for the ADR-052 world API on the digital-twin server (serve.py).

Runs with the auto-clock disabled and a manually-registered manual-tick world, so the
A2A/REST surface is exercised deterministically (no background thread, no timing races).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import digital_twin.inference.serve as serve
from digital_twin.world import WorldRuntime, register_runtime, reset_runtimes


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Don't let the lifespan spawn clock threads; we drive a manual world instead.
    monkeypatch.setattr(serve, "WORLD_ENABLED", False)
    with TestClient(serve.app) as c:
        reset_runtimes()
        register_runtime(WorldRuntime(city="bengaluru", seed=42).start(run_clock=False))
        yield c
        reset_runtimes()


def test_rest_world_state(client: TestClient) -> None:
    r = client.get("/world/state", params={"city": "bengaluru"})
    assert r.status_code == 200
    body = r.json()
    assert body["city"] == "bengaluru"
    assert body["is_synthetic"] is True
    assert len(body["inventory"]) == 10


def test_a2a_apply_action_reorder_mutates_world(client: TestClient) -> None:
    before = client.get("/world/state", params={"city": "bengaluru"}).json()["inventory"]["sku_0"]
    rpc = {
        "jsonrpc": "2.0", "id": "1", "method": "apply_action",
        "params": {
            "action_id": "a1", "kind": "reorder", "city": "bengaluru",
            "sku_id": "sku_0", "params": {"quantity": 250.0}, "decision_id": "dec-9",
        },
    }
    r = client.post("/a2a", json=rpc)
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["status"] == "applied"
    assert result["effect"]["new_level"] == before + 250.0


def test_a2a_world_state_unknown_city_is_honest_error(client: TestClient) -> None:
    rpc = {"jsonrpc": "2.0", "id": "2", "method": "world_state", "params": {"city": "atlantis"}}
    r = client.post("/a2a", json=rpc)
    assert r.status_code == 200  # JSON-RPC envelope is intact (I-7) ...
    assert r.json()["error"]["code"] == -32004  # ... with an honest "no world" error


def test_health_reports_world_liveness(client: TestClient) -> None:
    body = client.get("/health").json()
    assert "bengaluru" in body["worlds_advancing"]
