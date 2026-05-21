"""Tests for the Idempotency-Key middleware (Sprint 7, WS-2)."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from synapse_common.idempotency import (
    InMemoryStore,
    configure_store,
    idempotent,
)


@pytest.fixture
def app() -> FastAPI:
    configure_store(InMemoryStore())
    application = FastAPI()
    counter: dict[str, int] = {"calls": 0}

    @application.post("/echo")
    @idempotent(scope="echo")
    async def echo(payload: dict[str, Any], request: Request) -> dict[str, Any]:
        counter["calls"] += 1
        return {"received": payload, "calls": counter["calls"]}

    application.state.counter = counter
    return application


def test_first_call_executes(app: FastAPI) -> None:
    client = TestClient(app)
    resp = client.post(
        "/echo",
        json={"a": 1},
        headers={"Idempotency-Key": "k1"},
    )
    assert resp.status_code == 200
    assert resp.json()["calls"] == 1


def test_replay_returns_cached(app: FastAPI) -> None:
    client = TestClient(app)
    client.post("/echo", json={"a": 1}, headers={"Idempotency-Key": "k1"})
    resp = client.post("/echo", json={"a": 1}, headers={"Idempotency-Key": "k1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["calls"] == 1, "handler must NOT have run again"


def test_replay_with_different_body_is_422(app: FastAPI) -> None:
    client = TestClient(app)
    client.post("/echo", json={"a": 1}, headers={"Idempotency-Key": "k1"})
    resp = client.post("/echo", json={"a": 2}, headers={"Idempotency-Key": "k1"})
    assert resp.status_code == 422


def test_no_header_passes_through(app: FastAPI) -> None:
    client = TestClient(app)
    a = client.post("/echo", json={"a": 1})
    b = client.post("/echo", json={"a": 1})
    assert a.json()["calls"] == 1
    assert b.json()["calls"] == 2, "without header, every request executes"


def test_distinct_keys_execute_independently(app: FastAPI) -> None:
    client = TestClient(app)
    a = client.post("/echo", json={"a": 1}, headers={"Idempotency-Key": "k1"})
    b = client.post("/echo", json={"a": 1}, headers={"Idempotency-Key": "k2"})
    assert a.json()["calls"] == 1
    assert b.json()["calls"] == 2
