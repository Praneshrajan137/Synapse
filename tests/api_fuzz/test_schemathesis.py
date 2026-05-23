"""Schemathesis API fuzz testing skeleton (ADR-015, Layer 2)."""
from __future__ import annotations

import schemathesis


def test_schemathesis_import() -> None:
    """Verify schemathesis exposes an OpenAPI loader.

    The loader entrypoint moved across the 3.x line (top-level ``from_url`` ->
    ``schemathesis.openapi.from_uri``); accept any known name so the smoke
    test is stable across the pinned ``>=3.30,<4.0`` range.
    """
    openapi = getattr(schemathesis, "openapi", None)
    candidates = [
        getattr(schemathesis, "from_url", None),
        getattr(schemathesis, "from_uri", None),
        getattr(openapi, "from_uri", None),
        getattr(openapi, "from_url", None),
    ]
    assert any(c is not None for c in candidates), (
        "schemathesis must expose an OpenAPI loader (from_uri/from_url)"
    )
