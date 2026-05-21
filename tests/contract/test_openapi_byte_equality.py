"""OpenAPI byte-equality contract test (B5).

Plan §11/B5 + ADR-025. Asserts that the committed OpenAPI snapshot at
``packages/openapi/openapi.json`` is byte-identical (modulo sorted keys
and stable indentation) to the spec a freshly-booted gateway emits at
``GET /openapi.json``.

Why byte-equality, not "structurally equivalent"?
-------------------------------------------------
Orval generates TypeScript types and React-Query hooks from the
committed snapshot. If the live spec drifts by even an enum value or a
``required`` flag, the front-end's typed surface silently lies. A
byte-level diff in CI surfaces this as a code-review-visible red.

Update workflow
---------------
When a backend route legitimately changes:
  1. Add the route + tests as usual.
  2. Run ``python tests/contract/refresh_openapi_snapshot.py`` (lands
     alongside this test in the same PR).
  3. Commit the regenerated ``packages/openapi/openapi.json``.
  4. Reviewer reads the diff exactly the way they read schema migrations.

Determinism
-----------
FastAPI's OpenAPI generator is deterministic given a fixed app
definition. We canonicalise both sides through ``json.dumps(..., sort_keys=True,
indent=2)`` so trailing-newline / key-order drift won't fail the gate.
The intent is "same content," not "same byte stream produced by FastAPI."

Skipped if
----------
- ``packages/openapi/openapi.json`` is the v0 placeholder (info.version
  starts with ``0.0.0-placeholder``). This lets the test land in CI in
  S2 ahead of the first real refresh; the placeholder is treated as
  "no contract committed yet" and the test xfails. Once a real snapshot
  is committed, every drift becomes a hard failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "packages" / "openapi" / "openapi.json"


def _canonical(spec: dict) -> str:
    return json.dumps(spec, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def _is_placeholder(spec: dict) -> bool:
    return str(spec.get("info", {}).get("version", "")).startswith("0.0.0-placeholder")


def _live_spec() -> dict:
    """Return the gateway's live ``/openapi.json`` as a dict.

    Imports the FastAPI app in-process and calls ``app.openapi()`` directly,
    avoiding the cost (and flakiness) of booting a uvicorn server. Any
    side-effecty imports from the gateway must be tolerant of a test boot
    (no Postgres, no Redis, no Kafka). They are — every router defers
    those imports into the request-handler scope.
    """
    from api.main import app  # noqa: PLC0415

    spec = app.openapi()
    return dict(spec)


def test_snapshot_exists_and_is_valid_json() -> None:
    assert SNAPSHOT.exists(), f"missing OpenAPI snapshot: {SNAPSHOT}"
    text = SNAPSHOT.read_text(encoding="utf-8")
    json.loads(text)  # raises if not valid JSON


def test_openapi_byte_equality() -> None:
    """The committed snapshot equals the live spec, modulo sort + indent."""
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if _is_placeholder(committed):
        pytest.xfail(
            "OpenAPI snapshot is the v0 placeholder; first real refresh "
            "lands as a separate PR (plan §11/B5).",
        )

    live = _live_spec()

    expected = _canonical(committed)
    actual = _canonical(live)

    if expected != actual:
        # Produce a useful diff in CI logs — the canonical form is short
        # enough that a unified diff is the right tool.
        import difflib

        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                fromfile="committed (packages/openapi/openapi.json)",
                tofile="live (app.openapi())",
                lineterm="",
            ),
        )
        msg = (
            "OpenAPI snapshot drift detected. Run "
            "`python tests/contract/refresh_openapi_snapshot.py` and commit the "
            "regenerated packages/openapi/openapi.json.\n\n"
            f"{diff}"
        )
        pytest.fail(msg)
