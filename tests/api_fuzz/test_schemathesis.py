"""Schemathesis API fuzz testing skeleton (ADR-015, Layer 2)."""
from __future__ import annotations

import schemathesis


def test_schemathesis_import() -> None:
    """Verify schemathesis is installed and importable."""
    assert hasattr(schemathesis, "from_url")
