"""F1 (ADR-050): the firehose WebSocket auth gate.

Unit-tests the auth-decision helpers (the security-critical logic) with minted
RS256 tokens, plus an end-to-end reject of an unauthenticated connection when
enforcement is on. The FE token-passing + flipping the flag on is the
live-verified follow-up (needs the running stack); the backend control is proven
here.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from synapse_common.auth import Role

from api.middleware.jwt import manager
from api.routers import firehose as fh


class _FakeWS:
    def __init__(self, subprotocols: list[str] | None = None, token: str | None = None) -> None:
        self.scope: dict[str, Any] = {"subprotocols": subprotocols or []}
        self.query_params: dict[str, str] = {"token": token} if token else {}


def _viewer_token() -> str:
    tok, _ = manager().sign_access("viewer@test", Role.VIEWER)
    return tok


def test_auth_required_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNAPSE_FIREHOSE_AUTH_REQUIRED", raising=False)
    assert fh._firehose_auth_required() is False
    monkeypatch.setenv("SYNAPSE_FIREHOSE_AUTH_REQUIRED", "true")
    assert fh._firehose_auth_required() is True


def test_ws_token_prefers_subprotocol() -> None:
    tok, sub = fh._ws_token(_FakeWS(subprotocols=["synapse-jwt.abc123"]))
    assert tok == "abc123"
    assert sub == "synapse-jwt.abc123"


def test_ws_token_query_param_fallback() -> None:
    assert fh._ws_token(_FakeWS(token="xyz")) == ("xyz", None)


def test_ws_token_absent() -> None:
    assert fh._ws_token(_FakeWS()) == (None, None)


def test_authorize_rejects_missing_token() -> None:
    assert fh._authorize_ws(_FakeWS()) == (False, None)


def test_authorize_rejects_garbage_token() -> None:
    assert fh._authorize_ws(_FakeWS(token="not-a-jwt")) == (False, None)


def test_authorize_rejects_refresh_token() -> None:
    # A refresh token must not open the stream — verify(expected_type="access").
    tok, _ = manager().sign_refresh("viewer@test", Role.VIEWER)
    assert fh._authorize_ws(_FakeWS(token=tok)) == (False, None)


def test_authorize_accepts_valid_viewer_token() -> None:
    authorized, sub = fh._authorize_ws(_FakeWS(token=_viewer_token()))
    assert authorized is True
    assert sub is None


def test_authorize_accepts_viewer_via_subprotocol() -> None:
    tok = _viewer_token()
    authorized, sub = fh._authorize_ws(_FakeWS(subprotocols=[f"synapse-jwt.{tok}"]))
    assert authorized is True
    assert sub == f"synapse-jwt.{tok}"


def test_authorize_accepts_higher_role() -> None:
    tok, _ = manager().sign_access("ops@test", Role.OPS)
    authorized, _sub = fh._authorize_ws(_FakeWS(token=tok))
    assert authorized is True


def test_ws_rejected_without_token_when_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SYNAPSE_FIREHOSE_AUTH_REQUIRED", "true")
    app = FastAPI()
    app.include_router(fh.router, prefix="/ws")
    client = TestClient(app)
    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/firehose?topics=decision") as ws,
    ):
        ws.receive_text()


def test_ws_open_when_not_required(monkeypatch: pytest.MonkeyPatch) -> None:
    # Default Tier-D posture: no token needed; the demo keeps working.
    monkeypatch.delenv("SYNAPSE_FIREHOSE_AUTH_REQUIRED", raising=False)
    app = FastAPI()
    app.include_router(fh.router, prefix="/ws")
    client = TestClient(app)
    with client.websocket_connect("/ws/firehose?topics=decision") as ws:
        ws.send_text('{"type":"ping"}')
        assert ws.receive_text() == '{"type":"pong"}'
