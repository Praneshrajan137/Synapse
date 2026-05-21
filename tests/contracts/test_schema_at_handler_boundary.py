"""Schema-at-handler-boundary contract test (WS-2 §4, ADR-027).

Every ingress/handler module that builds an outbound payload must
reference ``validate_handler_input`` (or import from
``synapse_common.schemas``) so the boundary validation is mechanically
enforced rather than relying on reviewer discipline.

Scoped to:
  - ``api/routers/orders.py`` — orders ingress (ADR-029).

Future expansion (Sprint 8, ADR-027) extends this to all
``agents/*/a2a/handler.py`` once the agent handlers adopt the
``validate_handler_input`` call.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PATHS = [
    REPO_ROOT / "api" / "routers" / "orders.py",
]


@pytest.mark.contract
@pytest.mark.parametrize("path", REQUIRED_PATHS, ids=[p.name for p in REQUIRED_PATHS])
def test_handler_calls_validate(path: Path) -> None:
    content = path.read_text(encoding="utf-8")
    assert "validate_handler_input" in content, (
        f"{path.relative_to(REPO_ROOT)} must call "
        "synapse_common.schemas.validate_handler_input(...) at the handler "
        "boundary (WS-2 §4)."
    )
